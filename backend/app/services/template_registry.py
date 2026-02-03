"""Hardcoded template registry.

Templates are code-defined, not stored in the database.
Each template provides a pre-configured React Flow graph_json with nodes and edges.
"""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TemplateDefinition:
    id: str
    name: str
    description: str
    category: str
    tags: list[str]
    graph_json: dict
    thumbnail: str | None = None


def _make_node(
    node_id: str,
    node_type: str,
    label: str,
    x: float,
    y: float,
    config: dict | None = None,
) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": x, "y": y},
        "data": {
            "label": label,
            "nodeType": node_type,
            "config": config or {},
        },
    }


def _make_edge(source: str, target: str) -> dict:
    return {
        "id": f"e-{source}-{target}",
        "source": source,
        "target": target,
    }


TEMPLATES: dict[str, TemplateDefinition] = {
    "realtime-position-monitor": TemplateDefinition(
        id="realtime-position-monitor",
        name="Real-Time Position Monitor",
        description="Monitor positions grouped by symbol with aggregated quantities. Includes a bar chart and KPI card output.",
        category="Trading",
        tags=["positions", "real-time", "bar-chart", "kpi"],
        graph_json={
            "nodes": [
                _make_node("ds1", "data_source", "Positions", 0, 0, {"table": "positions", "freshness": "realtime"}),
                _make_node("gb1", "group_by", "Group by Symbol", 300, 0, {"group_columns": ["symbol"], "aggregations": [{"column": "quantity", "function": "SUM", "alias": "total_qty"}]}),
                _make_node("bar1", "chart_output", "Bar Chart", 600, -50, {"chart_type": "bar", "x_column": "symbol", "y_column": "total_qty"}),
                _make_node("kpi1", "chart_output", "KPI Card", 600, 100, {"chart_type": "kpi", "value_column": "total_qty", "label": "Total Positions"}),
            ],
            "edges": [
                _make_edge("ds1", "gb1"),
                _make_edge("gb1", "bar1"),
                _make_edge("gb1", "kpi1"),
            ],
        },
    ),
    "vwap-analysis": TemplateDefinition(
        id="vwap-analysis",
        name="VWAP Analysis",
        description="Calculate volume-weighted average price from trade data with time-windowed grouping and candlestick visualization.",
        category="Analytics",
        tags=["vwap", "trades", "candlestick", "formula"],
        graph_json={
            "nodes": [
                _make_node("ds1", "data_source", "Trades", 0, 0, {"table": "trades", "freshness": "analytical"}),
                _make_node("fm1", "formula", "Price x Quantity", 300, 0, {"expression": "[price] * [quantity]", "output_column": "trade_value"}),
                _make_node("gb1", "group_by", "Group by Time Window", 600, 0, {"group_columns": ["time_window"], "aggregations": [{"column": "trade_value", "function": "SUM", "alias": "total_value"}, {"column": "quantity", "function": "SUM", "alias": "total_volume"}]}),
                _make_node("chart1", "chart_output", "Candlestick Chart", 900, 0, {"chart_type": "candlestick", "time_column": "time_window", "value_column": "total_value"}),
            ],
            "edges": [
                _make_edge("ds1", "fm1"),
                _make_edge("fm1", "gb1"),
                _make_edge("gb1", "chart1"),
            ],
        },
    ),
    "sector-exposure": TemplateDefinition(
        id="sector-exposure",
        name="Sector Exposure",
        description="Join positions with instrument metadata and visualize exposure by sector as a bar chart.",
        category="Risk",
        tags=["positions", "instruments", "join", "sector", "bar-chart"],
        graph_json={
            "nodes": [
                _make_node("ds1", "data_source", "Positions", 0, 0, {"table": "positions", "freshness": "realtime"}),
                _make_node("ds2", "data_source", "Instruments", 0, 200, {"table": "instruments", "freshness": "analytical"}),
                _make_node("jn1", "join", "Join on Symbol", 300, 100, {"join_type": "inner", "left_column": "symbol", "right_column": "symbol"}),
                _make_node("gb1", "group_by", "Group by Sector", 600, 100, {"group_columns": ["sector"], "aggregations": [{"column": "quantity", "function": "SUM", "alias": "total_exposure"}]}),
                _make_node("bar1", "chart_output", "Sector Bar Chart", 900, 100, {"chart_type": "bar", "x_column": "sector", "y_column": "total_exposure"}),
            ],
            "edges": [
                _make_edge("ds1", "jn1"),
                _make_edge("ds2", "jn1"),
                _make_edge("jn1", "gb1"),
                _make_edge("gb1", "bar1"),
            ],
        },
    ),
    "trade-blotter": TemplateDefinition(
        id="trade-blotter",
        name="Trade Blotter",
        description="Live trade blotter with date filtering, sorted by most recent trades. Outputs to a table view.",
        category="Trading",
        tags=["trades", "blotter", "filter", "sort", "table"],
        graph_json={
            "nodes": [
                _make_node("ds1", "data_source", "Trades", 0, 0, {"table": "trades", "freshness": "realtime"}),
                _make_node("ft1", "filter", "Date Filter", 300, 0, {"conditions": [{"column": "trade_date", "operator": ">=", "value": "today-7d"}]}),
                _make_node("st1", "sort", "Sort by Time", 600, 0, {"sort_columns": [{"column": "trade_time", "direction": "desc"}]}),
                _make_node("tbl1", "table_output", "Trade Table", 900, 0, {"page_size": 50}),
            ],
            "edges": [
                _make_edge("ds1", "ft1"),
                _make_edge("ft1", "st1"),
                _make_edge("st1", "tbl1"),
            ],
        },
    ),
    "pnl-dashboard": TemplateDefinition(
        id="pnl-dashboard",
        name="P&L Dashboard",
        description="Calculate unrealized P&L from positions and display via KPI card and line chart over time.",
        category="Analytics",
        tags=["pnl", "positions", "formula", "kpi", "line-chart"],
        graph_json={
            "nodes": [
                _make_node("ds1", "data_source", "Positions", 0, 0, {"table": "positions", "freshness": "realtime"}),
                _make_node("fm1", "formula", "Unrealized P&L", 300, 0, {"expression": "([current_price] - [avg_cost]) * [quantity]", "output_column": "unrealized_pnl"}),
                _make_node("kpi1", "chart_output", "P&L KPI", 600, -100, {"chart_type": "kpi", "value_column": "unrealized_pnl", "label": "Total Unrealized P&L"}),
                _make_node("line1", "chart_output", "P&L Line Chart", 600, 100, {"chart_type": "line", "x_column": "symbol", "y_column": "unrealized_pnl"}),
            ],
            "edges": [
                _make_edge("ds1", "fm1"),
                _make_edge("fm1", "kpi1"),
                _make_edge("fm1", "line1"),
            ],
        },
    ),
}


