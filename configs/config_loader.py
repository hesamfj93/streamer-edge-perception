"""
config_loader.py
================
Shared, lightweight configuration loader for both the Jetson agent and
the Windows GUI. Python 3.8+ compatible. Standard-library only
(uses configparser; no TOML dependency).

Resolution order for each key:
    1. Environment variable (for one-off overrides / ops use)
    2. configs/config.ini       (user's local copy, gitignored variant
                                 lives at configs/config.local.ini)
    3. configs/config.example.ini (committed defaults)
    4. Hardcoded fallback (matches pre-refactor behavior)

Usage:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "configs"))
    from config_loader import load_config

    cfg = load_config()
    broker = cfg.mqtt_broker
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).resolve().parent


def _resolve_config_path() -> Optional[Path]:
    """Pick the active config file, in priority order."""
    candidates = [
        CONFIG_DIR / "config.local.ini",   # gitignored override
        CONFIG_DIR / "config.ini",         # main file
        CONFIG_DIR / "config.example.ini", # committed template
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


class Config:
    """Typed accessors over a configparser.ConfigParser instance."""

    def __init__(self, parser: configparser.ConfigParser, source: Optional[Path]):
        self._p = parser
        self.source = source  # which file we actually loaded (None = no file)

    # ---- internal ----
    def _get(
        self,
        section: str,
        key: str,
        env: Optional[str] = None,
        fallback: str = "",
    ) -> str:
        if env:
            v = os.environ.get(env)
            if v is not None and v != "":
                return v
        if self._p.has_option(section, key):
            v = self._p.get(section, key).strip()
            if v != "":
                return v
        return fallback

    # ---- MQTT ----
    @property
    def mqtt_broker(self) -> str:
        return self._get("mqtt", "broker", "MQTT_BROKER", "192.168.50.1")

    @property
    def mqtt_port(self) -> int:
        return int(self._get("mqtt", "port", "MQTT_PORT", "1883"))

    @property
    def mqtt_prefix(self) -> str:
        return self._get("mqtt", "prefix", "MQTT_PREFIX", "projectA/jetson-01").rstrip("/")

    @property
    def mqtt_client_id(self) -> str:
        return self._get("mqtt", "client_id", "MQTT_CLIENT_ID", "jetson-01-master")

    # ---- RTSP ----
    @property
    def rtsp_url(self) -> str:
        return self._get("rtsp", "url", "RTSP_URL", "rtsp://192.168.50.1:8554/jetson")

    # ---- Inference (Jetson) ----
    @property
    def engine_dir(self) -> Path:
        return Path(self._get(
            "inference", "engine_dir", "ENGINE_DIR",
            str(Path.home() / "models_y8s_trt"),
        ))

    @property
    def input_video(self) -> Path:
        return Path(self._get(
            "inference", "input_video", "INPUT_VIDEO",
            str(Path.home() / "Datasets" / "input.mp4"),
        ))

    @property
    def imgsz(self) -> int:
        return int(self._get("inference", "imgsz", "IMGSZ", "640"))

    @property
    def conf(self) -> float:
        return float(self._get("inference", "conf", "CONF", "0.25"))

    @property
    def script_path(self) -> str:
        """Empty string means 'auto-detect next to the agent'."""
        return self._get("inference", "script_path", "SCRIPT_PATH", "")


def load_config() -> Config:
    parser = configparser.ConfigParser()
    path = _resolve_config_path()
    if path is not None:
        parser.read(path, encoding="utf-8")
    return Config(parser, path)


# CLI helper for shell scripts: dump key as plain text.
# Usage: python3 config_loader.py mqtt_broker
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("usage: python3 config_loader.py <key>", file=sys.stderr)
        print("keys: mqtt_broker, mqtt_port, mqtt_prefix, mqtt_client_id, "
              "rtsp_url, engine_dir, input_video, imgsz, conf, script_path",
              file=sys.stderr)
        sys.exit(2)
    cfg = load_config()
    val = getattr(cfg, sys.argv[1], None)
    if val is None:
        print(f"unknown key: {sys.argv[1]}", file=sys.stderr)
        sys.exit(2)
    print(val)
