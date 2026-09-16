#!/usr/bin/env python3
"""为 Cellpose 原理动画导出真实数据（JSON + base64 图）：
  1) 肠类器官测试图 512×512 裁块：归一化灰度、网络输出（dX, dY, cellprob）、追踪后的掩码 —— 降采样到 256×256 供浏览器动画
  2) 一个非凸类器官的真值掩码（小块）—— 浏览器里做热扩散动画
  3) 直径参数影响：同一裁块在直径 12 / 自动估计 / 150 下的分割叠加图；脑类器官在自动直径 vs 404 下的叠加图
  4) 缩放示意：脑图 1024×768 → 缩到目标 30 px 后的尺寸
输出：/root/autodl-fs/AI4S/docs/cellpose_demo_data.json
"""
import base64, io, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "/root/autodl-fs/AI4S")
os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models")
from cellpose import models
from orgalyst.overlay import overlay
D = "/root/autodl-tmp/AI4S_data/processed/seg"

def b64png(arr_or_img, q=None):
    im = arr_or_img if isinstance(arr_or_img, Image.Image) else Image.fromarray(arr_or_img)
    buf = io.BytesIO()
    if q: im.convert("RGB").save(buf, "JPEG", quality=q)
    else: im.save(buf, "PNG", optimize=True)
    return "data:image/%s;base64," % ("jpeg" if q else "png") + base64.b64encode(buf.getvalue()).decode()

def q8(a):  # float [-1,1] → int8 → base64
    return base64.b64encode(np.clip(np.round(a * 127), -127, 127).astype(np.int8).tobytes()).decode()

out = {}
# ---------- 1. 肠类器官裁块 ----------
import glob
imgs = sorted(glob.glob(f"{D}/intestine/test/images/*.png"))
# 选实例数适中、尺寸 1024 的图
best = None
for ip in imgs:
    m = np.array(Image.open(ip.replace("/images/", "/masks/")))
    if m.shape[0] == 1024 and 20 <= m.max() <= 80: best = ip; break
best = best or imgs[0]
img = np.array(Image.open(best)); gt = np.array(Image.open(best.replace("/images/", "/masks/")))
if img.ndim == 3: img = img.mean(axis=2).astype(np.uint8)
# 选实例最密的 512 裁块
H, W = img.shape; bs = 512; cands = []
for y in range(0, H - bs + 1, 128):
    for x in range(0, W - bs + 1, 128):
        cands.append((len(np.unique(gt[y:y+bs, x:x+bs])) - 1, y, x))
n, y0, x0 = max(cands); crop = img[y0:y0+bs, x0:x0+bs]; gcrop = gt[y0:y0+bs, x0:x0+bs]
print("image", os.path.basename(best), "crop", (y0, x0), "gt instances in crop", n)
model = models.CellposeModel(gpu=True, pretrained_model="/root/autodl-fs/AI4S/weights/cellpose_ft/intestine/intestine")
sizer = models.Cellpose(gpu=True, model_type="cyto3").sz
d_auto = float(sizer.eval(crop, channels=[0, 0])[0]); print("auto diameter", d_auto)
masks, flows, _ = model.eval(crop, diameter=d_auto, channels=[0, 0])
flow_rgb, dP, cellprob = flows[0], flows[1], flows[2]
print("masks", masks.max(), "dP", dP.shape, "cellprob", cellprob.shape, float(cellprob.min()), float(cellprob.max()))
# 降采样到 256
def down(a): return np.array(Image.fromarray(a).resize((256, 256), Image.BILINEAR))
def down_nn(a): return np.array(Image.fromarray(a.astype(np.int32)).resize((256, 256), Image.NEAREST))
gray256 = down(crop)
dy, dx = dP[0], dP[1]
norm = np.sqrt(dx**2 + dy**2) + 1e-8
dx256 = down((dx / norm).astype(np.float32)); dy256 = down((dy / norm).astype(np.float32))
cp256 = down(cellprob.astype(np.float32)); cp256 = np.clip(cp256 / max(abs(cp256).max(), 1e-6), -1, 1)
m256 = down_nn(masks)
out["inference"] = dict(image=b64png(gray256), size=256, dx=q8(dx256), dy=q8(dy256), cellprob=q8(cp256),
                        masks=base64.b64encode(m256.astype(np.uint16).tobytes()).decode(), n_masks=int(masks.max()),
                        flow_rgb=b64png(np.array(Image.fromarray(flow_rgb).resize((256, 256)))), diameter=d_auto,
                        source=os.path.basename(best), crop=[int(y0), int(x0), bs], gt_instances=int(n))
