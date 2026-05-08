#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
master_agent.py
- کنترل و پایش YOLO TensorRT pipeline روی Jetson
- دریافت فرمان از MQTT (start/stop/set)
- اجرای run_trt_video.py و انتشار status, FPS, DET روی MQTT

Refactor note (Phase 1):
- Defaults now come from configs/config.ini (or env vars), not hardcoded.
- Topic schema, parsers, and process management are UNCHANGED.
"""

import os, sys, json, signal, threading, subprocess, re
from pathlib import Path
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

# -------- Locate and import the shared config loader --------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "configs"))
from config_loader import load_config  # noqa: E402

CFG = load_config()

# -------- Config (config-driven; env still wins via the loader) --------
BROKER    = CFG.mqtt_broker
PORT      = CFG.mqtt_port
PREFIX    = CFG.mqtt_prefix
CLIENTID  = CFG.mqtt_client_id
QOS       = 0
DEBUG_LOG = os.environ.get("DEBUG_LOG", "1") == "1"   # ← پیش‌فرض روشن برای دیباگ

ENGINE_DIR = CFG.engine_dir
VIDEO_IN   = CFG.input_video
# If script_path is empty in config, default to run_trt_video.py next to this file.
SCRIPT     = Path(CFG.script_path) if CFG.script_path else (Path(__file__).resolve().parent / "run_trt_video.py")

STATUS_ITV = 2.0

# -------- State --------
state = {"running": False, "imgsz": CFG.imgsz, "conf": CFG.conf, "fps": None}
_proc = None
_stop_evt = threading.Event()

# -------- Helpers --------
def iso_now(): 
    return datetime.now(timezone.utc).isoformat()

def build_status():
    return {
        "state": "running" if state["running"] else "idle",
        "imgsz": state["imgsz"],
        "conf": state["conf"],
        "fps": state["fps"],
        "ts": iso_now()
    }

def publish_status(c):
    c.publish(f"{PREFIX}/master/status", json.dumps(build_status()), qos=QOS, retain=True)

def _dbg(msg): 
    print(msg, flush=True)

def _engine_path():
    return ENGINE_DIR / f"best_fp16_{state['imgsz']}.engine"

# -------- Parsers --------
def _parse_fps(line: str):
    """Robust FPS parser for lines like:
       '[info] ... avg_fps=19.5', 'Avg FPS: 29.0', 'FPS: 28.7' """
    s = line.strip()
    low = s.lower()
    # 1) avg_fps=19.5
    m = re.search(r'avg[_\s]*fps\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)', low)
    if m: return float(m.group(1))
    # 2) fps: 28.7  یا avg fps: 29.0
    m = re.search(r'\bfps\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)', low)
    if m: return float(m.group(1))
    # 3) fallback: هر عددی بعد از 'avg_fps'
    m = re.search(r'avg[_\s]*fps[^0-9]*([0-9]+(?:\.[0-9]+)?)', low)
    if m: return float(m.group(1))
    return None

def _parse_det(line: str):
    """Parse DET {...} lines emitted by run_trt_video.py"""
    s = line.strip()
    if not s.startswith("DET "):
        return None
    try:
        return json.loads(s[4:])
    except Exception:
        return None

# -------- Pipeline control --------
def start_pipeline(client: mqtt.Client):
    global _proc
    if _proc and _proc.poll() is None:
        return
    eng = _engine_path()
    if not eng.exists():
        _ack(client, {"action": "start"}, ok=False, note=f"engine not found: {eng}")
        return
    if not SCRIPT.exists():
        _ack(client, {"action": "start"}, ok=False, note=f"script not found: {SCRIPT}")
        return
    if not VIDEO_IN.exists():
        _ack(client, {"action": "start"}, ok=False, note=f"input not found: {VIDEO_IN}")
        return

    cmd = [
        "python3", "-u", str(SCRIPT),
        "--engine", str(eng),
        "--input", str(VIDEO_IN),
        "--imgsz", str(state["imgsz"]),
        "--conf", str(state["conf"]),
        "--every", "200",
        "--det-every", "5"
    ]

    _dbg(f"[PIPE] Launching: {' '.join(cmd)}")
    try:
        _proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        _ack(client, {"action": "start"}, ok=False, note=f"launch error: {e}")
        return

    # ------------------ Reader thread ------------------
    def _reader():
        global _proc
        for line in _proc.stdout:
            if not line:
                continue
            # Mirror output if debug enabled
            if DEBUG_LOG:
                sys.stdout.write(line)
                sys.stdout.flush()

            # Parse FPS
            val = _parse_fps(line)
            if val is not None:
                state["fps"] = float(val)
                publish_status(client)
                continue

            # Parse DET
            det = _parse_det(line)
            if det is not None:
                try:
                    client.publish(f"{PREFIX}/master/dets", json.dumps(det), qos=QOS, retain=False)
                    _dbg(f"[PUB DET] objs={len(det.get('objs', []))}")
                except Exception as e:
                    _dbg(f"[DET ERR] {e}")
                continue

        # پایان
        state["fps"] = None
        state["running"] = False
        publish_status(client)
        _dbg("[PIPE] Exited.")

    threading.Thread(target=_reader, daemon=True).start()

def stop_pipeline():
    global _proc
    if _proc and _proc.poll() is None:
        _dbg("[PIPE] Stopping...")
        try:
            _proc.terminate()
            _proc.wait(timeout=5)
        except Exception:
            try:
                _proc.kill()
            except Exception:
                pass
    _proc = None
    state["fps"] = None

# -------- MQTT --------
def _ack(c, ack_obj, ok=True, note=""):
    c.publish(f"{PREFIX}/master/ack",
              json.dumps({"ack": ack_obj, "ok": ok, "note": note, "ts": iso_now()}),
              qos=QOS, retain=False)

def on_connect(c, u, flags, rc, props=None):
    _dbg(f"[MQTT] Connected: {rc}")
    c.subscribe(f"{PREFIX}/master/cmd", qos=QOS)
    publish_status(c)

def on_message(c, u, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        _ack(c, "bad_json", ok=False, note=str(e))
        return

    ok, note, action = True, "", payload.get("action")

    if action == "start":
        state["running"] = True
        start_pipeline(c)
    elif action == "stop":
        state["running"] = False
        stop_pipeline()
    elif action == "set" and payload.get("param") == "conf":
        v = payload.get("value", {})
        try:
            new_imgsz = state["imgsz"]
            if "imgsz" in v:
                new_imgsz = int(v["imgsz"])
            if "conf" in v:
                state["conf"] = float(v["conf"])
            need_restart = (new_imgsz != state["imgsz"]) and state["running"]
            state["imgsz"] = new_imgsz
            if need_restart:
                stop_pipeline()
                state["running"] = True
                start_pipeline(c)
        except Exception as e:
            ok, note = False, f"bad_value: {e}"
    else:
        ok, note = False, "unknown_cmd"

    _ack(c, payload, ok=ok, note=note)
    publish_status(c)

# -------- Status thread --------
def status_loop(c):
    while not _stop_evt.is_set():
        publish_status(c)
        _stop_evt.wait(STATUS_ITV)

# -------- Main --------
def main():
    _dbg(f"[CFG] Loaded from: {CFG.source}")
    _dbg(f"[CFG] broker={BROKER}:{PORT}  prefix={PREFIX}")
    _dbg(f"[CFG] engine_dir={ENGINE_DIR}")
    _dbg(f"[CFG] input_video={VIDEO_IN}")
    _dbg(f"[CFG] script={SCRIPT}")

    lwt = {"state": "offline", "ts": iso_now()}
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=CLIENTID, clean_session=True)
    c.will_set(f"{PREFIX}/master/status", json.dumps(lwt), qos=QOS, retain=True)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(BROKER, PORT, keepalive=30)

    threading.Thread(target=status_loop, args=(c,), daemon=True).start()

    def _sig(*_):
        _dbg("[SYS] Shutting down...")
        _stop_evt.set()
        stop_pipeline()
        try:
            publish_status(c)
        finally:
            c.disconnect()
            sys.exit(0)

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    c.loop_forever()

if __name__ == "__main__":
    main()
