# app/mqtt_bridge.py
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, QThread
import json
import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion


class MqttWorker(QObject):
    # ---- for UI Signals ----
    connected   = Signal()
    disconnected = Signal()
    statusMsg   = Signal(dict)  # payloadِ STATUS
    ackMsg      = Signal(dict)  # payloadِ ACK
    detections  = Signal(dict)  # NEW: payloadِ DETS (لیست آبجکت‌ها و اندازه‌ی فریم)
    error       = Signal(str)

    def __init__(self):
        super().__init__()
        self._client: mqtt.Client | None = None
        self._prefix = "projectA/jetson-01"
        self._broker = "192.168.50.1"
        self._port   = 1883

    # ------------- Connect -------------
    @Slot(str, str, int)
    def connectTo(self, broker: str, prefix: str, port: int = 1883):
        self._broker = (broker or "192.168.50.1").strip()
        self._prefix = (prefix or "projectA/jetson-01").strip().rstrip("/")
        self._port   = int(port) if port else 1883

        try:
            # Callback API v2 (با props)
            self._client = mqtt.Client(CallbackAPIVersion.VERSION2)
            self._client.on_connect    = self._on_connect
            self._client.on_message    = self._on_message
            self._client.on_disconnect = self._on_disconnect

            # LWT → status offline
            lwt = {"state": "offline"}
            self._client.will_set(f"{self._prefix}/master/status",
                                  json.dumps(lwt), qos=0, retain=True)

            self._client.connect(self._broker, self._port, keepalive=30)
            self._client.loop_start()
        except Exception as e:
            self.error.emit(f"MQTT connect error: {e}")

    # ------------- MQTT Callbacks -------------
    def _on_connect(self, c: mqtt.Client, u, flags, rc, props=None):
        try:
            # سه تاپیک اصلی
            c.subscribe(f"{self._prefix}/master/status", qos=0)
            c.subscribe(f"{self._prefix}/master/ack",    qos=0)
            c.subscribe(f"{self._prefix}/master/dets",   qos=0)  # NEW
            self.connected.emit()
        except Exception as e:
            self.error.emit(f"on_connect subscribe error: {e}")

    def _on_disconnect(self, c: mqtt.Client, u, rc, props=None):
        self.disconnected.emit()

    def _on_message(self, c: mqtt.Client, u, msg):
        # parse safe JSON
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception:
            payload = {}

        t = msg.topic or ""
        if t.endswith("/master/status"):
            self.statusMsg.emit(payload)
        elif t.endswith("/master/ack"):
            self.ackMsg.emit(payload)
        elif t.endswith("/master/dets"):
            # waiting : {"w":..., "h":..., "objs":[{x1,y1,x2,y2,cls,conf},...], "ts":...}
            self.detections.emit(payload)

    # ------------- Publish Commands -------------
    @Slot(dict)
    def publishCmd(self, obj: dict):
        if not self._client:
            self.error.emit("MQTT not connected")
            return
        try:
            self._client.publish(f"{self._prefix}/master/cmd",
                                 json.dumps(obj), qos=0, retain=False)
        except Exception as e:
            self.error.emit(f"publish error: {e}")

    # ------------- Stop -------------
    @Slot()
    def stop(self):
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            self._client = None


class MqttBridge(QObject):
    """
    اجرای MqttWorker داخل QThread و اکسپوز سیگنال‌ها برای MainWindow
    """
    connected   = Signal()
    disconnected = Signal()
    statusMsg   = Signal(dict)
    ackMsg      = Signal(dict)
    detections  = Signal(dict)  # NEW
    error       = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread(parent)
        self._worker = MqttWorker()
        self._worker.moveToThread(self._thread)

        # پل سیگنال‌ها
        self._worker.connected.connect(self.connected)
        self._worker.disconnected.connect(self.disconnected)
        self._worker.statusMsg.connect(self.statusMsg)
        self._worker.ackMsg.connect(self.ackMsg)
        self._worker.detections.connect(self.detections)  # NEW
        self._worker.error.connect(self.error)

        self._thread.start()

    # همان API ساده‌ای که MainWindow استفاده می‌کند
    def connectTo(self, broker: str, prefix: str, port: int = 1883):
        self._worker.connectTo(broker, prefix, port)

    def publishCmd(self, obj: dict):
        self._worker.publishCmd(obj)

    def stop(self):
        self._worker.stop()
        self._thread.quit()
        self._thread.wait()
