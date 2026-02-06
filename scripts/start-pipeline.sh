#!/usr/bin/env bash
# start-pipeline.sh — Orchestrates the full FlowForge development pipeline
#
# Usage:
#   ./scripts/start-pipeline.sh          # Start all components
#   ./scripts/start-pipeline.sh --seed   # Start with historical data seeding
#   ./scripts/start-pipeline.sh --stop   # Stop all components
#
# Components started:
#   1. Data generator (trades + quotes → Redpanda)
#   2. Bytewax VWAP flow (Redpanda → ClickHouse + Redis)
#   3. Bytewax Volatility flow (Redpanda → ClickHouse + Redis)
#   4. Backend (FastAPI)
#   5. Frontend (Vite dev server)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
PID_DIR="$WORKSPACE_DIR/.pipeline-pids"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

mkdir -p "$PID_DIR"

stop_all() {
    log_info "Stopping all pipeline components..."

    for pidfile in "$PID_DIR"/*.pid; do
        if [[ -f "$pidfile" ]]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                log_success "Stopped $name (PID $pid)"
            fi
            rm -f "$pidfile"
        fi
    done

    # Also kill any orphaned processes
    pkill -f "generator.py" 2>/dev/null || true
    pkill -f "bytewax.run" 2>/dev/null || true

    log_success "All components stopped."
}

check_services() {
    log_info "Checking required services..."

    # Check ClickHouse
    if ! curl -sf http://localhost:8123/ping >/dev/null 2>&1; then
        log_error "ClickHouse not available at localhost:8123"
        log_info "Make sure the devcontainer is running: docker compose up -d"
        exit 1
    fi
    log_success "ClickHouse is ready"

    # Check Redis
    if ! redis-cli -h localhost ping >/dev/null 2>&1; then
        log_error "Redis not available at localhost:6379"
        exit 1
    fi
    log_success "Redis is ready"

    # Check Redpanda
    if ! curl -sf http://localhost:9644/v1/status/ready >/dev/null 2>&1; then
        log_error "Redpanda not available at localhost:9644"
        exit 1
    fi
    log_success "Redpanda is ready"

    # Check PostgreSQL
    if ! pg_isready -h localhost -p 5432 -U flowforge >/dev/null 2>&1; then
        log_error "PostgreSQL not available at localhost:5432"
        exit 1
    fi
    log_success "PostgreSQL is ready"
}

seed_data() {
    log_info "Seeding historical data into ClickHouse..."
    cd "$WORKSPACE_DIR/scripts"

    # Update host for local development
    CLICKHOUSE_HOST=localhost python3 -c "
import os
os.environ['CLICKHOUSE_HOST'] = 'localhost'
exec(open('seed_historical.py').read().replace(
    'clickhouse.flowforge.svc.cluster.local',
    'localhost'
))
" 2>&1 | while read line; do echo "  $line"; done

    log_success "Historical data seeded"
}

start_generator() {
    log_info "Starting data generator..."
    cd "$WORKSPACE_DIR/pipeline/generator"

    # Install deps if needed
    if ! python3 -c "import confluent_kafka" 2>/dev/null; then
        pip install -q confluent-kafka orjson
    fi

    REDPANDA_BROKERS=localhost:9092 \
    python3 generator.py > "$PID_DIR/generator.log" 2>&1 &
    echo $! > "$PID_DIR/generator.pid"

    log_success "Generator started (PID $(cat $PID_DIR/generator.pid))"
}

start_bytewax_vwap() {
    log_info "Starting Bytewax VWAP flow..."
    cd "$WORKSPACE_DIR/pipeline/bytewax"

    # Install deps if needed
    if ! python3 -c "import bytewax" 2>/dev/null; then
        pip install -q bytewax clickhouse-connect redis
    fi

    REDPANDA_BROKERS=localhost:9092 \
    CLICKHOUSE_HOST=localhost \
    REDIS_HOST=localhost \
    python3 -m bytewax.run flows.vwap > "$PID_DIR/bytewax-vwap.log" 2>&1 &
    echo $! > "$PID_DIR/bytewax-vwap.pid"

    log_success "Bytewax VWAP started (PID $(cat $PID_DIR/bytewax-vwap.pid))"
}

start_bytewax_volatility() {
    log_info "Starting Bytewax Volatility flow..."
    cd "$WORKSPACE_DIR/pipeline/bytewax"

    REDPANDA_BROKERS=localhost:9092 \
    CLICKHOUSE_HOST=localhost \
    REDIS_HOST=localhost \
    python3 -m bytewax.run flows.volatility > "$PID_DIR/bytewax-volatility.log" 2>&1 &
    echo $! > "$PID_DIR/bytewax-volatility.pid"

    log_success "Bytewax Volatility started (PID $(cat $PID_DIR/bytewax-volatility.pid))"
}

start_backend() {
    log_info "Starting FastAPI backend..."
    cd "$WORKSPACE_DIR/backend"

    # Run migrations first
    if command -v alembic >/dev/null 2>&1; then
        log_info "Running Alembic migrations..."
        alembic upgrade head 2>&1 | while read line; do echo "  $line"; done
    fi

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > "$PID_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"

    log_success "Backend started at http://localhost:8000 (PID $(cat $PID_DIR/backend.pid))"
}

start_frontend() {
    log_info "Starting Vite frontend..."
    cd "$WORKSPACE_DIR/frontend"

    # Install deps if needed
    if [[ ! -d node_modules ]]; then
        log_info "Installing frontend dependencies..."
        npm install
    fi

    npm run dev > "$PID_DIR/frontend.log" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"

    log_success "Frontend started at http://localhost:5173 (PID $(cat $PID_DIR/frontend.pid))"
}

show_status() {
    echo ""
    echo "=========================================="
    echo "  FlowForge Pipeline Status"
    echo "=========================================="
    echo ""

    for pidfile in "$PID_DIR"/*.pid; do
        if [[ -f "$pidfile" ]]; then
            pid=$(cat "$pidfile")
            name=$(basename "$pidfile" .pid)
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "  ${GREEN}●${NC} $name (PID $pid)"
            else
                echo -e "  ${RED}●${NC} $name (dead)"
            fi
        fi
    done

    echo ""
    echo "URLs:"
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://localhost:8000"
    echo "  API Docs:  http://localhost:8000/docs"
    echo "  ClickHouse: http://localhost:8123"
    echo ""
    echo "Logs: $PID_DIR/*.log"
    echo "Stop: $0 --stop"
    echo ""
}

main() {
    case "${1:-}" in
        --stop)
            stop_all
            exit 0
            ;;
        --status)
            show_status
            exit 0
            ;;
        --seed)
            SEED_DATA=true
            ;;
    esac

    echo ""
    echo "=========================================="
    echo "  Starting FlowForge Pipeline"
    echo "=========================================="
    echo ""

    # Stop any existing processes first
    stop_all 2>/dev/null || true

    # Check services are available
    check_services

    # Optionally seed historical data
    if [[ "${SEED_DATA:-}" == "true" ]]; then
        seed_data
    fi

    # Start all components
    start_generator
    sleep 2  # Let generator create topics

    start_bytewax_vwap
    start_bytewax_volatility

    start_backend
    start_frontend

    # Wait a bit for everything to start
    sleep 3

    show_status

    log_info "Pipeline is running. Press Ctrl+C to stop, or run: $0 --stop"

    # Wait for interrupt
    trap stop_all EXIT
    wait
}

main "$@"