def get_all_templates() -> list[TemplateDefinition]:
    return list(TEMPLATES.values())


def get_template(template_id: str) -> TemplateDefinition | None:
    return TEMPLATES.get(template_id)


def instantiate_template(
    template_id: str, name_override: str | None = None
) -> dict | None:
    """Create a fresh copy of a template's graph_json with new UUIDs for all node and edge IDs."""
    template = TEMPLATES.get(template_id)
    if not template:
        return None

    graph = template.graph_json
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Map old IDs to new UUIDs
    id_map: dict[str, str] = {}
    for node in nodes:
        old_id = node["id"]
        new_id = f"{node['data']['nodeType']}_{uuid4().hex[:8]}"
        id_map[old_id] = new_id

    # Create new nodes with fresh IDs
    new_nodes = []
    for node in nodes:
        new_node = {
            **node,
            "id": id_map[node["id"]],
        }
        new_nodes.append(new_node)

    # Create new edges with fresh IDs and remapped source/target
    new_edges = []
    for edge in edges:
        new_source = id_map.get(edge["source"], edge["source"])
        new_target = id_map.get(edge["target"], edge["target"])
        new_edges.append({
            "id": f"e-{new_source}-{new_target}",
            "source": new_source,
            "target": new_target,
        })

    return {
        "nodes": new_nodes,
        "edges": new_edges,
    }
