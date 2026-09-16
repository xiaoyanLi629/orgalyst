"""分割：按器官加载专用 Cellpose 权重，输出实例掩码。"""
from __future__ import annotations
import hashlib, os
import numpy as np
from .config import SEG_MODELS, CELLPOSE_MODELS_DIR

def _md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

def to_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3: img = img[..., :3].mean(axis=2)
    if img.dtype != np.uint8:
        img = img.astype(np.float32); img = 255 * (img - img.min()) / max(1e-6, img.max() - img.min())
    return img.astype(np.uint8)

class Segmenter:
    """organ 取 config.SEG_MODELS 的键；未知器官用 'generic'（零样本 cyto3）。"""
    def __init__(self, organ: str = "generic", diam_mode: str | None = None, gpu: bool = True, pretrained_path: str | None = None):
        """pretrained_path 给出时直接用该权重（实验用，如联合/留一模型），否则按 organ 查注册表。"""
        os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", CELLPOSE_MODELS_DIR)
        from cellpose import models
        import torch
        spec = dict(SEG_MODELS.get(organ) or SEG_MODELS["generic"])
        if pretrained_path: spec["path"] = pretrained_path
        self.organ = organ if organ in SEG_MODELS else "generic"
        self.diam_mode = diam_mode or spec["diam_mode"]
        use_gpu = gpu and torch.cuda.is_available()
        if os.path.exists(spec["path"]):
            self.model = models.CellposeModel(gpu=use_gpu, pretrained_model=spec["path"])
            self.model_id = f"{os.path.basename(spec['path'])}:{_md5(spec['path'])[:12]}"
            self.model_diam = float(self.model.net.diam_labels.item())
        else:
            self.model = models.Cellpose(gpu=use_gpu, model_type=spec["path"])
            self.model_id = f"cellpose:{spec['path']}"; self.model_diam = None
        self.sizer = models.Cellpose(gpu=use_gpu, model_type="cyto3").sz if self.diam_mode == "sizemodel" else None

    def diameter_for(self, gray: np.ndarray) -> float | None:
        if self.diam_mode == "sizemodel": return float(self.sizer.eval(gray, channels=[0, 0])[0])
        if self.diam_mode in ("model", "refine"): return self.model_diam
        return None  # auto（仅内置模型带尺寸模型时有效）

    def run(self, img: np.ndarray, flow_threshold=0.4, cellprob_threshold=0.0) -> tuple[np.ndarray, dict]:
        gray = to_gray(img)
        d = self.model_diam if self.diam_mode == "refine" else self.diameter_for(gray)
        out = self.model.eval(gray, diameter=d, channels=[0, 0], flow_threshold=flow_threshold, cellprob_threshold=cellprob_threshold)
        masks = out[0].astype(np.uint16); d_used = d; refined = False
        if self.diam_mode == "refine":
            # 两遍推理：用第一遍分出的目标中位等效直径再分一次（限制在模型直径的 0.25–4 倍内），对尺寸两端的目标更稳
            ids, cnts = np.unique(masks, return_counts=True); cnts = cnts[ids != 0]
            if len(cnts):
                d2 = float(np.clip(np.median(2 * np.sqrt(cnts / np.pi)), 0.25 * (d or 30), 4 * (d or 30)))
                if d and abs(d2 - d) / d > 0.15:
                    out2 = self.model.eval(gray, diameter=d2, channels=[0, 0], flow_threshold=flow_threshold, cellprob_threshold=cellprob_threshold)
                    if out2[0].max() > 0: masks = out2[0].astype(np.uint16); d_used = d2; refined = True
            else:
                # 第一遍什么都没找到：用更小/更大的直径各试一次
                for d2 in (0.5 * (d or 30), 2.0 * (d or 30)):
                    out2 = self.model.eval(gray, diameter=d2, channels=[0, 0], flow_threshold=flow_threshold, cellprob_threshold=cellprob_threshold)
                    if out2[0].max() > 0: masks = out2[0].astype(np.uint16); d_used = d2; refined = True; break
        return masks, dict(model=self.model_id, organ=self.organ, diam_mode=self.diam_mode, diameter_px=d_used, refined=refined,
                           flow_threshold=flow_threshold, cellprob_threshold=cellprob_threshold, n_instances=int(masks.max()))
