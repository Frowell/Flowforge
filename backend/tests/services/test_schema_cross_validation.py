"""Cross-validation tests: verify Python schema engine matches fixture expectations.

Loads JSON fixtures from tests/fixtures/schema/ and asserts that
SchemaEngine.validate_dag() produces identical output schemas.
The TypeScript engine runs the same fixtures in a parallel test.
"""

import json
from pathlib import Path

import pytest

from app.services.schema_engine import SchemaEngine

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "tests"
    / "fixtures"
    / "schema"
)

engine = SchemaEngine()


def _load_fixtures() -> list[tuple[str, dict]]:
    """Load all JSON fixture files from the fixtures directory."""
    fixtures = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        with open(path) as f:
            data = json.load(f)
        fixtures.append((path.stem, data))
    return fixtures


def _schema_to_comparable(schema_list: list) -> list[dict]:
    """Normalize schema output for comparison.

    Converts Pydantic models to dicts and standardizes keys.
    """
    result = []
    for item in schema_list:
        if hasattr(item, "model_dump"):
            d = item.model_dump()
        elif isinstance(item, dict):
            d = item
        else:
            d = {"name": str(item)}
        # Only compare name, dtype, nullable
        result.append(
            {
                "name": d["name"],
                "dtype": d["dtype"],
                "nullable": d["nullable"],
            }
        )
    return result


@pytest.fixture(params=_load_fixtures(), ids=lambda x: x[0])
def fixture_data(request):
    return request.param


def test_schema_engine_matches_fixture(fixture_data):
    """SchemaEngine.validate_dag() output matches expected schemas in fixture."""
    name, data = fixture_data
    nodes = data["nodes"]
    edges = data["edges"]
    expected = data["expected"]

    actual = engine.validate_dag(nodes, edges)

    for node_id, expected_schema in expected.items():
        actual_schema = actual.get(node_id, [])
        actual_normalized = _schema_to_comparable(actual_schema)
        expected_normalized = [
            {"name": e["name"], "dtype": e["dtype"], "nullable": e["nullable"]}
            for e in expected_schema
        ]
        assert actual_normalized == expected_normalized, (
            f"Fixture '{name}', node '{node_id}': "
            f"expected {expected_normalized}, got {actual_normalized}"
        )
