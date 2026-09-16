#!/usr/bin/env python3
"""为"流水线动画"导出一张肠类器官整图从输入到报告的每一步产物（真实数据）。
运行示例：2048×2048 的 OrgaSegment 宽场图（类器官约 60–80 px，缩放到 30 px 的系数约 0.4，肉眼可见）。
输出 docs/pipeline_demo_data.json（所有图为 base64 JPEG/PNG，数组为 int8/uint16 base64）。
"""
import base64, glob, io, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "/root/autodl-fs/AI4S")
os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models")
from cellpose import models
from orgalyst.overlay import overlay
from orgalyst.morphometry import measure, summarize
from orgalyst.qc import image_qc, tta_agreement, flag_low_confidence
from orgalyst.segment import Segmenter
D = "/root/autodl-tmp/AI4S_data/processed/seg"
DISP = 512

def b64(im, q=82, fmt=None):
    buf = io.BytesIO()
    if isinstance(im, np.ndarray): im = Image.fromarray(im)
    if fmt == "png" or q is None: im.save(buf, "PNG", optimize=True); return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    im.convert("RGB").save(buf, "JPEG", quality=q); return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
def q8(a): return base64.b64encode(np.clip(np.round(a * 127), -127, 127).astype(np.int8).tobytes()).decode()

# ---- 选图：2048 的肠测试图，实例数最多的一张 ----
cands = []
for ip in sorted(glob.glob(f"{D}/intestine/test/images/*.png")):
    m = np.array(Image.open(ip.replace("/images/", "/masks/")))
    if m.shape[0] == 2048: cands.append((int(m.max()), ip))
n_gt, ip = max(cands); img = np.array(Image.open(ip)); gt = np.array(Image.open(ip.replace("/images/", "/masks/")))
gray = img.mean(axis=2).astype(np.uint8) if img.ndim == 3 else img
print("image", os.path.basename(ip), gray.shape, "gt", n_gt)
out = dict(source=os.path.basename(ip), shape=[int(gray.shape[1]), int(gray.shape[0])], gt_instances=int(n_gt))

# ---- 1 输入 ----
disp = Image.fromarray(gray).resize((DISP, DISP), Image.BILINEAR)
out["s1_input"] = dict(image=b64(disp), text=f"明场图 {gray.shape[1]}×{gray.shape[0]} px（这里缩到 {DISP} 显示）")
# ---- 2 归一化 + 缩放 ----
lo, hi = np.percentile(gray, 1), np.percentile(gray, 99)
norm = np.clip((gray - lo) / max(hi - lo, 1e-6), 0, 1)
seg = Segmenter("intestine", diam_mode="sizemodel")
diam = seg.diameter_for(gray); scale = 30.0 / diam
small = Image.fromarray((norm * 255).astype(np.uint8)).resize((max(1, int(gray.shape[1] * scale)), max(1, int(gray.shape[0] * scale))), Image.BILINEAR)
out["s2_rescale"] = dict(image=b64((norm * 255).astype(np.uint8)[::4, ::4]), small=b64(np.array(small), fmt="png"), small_size=list(small.size), diameter=float(diam), scale=float(scale),
                          lo=float(lo), hi=float(hi))
print("diameter", diam, "scale", scale, "small", small.size)
# ---- 3 切块（在缩放后的图上 224 窗口、重叠一半）----
W, H = small.size; bs = 224; step = 112
tiles = []
for y in range(0, max(1, H - bs + step), step):
    for x in range(0, max(1, W - bs + step), step):
        tiles.append([int(x), int(y), int(min(bs, W - x)), int(min(bs, H - y))])
