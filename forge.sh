#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# FORGE — Development Server Manager
# Usage: ./forge.sh {start|stop|restart|status|logs|test|deploy|health}
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
WORKERS_DIR="$ROOT_DIR/workers/preview-proxy"

CONDA_ENV="forge_v2"
PYTHON="/home/joe/miniconda3/envs/$CONDA_ENV/bin/python"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

mkdir -p "$PID_DIR" "$LOG_DIR"

# ── Helpers ──────────────────────────────────────────────────────

log() { echo -e "${CYAN}[forge]${NC} $1"; }
ok()  { echo -e "${GREEN}  ✓${NC} $1"; }
err() { echo -e "${RED}  ✗${NC} $1"; }
warn(){ echo -e "${YELLOW}  !${NC} $1"; }

is_running() {
    local pidfile="$PID_DIR/$1.pid"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pidfile"
    fi
    return 1
}

get_pid() {
    cat "$PID_DIR/$1.pid" 2>/dev/null || echo ""
}

# Kill a process and all its children (entire process tree)
kill_tree() {
    local pid=$1 sig=${2:-TERM}
    # Kill the entire process group if the pid is a group leader
    kill -"$sig" -- -"$pid" 2>/dev/null || true
    # Also kill direct children in case pgid differs
    local children
    children=$(pgrep -P "$pid" 2>/dev/null || true)
    for child in $children; do
        kill -"$sig" "$child" 2>/dev/null || true
    done
    # Kill the process itself
    kill -"$sig" "$pid" 2>/dev/null || true
}

# Wait for a process to exit, escalate to SIGKILL after timeout
wait_for_death() {
    local pid=$1 name=$2 timeout=${3:-10}
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 0.5
        elapsed=$((elapsed + 1))
        if (( elapsed >= timeout * 2 )); then
            warn "$name (pid $pid) did not exit after ${timeout}s — sending SIGKILL"
            kill_tree "$pid" KILL
            sleep 0.5
            if kill -0 "$pid" 2>/dev/null; then
                err "$name (pid $pid) could not be killed"
                return 1
            fi
            break
        fi
    done
    return 0
}

wait_for_port() {
    local port=$1 name=$2 timeout=${3:-15}
    local elapsed=0
    while ! nc -z localhost "$port" 2>/dev/null; do
        sleep 0.5
        elapsed=$((elapsed + 1))
        if (( elapsed >= timeout * 2 )); then
            err "$name failed to start on port $port within ${timeout}s"
            return 1
        fi
    done
    return 0
}

# ── Individual service start/stop ────────────────────────────────

start_redis() {
    if is_running redis; then
        warn "Redis already running (pid $(get_pid redis))"
        return 0
    fi
    log "Starting Redis (local)..."
    if command -v redis-server &>/dev/null; then
        redis-server --daemonize yes --logfile "$LOG_DIR/redis.log" --pidfile "$PID_DIR/redis.pid" --port 6379
        ok "Redis started on :6379"
    else
        warn "redis-server not found — using Upstash (REDIS_URL from .env.local)"
    fi
}

stop_redis() {
    if is_running redis; then
        local pid
        pid=$(get_pid redis)
        log "Stopping Redis (pid $pid)..."
        kill_tree "$pid"
        wait_for_death "$pid" "Redis" 5
        rm -f "$PID_DIR/redis.pid"
        ok "Redis stopped"
    fi
}

start_backend() {
    if is_running backend; then
        warn "Backend already running (pid $(get_pid backend))"
        return 0
    fi
    log "Starting Backend (FastAPI :8000)..."
    cd "$BACKEND_DIR"
    $PYTHON -m uvicorn app.main:app \
        --host 0.0.0.0 --port 8000 --reload \
        --log-level info \
        > "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
    if wait_for_port 8000 "Backend"; then
        ok "Backend started on :8000 (pid $(get_pid backend))"
    fi
    cd "$ROOT_DIR"
}

stop_backend() {
    if is_running backend; then
        local pid
        pid=$(get_pid backend)
        log "Stopping Backend (pid $pid)..."
        kill_tree "$pid"
        wait_for_death "$pid" "Backend" 10
        rm -f "$PID_DIR/backend.pid"
        ok "Backend stopped"
    fi
}

start_frontend() {
    if is_running frontend; then
        warn "Frontend already running (pid $(get_pid frontend))"
        return 0
    fi
    log "Starting Frontend (Vite :5173)..."
    cd "$FRONTEND_DIR"
    npx vite --host 0.0.0.0 --port 5173 \
        > "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"
    if wait_for_port 5173 "Frontend"; then
        ok "Frontend started on :5173 (pid $(get_pid frontend))"
    fi
    cd "$ROOT_DIR"
}

