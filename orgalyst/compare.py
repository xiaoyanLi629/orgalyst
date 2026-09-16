"""组间比较：把逐实例特征表按分组做统计检验与效应量，输出表格与图。
设计原则：每个类器官是一个观测；默认排除贴边实例；非参数检验（Mann-Whitney / Kruskal-Wallis），效应量用 Cliff's delta；多指标做 Holm 校正。
用法（Python）：
  res = compare_groups(features_df, group_col="group", metrics=("area_um2","circularity"))
  res["table"] 为每指标一行的 DataFrame；res["figures"] 为 {metric: base64 png}
命令行：python -m orgalyst compare --run RUN_DIR --groups groups.csv  （groups.csv 两列：image_id,group）
"""
from __future__ import annotations
import base64, io, itertools
import numpy as np
import pandas as pd

DEFAULT_METRICS = ("area_um2", "equiv_diameter_um", "area", "equiv_diameter", "circularity", "solidity", "aspect_ratio")

def cliffs_delta(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0 or len(b) == 0: return float("nan")
    # 用秩的方式 O((n+m)log(n+m)) 计算
    allv = np.concatenate([a, b]); ranks = pd.Series(allv).rank().values
    ra = ranks[: len(a)].sum(); U = ra - len(a) * (len(a) + 1) / 2
    return float(2 * U / (len(a) * len(b)) - 1)

def holm(pvals):
    p = np.asarray(pvals, float); n = len(p); order = np.argsort(p); adj = np.empty(n)
    running = 0.0
    for k, i in enumerate(order):
        running = max(running, (n - k) * p[i]); adj[i] = min(1.0, running)
    return adj

def compare_groups(df: pd.DataFrame, group_col: str = "group", metrics=DEFAULT_METRICS, exclude_border: bool = True, make_figures: bool = True) -> dict:
    from scipy import stats
    d = df[~df["touches_border"].fillna(False).astype(bool)] if exclude_border and "touches_border" in df else df
    d = d[d[group_col].notna()]
    groups = [g for g in d[group_col].unique()]
    metrics = [m for m in metrics if m in d and d[m].notna().any()]
    rows, figs = [], {}
    for m in metrics:
        samples = {g: d.loc[d[group_col] == g, m].dropna().values for g in groups}
        samples = {g: v for g, v in samples.items() if len(v) > 0}
        if len(samples) < 2: continue
        if len(samples) == 2:
            (g1, a), (g2, b) = samples.items()
            stat, p = stats.mannwhitneyu(a, b, alternative="two-sided"); test = "Mann-Whitney U"; eff = cliffs_delta(a, b)
            desc = f"{g1} 中位数 {np.median(a):.3g} (n={len(a)}) vs {g2} 中位数 {np.median(b):.3g} (n={len(b)})"
        else:
            stat, p = stats.kruskal(*samples.values()); test = "Kruskal-Wallis"; eff = float("nan")
            desc = "; ".join(f"{g} 中位数 {np.median(v):.3g} (n={len(v)})" for g, v in samples.items())
        rows.append(dict(metric=m, test=test, statistic=float(stat), p_value=float(p), cliffs_delta=eff, description=desc,
                         **{f"median_{g}": float(np.median(v)) for g, v in samples.items()}, **{f"n_{g}": int(len(v)) for g, v in samples.items()}))
        if make_figures: figs[m] = _boxplot(samples, m)
    table = pd.DataFrame(rows)
    if len(table): table["p_holm"] = holm(table["p_value"].values); table["significant_0.05"] = table["p_holm"] < 0.05
    # 成对比较（>2 组时）
    pairwise = []
    if len(groups) > 2:
        for m in metrics:
            for g1, g2 in itertools.combinations(groups, 2):
                a, b = d.loc[d[group_col] == g1, m].dropna().values, d.loc[d[group_col] == g2, m].dropna().values
                if len(a) and len(b):
                    _, p = stats.mannwhitneyu(a, b, alternative="two-sided"); pairwise.append(dict(metric=m, group_a=g1, group_b=g2, p_value=float(p), cliffs_delta=cliffs_delta(a, b)))
        pairwise = pd.DataFrame(pairwise)
        if len(pairwise): pairwise["p_holm"] = holm(pairwise["p_value"].values)
    return dict(table=table, pairwise=pairwise if len(groups) > 2 else None, figures=figs, groups=groups, n_per_group={g: int((d[group_col] == g).sum()) for g in groups})

def _boxplot(samples: dict, metric: str) -> str:
    import matplotlib, warnings; matplotlib.use("Agg"); warnings.filterwarnings("ignore", message="Glyph")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4.4, 3.0))
    labels, data = list(samples.keys()), list(samples.values())
    ax.boxplot(data, tick_labels=[str(l) for l in labels], showfliers=False, medianprops=dict(color="#0E7A6C", lw=2))
    rng = np.random.RandomState(0)
    for i, v in enumerate(data, 1):
        v = v if len(v) <= 400 else rng.choice(v, 400, replace=False)
        ax.scatter(i + rng.uniform(-.18, .18, len(v)), v, s=6, alpha=.35, color="#5A6A70", linewidths=0)
    ax.set_title(metric, fontsize=11); ax.tick_params(labelsize=8)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def attach_groups(features: pd.DataFrame, groups: pd.DataFrame, key: str = "image_id") -> pd.DataFrame:
    """groups：至少含 image_id 与 group 两列（可含 day/dose 等其他元数据），按 image_id 合并到特征表。"""
    g = groups.copy(); g[key] = g[key].astype(str).str.replace(r"\.[A-Za-z0-9]+$", "", regex=True)
    return features.merge(g, on=key, how="left")
