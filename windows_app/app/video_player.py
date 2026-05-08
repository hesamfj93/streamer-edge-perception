# app/video_player.py
from __future__ import annotations
import os
import time
import cv2
from typing import Optional, List, Dict, Tuple

from PySide6.QtCore import QObject, QThread, Signal, Qt, QSize, QEvent, QRect, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget


# ============================================================
# Worker: Reading RTSP or OpenCV/FFmpeg
# ============================================================
class _CvWorker(QThread):
    frame = Signal(QImage)
    error = Signal(str)
    status = Signal(str)
    fps = Signal(float)

    def __init__(self, url: str, fps_cap: float = 0.0, parent=None):
        super().__init__(parent)
        self.url = url
        self._running = True
        self._paused = False
        self._fps_cap = fps_cap

    def _open_capture_rtsp(self, url: str, transport: str = "tcp") -> cv2.VideoCapture:
        opts = [
            f"rtsp_transport;{transport}",
            "buffer_size;2097152",
            "stimeout;7000000",
            "reorder_queue_size;0",
            "fflags;nobuffer",
            "flags;low_delay",
            "max_delay;0",
        ]
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "|".join(opts)
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)

    def set_paused(self, p: bool):
        self._paused = p

    def stop(self):
        self._running = False

    def run(self):
        cap = self._open_capture_rtsp(self.url, "tcp")
        if not cap.isOpened():
            self.error.emit(f"Cannot open RTSP via TCP: {self.url}")
            return
        self.status.emit("RTSP opened via TCP")

        miss_count = 0
        last_tick = time.perf_counter()
        frame_counter = 0

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        delay = 1.0 / fps if fps > 0 else 0.04

        while self._running:
            if self._paused:
                time.sleep(0.03)
                continue

            ok, frame = cap.read()
            if not ok:
                miss_count += 1
                time.sleep(0.05)
                if miss_count >= 50:
                    cap.release()
                    cap = self._open_capture_rtsp(self.url, "tcp")
                    miss_count = 0
                continue

            miss_count = 0
            frame_counter += 1

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            self.frame.emit(qimg)

            if delay > 0:
                time.sleep(delay)

            now = time.perf_counter()
            if now - last_tick >= 1.0:
                self.fps.emit(frame_counter / (now - last_tick))
                last_tick = now
                frame_counter = 0

        cap.release()
        self.status.emit("RTSP stopped")


