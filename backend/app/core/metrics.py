"""Central Prometheus metrics registry.

All application metrics are defined here to avoid scattered metric definitions
and ensure consistent naming/labeling.
"""

from prometheus_client import Counter, Gauge, Histogram, Info

# Application info
app_info = Info("flowforge_app", "FlowForge application info")

# --- HTTP ---
http_requests_total = Counter(
    "flowforge_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "flowforge_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

# --- Query execution ---
query_compilation_duration_seconds = Histogram(
    "flowforge_query_compilation_duration_seconds",
    "Query compilation duration in seconds",
)
query_execution_duration_seconds = Histogram(
    "flowforge_query_execution_duration_seconds",
    "Query execution duration in seconds",
    ["target"],
)
query_result_rows = Histogram(
    "flowforge_query_result_rows",
    "Number of rows returned by a query",
    ["target"],
    buckets=[0, 1, 10, 100, 1000, 5000, 10000, 50000, 100000],
)

# --- WebSocket ---
websocket_connections_active = Gauge(
    "flowforge_websocket_connections_active",
    "Number of active WebSocket connections",
)
websocket_messages_sent_total = Counter(
    "flowforge_websocket_messages_sent_total",
    "Total WebSocket messages sent",
    ["message_type"],
)

# --- Cache ---
cache_operations_total = Counter(
    "flowforge_cache_operations_total",
    "Total cache operations",
    ["cache_type", "operation", "status"],
)

# --- Rate limiting ---
rate_limit_checks_total = Counter(
    "flowforge_rate_limit_checks_total",
    "Total rate limit checks",
    ["status"],
)
