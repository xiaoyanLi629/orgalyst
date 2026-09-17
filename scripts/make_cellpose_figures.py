#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 docs/cellpose_demo_data.json 渲染技术报告用的两张静态图到 docs/assets/：
cellpose_outputs.jpg（输入 → 方向图 → 概率图 → 追踪后的实例）与 cellpose_diffusion.jpg（训练目标方向图的热扩散来源）。"""
import json, base64, io, os, sys, warnings, numpy as np
LANG = "en" if "--lang" in sys.argv and sys.argv[sys.argv.index("--lang") + 1] == "en" else "zh"; SUF = "_en" if LANG == "en" else ""
T = {"zh": {}, "en": {}}
T["zh"].update(t0="① 输入（256×256 裁块）", t1="② 方向图（只画前景像素，每 6 像素一支）", t2="③ 哪里像类器官（概率图）", t3="④ 沿箭头追踪后：{n} 个实例（人工 {g}）", st="扩散 {t} 步", grad="热的梯度 = 训练目标方向图", sup="训练时方向图的来源：对一个人工标注的非凸实例（实心度 {s:.2f}）以中心为热源反复扩散，热只在实例内传播")
T["en"].update(t0="① input (256×256 crop)", t1="② flow field (foreground only, one arrow per 6 px)", t2="③ organoid probability map", t3="④ after following the arrows: {n} instances (manual {g})", st="diffusion step {t}", grad="gradient of heat = training target flow", sup="Where the training flow comes from: heat diffused from the centre of a manually annotated non-convex instance (solidity {s:.2f}); heat stays inside the instance")
L = T[LANG]
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; from matplotlib import font_manager
from PIL import Image
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(os.path.dirname(HERE), "docs"); A = os.path.join(D, "assets"); os.makedirs(A, exist_ok=True)
avail = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams.update({"font.family": [f for f in ("Hiragino Sans GB", "PingFang SC", "Noto Sans CJK SC", "Arial Unicode MS", "Heiti TC") if f in avail] + ["sans-serif"], "font.size": 9, "axes.unicode_minus": False})
C = json.load(open(f"{D}/cellpose_demo_data.json")); inf = C["inference"]; n = inf["size"]
q8 = lambda k: np.frombuffer(base64.b64decode(inf[k]), dtype=np.int8).astype(np.float32).reshape(n, n) / 127
dx, dy, cp = q8("dx"), q8("dy"), q8("cellprob"); m = np.frombuffer(base64.b64decode(inf["masks"]), dtype=np.uint16).reshape(n, n)
img = np.array(Image.open(io.BytesIO(base64.b64decode(inf["image"].split(",")[1]))).convert("L"))
# ---- 图 A ----
fig, ax = plt.subplots(1, 4, figsize=(12, 3.3))
ax[0].imshow(img, cmap="gray"); ax[0].set_title(L["t0"])
ax[1].imshow(img, cmap="gray", alpha=.35); st = 6; yy, xx = np.mgrid[st // 2:n:st, st // 2:n:st]; keep = cp[yy, xx] > 0
ax[1].quiver(xx[keep], yy[keep], dx[yy, xx][keep], -dy[yy, xx][keep], color="#0E7A6C", scale=30, width=.004, headwidth=4); ax[1].set_title(L["t1"])
ax[2].imshow(cp, cmap="magma", vmin=-1, vmax=1); ax[2].set_title(L["t2"])
rng = np.random.default_rng(1); K = int(m.max()); cols = np.vstack([[[0, 0, 0, 0]], np.c_[rng.random((K, 3)), np.full(K, .45)]])
ax[3].imshow(img, cmap="gray"); ax[3].imshow(cols[m]); ax[3].contour(m, levels=np.arange(.5, K + 1, 1), colors="#14FF96", linewidths=.6); ax[3].set_title(L["t3"].format(n=inf['n_masks'], g=inf['gt_instances']))
for a in ax: a.set_xticks([]); a.set_yticks([])
fig.tight_layout(); fig.savefig(f"{A}/cellpose_outputs{SUF}.jpg", dpi=130, pil_kwargs={"quality": 85}); plt.close(fig)
# ---- 图 B ----
d = C["diffusion"]; h, w = d["h"], d["w"]; mask = np.unpackbits(np.frombuffer(base64.b64decode(d["mask"]), dtype=np.uint8))[:h * w].reshape(h, w).astype(bool)
ys, xs = np.nonzero(mask); my, mx = np.median(ys), np.median(xs); k = np.argmin((ys - my) ** 2 + (xs - mx) ** 2); cy, cx = int(ys[k]), int(xs[k])   # Cellpose 的做法：坐标中位数，落在外面就取最近的内部像素
T = np.zeros((h, w), np.float32); snaps = {}; steps = [1, 5, 30, 200]
for t in range(1, 201):
    T[cy, cx] += 1; P = np.pad(T, 1); T = (P[:-2, 1:-1] + P[2:, 1:-1] + P[1:-1, :-2] + P[1:-1, 2:]) / 4; T[~mask] = 0
    if t in steps: snaps[t] = T.copy()
gy, gx = np.gradient(np.log1p(snaps[200])); nrm = np.hypot(gx, gy) + 1e-9; gx, gy = gx / nrm, gy / nrm; gx[~mask] = 0; gy[~mask] = 0
fig, ax = plt.subplots(1, 5, figsize=(12, 4))
for i, t in enumerate(steps):
    a = ax[i]; a.imshow(np.where(mask, np.log1p(snaps[t]), np.nan), cmap="inferno"); a.plot(cx, cy, "o", mfc="none", mec="#14FF96", ms=6); a.set_title(L["st"].format(t=t))
a = ax[4]; a.imshow(mask, cmap="gray", alpha=.25); st = 4; yy, xx = np.mgrid[1:h:st, 1:w:st]; kk = mask[yy, xx]
a.quiver(xx[kk], yy[kk], gx[yy, xx][kk], -gy[yy, xx][kk], color="#0E7A6C", scale=18, width=.009, headwidth=4); a.plot(cx, cy, "o", mfc="none", mec="#C0392B", ms=8); a.set_title(L["grad"])
for a in ax: a.set_xticks([]); a.set_yticks([]); a.set_facecolor("#111")
fig.suptitle(L["sup"].format(s=d['solidity']), y=1.02)
fig.tight_layout(); fig.savefig(f"{A}/cellpose_diffusion{SUF}.jpg", dpi=130, bbox_inches="tight", pil_kwargs={"quality": 85}); plt.close(fig)
print("figures →", A)
