#!/usr/bin/env bash
# validate-schema-parity.sh — Run cross-validation fixtures against both
# Python and TypeScript schema engines, ensuring parity.
#
# Usage: bash scripts/validate-schema-parity.sh
#
# Exit code 0 = both engines agree on all fixtures.
# Non-zero = discrepancy detected.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== FlowForge Schema Parity Validation ==="
echo ""

FAILED=0

# --- Python ---
echo "▸ Running Python schema engine tests..."
cd "$ROOT_DIR/backend"
if python -m pytest tests/services/test_schema_cross_validation.py -v --tb=short 2>&1; then
    echo "  ✓ Python tests passed"
else
    echo "  ✗ Python tests FAILED"
    FAILED=1
fi
echo ""

# --- TypeScript ---
echo "▸ Running TypeScript schema engine tests..."
cd "$ROOT_DIR/frontend"
if npx vitest run src/shared/schema/__tests__/cross-validation.test.ts --reporter=verbose 2>&1; then
    echo "  ✓ TypeScript tests passed"
else
    echo "  ✗ TypeScript tests FAILED"
    FAILED=1
fi
echo ""

# --- Summary ---
if [ "$FAILED" -eq 0 ]; then
    echo "=== All schema parity checks PASSED ==="
    exit 0
else
    echo "=== Schema parity checks FAILED ==="
    exit 1
fi
