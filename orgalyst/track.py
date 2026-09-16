"""跨时间点追踪与生长曲线（P1）：不做像素级跟踪，按元数据把同一个体（subject）在不同时间点（timepoint）的测量串起来。
元数据来源：meta.csv（image_id, subject, timepoint[, group, pixel_size_um, ...]），或用 parse_name() 从文件名按正则提取。
输出：每个体每时间点一行的 growth 表（面积/直径中位数或单实例值）、按组的均值曲线、生长率（相对第一个时间点），以及 base64 图。
"""
from __future__ import annotations
import base64, io, re
import numpy as np
import pandas as pd

# 内置命名规则：Schröter 2024 脑类器官数据集 "org01_wt2D_d02_LabA" → subject=org01, group=wt2D, timepoint=2, lab=A
BRAIN_PATTERN = r"^(?P<subject>org\d+)_(?P<group>[A-Za-z0-9\-]+)_d(?P<timepoint>\d+)_Lab(?P<lab>[AB])(?:_(?P<note>.+))?$"

def parse_name(image_ids, pattern: str = BRAIN_PATTERN) -> pd.DataFrame:
    rx = re.compile(pattern); rows = []
    for iid in image_ids:
        m = rx.match(str(iid)); d = dict(image_id=iid)
        if m: d.update(m.groupdict())
        rows.append(d)
    df = pd.DataFrame(rows)
    if "timepoint" in df: df["timepoint"] = pd.to_numeric(df["timepoint"], errors="coerce")
    return df

def growth_table(features: pd.DataFrame, meta: pd.DataFrame, metric: str | None = None, exclude_border: bool = True) -> pd.DataFrame:
    """每个 (subject, timepoint) 一行：该图内实例的 metric 中位数与计数；单实例图（如脑类器官）即该实例的值。"""
    f = features[~features["touches_border"].fillna(False).astype(bool)] if exclude_border and "touches_border" in features else features
    m = meta.copy(); m["image_id"] = m["image_id"].astype(str)
    df = f.merge(m, on="image_id", how="inner", suffixes=("", "_meta"))
    if metric is None: metric = "area_um2" if "area_um2" in df and df["area_um2"].notna().any() else "area"
    keys = [k for k in ("subject", "group", "timepoint") if k in df]
    g = df.groupby(keys, dropna=False)[metric].agg(value="median", n="size").reset_index()
    g["metric"] = metric
    if "subject" in g and "timepoint" in g:
        g = g.sort_values(["subject", "timepoint"])
        first = g.groupby("subject")["value"].transform("first")
        g["fold_change_vs_first"] = g["value"] / first
    return g

def group_curves(growth: pd.DataFrame) -> pd.DataFrame:
    keys = [k for k in ("group", "timepoint") if k in growth]
    if "timepoint" not in keys: return pd.DataFrame()
    c = growth.groupby(keys)["value"].agg(mean="mean", median="median", std="std", n="size").reset_index()
    return c

def plot_growth(growth: pd.DataFrame, curves: pd.DataFrame, metric_label: str) -> str:
    import matplotlib, warnings; matplotlib.use("Agg"); warnings.filterwarnings("ignore", message="Glyph")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    palette = ["#0E7A6C", "#9A6A12", "#3F5FB5", "#B5473F", "#6B4FA0", "#2F8F4E"]
    groups = list(curves["group"].unique()) if "group" in curves else [None]
    for i, gname in enumerate(groups):
        col = palette[i % len(palette)]
        gg = growth[growth["group"] == gname] if gname is not None else growth
        for sid, sub in gg.groupby("subject"):
            ax.plot(sub["timepoint"], sub["value"], color=col, alpha=.18, lw=1)
        cc = curves[curves["group"] == gname] if gname is not None else curves
        ax.plot(cc["timepoint"], cc["mean"], color=col, lw=2.4, marker="o", ms=4, label=f"{gname} (n={int(cc['n'].max())})" if gname is not None else "mean")
    ax.set_xlabel("day"); ax.set_ylabel(metric_label); ax.legend(fontsize=8, frameon=False)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