stop_frontend() {
    if is_running frontend; then
        local pid
        pid=$(get_pid frontend)
        log "Stopping Frontend (pid $pid)..."
        kill_tree "$pid"
        wait_for_death "$pid" "Frontend" 5
        rm -f "$PID_DIR/frontend.pid"
        ok "Frontend stopped"
    fi
}

start_inngest() {
    if is_running inngest; then
        warn "Inngest dev server already running (pid $(get_pid inngest))"
        return 0
    fi
    log "Starting Inngest dev server (:8288)..."
    if command -v npx &>/dev/null; then
        npx inngest-cli@latest dev \
            --no-discovery \
            -u http://localhost:8000/api/inngest \
            --port 8288 \
            > "$LOG_DIR/inngest.log" 2>&1 &
        echo $! > "$PID_DIR/inngest.pid"
        if wait_for_port 8288 "Inngest" 20; then
            ok "Inngest dev server started on :8288 (pid $(get_pid inngest))"
        fi
    else
        err "npx not found — install Node.js first"
        return 1
    fi
}

stop_inngest() {
    if is_running inngest; then
        local pid
        pid=$(get_pid inngest)
        log "Stopping Inngest (pid $pid)..."
        kill_tree "$pid"
        wait_for_death "$pid" "Inngest" 10
        rm -f "$PID_DIR/inngest.pid"
        ok "Inngest stopped"
    fi
}

# ── Compound commands ────────────────────────────────────────────

cmd_start() {
    local service="${1:-all}"
    echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║       FORGE — Starting Services      ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
    echo ""

    case "$service" in
        all)
            start_redis
            start_backend
            start_inngest
            start_frontend
            echo ""
            log "All services started. Dashboard: ${CYAN}http://localhost:5173${NC}"
            log "Inngest UI: ${CYAN}http://localhost:8288${NC}"
            ;;
        redis)    start_redis ;;
        backend)  start_backend ;;
        frontend) start_frontend ;;
        inngest)  start_inngest ;;
        *)        err "Unknown service: $service"; usage ;;
    esac
}

cmd_stop() {
    local service="${1:-all}"
    echo -e "${BOLD}Stopping FORGE services...${NC}"

    case "$service" in
        all)
            stop_frontend
            stop_inngest
            stop_backend
            stop_redis
            echo ""
            ok "All services stopped"
            ;;
        redis)    stop_redis ;;
        backend)  stop_backend ;;
        frontend) stop_frontend ;;
        inngest)  stop_inngest ;;
        *)        err "Unknown service: $service"; usage ;;
    esac
}

cmd_restart() {
    local service="${1:-all}"
    cmd_stop "$service"

    # Verify all target PIDs are actually gone before restarting
    local services_to_check=()
    if [[ "$service" == "all" ]]; then
        services_to_check=(redis backend inngest frontend)
    else
        services_to_check=("$service")
    fi
    for svc in "${services_to_check[@]}"; do
        if is_running "$svc"; then
            err "$svc is still running after stop — aborting restart"
            return 1
        fi
    done
    ok "All target processes confirmed stopped"

    cmd_start "$service"
}

cmd_status() {
    echo -e "${BOLD}FORGE Service Status${NC}"
    echo "────────────────────────────────────"
    for svc in redis backend inngest frontend; do
        if is_running "$svc"; then
            local pid
            pid=$(get_pid "$svc")
            local port=""
            case "$svc" in
                redis)    port=":6379" ;;
                backend)  port=":8000" ;;
                inngest)  port=":8288" ;;
                frontend) port=":5173" ;;
            esac
            echo -e "  ${GREEN}●${NC} ${BOLD}$svc${NC}  pid=$pid  $port"
        else
            echo -e "  ${RED}○${NC} ${BOLD}$svc${NC}  stopped"
        fi
    done
    echo "────────────────────────────────────"
}

