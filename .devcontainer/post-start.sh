#!/usr/bin/env bash
set -euo pipefail

echo "╔═══════════════════════════════════════════════════╗"
echo "║   FlowForge — Starting Services                  ║"
echo "╚═══════════════════════════════════════════════════╝"

# Wait for dependent services
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h db -U flowforge -q 2>/dev/null; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

echo "⏳ Waiting for Redis..."
until redis-cli -h redis ping 2>/dev/null | grep -q PONG; do
  sleep 1
done
echo "✅ Redis is ready"

echo "⏳ Waiting for ClickHouse..."
until wget --spider -q http://clickhouse:8123/ping 2>/dev/null; do
  sleep 1
done
echo "✅ ClickHouse is ready"

echo "⏳ Waiting for Redpanda..."
until curl -sf http://redpanda:9644/v1/status/ready >/dev/null 2>&1; do
  sleep 1
done
echo "✅ Redpanda is ready"

echo "⏳ Waiting for Materialize..."
until pg_isready -h materialize -p 6875 -U materialize -q 2>/dev/null; do
  sleep 1
done
echo "✅ Materialize is ready"

echo ""
echo "🚀 All infrastructure services are up!"
echo ""
echo "  Quick commands:"
echo "    make dev        — Start frontend + backend"
echo "    make backend    — Start FastAPI only"
echo "    make frontend   — Start Vite only"
echo "    make test       — Run all tests"
echo "    make migrate    — Run database migrations"
echo "    make db-shell   — Open psql shell"
echo ""
