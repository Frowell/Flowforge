"""Schema Engine — server-side DAG schema validation.

Every node type registers a transform function:
    (node_config, input_schemas) -> output_schema

This engine MUST produce identical results to the TypeScript engine
in frontend/src/shared/schema/propagation.ts.
"""

import logging
from collections.abc import Callable

from app.schemas.schema import ColumnSchema

logger = logging.getLogger(__name__)

# Type alias for schema transform functions
# Input: (node_config dict, list of input schemas) -> output schema
SchemaTransformFn = Callable[[dict, list[list[ColumnSchema]]], list[ColumnSchema]]

# Registry of transform functions keyed by node type
_transforms: dict[str, SchemaTransformFn] = {}


def register_transform(node_type: str) -> Callable:
    """Decorator to register a schema transform for a node type."""

    def decorator(fn: SchemaTransformFn) -> SchemaTransformFn:
        _transforms[node_type] = fn
        return fn

    return decorator


# ── Node Type Transforms ─────────────────────────────────────────────────


@register_transform("data_source")
def data_source_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Output schema comes from the schema catalog, not from inputs."""
    columns = config.get("columns", [])
    return [ColumnSchema(**col) if isinstance(col, dict) else col for col in columns]


@register_transform("filter")
def filter_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Passthrough — same columns, fewer rows."""
    if not inputs:
        return []
    return list(inputs[0])


@register_transform("select")
def select_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Subset of input columns in the specified order."""
    if not inputs:
        return []
    selected_names = config.get("columns", [])
    input_by_name = {col.name: col for col in inputs[0]}
    return [input_by_name[name] for name in selected_names if name in input_by_name]


@register_transform("rename")
def rename_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Input columns with name substitutions."""
    if not inputs:
        return []
    rename_map: dict[str, str] = config.get("rename_map", {})
    return [
        ColumnSchema(
            name=rename_map.get(col.name, col.name),
            dtype=col.dtype,
            nullable=col.nullable,
        )
        for col in inputs[0]
    ]


@register_transform("sort")
def sort_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Passthrough — same columns, reordered rows."""
    if not inputs:
        return []
    return list(inputs[0])


@register_transform("join")
def join_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Merged schemas from both inputs."""
    if len(inputs) < 2:
        return inputs[0] if inputs else []
    left = inputs[0]
    right = inputs[1]
    left_names = {col.name for col in left}
    merged = list(left)
    for col in right:
        if col.name not in left_names:
            merged.append(col)
    return merged


@register_transform("group_by")
def group_by_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Group keys + aggregate output columns."""
    if not inputs:
        return []
    group_columns: list[str] = config.get("group_columns", [])
    aggregations: list[dict] = config.get("aggregations", [])

    input_by_name = {col.name: col for col in inputs[0]}
    output: list[ColumnSchema] = []

    for name in group_columns:
        if name in input_by_name:
            output.append(input_by_name[name])

    for agg in aggregations:
        output.append(
            ColumnSchema(
                name=agg.get("alias", f"{agg.get('function', 'agg')}_{agg.get('column', '')}"),
                dtype=agg.get("output_dtype", "float64"),
                nullable=True,
            )
        )

    return output


@register_transform("pivot")
def pivot_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Row dimension columns + pivoted value column."""
    if not inputs:
        return []
    row_columns: list[str] = config.get("row_columns", [])
    value_column: str = config.get("value_column", "")
    aggregation: str = config.get("aggregation", "SUM")

    input_by_name = {col.name: col for col in inputs[0]}
    output: list[ColumnSchema] = []

    for name in row_columns:
        if name in input_by_name:
            output.append(input_by_name[name])

    # Pivoted value column — actual column explosion happens at query time
    if value_column:
        output.append(
            ColumnSchema(
                name=f"{value_column}_{aggregation.lower()}",
                dtype="float64",
                nullable=True,
            )
        )

    return output


@register_transform("formula")
def formula_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Input columns + new calculated column."""
    if not inputs:
        return []
    output = list(inputs[0])
    new_col_name = config.get("output_column", "calculated")
    new_col_type = config.get("output_dtype", "float64")
    output.append(ColumnSchema(name=new_col_name, dtype=new_col_type, nullable=True))
    return output


@register_transform("unique")
def unique_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Passthrough — deduplicated rows."""
    if not inputs:
        return []
    return list(inputs[0])


@register_transform("sample")
def sample_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Passthrough — fewer rows."""
    if not inputs:
        return []
    return list(inputs[0])


@register_transform("limit")
def limit_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Passthrough — limited rows."""
    if not inputs:
        return []
    return list(inputs[0])


@register_transform("window")
def window_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Input columns + new window function column."""
    if not inputs:
        return []
    output = list(inputs[0])
    output_column = config.get("output_column", "window_result")
    func = config.get("function", "ROW_NUMBER")

    # Determine output dtype based on function
    if func in ("SUM", "AVG", "MIN", "MAX"):
        dtype = "float64"
    elif func in ("FIRST_VALUE", "LAST_VALUE", "LAG", "LEAD"):
        # Match source column dtype
        source_col = config.get("source_column", "")
        input_by_name = {col.name: col for col in inputs[0]}
        src_schema = input_by_name.get(source_col)
        dtype = src_schema.dtype if src_schema else "float64"
    else:
        dtype = "int64"

    output.append(ColumnSchema(name=output_column, dtype=dtype, nullable=True))
    return output


@register_transform("union")
def union_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Columns from first input (both inputs must have compatible schemas)."""
    if not inputs:
        return []
    return list(inputs[0])


@register_transform("chart_output")
def chart_output_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Terminal — no output schema."""
    return []


@register_transform("table_output")
def table_output_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Terminal — no output schema."""
    return []


@register_transform("kpi_output")
def kpi_output_transform(config: dict, inputs: list[list[ColumnSchema]]) -> list[ColumnSchema]:
    """Terminal — no output schema."""
    return []


# ── Engine ────────────────────────────────────────────────────────────────


class SchemaEngine:
    """Validates and propagates schemas through a workflow DAG."""

    def validate_dag(
        self,
        nodes: list[dict],
        edges: list[dict],
    ) -> dict[str, list[ColumnSchema]]:
        """Walk the DAG in topological order, computing output schemas.

        Returns a mapping of node_id -> output_schema.
        Raises ValueError on validation failures.
        """
        # Build adjacency: target_node_id -> list of source_node_ids
        inbound: dict[str, list[str]] = {}
        for edge in edges:
            target = edge["target"]
            source = edge["source"]
            inbound.setdefault(target, []).append(source)

        node_map = {n["id"]: n for n in nodes}
        output_schemas: dict[str, list[ColumnSchema]] = {}

        # Topological sort (Kahn's algorithm)
        in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
        for edge in edges:
            in_degree[edge["target"]] += 1

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        visited = 0

        while queue:
            node_id = queue.pop(0)
            visited += 1
            node = node_map[node_id]
            node_type = node.get("type", "")
            node_config = node.get("data", {}).get("config", {})

            # Gather input schemas from upstream nodes
            input_schemas = [
                output_schemas.get(src_id, [])
                for src_id in inbound.get(node_id, [])
            ]

            transform = _transforms.get(node_type)
            if transform is None:
                raise ValueError(f"Unknown node type: {node_type}")

            output_schemas[node_id] = transform(node_config, input_schemas)

            for edge in edges:
                if edge["source"] == node_id:
                    in_degree[edge["target"]] -= 1
                    if in_degree[edge["target"]] == 0:
                        queue.append(edge["target"])

        if visited != len(nodes):
            raise ValueError("Workflow contains a cycle")

        return output_schemas
