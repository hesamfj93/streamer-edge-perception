# Deployment

This is the long-form companion to the *Setup* section of the top-level
[`README.md`](../README.md). The README gives you the daily commands;
this document covers first-time installation, the network layout, and the
verification checklist.

## Network layout

The supported topology is a direct, isolated Ethernet link between the
Jetson and the laptop. No router, no Wi-Fi, no DHCP. This was chosen
because field testing on institutional networks introduced too many
variables (NAT timeouts, multicast suppression, subnet hopping when
Wi-Fi reasserted a default route).

```
   Jetson Orin NX                              Laptop
   192.168.50.1   ───── direct Cat-6 ─────  192.168.50.2
   eth0           ┌─── 192.168.50.0/24 ──┐  Ethernet
                  │                       │
   :1883 mosquitto│                       │ MQTT client
   :8554 MediaMTX │                       │ RTSP client
```

Both machines should have Wi-Fi disabled during operation, or at minimum
configured on a different subnet, to prevent the OS from picking the
wrong route.

## First-time setup, Jetson

Tested with JetPack 5.1.2 on Jetson Orin NX 16 GB.

```bash
# 1. System packages
sudo apt update
sudo apt install -y mosquitto mosquitto-clients gstreamer1.0-tools \
                    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad

# 2. mosquitto: bind to all interfaces (default is localhost only)
sudo tee /etc/mosquitto/conf.d/local.conf <<'EOF'
listener 1883 0.0.0.0
allow_anonymous true
EOF
sudo systemctl restart mosquitto

# 3. MediaMTX
#    Download the linux_arm64 release from
#    https://github.com/bluenviron/mediamtx/releases
#    Place the binary at ~/mediamtx and the config at ~/mediamtx.yml
cp configs/mediamtx.example.yml ~/mediamtx.yml

# 4. Python deps
pip3 install -r jetson/requirements.txt

# 5. Local config
cp configs/config.example.ini configs/config.ini
nano configs/config.ini
#   Set:
#     [inference] engine_dir   to the directory holding your .engine files
#     [inference] input_video  to your test video (or a v4l2 device path)
```

The TensorRT engine itself is built outside this repository, by exporting
your YOLOv8 weights to ONNX (`yolo export format=onnx`) and then compiling
to an engine via `trtexec --onnx=... --fp16 --saveEngine=best_fp16_640.engine`.
The expected engine filename pattern is `best_fp16_<imgsz>.engine` and
the expected location is `<engine_dir>/`.

## First-time setup, laptop

Tested on Windows 10 and 11 with Python 3.10, 3.11, 3.12.

```powershell
cd <repo path>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r windows_app\requirements.txt
```

In Windows network settings, set the Ethernet adapter to:

- IPv4: **Static**
- IP: **192.168.50.2**
- Mask: **255.255.255.0**
- Gateway: leave **empty**
- DNS: leave **empty**

Disable Wi-Fi or, if you need it on, ensure your Wi-Fi network is on a
different subnet from `192.168.50.0/24`.

## Daily startup

```bash
# Jetson
cd <repo path>
scripts/check_network.sh   # read-only diagnostic; no changes
scripts/start_jetson.sh    # idempotent
tail -f .run/jetson/master_agent.log   # optional, watch the agent
```

```powershell
# Laptop
cd <repo path>
.\scripts\start_windows_ui.ps1
```

In the GUI:

1. **Connect MQTT** → accept the dialog defaults (read from `config.ini`).
2. **Play RTSP…** → accept the default URL.
3. **Start** → the Jetson begins inference; FPS and detection overlays
   appear within a couple of seconds.

## Verifying the deployment

A 10-minute smoke test that confirms each layer works.

| # | Where | Command / action | Pass criterion |
|---|---|---|---|
| 1 | Jetson | `scripts/check_network.sh` | All sections show ✓ where the corresponding service is supposed to be running |
| 2 | Jetson | `scripts/start_jetson.sh` | Five "started" / "already running" lines, finishes with `=== Jetson side up ===` |
| 3 | Jetson | `tail .run/jetson/master_agent.log` | `[MQTT] Connected: 0` |
| 4 | Jetson | `mosquitto_sub -h 192.168.50.1 -t 'projectA/jetson-01/master/#' -v` | Within 2 s see a retained `master/status {"state":"idle",...}` |
| 5 | Laptop | `Test-NetConnection 192.168.50.1 -Port 8554` | `TcpTestSucceeded : True` |
| 6 | Laptop | Open the URL in VLC: `rtsp://192.168.50.1:8554/jetson` | Video plays within 3 s |
| 7 | Laptop | `.\scripts\start_windows_ui.ps1` | GUI window appears |
| 8 | GUI    | *Connect MQTT* | `lblMqtt` becomes `connected` |
| 9 | GUI    | *Play RTSP…* | Live video appears in the central panel |
| 10 | GUI   | *Start* | Agent log shows `[PIPE] Launching:`; status switches to `running`; FPS becomes non-zero |
| 11 | GUI   | wait 10 s | Detection boxes appear over the video; `mosquitto_sub` shows steady `dets` messages |
| 12 | GUI   | *Stop*, then close | Status returns to `idle`; `pgrep run_trt_video.py` returns nothing |
| 13 | Jetson | `scripts/stop_jetson.sh` | Five "stopped" lines |

If 1–13 pass, the deployment is verified end-to-end.

## Shutdown

```bash
scripts/stop_jetson.sh
```

The script stops in reverse dependency order: agent → GStreamer push →
MediaMTX → mosquitto, with a 5-second grace per component before
escalating to SIGKILL.

## Configuration reference

All runtime configuration lives in `configs/config.ini`. The resolution
order, highest priority first, is:

1. Environment variables (e.g. `MQTT_BROKER`, `RTSP_URL`, `IMGSZ`).
2. `configs/config.local.ini` (gitignored personal override).
3. `configs/config.ini`.
4. `configs/config.example.ini` (committed template).
5. Hardcoded fallbacks in `configs/config_loader.py`.

The MQTT topic schema is fixed and documented in
[`architecture.md`](architecture.md). Changing topic names requires
matching changes on both sides; configuration only changes the prefix
and broker.