cmd_logs() {
    local service="${1:-all}"
    if [[ "$service" == "all" ]]; then
        log "Tailing all logs (Ctrl+C to stop)..."
        tail -f "$LOG_DIR"/*.log 2>/dev/null || err "No log files found"
    else
        local logfile="$LOG_DIR/$service.log"
        if [[ -f "$logfile" ]]; then
            log "Tailing $service logs..."
            tail -f "$logfile"
        else
            err "No log file for $service"
        fi
    fi
}

cmd_test() {
    local target="${1:-all}"
    echo -e "${BOLD}FORGE — Running Tests${NC}"

    case "$target" in
        all)
            log "Backend tests..."
            cd "$BACKEND_DIR"
            $PYTHON -m pytest tests/ -v --timeout=30
            echo ""
            log "Frontend typecheck..."
            cd "$FRONTEND_DIR"
            npm run typecheck
            ;;
        backend)
            cd "$BACKEND_DIR"
            $PYTHON -m pytest tests/ -v --timeout=30
            ;;
        frontend)
            cd "$FRONTEND_DIR"
            npm run typecheck
            ;;
        *)
            # Assume it's a specific test file/pattern
            cd "$BACKEND_DIR"
            $PYTHON -m pytest "$target" -v --timeout=30
            ;;
    esac
    cd "$ROOT_DIR"
}

cmd_deploy() {
    local target="${1:-check}"

    case "$target" in
        check)
            echo -e "${BOLD}FORGE — Pre-deploy Checklist${NC}"
            echo "────────────────────────────────────"

            log "1. Backend tests..."
            cd "$BACKEND_DIR"
            if $PYTHON -m pytest tests/ -v --timeout=30; then
                ok "Backend tests passed"
            else
                err "Backend tests FAILED — fix before deploying"
                exit 1
            fi

            echo ""
            log "2. Frontend typecheck..."
            cd "$FRONTEND_DIR"
            if npm run typecheck; then
                ok "Frontend typecheck passed"
            else
                err "Frontend typecheck FAILED"
                exit 1
            fi

            echo ""
            log "3. Frontend build..."
            if npm run build; then
                ok "Frontend build succeeded"
            else
                err "Frontend build FAILED"
                exit 1
            fi

            echo ""
            ok "All pre-deploy checks passed!"
            cd "$ROOT_DIR"
            ;;
        migrate)
            log "Running Alembic migrations (DATABASE_DIRECT_URL)..."
            cd "$BACKEND_DIR"
            $PYTHON -m alembic upgrade head
            ok "Migrations complete"
            cd "$ROOT_DIR"
            ;;
        worker)
            log "Deploying preview-proxy worker..."
            cd "$WORKERS_DIR"
            npx wrangler deploy
            ok "Worker deployed"
            cd "$ROOT_DIR"
            ;;
        *)
            err "Unknown deploy target: $target"
            echo "  Usage: ./forge.sh deploy {check|migrate|worker}"
            ;;
    esac
}

cmd_health() {
    echo -e "${BOLD}FORGE — Health Checks${NC}"
    echo "────────────────────────────────────"

    # Backend
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        local resp
        resp=$(curl -sf http://localhost:8000/health)
        ok "Backend  :8000  $resp"
    else
        err "Backend  :8000  unreachable"
    fi

    # Frontend
    if curl -sf http://localhost:5173 > /dev/null 2>&1; then
        ok "Frontend :5173  serving"
    else
        err "Frontend :5173  unreachable"
    fi

    # Inngest
    if curl -sf http://localhost:8288 > /dev/null 2>&1; then
        ok "Inngest  :8288  serving"
    else
        err "Inngest  :8288  unreachable"
    fi

    # Redis
    if command -v redis-cli &>/dev/null && redis-cli ping 2>/dev/null | grep -q PONG; then
        ok "Redis    :6379  PONG"
    else
        warn "Redis    local not responding (may be using Upstash)"
    fi

    echo "────────────────────────────────────"
}

cmd_clean() {
    log "Cleaning PID files and logs..."
    rm -f "$PID_DIR"/*.pid
    rm -f "$LOG_DIR"/*.log
    ok "Cleaned .pids/ and .logs/"
}

usage() {
    echo ""
    echo -e "${BOLD}Usage:${NC} ./forge.sh <command> [service]"
    echo ""
    echo -e "${BOLD}Commands:${NC}"
    echo "  start   [service]   Start services (all|redis|backend|frontend|inngest)"
    echo "  stop    [service]   Stop services"
    echo "  restart [service]   Restart services"
    echo "  status              Show running services"
    echo "  logs    [service]   Tail logs (all|redis|backend|frontend|inngest)"
    echo "  health              HTTP health checks on all services"
    echo "  test    [target]    Run tests (all|backend|frontend|<file>)"
    echo "  deploy  [target]    Deploy checks (check|migrate|worker)"
    echo "  clean               Remove PID files and logs"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo "  ./forge.sh start              # Start everything"
    echo "  ./forge.sh start backend      # Start only backend"
    echo "  ./forge.sh restart frontend   # Restart frontend"
    echo "  ./forge.sh logs backend       # Tail backend logs"
    echo "  ./forge.sh test               # Run all tests"
    echo "  ./forge.sh deploy check       # Pre-deploy checklist"
    echo "  ./forge.sh deploy migrate     # Run Alembic migrations"
    echo ""
    exit 1
}

# ── Main ─────────────────────────────────────────────────────────

command="${1:-}"
shift || true

case "$command" in
    start)   cmd_start "${1:-all}" ;;
    stop)    cmd_stop "${1:-all}" ;;
    restart) cmd_restart "${1:-all}" ;;
    status)  cmd_status ;;
    logs)    cmd_logs "${1:-all}" ;;
    health)  cmd_health ;;
    test)    cmd_test "${1:-all}" ;;
    deploy)  cmd_deploy "${1:-check}" ;;
    clean)   cmd_clean ;;
    *)       usage ;;
esac
