#!/usr/bin/env python3
"""E2 补充：在 val 集上标定检测计数用的置信度阈值。
对每个模型（all / intestine / brain / lung）在各器官 val 图上以 conf=0.05 预测一次，保留每个框的置信度，
再扫 0.05..0.90 的阈值算计数误差（MAPE、中位 APE、总数偏差），选 MAPE 最小者；最后用选出的阈值在 test 上复核。
输出 results/e2_conf_calibration.json。
"""
import glob, json, os, time
import numpy as np
ROOT = "/root/autodl-fs/AI4S"; D = f"{ROOT}/data/processed"
_LOCAL = "/root/autodl-tmp/AI4S_data/processed"
if os.path.exists(os.path.join(_LOCAL, ".complete")): D = _LOCAL
ORGANS = ["intestine", "brain", "lung"]; THR = [round(t, 2) for t in np.arange(0.05, 0.91, 0.05)]; IMGSZ = 1024

def collect(model, organ, split):
    out = []
    for ip in sorted(glob.glob(f"{D}/det/{organ}/{split}/images/*.png")):
        lp = ip.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        n_gt = sum(1 for l in open(lp) if l.strip()) if os.path.exists(lp) else 0
        r = model.predict(ip, imgsz=IMGSZ, conf=0.05, verbose=False, max_det=2000)[0]
        out.append((n_gt, r.boxes.conf.cpu().numpy()))
    return out

def errors(samples, t):
    ape = []; gt = pred = 0
    for n_gt, conf in samples:
        n = int((conf >= t).sum()); ape.append(abs(n - n_gt) / max(n_gt, 1)); gt += n_gt; pred += n
    return dict(mape=float(np.mean(ape)), median_ape=float(np.median(ape)), bias=float(pred / max(gt, 1)), n_images=len(ape))

def main():
    from ultralytics import YOLO
    res = {}
    for name in ["all"] + ORGANS:
        model = YOLO(f"{ROOT}/weights/yolo/{name}/weights/best.pt")
        organs = ORGANS if name == "all" else [name]
        res[name] = {}
        pooled = []
        for o in organs:
            t0 = time.time(); val = collect(model, o, "val"); pooled += val
            sweep = {str(t): errors(val, t) for t in THR}
            best_t = min(THR, key=lambda t: (sweep[str(t)]["mape"], abs(sweep[str(t)]["bias"] - 1)))
            test = collect(model, o, "test")
            res[name][o] = dict(sweep=sweep, best_conf=best_t, val=sweep[str(best_t)], test_at_best=errors(test, best_t), test_at_025=errors(test, 0.25), minutes=(time.time() - t0) / 60)
            print(name, o, "best", best_t, "val", json.dumps(res[name][o]["val"]), "test", json.dumps(res[name][o]["test_at_best"]), "test@0.25", json.dumps(res[name][o]["test_at_025"]), flush=True)
        if name == "all":
            sweep = {str(t): errors(pooled, t) for t in THR}
            gt = min(THR, key=lambda t: sweep[str(t)]["mape"])
            res[name]["_pooled"] = dict(sweep=sweep, best_conf=gt, val=sweep[str(gt)])
            print("all pooled best", gt, json.dumps(sweep[str(gt)]), flush=True)
    json.dump(res, open(f"{ROOT}/results/e2_conf_calibration.json", "w"), indent=1)
    print("saved", flush=True)

if __name__ == "__main__":
    main()
