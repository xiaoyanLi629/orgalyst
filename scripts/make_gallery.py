#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技术报告示例图集：四种器官各取若干测试图跑系统默认流程，保存叠加图 + 元数据（docs/assets/gallery/），拼图在本机做（服务器无中文字体）。"""
import glob, json, os, sys, numpy as np
from PIL import Image
sys.path.insert(0, "/root/autodl-fs/AI4S"); os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models"); os.environ.setdefault("YOLO_OFFLINE", "1")
from orgalyst.segment import Segmenter, to_gray
from orgalyst.detect import Detector, draw_boxes
from cellpose.metrics import average_precision
P = "/root/autodl-tmp/AI4S_data/processed"; OUT = "/root/autodl-fs/AI4S/docs/assets/gallery"; os.makedirs(OUT, exist_ok=True)
picks = {"brain": ["org01_wt2D_d02_LabA", "org17_TH2-7_d16_LabB", "org33_A1A-1_d30_LabA"],
         "intestine": [os.path.splitext(os.path.basename(p))[0] for p in sorted(glob.glob(f"{P}/seg/intestine/test/images/*.png"))[:3]],
         "pdac": [os.path.splitext(os.path.basename(p))[0] for p in sorted(glob.glob(f"{P}/seg/pdac/test/images/*.png"))[:2]],
         "colon": [os.path.splitext(os.path.basename(p))[0] for p in sorted(glob.glob(f"{P}/seg/colon/test/images/*.png"))[:2]]}
def overlay_fill(img, masks, rng):
    base = img if img.ndim == 3 else np.stack([img] * 3, -1); base = base.astype(np.float32); K = int(masks.max())
    cols = rng.random((K + 1, 3)) * 255; inside = masks > 0
    out = base.copy(); out[inside] = base[inside] * 0.6 + cols[masks][inside] * 0.4
    b = np.zeros(masks.shape, bool)
    for s in ((slice(1, None), slice(None)), (slice(None), slice(1, None))):
        pass
    b[1:, :] |= masks[1:, :] != masks[:-1, :]; b[:, 1:] |= masks[:, 1:] != masks[:, :-1]; b[:-1, :] |= masks[:-1, :] != masks[1:, :]; b[:, :-1] |= masks[:, :-1] != masks[:, 1:]
    b &= inside; w = max(1, masks.shape[0] // 700)
    from scipy.ndimage import binary_dilation; b = binary_dilation(b, iterations=w)
    out[b] = [20, 255, 150]; return Image.fromarray(out.astype(np.uint8))
meta = []; rng = np.random.default_rng(0)
for organ, ids in picks.items():
    seg = Segmenter(organ)
    for iid in ids:
        ip = f"{P}/seg/{organ}/test/images/{iid}.png"; img = np.array(Image.open(ip)); gt = np.array(Image.open(ip.replace("/images/", "/masks/")))
        masks, info = seg.run(img)
        ap = float(average_precision([gt], [masks], threshold=[0.5])[0][0][0]) if gt.max() > 0 else None
        ov = overlay_fill(img, masks, rng); ov.thumbnail((900, 900)); ov.save(f"{OUT}/{organ}__{iid}.jpg", quality=86)
        meta.append(dict(organ=organ, image_id=iid, file=f"{organ}__{iid}.jpg", shape=list(img.shape[:2]), n_pred=int(masks.max()), n_gt=int(gt.max()), ap50=ap, diam_mode=seg.diam_mode, diameter_px=info.get("diameter_px")))
        print(organ, iid, meta[-1]["n_pred"], meta[-1]["n_gt"], ap, flush=True)
det = Detector("lung")
for iid in [os.path.splitext(os.path.basename(p))[0] for p in sorted(glob.glob(f"{P}/det/lung/test/images/*.png"))[1:3]]:
    ip = f"{P}/det/lung/test/images/{iid}.png"; img = np.array(Image.open(ip)); lp = ip.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
    n_gt = sum(1 for l in open(lp) if l.strip()) if os.path.exists(lp) else 0
    r = det.run(img); im = draw_boxes(img, r["boxes"], width=max(2, img.shape[0] // 400)); im.thumbnail((900, 900)); im.save(f"{OUT}/lung__{iid}.jpg", quality=86)
    meta.append(dict(organ="lung", image_id=iid, file=f"lung__{iid}.jpg", shape=list(img.shape[:2]), n_pred=r["n"], n_gt=n_gt, conf=r["conf"], task="count")); print("lung", iid, r["n"], n_gt, flush=True)
json.dump(meta, open(f"{OUT}/gallery.json", "w"), indent=1); print("GALLERY_DONE", len(meta))
