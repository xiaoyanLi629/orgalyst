#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 docs/assets/gallery/ 里的叠加图拼成技术报告的示例图集 docs/assets/gallery.jpg（4 列 × 3 行，含器官、预测数 / 人工数、单图 AP50）。"""
import json, os, warnings
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; from matplotlib import font_manager
from PIL import Image
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); A = os.path.join(os.path.dirname(HERE), "docs", "assets"); G = os.path.join(A, "gallery")
avail = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams.update({"font.family": [f for f in ("Hiragino Sans GB", "PingFang SC", "Noto Sans CJK SC", "Arial Unicode MS") if f in avail] + ["sans-serif"], "font.size": 10})
meta = json.load(open(f"{G}/gallery.json")); ZH = dict(brain="脑", intestine="肠", pdac="胰腺癌 (pdac)", colon="结肠", lung="肺 · 检测计数")
fig, axes = plt.subplots(3, 4, figsize=(16, 11.2))
for ax, r in zip(axes.flat, meta):
    im = Image.open(f"{G}/{r['file']}"); ax.imshow(im); ax.set_xticks([]); ax.set_yticks([])
    tag = f"AP50 {r['ap50']:.2f}" if r.get("ap50") is not None else f"阈值 {r['conf']}"
    ax.set_title(f"{ZH[r['organ']]} · {r['shape'][1]}×{r['shape'][0]} px\n预测 {r['n_pred']} / 人工 {r['n_gt']} · {tag}", fontsize=10)
    for s in ax.spines.values(): s.set_edgecolor("#0E7A6C" if r["organ"] != "lung" else "#9A6A12"); s.set_linewidth(1.5)
for ax in list(axes.flat)[len(meta):]: ax.axis("off")
fig.tight_layout(); fig.savefig(f"{A}/gallery.jpg", dpi=110, pil_kwargs={"quality": 86}); print("gallery.jpg", len(meta), "panels")
