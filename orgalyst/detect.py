"""检测计数：用三器官联合的 YOLO11m 模型（E2 结论：联合模型 ≥ 单器官模型）数一张明场图里有几个类器官。
置信度阈值来自 config.DET_CONF（在各器官 val 集上标定，见 results/e2_conf_calibration.json），不是 ultralytics 默认的 0.25。"""
from __future__ import annotations
import os
import numpy as np
from .config import DET_MODELS, DET_CONF, DET_IMGSZ
from .segment import _md5

class Detector:
    def __init__(self, organ: str = "generic", conf: float | None = None, model: str = "all", imgsz: int = DET_IMGSZ, gpu: bool = True):
        from ultralytics import YOLO
        os.environ.setdefault("YOLO_OFFLINE", "1")
        path = DET_MODELS[model]
        if not os.path.exists(path): raise FileNotFoundError(f"detection weights not found: {path}")
        self.model = YOLO(path); self.model_name = model
        self.model_id = f"yolo11m-{model}:{_md5(path)[:12]}"
        self.organ = organ if organ in DET_CONF else "generic"
        self.conf = float(conf) if conf is not None else DET_CONF[self.organ]
        self.imgsz = imgsz; self.device = 0 if gpu else "cpu"

    def run(self, img: np.ndarray) -> dict:
        """返回 n（计数）、boxes（x1,y1,x2,y2,conf，按置信度降序）与所用阈值。"""
        if img.ndim == 2: img = np.stack([img] * 3, axis=-1)
        r = self.model.predict(np.ascontiguousarray(img[..., :3]), imgsz=self.imgsz, conf=self.conf, verbose=False, max_det=2000, device=self.device)[0]
        b = r.boxes
        boxes = np.concatenate([b.xyxy.cpu().numpy(), b.conf.cpu().numpy()[:, None]], axis=1) if len(b) else np.zeros((0, 5))
        boxes = boxes[np.argsort(-boxes[:, 4])] if len(boxes) else boxes
        return dict(n=int(len(boxes)), boxes=boxes, conf=self.conf)

def draw_boxes(img: np.ndarray, boxes: np.ndarray, color=(255, 170, 0), width: int = 3):
    from PIL import Image, ImageDraw
    base = img if img.ndim == 3 else np.stack([img] * 3, axis=-1)
    im = Image.fromarray(base.astype(np.uint8)); d = ImageDraw.Draw(im)
    for x1, y1, x2, y2, c in boxes: d.rectangle([x1, y1, x2, y2], outline=color, width=width)
    return im
