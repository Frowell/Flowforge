#!/usr/bin/env bash
set -euo pipefail

echo "╔═══════════════════════════════════════════════════╗"
echo "║   FlowForge — Post-Create Setup                  ║"
echo "╚═══════════════════════════════════════════════════╝"

# ── Frontend: Install dependencies ────────────────────────────────────
if [ -f /workspace/frontend/package.json ]; then
  echo "📦 Installing frontend dependencies..."
  cd /workspace/frontend
  npm install
else
  echo "⏭️  No frontend/package.json found — skipping npm install"
  echo "   Run 'make scaffold' to generate the project structure"
fi

# ── Backend: Install in editable mode ─────────────────────────────────
if [ -f /workspace/backend/pyproject.toml ]; then
  echo "🐍 Installing backend in editable mode..."
  cd /workspace/backend
  pip install -e ".[dev]" --quiet
else
  echo "⏭️  No backend/pyproject.toml found — skipping pip install"
  echo "   Run 'make scaffold' to generate the project structure"
fi

# ── Database: Run migrations ──────────────────────────────────────────
if [ -f /workspace/backend/alembic.ini ]; then
  echo "🗄️  Running database migrations..."
  cd /workspace/backend
  alembic upgrade head
else
  echo "⏭️  No alembic.ini found — skipping migrations"
fi

# ── Git: Setup pre-commit hooks ───────────────────────────────────────
if [ -f /workspace/.pre-commit-config.yaml ]; then
  echo "🔗 Installing pre-commit hooks..."
  cd /workspace
  pre-commit install
fi

echo ""
echo "✅ Post-create setup complete!"
echo "   Run 'make dev' to start all services"
echo ""
