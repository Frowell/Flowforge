"""Workflow compiler tests — verify query merging and SQL generation."""

from app.services.schema_engine import SchemaEngine
from app.services.workflow_compiler import WorkflowCompiler


def get_compiler() -> WorkflowCompiler:
    return WorkflowCompiler(schema_engine=SchemaEngine())


class TestTopologicalSort:
    def test_linear_chain_sorted_correctly(self):
        compiler = get_compiler()
        nodes = [
            {"id": "a", "type": "data_source", "data": {"config": {"table": "trades", "columns": []}}},
            {"id": "b", "type": "filter", "data": {"config": {}}},
            {"id": "c", "type": "table_output", "data": {"config": {}}},
        ]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
        result = compiler._topological_sort(nodes, edges)
        assert result.index("a") < result.index("b") < result.index("c")


class TestSubgraphExtraction:
    def test_find_ancestors_returns_all_upstream_nodes(self):
        compiler = get_compiler()
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
            {"source": "d", "target": "c"},
        ]
        ancestors = compiler._find_ancestors("c", edges)
        assert ancestors == {"a", "b", "d"}


# TODO: Add query merging tests once merge logic is implemented
# Key scenarios to test:
# - Filter -> Select -> Sort on same source = 1 query
# - Join creates a new segment combining two upstream segments
# - Group By following linear chain extends the same query