# ============================================================
# VideoPlayer: انتخاب بین OpenCV (RTSP) و QMediaPlayer (فایل)
# ============================================================
class VideoPlayer(QObject):
    status = Signal(str)
    error = Signal(str)
    fps = Signal(float)

    def __init__(self, video_widget: QVideoWidget | QWidget, parent: QObject | None = None):
        super().__init__(parent)
        self._mode = "qt"  # 'qt' or 'cv'
        self._url = ""
        self._cv_worker: Optional[_CvWorker] = None

        self._player = QMediaPlayer(parent=self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)

        self._container = video_widget
        self._host: QWidget = self._container.parentWidget() or self._container

        # QLabel برای نمایش فریم RTSP و کشیدن دیتکشن‌ها
        self._label = QLabel(parent=self._host)
        self._label.setStyleSheet("background:black;")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.hide()

        if isinstance(self._container, QVideoWidget):
            self._player.setVideoOutput(self._container)

        if self._host:
            self._host.installEventFilter(self)
        if self._container and self._container is not self._host:
            self._container.installEventFilter(self)

        self._player.errorOccurred.connect(lambda *_: self._on_media_error())

        #  for overlay Detections
        self._detections: List[Dict] = []
        self._frame_size: Optional[Tuple[int, int]] = None
        self._last_frame: Optional[QImage] = None

    # -----------------------------------
    # Event Filter
    # -----------------------------------
    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Resize, QEvent.Show, QEvent.Move):
            self._sync_label_geometry()
        return super().eventFilter(obj, event)

    def _sync_label_geometry(self):
        rect: QRect = self._container.geometry()
        self._label.setGeometry(rect)
        self._label.raise_()

    def _switch_mode(self, mode: str):
        if mode != self._mode:
            self.stop()
            self._mode = mode

    # -----------------------------------
    # API
    # -----------------------------------
    def setSource(self, url: str):
        from PySide6.QtCore import QUrl
        self._url = (url or "").strip()

        if self._url.lower().startswith("rtsp://"):
            self._switch_mode("cv")
            if isinstance(self._container, QVideoWidget):
                self._container.hide()
            self._sync_label_geometry()
            self._label.show()
            self.status.emit("Source set: RTSP (OpenCV backend)")
        else:
            self._switch_mode("qt")
            self._label.hide()
            if isinstance(self._container, QVideoWidget):
                self._container.show()
                self._player.setVideoOutput(self._container)
            self._player.setSource(QUrl.fromUserInput(self._url))
            self.status.emit("Source set: Local file (Qt backend)")

    def play(self):
        if not self._url:
            self.status.emit("No source set.")
            return

        if self._mode == "qt":
            self._player.play()
            self.status.emit("Playing (Qt)")
        else:
            if self._cv_worker is None:
                self._cv_worker = _CvWorker(self._url)
                self._cv_worker.frame.connect(self._on_cv_frame)
                self._cv_worker.error.connect(self._on_cv_error)
                self._cv_worker.status.connect(self.status.emit)
                self._cv_worker.fps.connect(self.fps.emit)
                self._cv_worker.start()
            else:
                self._cv_worker.set_paused(False)
            self.status.emit("Playing (OpenCV/RTSP)")

    def pause(self):
        if self._mode == "qt":
            self._player.pause()
            self.status.emit("Paused (Qt)")
        else:
            if self._cv_worker:
                self._cv_worker.set_paused(True)
            self.status.emit("Paused (OpenCV)")

    def stop(self):
        if self._mode == "qt":
            self._player.stop()
            self.status.emit("Stopped (Qt)")
        else:
            if self._cv_worker:
                self._cv_worker.stop()
                self._cv_worker.wait(2000)
                self._cv_worker = None
            self._label.clear()
            self._label.hide()
            if isinstance(self._container, QVideoWidget):
                self._container.show()
            self.status.emit("Stopped (OpenCV)")

    # -----------------------------------
    # Overlay مدیریت دیتکشن‌ها
    # -----------------------------------
    def set_detections(self, objs: List[Dict], frame_size: Optional[Tuple[int, int]] = None):
        """دریافت لیست دیتکشن‌ها از MQTT (cls, conf, bbox)."""
        self._detections = objs or []
        self._frame_size = frame_size

    # -----------------------------------
    # نمایش فریم
    # -----------------------------------
    def _on_cv_frame(self, qimg: QImage):
        self._last_frame = qimg
        pix = QPixmap.fromImage(qimg).scaled(
            self._label.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

        # اگر دیتکشن داریم → روی تصویر بکش
        if self._detections and self._frame_size:
            painter = QPainter(pix)
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            fw, fh = self._frame_size
            pw, ph = pix.width(), pix.height()

            sx, sy = pw / fw, ph / fh
            for o in self._detections:
                x1 = int(o.get("x1", 0) * sx)
                y1 = int(o.get("y1", 0) * sy)
                x2 = int(o.get("x2", 0) * sx)
                y2 = int(o.get("y2", 0) * sy)
                cls = o.get("cls", "?")
                conf = o.get("conf", 0)
                painter.drawRect(x1, y1, x2 - x1, y2 - y1)
                painter.drawText(QPoint(x1 + 4, y1 + 16), f"{cls} {conf:.2f}")
            painter.end()

        self._label.setPixmap(pix)

    # -----------------------------------
    # Error Handling
    # -----------------------------------
    def _on_cv_error(self, msg: str):
        self.error.emit(msg)
        self.status.emit(msg)

    def _on_media_error(self):
        try:
            err_str = self._player.errorString()
        except Exception:
            err_str = "QMediaPlayer error"
        self.error.emit(err_str)
        self.status.emit(err_str)