#!/usr/bin/env python3
"""补充导出：同一张肠图的 512 掩码 + 低可信实例编号 + 逐实例一致性（供本机渲染加粗的质检叠加图）。"""
import glob, json, os, sys, base64
import numpy as np
from PIL import Image
sys.path.insert(0, "/root/autodl-fs/AI4S")
os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models")
from orgalyst.morphometry import measure
from orgalyst.qc import tta_agreement, flag_low_confidence
from orgalyst.segment import Segmenter
D = "/root/autodl-tmp/AI4S_data/processed/seg"; DISP = 512
cands = []
for ip in sorted(glob.glob(f"{D}/intestine/test/images/*.png")):
    m = np.array(Image.open(ip.replace("/images/", "/masks/")))
    if m.shape[0] == 2048: cands.append((int(m.max()), ip))
n_gt, ip = max(cands); img = np.array(Image.open(ip))
gray = img.mean(axis=2).astype(np.uint8) if img.ndim == 3 else img
seg = Segmenter("intestine", diam_mode="sizemodel"); diam = seg.diameter_for(gray)
masks, flows, _ = seg.model.eval(gray, diameter=diam, channels=[0, 0], flow_threshold=0.4, cellprob_threshold=0.0)
feats = measure(masks, gray, None, "x"); agr = tta_agreement(seg, img, masks, k=4)
feats["tta_agreement"] = agr[feats["label"].values - 1]; feats = flag_low_confidence(feats)
low_ids = feats.loc[feats["low_confidence"], "label"].astype(int).tolist()
m_disp = np.array(Image.fromarray(masks.astype(np.int32)).resize((DISP, DISP), Image.NEAREST)).astype(np.uint16)
json.dump(dict(masks=base64.b64encode(m_disp.tobytes()).decode(), n=int(masks.max()), low_ids=low_ids, agreement=[float(a) for a in agr]), open("/root/autodl-fs/AI4S/docs/qc_extra.json", "w"))
print("n", masks.max(), "low", low_ids)
