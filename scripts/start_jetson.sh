#!/usr/bin/env bash
# =====================================================================
# start_jetson.sh
# Bring up the Jetson side of the pipeline in dependency order:
#   1. Static IP on eth0  (192.168.50.1/24)
#   2. mosquitto MQTT broker
#   3. MediaMTX RTSP server
#   4. GStreamer push pipeline (file -> RTSP)
#   5. master_agent.py (subscribes to MQTT, supervises run_trt_video.py)
#
# Idempotent: skips steps that are already running.
# Uses values from configs/config.ini (read via config_loader.py).
# =====================================================================
set -u

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
CONFIGS_DIR="$REPO_ROOT/configs"
JETSON_DIR="$REPO_ROOT/jetson"
LOG_DIR="$REPO_ROOT/.run/jetson"
PID_DIR="$REPO_ROOT/.run/jetson/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

# Tunables (override by exporting before invocation) ------------------
ETH_IFACE="${ETH_IFACE:-eth0}"
JETSON_IP="${JETSON_IP:-192.168.50.1/24}"
DISABLE_WIFI="${DISABLE_WIFI:-1}"     # 1 = nmcli radio wifi off
MEDIAMTX_BIN="${MEDIAMTX_BIN:-$HOME/mediamtx}"
MEDIAMTX_CFG="${MEDIAMTX_CFG:-$HOME/mediamtx.yml}"
# ---------------------------------------------------------------------

# Pull config values via the shared loader (single source of truth)
read_cfg() { python3 "$CONFIGS_DIR/config_loader.py" "$1"; }

INPUT_VIDEO="$(read_cfg input_video)"
RTSP_URL="$(read_cfg rtsp_url)"
MQTT_BROKER="$(read_cfg mqtt_broker)"
MQTT_PORT="$(read_cfg mqtt_port)"

# Derive the MediaMTX path/name from the RTSP URL  (e.g. /jetson)
RTSP_PATH="$(printf '%s' "$RTSP_URL" | sed -E 's#rtsp://[^/]+(/.*)#\1#')"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
info()  { printf '\033[36m[start]\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m[start]\033[0m %s\n' "$*"; }

# ---- 1. Network -----------------------------------------------------
info "Setting static IP $JETSON_IP on $ETH_IFACE"
if ! ip addr show "$ETH_IFACE" 2>/dev/null | grep -q "${JETSON_IP%/*}"; then
    sudo ip addr flush dev "$ETH_IFACE" 2>/dev/null || true
    sudo ip addr add "$JETSON_IP" dev "$ETH_IFACE"
    sudo ip link set "$ETH_IFACE" up
    green "  -> assigned"
else
    green "  -> already configured"
fi

if [ "$DISABLE_WIFI" = "1" ]; then
    info "Disabling Wi-Fi to avoid route conflicts (set DISABLE_WIFI=0 to skip)"
    if command -v nmcli >/dev/null 2>&1; then
        sudo nmcli radio wifi off || true
    else
        warn "  nmcli not found, skipping"
    fi
fi

# ---- 2. mosquitto ----------------------------------------------------
info "Starting mosquitto broker on :$MQTT_PORT"
if ss -ltn 2>/dev/null | grep -q ":$MQTT_PORT "; then
    green "  -> already listening on :$MQTT_PORT"
else
    if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q '^mosquitto'; then
        sudo systemctl start mosquitto
        green "  -> started via systemd"
    elif command -v mosquitto >/dev/null 2>&1; then
        nohup mosquitto -p "$MQTT_PORT" >"$LOG_DIR/mosquitto.log" 2>&1 &
        echo $! > "$PID_DIR/mosquitto.pid"
        green "  -> started in foreground (PID $(cat "$PID_DIR/mosquitto.pid"))"
    else
        red "  mosquitto is not installed. Install with: sudo apt install mosquitto"
        red "  Skipping; the agent will fail to connect."
    fi
fi

# ---- 3. MediaMTX ----------------------------------------------------
info "Starting MediaMTX RTSP server"
if pgrep -x mediamtx >/dev/null 2>&1; then
    green "  -> already running"
elif [ -x "$MEDIAMTX_BIN" ]; then
    nohup "$MEDIAMTX_BIN" "$MEDIAMTX_CFG" >"$LOG_DIR/mediamtx.log" 2>&1 &
    echo $! > "$PID_DIR/mediamtx.pid"
    sleep 1
    green "  -> started (PID $(cat "$PID_DIR/mediamtx.pid"))"
else
    red "  MediaMTX binary not found at $MEDIAMTX_BIN"
    red "  Set MEDIAMTX_BIN=/path/to/mediamtx and re-run, or install MediaMTX."
fi

# ---- 4. GStreamer push ----------------------------------------------
info "Starting GStreamer push pipeline -> $RTSP_URL"
if pgrep -f "rtspclientsink location=$RTSP_URL" >/dev/null 2>&1; then
    green "  -> already running"
elif [ ! -f "$INPUT_VIDEO" ]; then
    red "  Input video not found: $INPUT_VIDEO"
    red "  Edit configs/config.ini (inference.input_video) and re-run."
elif command -v gst-launch-1.0 >/dev/null 2>&1; then
    nohup gst-launch-1.0 -e \
        filesrc location="$INPUT_VIDEO" \
        ! decodebin ! nvvidconv \
        ! 'video/x-raw(memory:NVMM),format=NV12' \
        ! nvv4l2h264enc bitrate=4000000 maxperf-enable=1 iframeinterval=30 insert-sps-pps=1 \
        ! h264parse config-interval=1 \
        ! rtspclientsink "location=$RTSP_URL" protocols=tcp \
        >"$LOG_DIR/gstreamer.log" 2>&1 &
    echo $! > "$PID_DIR/gstreamer.pid"
    sleep 2
    green "  -> started (PID $(cat "$PID_DIR/gstreamer.pid"))"
else
    red "  gst-launch-1.0 not found. Install with: sudo apt install gstreamer1.0-tools"
fi

# ---- 5. master_agent.py ---------------------------------------------
info "Starting master_agent.py"
if pgrep -f "$JETSON_DIR/master_agent.py" >/dev/null 2>&1; then
    green "  -> already running"
else
    nohup python3 -u "$JETSON_DIR/master_agent.py" \
        >"$LOG_DIR/master_agent.log" 2>&1 &
    echo $! > "$PID_DIR/master_agent.pid"
    sleep 1
    green "  -> started (PID $(cat "$PID_DIR/master_agent.pid"))"
fi

echo
green "=== Jetson side up ==="
echo "  RTSP:   $RTSP_URL"
echo "  MQTT:   $MQTT_BROKER:$MQTT_PORT"
echo "  Logs:   $LOG_DIR"
echo "  PIDs:   $PID_DIR"
echo
echo "Tail logs with:  tail -f $LOG_DIR/master_agent.log"
echo "Stop with:       scripts/stop_jetson.sh"
