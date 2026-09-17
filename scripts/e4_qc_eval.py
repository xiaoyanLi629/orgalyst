#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E4：质控标记有没有用？在有真值掩码的测试集上，比较“低可信”（翻转旋转一致性 < 0.5）实例与其他实例的真实质量（与真值的最大 IoU），
并算把 IoU<0.5 的错误实例挑出来的精确率 / 召回率。输出 results/e4_qc_eval.json。"""
import glob, json, os, sys, numpy as np
from PIL import Image
sys.path.insert(0, "/root/autodl-fs/AI4S"); os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models")
from orgalyst.segment import Segmenter
from orgalyst.qc import tta_agreement
P = "/root/autodl-tmp/AI4S_data/processed"
def best_iou(masks, gt):
    """每个预测实例与任一真值实例的最大 IoU。"""
    K = int(masks.max()); out = np.zeros(K)
    if K == 0 or gt.max() == 0: return out
    for k in range(1, K + 1):
        pm = masks == k; cand = np.unique(gt[pm]); cand = cand[cand > 0]; best = 0.0
        for g in cand:
            gm = gt == g; inter = np.logical_and(pm, gm).sum(); union = np.logical_or(pm, gm).sum(); best = max(best, inter / union)
        out[k - 1] = best
    return out
res = {}
for organ in ("intestine", "colon", "pdac"):
    seg = Segmenter(organ); rows = []
    for ip in sorted(glob.glob(f"{P}/seg/{organ}/test/images/*.png")):
        img = np.array(Image.open(ip)); gt = np.array(Image.open(ip.replace("/images/", "/masks/")))
        masks, _ = seg.run(img)
        if masks.max() == 0: continue
        agr = tta_agreement(seg, img, masks, k=4); iou = best_iou(masks, gt)
        rows += [dict(image=os.path.basename(ip), label=k + 1, agreement=float(agr[k]), iou=float(iou[k])) for k in range(len(iou))]
        print(organ, os.path.basename(ip), "n", len(iou), "low", int((agr < 0.5).sum()), "bad", int((iou < 0.5).sum()), flush=True)
    a = np.array([r["agreement"] for r in rows]); i = np.array([r["iou"] for r in rows]); low = a < 0.5; bad = i < 0.5
    res[organ] = dict(n_instances=int(len(rows)), n_low=int(low.sum()), n_bad=int(bad.sum()),
                      iou_mean_low=float(i[low].mean()) if low.any() else None, iou_mean_high=float(i[~low].mean()) if (~low).any() else None,
                      bad_rate_low=float(bad[low].mean()) if low.any() else None, bad_rate_high=float(bad[~low].mean()) if (~low).any() else None,
                      flag_precision=float((low & bad).sum() / max(low.sum(), 1)), flag_recall=float((low & bad).sum() / max(bad.sum(), 1)),
                      spearman=float(__import__("scipy.stats").stats.spearmanr(a, i).correlation) if len(rows) > 2 else None)
    print(organ, json.dumps(res[organ]), flush=True)
json.dump(res, open("/root/autodl-fs/AI4S/results/e4_qc_eval.json", "w"), indent=1); print("E4_DONE")
