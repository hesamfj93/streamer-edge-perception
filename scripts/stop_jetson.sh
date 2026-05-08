#!/usr/bin/env bash
# =====================================================================
# stop_jetson.sh
# Stop every component started by scripts/start_jetson.sh, in reverse
# dependency order. Safe to run multiple times.
# =====================================================================
set -u

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
PID_DIR="$REPO_ROOT/.run/jetson/pids"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
info()  { printf '\033[36m[stop]\033[0m %s\n' "$*"; }

stop_pidfile() {
    local name="$1"
    local pidfile="$PID_DIR/$name.pid"
    if [ -f "$pidfile" ]; then
        local pid
        pid="$(cat "$pidfile")"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            info "Stopping $name (PID $pid)"
            kill "$pid" 2>/dev/null || true
            for _ in $(seq 1 10); do
                if kill -0 "$pid" 2>/dev/null; then sleep 0.5; else break; fi
            done
            if kill -0 "$pid" 2>/dev/null; then
                red "  -> still alive, sending SIGKILL"
                kill -9 "$pid" 2>/dev/null || true
            fi
            green "  -> stopped"
        else
            info "$name not running (stale PID file)"
        fi
        rm -f "$pidfile"
    else
        info "$name has no PID file (likely not started by this script)"
    fi
}

# Reverse order: agent -> gstreamer -> mediamtx -> mosquitto
stop_pidfile master_agent
stop_pidfile gstreamer
stop_pidfile mediamtx

# mosquitto: prefer systemd if it is running that unit
if [ -f "$PID_DIR/mosquitto.pid" ]; then
    stop_pidfile mosquitto
elif command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet mosquitto; then
    info "Stopping mosquitto via systemd"
    sudo systemctl stop mosquitto && green "  -> stopped"
fi

# Belt-and-braces: kill orphaned processes by pattern
for pattern in "master_agent.py" "rtspclientsink" "mediamtx"; do
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        info "Found leftover $pattern processes: $pids"
        kill $pids 2>/dev/null || true
    fi
done

green "=== Jetson side stopped ==="
