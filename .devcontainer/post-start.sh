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
