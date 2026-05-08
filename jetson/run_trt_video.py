#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_trt_video.py
- Decode MP4 with PyAV (بدون نیاز به OpenCV codecs)
- Run Ultralytics YOLO TensorRT per-frame
- Encode MP4 (H.264 yuv420p) خروجی
- چاپ متادیتای دیتکشن در stdout با پیشوند "DET " برای مصرف master_agent/MQTT
- سازگار با Jetson + Python 3.8
"""

from __future__ import annotations

import os
import re
import json
import time
import importlib
import argparse
from pathlib import Path

import av  # PyAV
import numpy as np

# ========= DEFAULTS (قابل override با CLI) =========
ENGINE_PATH = str(Path.home() / "models_y8s_trt" / "best_fp16_640.engine")
INPUT_PATH  = str(Path.home() / "Datasets" / "input.mp4")
OUTPUT_PATH = None         # اگر None بماند، خودکار ساخته می‌شود
IMG_SIZE    = None         # اگر None بماند، از اسم engine حدس می‌زنیم (640/1280)
CONF        = 0.25
DEVICE      = 0
LOG_EVERY   = 200          # هر چند فریم یک لاگِ پیشرفت بده
DET_EVERY   = 5            # هر چند فریم یکبار "DET {...}" چاپ شود (1 = هر فریم)
NO_DET      = False        # اگر True باشد، DET چاپ نمی‌شود
# ===================================================

# کلاس‌ها (بر اساس ترتیبی که قبلاً دادی؛ خالی‌ها را classX گذاشتم)
names_list = [
    "",  # id=0
    "Aplysina aerophoba",
    "Asteroidea",
    "Astropecten spp",
    "Condylactis aurantiaca",
    "Echinaster sepositus",
    "Gobius sp",
    "Holothuria tubulosa",
    "Keratosa -cfr Sarcotragus-",
    "Phaeophyceae -cfr Cystoseira-",
    "",  # id=10
    "Sarcotragus spinosulus",
    "Serranus scriba",
    "Sphaerechinus granularis",
]
names_dict = {i: (n if n else f"class{i}") for i, n in enumerate(names_list)}


def guess_imgsz_from_engine(path: str, fallback: int = 640) -> int:
    m = re.search(r"(?:^|[_-])(640|1280)(?:[^0-9]|$)", Path(path).name)
    return int(m.group(1)) if m else fallback


def auto_output_path(input_path: str, imgsz: int, engine_path: str) -> str:
    runs = Path.home() / "runs_trt"
    runs.mkdir(parents=True, exist_ok=True)
    stem = Path(input_path).stem
    eng  = Path(engine_path).stem
    # خروجی: <input>_pred_<imgsz>__<engine-stem>.mp4  (برای تشخیص سریع)
    return str(runs / f"{stem}_pred_{imgsz}__{eng}.mp4")


# --- قبل از import YOLO، AutoBackend را پچ می‌کنیم
ul_nn = importlib.import_module("ultralytics.nn.autobackend")

# 1) گرم‌کردن را بی‌اثر کن (برای پرهیز از خطا و سرعت بیشتر)
try:
    ul_nn.AutoBackend.warmup = lambda self, *a, **k: None
except Exception:
    pass

# 2) forward را امن کن تا task/names/nc اگر نبود، تنظیم شوند
try:
    _orig_forward = ul_nn.AutoBackend.forward

    def _forward_safe(self, im, *args, **kwargs):
        # task
        if not hasattr(self, "task") or self.task is None:
            try:
                setattr(self, "task", "detect")
            except Exception:
                pass
        # names
        need_names = False
        try:
            need_names = (not hasattr(self, "names")) or (not self.names) or \
                         (isinstance(self.names, int) and self.names == 999)
        except Exception:
            need_names = True
        if need_names:
            try:
                setattr(self, "names", names_dict)
            except Exception:
                pass
        # nc
        if not hasattr(self, "nc") or not isinstance(getattr(self, "nc", None), int):
            try:
                setattr(self, "nc", len(names_dict))
            except Exception:
                pass
        # call original forward
        return _orig_forward(self, im, *args, **kwargs)

    ul_nn.AutoBackend.forward = _forward_safe
except Exception:
    pass

from ultralytics import YOLO  # بعد از پچ


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", type=str, help="Path to .engine (TensorRT)")
    ap.add_argument("--input",  type=str, help="Input video path (e.g., .mp4)")
    ap.add_argument("--output", type=str, help="Output mp4 path (auto if omitted)")
    ap.add_argument("--imgsz",  type=int, help="Inference size (640 or 1280). If omitted, guessed from engine name.")
    ap.add_argument("--conf",   type=float, help=f"Confidence threshold (default {CONF})")
    ap.add_argument("--device", type=int, help=f"CUDA device index (default {DEVICE})")
    ap.add_argument("--every",  type=int, help=f"Progress log interval (frames, default {LOG_EVERY})")
    ap.add_argument("--det-every", type=int, default=DET_EVERY, help="Print DET JSON every N frames (1=each frame)")
    ap.add_argument("--no-det", action="store_true", help="Disable DET printing")
    return ap.parse_args()


def results_to_boxes(result, conf_thr: float = 0.0):
    """
    از نتیجه‌ی Ultralytics، لیست جعبه‌ها را برمی‌گرداند:
    [(x1,y1,x2,y2,label,score), ...]  (پیکسل/float)
    """
    boxes = []
    try:
        rb = result.boxes
        if rb is None:
            return boxes
        xyxy = rb.xyxy.detach().cpu().numpy()       # (N,4)
        conf = rb.conf.detach().cpu().numpy()       # (N,)
        cls  = rb.cls.detach().cpu().numpy().astype(np.int32)  # (N,)
        for i in range(xyxy.shape[0]):
            if conf[i] < conf_thr:
                continue
            x1, y1, x2, y2 = map(float, xyxy[i].tolist())
            label = names_dict.get(int(cls[i]), f"class{int(cls[i])}")
            boxes.append((x1, y1, x2, y2, label, float(conf[i])))
    except Exception:
        pass
    return boxes


def print_det(frame_w: int, frame_h: int, boxes, ts_ms: int):
    """
    چاپ خط DET برای مصرف master_agent → MQTT
    """
    payload = {
        "w": int(frame_w),
        "h": int(frame_h),
        "ts": int(ts_ms),
        "objs": [
            {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
             "cls": str(label), "conf": float(score)}
            for (x1, y1, x2, y2, label, score) in boxes
        ]
    }
    # خیلی مهم: flush=True
    print("DET " + json.dumps(payload), flush=True)


def main():
    global ENGINE_PATH, INPUT_PATH, OUTPUT_PATH, IMG_SIZE, CONF, DEVICE, LOG_EVERY, DET_EVERY, NO_DET

    args = parse_args()
    if args.engine: ENGINE_PATH = args.engine
    if args.input:  INPUT_PATH  = args.input
    if args.output: OUTPUT_PATH = args.output
    if args.imgsz is not None: IMG_SIZE = args.imgsz
    if args.conf  is not None: CONF     = args.conf
    if args.device is not None: DEVICE  = args.device
    if args.every  is not None: LOG_EVERY = args.every
    if args.det_every is not None: DET_EVERY = max(1, int(args.det_every))
    if args.no_det: NO_DET = True

    # اگر imgsz داده نشده، از اسم engine حدس بزن (640/1280). اگر نشد، 640.
    if IMG_SIZE is None:
        IMG_SIZE = guess_imgsz_from_engine(ENGINE_PATH, fallback=640)

    # اگر output داده نشده، خودکار بساز
    if OUTPUT_PATH is None:
        OUTPUT_PATH = auto_output_path(INPUT_PATH, IMG_SIZE, ENGINE_PATH)

    # مطمئن شو مسیر خروجی وجود داره
    out_dir = Path(OUTPUT_PATH).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[cfg] engine={ENGINE_PATH}")
    print(f"[cfg] input={INPUT_PATH}")
    print(f"[cfg] output={OUTPUT_PATH}")
    print(f"[cfg] imgsz={IMG_SIZE}  conf={CONF}  device={DEVICE}")

    # مدل TRT را لود کن
    model = YOLO(ENGINE_PATH)

    # ویدیو ورودی
    in_c = av.open(INPUT_PATH)
    vst = in_c.streams.video[0]
    vst.thread_type = "AUTO"
    try:
        # تعداد نخ‌های دیکودر (۲ معمولاً خوبه؛ اگر CPU آزاد بود ۳ هم تست کن)
        vst.codec_context.thread_count = 2
    except Exception:
        pass

    fps = float(vst.average_rate) if vst.average_rate else 30.0
    w   = int(vst.codec_context.width)
    h   = int(vst.codec_context.height)

    # ---- تنظیمات خروجی H.264: محدود کردن به 1080p + even-size + تنظیم preset/crf
    out_w, out_h = w, h
    if out_h > 1080:
        out_h = 1080
        out_w = int(round(out_h * (w / h)))
    # even (yuv420p نیاز دارد)
    out_w -= out_w % 2
    out_h -= out_h % 2

    out_c = av.open(OUTPUT_PATH, mode="w")
    out_st = out_c.add_stream("libx264", rate=fps)
    out_st.pix_fmt = "yuv420p"
    out_st.width   = out_w
    out_st.height  = out_h
    # کاهش تأخیر و مصرف CPU (کیفیت را با crf تنظیم کن: 20–22 بهتر، 24–28 سریع‌تر)
    out_st.options = {
        "preset": "ultrafast",
        "tune": "zerolatency",
        "crf": "23",
    }

    frame_idx = 0
    t0 = time.time()

    try:
        for f in in_c.decode(vst):
            frame_idx += 1

            img_bgr = f.to_ndarray(format="bgr24")

            # اینفرانس TRT (warmup از کار افتاده و forward امن شده)
            res = model(img_bgr, imgsz=IMG_SIZE, device=DEVICE, conf=CONF, verbose=False)
            r = res[0]

            # مطمئن شو names داخل Result هم ست است (برای plot)
            try:
                r.names = names_dict
            except Exception:
                pass

            # استخراج جعبه‌ها برای DET
            boxes = results_to_boxes(r, conf_thr=CONF)

            # چاپ DET هر N فریم (برای کاهش ترافیک)
            if (not NO_DET) and (frame_idx % DET_EVERY == 0):
                ts_ms = int(time.time() * 1000)
                print_det(w, h, boxes, ts_ms)

            # رسم روی فریم و آماده‌سازی خروجی
            annotated = r.plot()  # BGR ndarray

            # ساخت فریم خروجی و اطمینان از ابعاد صحیح برای انکودر
            out_frame = av.VideoFrame.from_ndarray(annotated, format="bgr24")
            if out_frame.width != out_w or out_frame.height != out_h:
                out_frame = out_frame.reformat(width=out_w, height=out_h, format="bgr24")

            for pkt in out_st.encode(out_frame):
                out_c.mux(pkt)

            # لاگ پیشرفت + avg_fps (برای پارسر agent)
            if LOG_EVERY > 0 and frame_idx % LOG_EVERY == 0:
                dt = time.time() - t0
                avg_fps = frame_idx / max(dt, 1e-6)
                print("[info] frames=%d elapsed=%.1fs avg_fps=%.1f" %
                      (frame_idx, dt, avg_fps), flush=True)
                # یک خطِ سازگار با پارسرهای ساده:
                print(f"avg_fps={avg_fps:.2f}", flush=True)

        # flush
        for pkt in out_st.encode():
            out_c.mux(pkt)

    finally:
        out_c.close()
        in_c.close()

    dt = time.time() - t0
    avg_fps = frame_idx / max(dt, 1e-6)
    print("\nDONE -> %s" % OUTPUT_PATH)
    print("Frames: %d | Elapsed: %.2fs | Avg FPS: %.2f" %
          (frame_idx, dt, avg_fps), flush=True)
    # خط نهایی برای سازگاری با agent
    print(f"avg_fps={avg_fps:.2f}", flush=True)


if __name__ == "__main__":
    main()
