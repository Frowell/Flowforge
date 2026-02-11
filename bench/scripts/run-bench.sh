#!/usr/bin/env bash
set -euo pipefail

# ── FlowForge Benchmark Orchestrator ─────────────────────────────────
#
# Usage:
#   ./scripts/run-bench.sh [scenario]
#
# Scenarios:
#   event_rate    — Scenario 1: P95/P99 query latency at varying event rates
#   widgets       — Scenario 2: Dashboard load time vs widget count
#   ws            — Scenario 3: WebSocket delivery latency vs viewer count
#   chaos         — Scenario 4: Store failure via Toxiproxy
#   all           — Run all 4 scenarios sequentially (default)
#
# Prerequisites:
#   - bench infra running: make bench-up
#   - backend running: make backend

SCENARIO="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCUST_DIR="$BENCH_DIR/locustfiles"

API_BASE="${BENCH_API_BASE:-http://localhost:8000}"
RESULTS_DIR="$BENCH_DIR/results"
mkdir -p "$RESULTS_DIR"

CYAN='\033[36m'
GREEN='\033[32m'
RED='\033[31m'
RESET='\033[0m'

log() { echo -e "${CYAN}[bench]${RESET} $*"; }
ok()  { echo -e "${GREEN}[bench]${RESET} $*"; }
err() { echo -e "${RED}[bench]${RESET} $*" >&2; }

# ── Wait for backend readiness ────────────────────────────────────────
wait_ready() {
    log "Waiting for backend readiness..."
    for i in $(seq 1 30); do
        if curl -sf "$API_BASE/health/ready" > /dev/null 2>&1; then
            ok "Backend is ready."
            return 0
        fi
        sleep 2
    done
    err "Backend not ready after 60s."
    return 1
}

# ── Seed benchmark data ──────────────────────────────────────────────
seed_data() {
    log "Seeding benchmark data..."
    python3 "$SCRIPT_DIR/seed-bench-data.py" \
        --api-base "$API_BASE" \
        --output "$RESULTS_DIR/bench-env.sh"
    # shellcheck disable=SC1091
    source "$RESULTS_DIR/bench-env.sh"
    ok "Seed complete."
}

# ── Run a Locust scenario headless ───────────────────────────────────
run_scenario() {
    local name="$1"
    local locustfile="$2"
    local extra_args="${3:-}"

    log "Running scenario: $name"
    locust \
        --locustfile "$locustfile" \
        --host "$API_BASE" \
        --headless \
        --csv "$RESULTS_DIR/$name" \
        --html "$RESULTS_DIR/$name.html" \
        --run-time 5m \
        --stop-timeout 10 \
        $extra_args \
        2>&1 | tee "$RESULTS_DIR/$name.log"
    ok "Scenario $name complete."
}

# ── Scenario runners ─────────────────────────────────────────────────
run_event_rate() {
    run_scenario "event_rate" "$LOCUST_DIR/scenario_event_rate.py"
}

run_widgets() {
    run_scenario "widget_count" "$LOCUST_DIR/scenario_widget_count.py" "--users 10 --spawn-rate 5"
}

run_ws() {
    run_scenario "ws_viewers" "$LOCUST_DIR/scenario_ws_viewers.py"
}

run_chaos() {
    run_scenario "store_failure" "$LOCUST_DIR/scenario_store_failure.py" "--users 25 --spawn-rate 10 --run-time 3m"
}

# ── Main ─────────────────────────────────────────────────────────────
main() {
    wait_ready
    seed_data

    case "$SCENARIO" in
        event_rate)
            run_event_rate
            ;;
        widgets)
            run_widgets
            ;;
        ws)
            run_ws
            ;;
        chaos)
            run_chaos
            ;;
        all)
            run_event_rate
            run_widgets
            run_ws
            run_chaos
            ;;
        *)
            err "Unknown scenario: $SCENARIO"
            echo "Usage: $0 [event_rate|widgets|ws|chaos|all]"
            exit 1
            ;;
    esac

    log "All requested scenarios complete. Results in $RESULTS_DIR/"
}

main
