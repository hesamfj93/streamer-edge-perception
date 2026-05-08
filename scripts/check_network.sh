#!/usr/bin/env bash
# =====================================================================
# check_network.sh
# Pre-flight network diagnostic. Run on either side; it auto-detects
# whether it's on the Jetson or the laptop.
#
# Verifies:
#   - eth0 has the expected IP
#   - the peer is reachable (ping)
#   - MQTT broker port is listening / reachable
#   - RTSP server port is listening / reachable
#   - Wi-Fi state (warns about route conflicts)
#
# Read-only. Does not change configuration.
# =====================================================================
set -u

REPO_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
CONFIGS_DIR="$REPO_ROOT/configs"

read_cfg() { python3 "$CONFIGS_DIR/config_loader.py" "$1"; }

JETSON_IP="${JETSON_IP:-192.168.50.1}"
LAPTOP_IP="${LAPTOP_IP:-192.168.50.2}"
MQTT_BROKER="$(read_cfg mqtt_broker)"
MQTT_PORT="$(read_cfg mqtt_port)"
RTSP_URL="$(read_cfg rtsp_url)"
RTSP_HOST="$(printf '%s' "$RTSP_URL" | sed -E 's#rtsp://([^:/]+).*#\1#')"
RTSP_PORT="$(printf '%s' "$RTSP_URL" | sed -nE 's#rtsp://[^:]+:([0-9]+).*#\1#p')"
RTSP_PORT="${RTSP_PORT:-8554}"

green()  { printf '\033[32m✓\033[0m %s\n' "$*"; }
red()    { printf '\033[31m✗\033[0m %s\n' "$*"; }
yellow() { printf '\033[33m!\033[0m %s\n' "$*"; }
hdr()    { printf '\n\033[36m== %s ==\033[0m\n' "$*"; }

# Auto-detect side
LOCAL_IPS="$(hostname -I 2>/dev/null || ip -4 -o addr show 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | tr '\n' ' ')"
SIDE="unknown"
if printf '%s ' $LOCAL_IPS | grep -q "$JETSON_IP "; then
    SIDE="jetson"
elif printf '%s ' $LOCAL_IPS | grep -q "$LAPTOP_IP "; then
    SIDE="laptop"
fi
hdr "Side detection"
echo "Local IPs:  $LOCAL_IPS"
echo "Detected:   $SIDE"

# 1. Ethernet IP
hdr "Ethernet"
if printf '%s ' $LOCAL_IPS | grep -q -E "(${JETSON_IP}|${LAPTOP_IP}) "; then
    green "Ethernet IP looks correct (one of $JETSON_IP / $LAPTOP_IP)"
else
    red "Neither $JETSON_IP nor $LAPTOP_IP found on this host"
    yellow "Run scripts/start_jetson.sh on Jetson, or set the IP manually on the laptop."
fi

# 2. Peer ping
hdr "Peer reachability"
if [ "$SIDE" = "jetson" ]; then
    PEER="$LAPTOP_IP"
elif [ "$SIDE" = "laptop" ]; then
    PEER="$JETSON_IP"
else
    PEER="$JETSON_IP"
fi
if ping -c 2 -W 2 "$PEER" >/dev/null 2>&1; then
    green "$PEER is reachable"
else
    red "$PEER did NOT respond to ping"
    yellow "Check the cable, the static IP on the other side, and any host firewall."
fi

# 3. Wi-Fi conflict warning
hdr "Wi-Fi state"
if command -v nmcli >/dev/null 2>&1; then
    WIFI_STATE="$(nmcli radio wifi 2>/dev/null || echo unknown)"
    if [ "$WIFI_STATE" = "enabled" ]; then
        yellow "Wi-Fi is ENABLED. Past debugging notes show this can cause routing"
        yellow "conflicts on Jetson. Disable with:  sudo nmcli radio wifi off"
    else
        green "Wi-Fi is $WIFI_STATE"
    fi
else
    echo "(nmcli not installed; skipping)"
fi

# 4. MQTT port
hdr "MQTT broker ($MQTT_BROKER:$MQTT_PORT)"
if [ "$MQTT_BROKER" = "$JETSON_IP" ] || [ "$MQTT_BROKER" = "localhost" ] || [ "$MQTT_BROKER" = "127.0.0.1" ]; then
    if [ "$SIDE" = "jetson" ]; then
        # Local: check it's listening
        if ss -ltn 2>/dev/null | grep -q ":$MQTT_PORT "; then
            green "mosquitto is listening on :$MQTT_PORT"
        else
            red "Nothing is listening on :$MQTT_PORT — start mosquitto first"
        fi
    fi
fi
# From any side, attempt a TCP connect
if command -v nc >/dev/null 2>&1; then
    if nc -z -w 2 "$MQTT_BROKER" "$MQTT_PORT" 2>/dev/null; then
        green "TCP connect to $MQTT_BROKER:$MQTT_PORT OK"
    else
        red "TCP connect to $MQTT_BROKER:$MQTT_PORT FAILED"
    fi
elif command -v python3 >/dev/null 2>&1; then
    if python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('$MQTT_BROKER', $MQTT_PORT)); s.close()" 2>/dev/null; then
        green "TCP connect to $MQTT_BROKER:$MQTT_PORT OK"
    else
        red "TCP connect to $MQTT_BROKER:$MQTT_PORT FAILED"
    fi
fi

# 5. RTSP port
hdr "RTSP server ($RTSP_HOST:$RTSP_PORT)"
if [ "$SIDE" = "jetson" ]; then
    if ss -ltn 2>/dev/null | grep -q ":$RTSP_PORT "; then
        green "MediaMTX (or another RTSP server) is listening on :$RTSP_PORT"
    else
        red "Nothing is listening on :$RTSP_PORT — start MediaMTX first"
    fi
fi
if command -v nc >/dev/null 2>&1; then
    if nc -z -w 2 "$RTSP_HOST" "$RTSP_PORT" 2>/dev/null; then
        green "TCP connect to $RTSP_HOST:$RTSP_PORT OK"
    else
        red "TCP connect to $RTSP_HOST:$RTSP_PORT FAILED"
    fi
fi

hdr "Done"
echo "RTSP URL the laptop should use:  $RTSP_URL"
echo "MQTT broker the laptop should use:  $MQTT_BROKER:$MQTT_PORT"