# ---------- 2. 热扩散：选裁块里最不凸的一个真值实例 ----------
from skimage.measure import regionprops
props = [p for p in regionprops(gcrop) if p.area > 400]
p = min(props, key=lambda p: p.solidity)
y1, x1, y2, x2 = p.bbox; sub = (gcrop[y1:y2, x1:x2] == p.label)
# 缩到最长边 96
scale = 96 / max(sub.shape); sub = np.array(Image.fromarray(sub.astype(np.uint8) * 255).resize((max(1, int(sub.shape[1] * scale)), max(1, int(sub.shape[0] * scale))), Image.NEAREST)) > 127
from scipy.ndimage import distance_transform_edt
dt = distance_transform_edt(sub); cy, cx = np.unravel_index(np.argmax(dt), dt.shape)
out["diffusion"] = dict(h=int(sub.shape[0]), w=int(sub.shape[1]), mask=base64.b64encode(np.packbits(sub.ravel()).tobytes()).decode(),
                        center=[int(cy), int(cx)], solidity=float(p.solidity), label=int(p.label))
print("diffusion mask", sub.shape, "solidity %.2f" % p.solidity)
# ---------- 3. 直径影响 ----------
diam_demo = {}
for name, d in (("small", 12.0), ("auto", d_auto), ("large", 150.0)):
    mk, _, _ = model.eval(crop, diameter=d, channels=[0, 0])
    ov = overlay(crop, mk); ov.thumbnail((384, 384))
    diam_demo[name] = dict(diameter=float(d), n=int(mk.max()), image=b64png(ov, q=80))
out["diameter_intestine"] = diam_demo
bimg_p = sorted(glob.glob(f"{D}/brain/test/images/*d10_LabA.png"))[0]
bimg = np.array(Image.open(bimg_p)); bgray = bimg.mean(axis=2).astype(np.uint8) if bimg.ndim == 3 else bimg
cyto3 = models.Cellpose(gpu=True, model_type="cyto3")
mk_auto, _, _, d_est = cyto3.eval(bgray, diameter=None, channels=[0, 0])
mk_400, _, _, _ = cyto3.eval(bgray, diameter=404, channels=[0, 0])
brain_ft = models.CellposeModel(gpu=True, pretrained_model="/root/autodl-fs/AI4S/weights/cellpose_ft/brain/brain")
mk_ft, _, _ = brain_ft.eval(bgray, diameter=404, channels=[0, 0])
bd = {}
for name, mk, d in (("auto", mk_auto, float(d_est)), ("d404", mk_400, 404.0), ("finetuned", mk_ft, 404.0)):
    ov = overlay(bimg, mk); ov.thumbnail((384, 384)); bd[name] = dict(diameter=d, n=int(mk.max()), image=b64png(ov, q=80))
out["diameter_brain"] = bd
# ---------- 4. 缩放示意 ----------
small = Image.fromarray(bgray).resize((max(1, int(bgray.shape[1] * 30 / 404)), max(1, int(bgray.shape[0] * 30 / 404))), Image.BILINEAR)
big = Image.fromarray(bgray); big.thumbnail((384, 384))
out["rescale"] = dict(original=b64png(big, q=80), original_size=[int(bgray.shape[1]), int(bgray.shape[0])], scaled=b64png(np.array(small)), scaled_size=list(small.size), diameter=404, target=30)
json.dump(out, open("/root/autodl-fs/AI4S/docs/cellpose_demo_data.json", "w"))
print("saved", sum(len(v) if isinstance(v, str) else 0 for v in json.dumps(out)) , "bytes")
