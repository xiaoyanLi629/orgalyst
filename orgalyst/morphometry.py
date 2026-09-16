"""形态学测量：实例掩码 → 每个类器官一行的特征表。"""
from __future__ import annotations
import numpy as np
import pandas as pd
from skimage.measure import regionprops_table, perimeter as _perimeter

FEATURES = ["label", "area", "equivalent_diameter_area", "perimeter", "major_axis_length", "minor_axis_length",
            "eccentricity", "solidity", "extent", "orientation", "centroid", "bbox", "intensity_mean", "intensity_std"]

def measure(masks: np.ndarray, gray: np.ndarray | None = None, pixel_size_um: float | None = None, image_id: str = "") -> pd.DataFrame:
    """返回 DataFrame：像素单位的几何量 + （若给定像素尺寸）微米单位的面积/直径/周长；含贴边标记与圆度。"""
    if masks.max() == 0:
        return pd.DataFrame(columns=["image_id", "label"])
    props = regionprops_table(masks.astype(np.int32), intensity_image=gray, properties=[f for f in FEATURES if gray is not None or not f.startswith("intensity")])
    df = pd.DataFrame(props)
    df.insert(0, "image_id", image_id)
    df["circularity"] = np.clip(4 * np.pi * df["area"] / np.maximum(df["perimeter"], 1e-6) ** 2, 0, 1)
    df["aspect_ratio"] = df["major_axis_length"] / np.maximum(df["minor_axis_length"], 1e-6)
    h, w = masks.shape
    df["touches_border"] = (df["bbox-0"] == 0) | (df["bbox-1"] == 0) | (df["bbox-2"] == h) | (df["bbox-3"] == w)
    df = df.rename(columns={"equivalent_diameter_area": "equiv_diameter", "centroid-0": "cy", "centroid-1": "cx",
                            "bbox-0": "y0", "bbox-1": "x0", "bbox-2": "y1", "bbox-3": "x1"})
    df["pixel_size_um"] = pixel_size_um if pixel_size_um else np.nan
    if pixel_size_um:
        df["area_um2"] = df["area"] * pixel_size_um ** 2
        df["equiv_diameter_um"] = df["equiv_diameter"] * pixel_size_um
        df["perimeter_um"] = df["perimeter"] * pixel_size_um
    return df

def border_mask(df: pd.DataFrame) -> pd.Series:
    """touches_border 列在与空表拼接后可能变成 object/NaN，这里统一转成布尔。"""
    return df["touches_border"].fillna(False).astype(bool)

def summarize(df: pd.DataFrame, exclude_border: bool = True) -> dict:
    """一张图（或一组）的汇总：计数、面积/直径/圆度的中位数与四分位，贴边实例默认排除。"""
    d = df[~border_mask(df)] if exclude_border and "touches_border" in df else df
    if len(d) == 0: return dict(n=0, n_border_excluded=int(len(df) - len(d)))
    q = lambda c: dict(median=float(d[c].median()), q1=float(d[c].quantile(.25)), q3=float(d[c].quantile(.75)), mean=float(d[c].mean()))
    out = dict(n=int(len(d)), n_border_excluded=int(len(df) - len(d)), area_px=q("area"), equiv_diameter_px=q("equiv_diameter"),
               circularity=q("circularity"), solidity=q("solidity"), aspect_ratio=q("aspect_ratio"))
    if "area_um2" in d and d["area_um2"].notna().any(): out["area_um2"] = q("area_um2"); out["equiv_diameter_um"] = q("equiv_diameter_um")
    return out
