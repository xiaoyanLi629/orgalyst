#!/usr/bin/env python3
"""E3：自动形态测量 vs 专家标注面积的一致性（脑类器官 test 集，Schröter 2024 dataset_overview.csv）。
输出 results/e3_brain_consistency.json + results/e3_brain_consistency.png + results/e3_brain_worst.csv"""
import glob, json, os, sys
import numpy as np, pandas as pd
ROOT = "/root/autodl-fs/AI4S"
run = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("/root/autodl-tmp/orgalyst_runs/brain_test_e3_*"))[-1]
ov = pd.read_csv(f"{ROOT}/data/brain_original/dataset_overview.csv")
f = pd.read_csv(f"{run}/tables/features.csv").rename(columns={"image_id": "img_id"})
auto = f.groupby("img_id").agg(auto_px=("area", "sum"), auto_um2=("area_um2", "sum"), n=("label", "size")).reset_index()
m = pd.read_csv("/root/autodl-tmp/brain_test_meta.csv").rename(columns={"image_id": "img_id"})
d = m[["img_id"]].merge(ov, on="img_id", how="left").merge(auto, on="img_id", how="left")
d["detected"] = d["n"].fillna(0) > 0
dd = d[d.detected].copy()
from scipy import stats
pear = stats.pearsonr(dd.auto_um2, dd.org_size_mikrometer2); spear = stats.spearmanr(dd.auto_um2, dd.org_size_mikrometer2)
dd["ratio"] = dd.auto_um2 / dd.org_size_mikrometer2; dd["log_ratio"] = np.log(dd.ratio); dd["ape"] = np.abs(dd.ratio - 1)
bias = dd.log_ratio.mean(); sd = dd.log_ratio.std(); loa = (np.exp(bias - 1.96 * sd), np.exp(bias + 1.96 * sd))
res = dict(run=run, n_images=int(len(d)), n_detected=int(d.detected.sum()), n_missed=int((~d.detected).sum()),
           pearson_r=float(pear[0]), spearman_rho=float(spear[0]), median_ratio=float(dd.ratio.median()), mean_log_ratio=float(bias),
           limits_of_agreement_ratio=[float(loa[0]), float(loa[1])], mape=float(dd.ape.mean()), median_ape=float(dd.ape.median()),
           within_10pct=float((dd.ape <= .10).mean()), within_20pct=float((dd.ape <= .20).mean()), frac_ratio_gt_1_5=float((dd.ratio > 1.5).mean()),
           by_lab={lab: dict(n=int(len(g)), median_ratio=float(g.ratio.median()), mape=float(g.ape.mean()), within_20pct=float((g.ape <= .2).mean())) for lab, g in dd.groupby("Imaging")},
           by_day={int(day): dict(n=int(len(g)), median_ratio=float(g.ratio.median()), mape=float(g.ape.mean())) for day, g in dd.groupby("Day")},
           missed_images=d[~d.detected].img_id.tolist())
json.dump(res, open(f"{ROOT}/results/e3_brain_consistency.json", "w"), indent=2)
dd.sort_values("ape", ascending=False)[["img_id", "Day", "Clone", "Imaging", "org_size_mikrometer2", "auto_um2", "ratio", "n"]].head(15).to_csv(f"{ROOT}/results/e3_brain_worst.csv", index=False)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(9, 3.8))
ax[0].scatter(dd.org_size_mikrometer2 / 1e6, dd.auto_um2 / 1e6, s=12, alpha=.6, color="#0E7A6C"); lim = [0, max(dd.org_size_mikrometer2.max(), dd.auto_um2.max()) / 1e6 * 1.05]
ax[0].plot(lim, lim, "--", color="#5A6A70", lw=1); ax[0].set_xlabel("expert-annotated area (mm²)"); ax[0].set_ylabel("Orgalyst area (mm²)"); ax[0].set_title(f"r = {pear[0]:.3f}, ρ = {spear[0]:.3f}, n = {len(dd)}", fontsize=10)
mean_ = (dd.auto_um2 + dd.org_size_mikrometer2) / 2 / 1e6
ax[1].scatter(mean_, dd.log_ratio, s=12, alpha=.6, color="#0E7A6C"); ax[1].axhline(bias, color="#9A6A12"); ax[1].axhline(np.log(loa[0]), ls="--", color="#9A6A12"); ax[1].axhline(np.log(loa[1]), ls="--", color="#9A6A12")
ax[1].set_xlabel("mean area (mm²)"); ax[1].set_ylabel("log(auto / expert)"); ax[1].set_title(f"Bland-Altman: ratio LoA {loa[0]:.2f}–{loa[1]:.2f}", fontsize=10)
for a_ in ax:
    for s_ in ("top", "right"): a_.spines[s_].set_visible(False)
fig.tight_layout(); fig.savefig(f"{ROOT}/results/e3_brain_consistency.png", dpi=130)
print(json.dumps({k: v for k, v in res.items() if k not in ("by_day", "missed_images")}, indent=1, ensure_ascii=False)); print("missed:", res["missed_images"][:10])
print(open(f"{ROOT}/results/e3_brain_worst.csv").read()[:900])
