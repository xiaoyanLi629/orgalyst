#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""效率基准：各阶段单图耗时（GPU）、显存峰值、CPU 下的分割耗时。输出 results/timing.json。"""
import glob, json, os, sys, time, numpy as np, torch
from PIL import Image
sys.path.insert(0, "/root/autodl-fs/AI4S"); os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models"); os.environ.setdefault("YOLO_OFFLINE", "1")
from orgalyst.segment import Segmenter, to_gray
from orgalyst.qc import tta_agreement, image_qc
from orgalyst.morphometry import measure, summarize
from orgalyst.overlay import overlay
from orgalyst.detect import Detector
P = "/root/autodl-tmp/AI4S_data/processed"
imgs = {}
for ip in sorted(glob.glob(f"{P}/seg/intestine/test/images/*.png")):
    a = np.array(Image.open(ip)); imgs.setdefault(a.shape[0], ip)
out = dict(gpu=torch.cuda.get_device_name(0), cases={})
def tm(f, n=3):
    f(); torch.cuda.synchronize(); t = []
    for _ in range(n): t0 = time.perf_counter(); f(); torch.cuda.synchronize(); t.append(time.perf_counter() - t0)
    return float(np.median(t))
seg = Segmenter("intestine"); det = Detector("intestine")
for size in sorted(imgs):
    img = np.array(Image.open(imgs[size])); gray = to_gray(img); torch.cuda.reset_peak_memory_stats()
    t_seg = tm(lambda: seg.run(img)); masks, _ = seg.run(img)
    t_qc = tm(lambda: tta_agreement(seg, img, masks, k=4), n=1); t_iq = tm(lambda: image_qc(gray))
    t_meas = tm(lambda: summarize(measure(masks, gray, None, "x"))); t_ov = tm(lambda: overlay(img, masks))
    t_det = tm(lambda: det.run(img)); mem = torch.cuda.max_memory_allocated() / 2**30
    out["cases"][f"{size}px"] = dict(image=os.path.basename(imgs[size]), n_instances=int(masks.max()), segment_s=t_seg, qc_tta4_s=t_qc, image_qc_s=t_iq, measure_s=t_meas, overlay_s=t_ov, count_yolo_s=t_det, gpu_peak_gb=mem)
    print(size, json.dumps(out["cases"][f"{size}px"]), flush=True)
# CPU：最小的那张图
size = min(imgs); img = np.array(Image.open(imgs[size])); segc = Segmenter("intestine", gpu=False); t0 = time.perf_counter(); segc.run(img); out["cpu_segment_s"] = dict(size=f"{size}px", seconds=time.perf_counter() - t0)
print("cpu", out["cpu_segment_s"], flush=True)
json.dump(out, open("/root/autodl-fs/AI4S/results/timing.json", "w"), indent=1); print("TIMING_DONE")
