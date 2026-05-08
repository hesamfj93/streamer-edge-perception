# app/main.py
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Dict
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QToolBar, QInputDialog, QLabel
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from app.ui_main_window import Ui_MainWindow
from app.mqtt_bridge import MqttBridge
from app.video_player import VideoPlayer

# =============================
#  Locate the shared config loader (in <repo_root>/configs/)
# =============================
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "configs"))
from config_loader import load_config  # noqa: E402

CFG = load_config()

# =============================
#  Setting FFmpeg / OpenCV options BEFORE OpenCV is imported
#  by video_player.py. NB: this *must* run before the first cv2
#  capture is created (we are still safe here because video_player
#  only opens captures inside _CvWorker.run, after we set this).
# =============================
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
    "rtsp_transport;tcp|buffer_size;1048576|stimeout;5000000|reorder_queue_size;0"
)
# Phase 3: removed dead env var QT_MEDIA_RTSP_TRANSPORT — no RTSP URL is
# ever fed to QMediaPlayer in this app (RTSP routes through the OpenCV
# worker), so the variable was never read.
print("[INFO] Using OpenCV FFmpeg options:", os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"])
print(f"[INFO] Config loaded from: {CFG.source}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ---------- UI ----------
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # ---------- State ----------
        self._playing: bool = False
        self._rtsp_url: str = CFG.rtsp_url

        # ---------- MQTT ----------
        self.mqtt = MqttBridge(self)
        self.mqtt.connected.connect(self.on_mqtt_connected)
        self.mqtt.disconnected.connect(self.on_mqtt_disconnected)
        self.mqtt.statusMsg.connect(self.on_status_msg)
        self.mqtt.ackMsg.connect(self.on_ack)
        self.mqtt.error.connect(self.on_mqtt_error)
        self.mqtt.detections.connect(self.on_dets)

        # ---------- Video ----------
        self.vp = VideoPlayer(self.ui.videoWidget, self)

        # Connecting video signals to the status bar
        self.vp.status.connect(self.statusBar().showMessage)
        self.vp.error.connect(lambda m: self.statusBar().showMessage(f"ERROR: {m}"))
        self.vp.fps.connect(lambda f: self.statusBar().showMessage(f"{f:.1f} FPS"))

        # FPS label under video
        self._fps_label = QLabel("FPS: -", parent=self)
        try:
            if hasattr(self.ui, "verticalLayout_2"):
                self.ui.verticalLayout_2.addWidget(self._fps_label)
        except Exception:
            pass
        self.vp.fps.connect(lambda f: self._fps_label.setText(f"FPS: {f:.1f}"))

        # ---------- Hide legacy inline controls; use toolbar instead ----------
        if hasattr(self.ui, "groupBoxControls"):
            self.ui.groupBoxControls.hide()
        if hasattr(self.ui, "groupBoxMqtt"):
            self.ui.groupBoxMqtt.hide()
        # Hide inline video controls and URL field (toolbar will handle it)
        if hasattr(self.ui, "editVideoUrl"):
            self.ui.editVideoUrl.hide()
        if hasattr(self.ui, "btnOpenVideo"):
            self.ui.btnOpenVideo.hide()
        if hasattr(self.ui, "btnPlay"):
            self.ui.btnPlay.hide()
        if hasattr(self.ui, "btnStopVideo"):
            self.ui.btnStopVideo.hide()

        # ---------- Toolbar ----------
        self._setup_toolbar()

        # If the user enters in the URL field → Play
        if hasattr(self.ui, "editVideoUrl"):
            self.ui.editVideoUrl.returnPressed.connect(self.play_from_url)

        # ---------- Init Labels ----------
        self.ui.lblState.setText("-")
        self.ui.lblImgsz.setText(str(CFG.imgsz))
        self.ui.lblConf.setText(f"{CFG.conf:.2f}")
        self.ui.lblFps.setText("-")
        self.ui.lblMqtt.setText("disconnected")

        # ---------- Window setup ----------
        self.setWindowTitle("Jetson Control + Video (PySide6)")
        self.resize(1150, 750)

    def _setup_toolbar(self):
        tb = QToolBar("Controls", self)
        self.addToolBar(tb)

        # MQTT
        act_connect = QAction("Connect MQTT", self)
        act_connect.setToolTip("Connect to the MQTT broker and topic prefix")
        act_connect.triggered.connect(self._action_connect_mqtt)
        tb.addAction(act_connect)

        tb.addSeparator()

        # Runtime
        act_start = QAction("Start", self)
        act_start.setToolTip("Send start command to Jetson")
        act_start.triggered.connect(lambda: self.send_cmd({"action": "start"}))
        tb.addAction(act_start)

        act_stop = QAction("Stop", self)
        act_stop.setToolTip("Send stop command to Jetson")
        act_stop.triggered.connect(lambda: self.send_cmd({"action": "stop"}))
        tb.addAction(act_stop)

        act_set640 = QAction("Set 640", self)
        act_set640.setToolTip("Set imgsz=640, conf=0.25 on Jetson")
        act_set640.triggered.connect(lambda: self.send_cmd({"action": "set", "param": "conf", "value": {"imgsz": 640, "conf": 0.25}}))
        tb.addAction(act_set640)

        act_set1280 = QAction("Set 1280", self)
        act_set1280.setToolTip("Set imgsz=1280, conf=0.25 on Jetson")
        act_set1280.triggered.connect(lambda: self.send_cmd({"action": "set", "param": "conf", "value": {"imgsz": 1280, "conf": 0.25}}))
        tb.addAction(act_set1280)

        act_set_params = QAction("Set Params…", self)
        act_set_params.setToolTip("Set imgsz and conf via dialog and send to Jetson")
        act_set_params.triggered.connect(self._action_set_params)
        tb.addAction(act_set_params)

        tb.addSeparator()

        # Video
        act_open = QAction("Open File…", self)
        act_open.setToolTip("Open a local video file")
        act_open.triggered.connect(self.open_video)
        tb.addAction(act_open)

        act_play_pause = QAction("Play/Pause", self)
        act_play_pause.setToolTip("Play or pause current source")
        act_play_pause.triggered.connect(self.toggle_play_pause)
        tb.addAction(act_play_pause)

        act_stop_video = QAction("Stop Video", self)
        act_stop_video.setToolTip("Stop playback")
        act_stop_video.triggered.connect(self.stop_video)
        tb.addAction(act_stop_video)

        # RTSP specific actions
        act_play_rtsp = QAction("Play RTSP…", self)
        act_play_rtsp.setToolTip("Enter an RTSP URL and play it")
        act_play_rtsp.triggered.connect(self._action_play_rtsp_dialog)
        tb.addAction(act_play_rtsp)

    def _action_connect_mqtt(self):
        # Defaults come from configs/config.ini (or env var override).
        default_broker = CFG.mqtt_broker
        default_prefix = CFG.mqtt_prefix

        host, ok1 = QInputDialog.getText(self, "MQTT Broker", "Broker host:", text=default_broker)
        if not ok1 or not host.strip():
            return
        topic_prefix, ok2 = QInputDialog.getText(self, "MQTT Topic Prefix", "Topic prefix:", text=default_prefix)
        if not ok2 or not topic_prefix.strip():
            return
        self.mqtt.connectTo(host.strip(), topic_prefix.strip(), CFG.mqtt_port)

    def _action_set_params(self):
        # Prompt imgsz and conf
        imgsz, ok1 = QInputDialog.getInt(self, "Image size", "imgsz:", CFG.imgsz, 64, 4096, 32)
        if not ok1:
            return
        # QInputDialog lacks double precision dialog; use getText then cast for simplicity
        conf_text, ok2 = QInputDialog.getText(self, "Confidence", "conf (0-1):", text=f"{CFG.conf:.2f}")
        if not ok2:
            return
        try:
            conf = float(conf_text)
        except Exception:
            QMessageBox.warning(self, "Invalid", "conf باید یک عدد اعشاری بین 0 و 1 باشد.")
            return
        self.send_cmd({"action": "set", "param": "conf", "value": {"imgsz": int(imgsz), "conf": float(conf)}})
        self.statusBar().showMessage(f"Params sent: imgsz={int(imgsz)} conf={float(conf)}", 3000)

    def _action_play_rtsp_dialog(self):
        default = self._rtsp_url or CFG.rtsp_url
        url, ok = QInputDialog.getText(self, "Play RTSP", "Enter RTSP URL:", text=default)
        if not ok:
            return
        rtsp = url.strip()
        if not rtsp.lower().startswith("rtsp://"):
            QMessageBox.information(self, "RTSP", "URL must start with rtsp://")
            return
        self._rtsp_url = rtsp
        self.vp.setSource(self._rtsp_url)
        self.play_video()

    # ============================
    # MQTT
    # ============================
    # Phase 3: removed dead method `do_connect_mqtt()` — it read fields
    # (editBroker / editPrefix) that are hidden after setupUi and never
    # surfaced to the user. _action_connect_mqtt is the live path.

    def on_mqtt_connected(self):
        self.ui.lblMqtt.setText("connected")
        self.statusBar().showMessage("MQTT connected", 3000)

    def on_mqtt_disconnected(self):
        self.ui.lblMqtt.setText("disconnected")
        self.statusBar().showMessage("MQTT disconnected", 3000)

    def on_mqtt_error(self, msg: str):
        QMessageBox.warning(self, "MQTT Error", msg)

    def send_cmd(self, obj: Dict[str, Any]):
        try:
            self.mqtt.publishCmd(obj)
            self.statusBar().showMessage(f"CMD → {obj}", 2000)
        except Exception as ex:
            QMessageBox.warning(self, "MQTT Error", f"ارسال فرمان ناموفق: {ex}")

    # Phase 3: removed dead method `apply_values()` — it read editImgsz /
    # editConf, which are inside the hidden groupBoxControls. The live
    # path is _action_set_params (toolbar → "Set Params…" dialog).

    def on_status_msg(self, d: Dict[str, Any]):
        self.ui.lblState.setText(str(d.get("state", "-")))
        self.ui.lblImgsz.setText(str(d.get("imgsz", "-")))
        self.ui.lblConf.setText(str(d.get("conf", "-")))
        fps = d.get("fps", None)
        self.ui.lblFps.setText("-" if fps is None else f"{float(fps):.2f}")

    def on_ack(self, d: Dict[str, Any]):
        ok = d.get("ok", False)
        note = d.get("note", "")
        self.statusBar().showMessage(f"ACK ok={ok}  {note}", 5000)

    # New method: Get DET data from Jetson
    def on_dets(self, d: dict):
        objs = d.get("objs", [])
        w, h = d.get("w"), d.get("h")

        # If the VideoPlayer is ready for overlay:
        if hasattr(self.vp, "set_detections"):
            self.vp.set_detections(objs, (w, h) if (w and h) else None)

        # For simple display in the status bar
        n = len(objs)
        self.statusBar().showMessage(f"Detections received: {n} objects", 2000)

    # ============================
    # Video
    # ============================
    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", "", "Video Files (*.mp4 *.avi *.mkv);;All (*.*)"
        )
        if not path:
            return
        if hasattr(self.ui, "editVideoUrl"):
            self.ui.editVideoUrl.setText(path)
        self.vp.setSource(path)
        self.play_video()

    def play_from_url(self):
        src = self._current_url()
        if not src:
            QMessageBox.information(self, "Play", "آدرس ویدیو/RTSP را وارد کنید.")
            return
        self.vp.setSource(src)
        self.play_video()

    def toggle_play_pause(self):
        if not self._playing:
            if not self._has_source():
                src = self._current_url()
                if src:
                    self.vp.setSource(src)
            self.play_video()
        else:
            self.pause_video()

    def play_video(self):
        self.vp.play()
        self._playing = True
        self.ui.btnPlay.setText("Pause")

    def pause_video(self):
        self.vp.pause()
        self._playing = False
        self.ui.btnPlay.setText("Play/Pause")

    def stop_video(self):
        self.vp.stop()
        self._playing = False
        self.ui.btnPlay.setText("Play/Pause")
        self.statusBar().showMessage("Stopped")

    def _current_url(self) -> str:
        le = getattr(self.ui, "editVideoUrl", None)
        return "" if le is None else le.text().strip()

    def _has_source(self) -> bool:
        return bool(self._current_url())

    # ============================
    # Events
    # ============================
    def closeEvent(self, e):
        try:
            try:
                self.vp.stop()
            except Exception:
                pass
            self.mqtt.stop()
        finally:
            super().closeEvent(e)


# =============================
#  Entry point
# =============================
def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
