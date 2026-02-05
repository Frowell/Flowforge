#!/usr/bin/env bash
set -uo pipefail

echo "=== FlowForge Connectivity Check ==="
echo ""

check() {
  local name="$1"
  local cmd="$2"
  printf "%-20s" "$name:"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
  fi
}

check "PostgreSQL" "pg_isready -h postgres.flowforge.svc.cluster.local -p 5432 -U flowforge"
check "Redis" "redis-cli -h redis.flowforge.svc.cluster.local ping | grep -q PONG"
check "ClickHouse HTTP" "curl -sf http://clickhouse.flowforge.svc.cluster.local:8123/ping"
check "Materialize" "psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize -c 'SELECT 1'"
check "Redpanda Admin" "curl -sf http://redpanda.flowforge.svc.cluster.local:9644/v1/cluster/health_overview | grep -q is_healthy"

echo ""
echo "=== Redpanda Topics ==="
rpk topic list --brokers redpanda.flowforge.svc.cluster.local:29092 2>/dev/null || echo "rpk not available in this container"

echo ""
echo "=== ClickHouse Tables ==="
curl -sf "http://clickhouse.flowforge.svc.cluster.local:8123/?query=SHOW+TABLES+FROM+flowforge" 2>/dev/null || echo "No tables yet"

echo ""
echo "=== Materialize Views ==="
psql -h materialize.flowforge.svc.cluster.local -p 6875 -U materialize -c "SHOW MATERIALIZED VIEWS" 2>/dev/null || echo "No views yet"
