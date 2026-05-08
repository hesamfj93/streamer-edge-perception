# Architecture

## Three runtime planes

The system has three independent runtime planes. Knowing this is the
single most important thing for debugging, because the planes can fail
independently and produce different symptoms.

```
   ┌──────────────── Jetson (192.168.50.1) ─────────────────┐
   │                                                         │
   │  master_agent.py  ←──── MQTT cmd ──────┐                │
   │       │                                 │                │
   │       │ Popen                           │                │
   │       ▼                                 │                │
   │  run_trt_video.py                       │                │
   │   ├─ TensorRT inference                 │                │
   │   ├─ stdout: "DET {...}" + "avg_fps=X"  │                │
   │   └─ writes annotated MP4 to ~/runs_trt │                │
   │       │                                 │                │
   │       ▼ (parsed)                        │                │
   │  master_agent → MQTT publishes ─────────┘                │
   │                  (status, dets, ack)                     │
   │                                                          │
   │  GStreamer push pipeline ──▶ MediaMTX ──▶ RTSP listen    │
   │  (separate process)            on :8554                  │
   │                                                          │
   └──────────────── │ (eth0) ──── │ (8554) ────── │ (1883) ──┘
                     │             │               │
              direct Ethernet — 192.168.50.0/24 — direct Ethernet
                     │             │               │
   ┌──────────────── │ (192.168.50.2) ─────────── │ ─────────┐
   │                                                          │
   │  windows_app/run_app.py                                  │
   │   ├─ MqttBridge (paho on QThread) ──── MQTT ◀────┐       │
   │   ├─ VideoPlayer                                  │       │
   │   │   ├─ QMediaPlayer  (local files)             │       │
   │   │   └─ _CvWorker     (RTSP via OpenCV/FFmpeg) ─┼─ RTSP │
   │   └─ DET overlay drawn on top of RTSP frames     │       │
   │      (scaled by frame_size ratio)                 │       │
   │                                                          │
   └─────────────────────────── Windows laptop ───────────────┘
```

## Plane A — Inference & control (in repo, `jetson/`)

`master_agent.py` is a long-running MQTT client that supervises
`run_trt_video.py`. It does not produce video; it produces detection
metadata and FPS readings on MQTT.

`run_trt_video.py` is the YOLOv8 TensorRT inference pipeline. It
decodes a local MP4 with PyAV, runs inference, and writes an annotated
MP4 to disk. The MP4 file is incidental — the live signal that matters
is its **stdout**, which the agent parses.

## Plane B — Video transport (NOT in repo)

The actual RTSP video the laptop sees is produced by an external
GStreamer pipeline that pushes a video stream into MediaMTX. The
GStreamer command and MediaMTX configuration are now wrapped by
`scripts/start_jetson.sh`, but neither program is part of this Python
codebase. Both must be installed on the Jetson.

A reference `configs/mediamtx.example.yml` is provided.

## Plane C — Windows GUI (in repo, `windows_app/`)

PySide6 application with two video backends:

- **Files** (`.mp4`, `.avi`, ...) → `QMediaPlayer` writing to the
  `QVideoWidget` from the .ui.
- **RTSP** (`rtsp://...`) → custom `_CvWorker(QThread)` using
  OpenCV/FFmpeg over TCP, frames painted onto a `QLabel` overlaid on
  the (hidden) `QVideoWidget`.

MQTT runs in its own QThread (`MqttBridge` → `MqttWorker`).

The two streams (RTSP video, MQTT detections) are independent. The DET
overlay uses "latest DET wins"; it is not frame-synchronised to the
displayed video.

## Configuration

A single source: `configs/config.ini` (or `config.example.ini` as
fallback). Loaded by `configs/config_loader.py`, used by both the
Jetson agent and the Windows app. Environment variables override the
file (see comment headers in the config).

## Why three planes, not one?

This split exists for a reason: TensorRT engines are Jetson-only and
the Windows side cannot run inference. Annotating frames on the Jetson
and re-encoding to RTSP would double the Jetson's CPU load (libx264
software encode on top of TRT inference). Sending compact JSON
detections over MQTT and overlaying on the client is much cheaper.

The trade-off is the absence of strict frame–detection sync. For a
human watching the stream this is rarely visible (DETs arrive every
~5 frames, latency under 100 ms on a clean LAN). For automated
analysis, it would matter and a different design would be appropriate.
