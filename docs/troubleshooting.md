# Troubleshooting

Symptoms, in roughly the order you'll hit them after a long break.

## "Cannot ping 192.168.50.1 from the laptop"

The eth0 static IP wasn't (re)applied on the Jetson, or Wi-Fi is
hijacking the route on either side.

Run on Jetson:
```bash
ip addr show eth0   # expect: inet 192.168.50.1/24
sudo nmcli radio wifi off
```
or just re-run `scripts/start_jetson.sh` (idempotent).

On the laptop, check that the Ethernet adapter is set to static
192.168.50.2 / 255.255.255.0 with NO gateway, and Wi-Fi is on a
different subnet (or off). PowerShell:
```powershell
Get-NetIPConfiguration
Test-NetConnection 192.168.50.1 -Port 8554
```

## "Cannot open RTSP via TCP" in the GUI

Three independent causes:

1. **MediaMTX not running.** From Jetson: `pgrep -x mediamtx`.
   Restart with `scripts/start_jetson.sh`.
2. **GStreamer push pipeline not running.** From Jetson:
   `pgrep -f rtspclientsink`. Same fix.
3. **OpenCV/FFmpeg version drift on Windows.** The pip wheel of
   `opencv-python` ships its own FFmpeg; rare release combinations
   break RTSP option parsing. If everything else looks healthy, try:
   ```
   pip install "opencv-python==4.10.0.84"
   ```

A quick sanity check from Windows (without our app): open VLC →
*Media → Open Network Stream → `rtsp://192.168.50.1:8554/jetson`*.
If VLC plays, the source is fine and the bug is on the client side.

## RTSP plays but no detection boxes appear

The MQTT plane is independent from the video plane. Check, in order:

- The GUI's MQTT label says "connected" (top-right area).
- `master_agent.py` is running on Jetson (`pgrep -f master_agent.py`)
  and you sent `Start` from the toolbar.
- The agent log shows `[PUB DET] objs=N` lines:
  ```bash
  tail -f .run/jetson/master_agent.log
  ```
  If there are no `[PUB DET]` lines, the `run_trt_video.py` subprocess
  exited (engine missing? input video missing?). Check the same log
  for `engine not found` or `input not found` `ack` messages.

## "Opening in BLOCKING MODE" from gst-launch

This was the original sticky failure. Two causes:

- The RTSP sink connected before MediaMTX was up. `start_jetson.sh`
  starts MediaMTX first and sleeps a second before the GStreamer push
  to avoid this race.
- UDP transport on a mixed Wi-Fi / Ethernet setup. `start_jetson.sh`
  enforces TCP via `protocols=tcp`.

## MQTT connect succeeds then immediately disconnects

Two likely causes:

1. The Windows side previously published a Last-Will-Testament marking
   the Jetson status as `offline`. (Known limitation of the current
   client.) Manual workaround: restart `master_agent.py` so its first
   `publish_status` overwrites the retained "offline" message.
2. Two clients with the same `client_id`. paho's broker disconnects
   the older one. Make sure no other process is using
   `jetson-01-master`.

## Engine file not found

`master_agent.py` looks for
`<engine_dir>/best_fp16_<imgsz>.engine`. Check
`configs/config.ini` `[inference]` keys, and that the engine file
actually exists for the imgsz you're requesting (640 vs 1280 are
different engines).

## Jetson power throttling banner

If you see "System throttled due to Over-current," the 45 W brick is
undersized for sustained Orin NX inference under simultaneous TensorRT +
hardware encode load. Use a 19 V / ≥ 65 W barrel adapter. Not a software
problem.

## "Module not found: config_loader"

You're running `master_agent.py` or `main.py` from a directory where
the relative path to `configs/` doesn't resolve. Both scripts compute
the repo root relative to their own location, so as long as the file
layout matches the repo (`jetson/master_agent.py` and
`windows_app/app/main.py`), it works. Don't move the scripts out of
their folders.

## Windows GUI launches but no toolbar visible

Qt sometimes hides toolbars when the window is first opened tiny. The
toolbar is there — drag the window edge to make it bigger and it
should appear, or right-click in the title bar and check the
"Controls" toolbar entry.
