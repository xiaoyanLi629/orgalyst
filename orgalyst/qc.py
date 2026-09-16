"""质量控制与不确定性（P1）：
- 图像级：focus_score（拉普拉斯方差，越低越可能失焦；按图像归一化后与同批比较）、illumination_cv（大尺度背景的变异系数，越高光照越不均）、
          saturation_frac（饱和像素比例）。
- 实例级：tta_agreement —— 对同一张图做 K 次翻转/旋转变换后重新分割，把结果变换回原坐标，与原分割逐实例匹配（IoU≥0.5 计一次命中），
          agreement = 命中次数 / K；越低表示该实例对模型越不稳定，报告里标为低可信。
"""
from __future__ import annotations
import numpy as np
import pandas as pd

def image_qc(gray: np.ndarray) -> dict:
    from scipy.ndimage import laplace, gaussian_filter
    g = gray.astype(np.float32)
    lap = laplace(g); focus = float(lap.var() / max(g.var(), 1e-6))     # 归一化拉普拉斯方差，消除对比度影响
    bg = gaussian_filter(g, sigma=max(g.shape) / 16)                        # 大尺度背景
    illum_cv = float(bg.std() / max(bg.mean(), 1e-6))
    sat = float(((gray <= 0) | (gray >= 255)).mean())
    return dict(focus_score=focus, illumination_cv=illum_cv, saturation_frac=sat)

# 8 个二面体变换（翻转/旋转）及其逆
_TFS = [
    (lambda a: a,                     lambda a: a),
    (lambda a: a[:, ::-1],            lambda a: a[:, ::-1]),
    (lambda a: a[::-1, :],            lambda a: a[::-1, :]),
    (lambda a: np.rot90(a, 1),        lambda a: np.rot90(a, -1)),
    (lambda a: np.rot90(a, 2),        lambda a: np.rot90(a, -2)),
    (lambda a: np.rot90(a, 3),        lambda a: np.rot90(a, -3)),
    (lambda a: np.rot90(a, 1)[:, ::-1], lambda a: np.rot90(a[:, ::-1], -1)),
    (lambda a: np.rot90(a, 1)[::-1, :], lambda a: np.rot90(a[::-1, :], -1)),
]

def _match_iou(ref: np.ndarray, other: np.ndarray, thr: float = 0.5) -> np.ndarray:
    """对 ref 的每个实例（1..N），在 other 中找重叠最大的实例，返回其 IoU 是否≥thr 的布尔数组。"""
    n = int(ref.max())
    if n == 0: return np.zeros(0, bool)
    m = int(other.max())
    hits = np.zeros(n, bool)
    if m == 0: return hits
    # 联合直方图：ref×other 的像素重叠数
    pair = ref.astype(np.int64) * (m + 1) + other.astype(np.int64)
    counts = np.bincount(pair.ravel(), minlength=(n + 1) * (m + 1)).reshape(n + 1, m + 1)
    area_r = counts.sum(1); area_o = counts.sum(0)
    for i in range(1, n + 1):
        j = int(np.argmax(counts[i, 1:])) + 1; inter = counts[i, j]
        if inter == 0: continue
        iou = inter / (area_r[i] + area_o[j] - inter)
        hits[i - 1] = iou >= thr
    return hits

def tta_agreement(segmenter, img: np.ndarray, base_masks: np.ndarray, k: int = 4, **eval_kw) -> np.ndarray:
    """返回 base_masks 每个实例的 agreement ∈ [0,1]（K 次变换中被稳定找到的比例）。"""
    from .segment import to_gray
    gray = to_gray(img); n = int(base_masks.max())
    if n == 0: return np.zeros(0)
    hits = np.zeros(n)
    for fwd, inv in _TFS[1:1 + k]:
        m_t, _ = segmenter.run(np.ascontiguousarray(fwd(gray)), **eval_kw)
        m_back = np.ascontiguousarray(inv(m_t))
        hits += _match_iou(base_masks, m_back)
    return hits / k

def flag_low_confidence(features: pd.DataFrame, agreement_thr: float = 0.5) -> pd.DataFrame:
    if "tta_agreement" in features:
        features["low_confidence"] = features["tta_agreement"] < agreement_thr
    return features