out["s3_tiles"] = dict(bsize=bs, overlap=0.5, tiles=tiles, n=len(tiles))
# ---- 4 网络输出 ----
masks, flows, _ = seg.model.eval(gray, diameter=diam, channels=[0, 0], flow_threshold=0.4, cellprob_threshold=0.0)
flow_rgb, dP, cellprob = flows[0], flows[1], flows[2]
def down(a, mode=Image.BILINEAR): return np.array(Image.fromarray(a).resize((DISP, DISP), mode))
cp = cellprob.astype(np.float32); cpn = np.clip(cp / max(abs(cp).max(), 1e-6), -1, 1)
cp_img = ((down(cpn) + 1) / 2 * 255).astype(np.uint8)
out["s4_net"] = dict(flow=b64(Image.fromarray(flow_rgb).resize((DISP, DISP))), prob=b64(cp_img), dx=q8(down(dP[1].astype(np.float32) / (np.hypot(dP[0], dP[1]) + 1e-8)) if False else down((dP[1] / (np.hypot(dP[0], dP[1]) + 1e-8)).astype(np.float32))),
                     dy=q8(down((dP[0] / (np.hypot(dP[0], dP[1]) + 1e-8)).astype(np.float32))), cellprob=q8(down(cpn)), size=DISP)
# ---- 5 阈值化 ----
thr = (cellprob > 0)
out["s5_thresh"] = dict(image=b64(Image.fromarray((thr * 255).astype(np.uint8)).resize((DISP, DISP), Image.NEAREST)), frac=float(thr.mean()))
# ---- 6 追踪 → 实例（用 cellpose 返回的最终位置 p 画汇聚点）----
p = flows[3] if len(flows) > 3 and flows[3] is not None else None
m_disp = np.array(Image.fromarray(masks.astype(np.int32)).resize((DISP, DISP), Image.NEAREST))
out["s6_track"] = dict(masks=base64.b64encode(m_disp.astype(np.uint16).tobytes()).decode(), n=int(masks.max()))
# ---- 7 掩码放回原图 + 叠加 ----
ov = overlay(img, masks); ov.thumbnail((DISP, DISP))
out["s7_masks"] = dict(overlay=b64(ov), n=int(masks.max()), gt=int(n_gt))
# ---- 8 形态测量 ----
feats = measure(masks, gray, None, os.path.splitext(os.path.basename(ip))[0])
cols = ["label", "area", "equiv_diameter", "perimeter", "circularity", "solidity", "aspect_ratio", "touches_border"]
rows = feats[cols].sort_values("area", ascending=False).head(10).round(3).values.tolist()
summ = summarize(feats)
out["s8_measure"] = dict(columns=cols, rows=[[int(r[0]), int(r[1]), round(r[2], 1), round(r[3], 1), round(r[4], 3), round(r[5], 3), round(r[6], 2), bool(r[7])] for r in rows], n=int(len(feats)),
                         summary=dict(n=summ["n"], border_excluded=summ["n_border_excluded"], area_median=summ["area_px"]["median"], diam_median=summ["equiv_diameter_px"]["median"], circ_median=summ["circularity"]["median"]))
# ---- 9 质控 ----
q = image_qc(gray); agr = tta_agreement(seg, img, masks, k=4)
feats["tta_agreement"] = agr[feats["label"].values - 1]; feats = flag_low_confidence(feats)
low_ids = feats.loc[feats["low_confidence"], "label"].astype(int).tolist()
low_mask = np.isin(masks, low_ids) * masks
ov2 = overlay(np.array(ov.resize((DISP, DISP))) if False else img, masks); ov2 = overlay(np.array(ov2), low_mask, color=(230, 140, 20), width=4); ov2.thumbnail((DISP, DISP))
out["s9_qc"] = dict(overlay=b64(ov2), focus=q["focus_score"], illum=q["illumination_cv"], sat=q["saturation_frac"], n_low=len(low_ids), agreement_mean=float(agr.mean()), k=4)
# ---- 10 报告 & 溯源（文字，报告缩略图在本机渲染后再拼进页面）----
out["s10_manifest"] = dict(model="intestine:" + seg.model_id.split(":")[-1], diam_mode="sizemodel", diameter=float(diam), versions=dict(cellpose="3.1.1.3", torch="2.14.0+cu130"), image_md5="…")
json.dump(out, open("/root/autodl-fs/AI4S/docs/pipeline_demo_data.json", "w"))
print("masks", masks.max(), "tiles", len(tiles), "low-confidence", len(low_ids), "saved", os.path.getsize("/root/autodl-fs/AI4S/docs/pipeline_demo_data.json") // 1024, "KB")
