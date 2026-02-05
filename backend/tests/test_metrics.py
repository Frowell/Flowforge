"""Tests for Prometheus metrics.

Run with: pytest tests/test_metrics.py -v --noconftest
"""

from prometheus_client import REGISTRY, generate_latest

from app.core.metrics import (
    cache_operations_total,
    http_request_duration_seconds,
    http_requests_total,
    rate_limit_checks_total,
)


def test_registry_contains_expected_metrics():
    metric_names = {m.name for m in REGISTRY.collect()}
    expected = [
        "flowforge_http_requests",
        "flowforge_http_request_duration_seconds",
        "flowforge_query_compilation_duration_seconds",
        "flowforge_query_execution_duration_seconds",
        "flowforge_query_result_rows",
        "flowforge_websocket_connections_active",
        "flowforge_websocket_messages_sent",
        "flowforge_cache_operations",
        "flowforge_rate_limit_checks",
    ]
    for name in expected:
        # prometheus_client may strip _total suffix in the registry
        assert any(name in m for m in metric_names), (
            f"Metric {name} not found in registry. Available: {metric_names}"
        )


def test_counter_increment():
    before = http_requests_total.labels(
        method="GET", path="/test", status=200
    )._value.get()
    http_requests_total.labels(method="GET", path="/test", status=200).inc()
    after = http_requests_total.labels(
        method="GET", path="/test", status=200
    )._value.get()
    assert after == before + 1


def test_histogram_observe():
    http_request_duration_seconds.labels(method="GET", path="/test").observe(0.123)
    # No exception means success — histogram observe is fire-and-forget


def test_generate_latest_produces_valid_output():
    output = generate_latest()
    assert isinstance(output, bytes)
    text = output.decode("utf-8")
    assert "flowforge_http_requests_total" in text
    assert "flowforge_http_request_duration_seconds" in text


def test_cache_counter_labels():
    cache_operations_total.labels(
        cache_type="preview", operation="get", status="hit"
    ).inc()
    cache_operations_total.labels(
        cache_type="widget", operation="set", status="miss"
    ).inc()
    output = generate_latest().decode("utf-8")
    assert 'cache_type="preview"' in output
    assert 'cache_type="widget"' in output


def test_rate_limit_counter():
    rate_limit_checks_total.labels(status="allowed").inc()
    output = generate_latest().decode("utf-8")
    assert "flowforge_rate_limit_checks_total" in output
