#!/usr/bin/env python3
"""E1 补充：Cellpose-SAM（cellpose 4，cpsam 权重）在 processed/seg/<organ>/test 上的实例分割指标。需在 cellpose4 环境运行：
  /root/autodl-tmp/cellpose4-env/bin/python scripts/eval_seg_cpsam.py [--pretrained PATH] [--diam_mode native|per_image_gt|train_median]
输出格式与 eval_seg_zeroshot.py 一致：results/e1_{zeroshot|ft}_cpsam_<split>[_tag].csv / .summary.json
说明：Cellpose-SAM 训练时不做固定缩放，官方推荐 diameter=None（native）；这里另给 per_image_gt 作对照，看它是否真的不依赖直径。
"""
import argparse, csv, glob, json, os, time
import numpy as np
from PIL import Image
ROOT = "/root/autodl-fs/AI4S"; D = f"{ROOT}/data/processed"
_LOCAL = "/root/autodl-tmp/AI4S_data/processed"
if os.path.exists(os.path.join(_LOCAL, ".complete")): D = _LOCAL

def load_pairs(organ, split):
    out = []
    for ip in sorted(glob.glob(f"{D}/seg/{organ}/{split}/images/*.png")):
        mp = f"{D}/seg/{organ}/{split}/masks/{os.path.basename(ip)}"
        if os.path.exists(mp): out.append((ip, mp))
    return out

def gt_median_diameter(organ, split="train", max_images=200):
    ds = []
    for _, mp in load_pairs(organ, split)[:max_images]:
        m = np.array(Image.open(mp)); ids, c = np.unique(m, return_counts=True); ds.extend(2 * np.sqrt(c[ids != 0] / np.pi))
    return float(np.median(ds)) if ds else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pretrained", default=None, help="微调权重路径；不给则用内置 cpsam")
    ap.add_argument("--organs", nargs="+", default=["intestine", "pdac", "brain", "colon"])
    ap.add_argument("--split", default="test"); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--diam_mode", default="native", choices=["native", "per_image_gt", "train_median"])
    ap.add_argument("--flow_threshold", type=float, default=0.4); ap.add_argument("--cellprob_threshold", type=float, default=0.0)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    from cellpose import models, metrics
    import torch
    builtin = (args.pretrained or "cpsam") in getattr(models, "MODEL_NAMES", ["cpsam"])
    model = models.CellposeModel(gpu=torch.cuda.is_available(), pretrained_model=args.pretrained or "cpsam")
    name = (args.pretrained or "cpsam") if builtin else os.path.basename(args.pretrained.rstrip("/"))
    prefix = "e1_zeroshot" if builtin else "e1_ft"
    tag = ("_" + args.tag) if args.tag else ("" if args.diam_mode == "native" else "_" + args.diam_mode)
    os.makedirs(f"{ROOT}/results", exist_ok=True); out_csv = f"{ROOT}/results/{prefix}_{name}_{args.split}{tag}.csv"
    rows, summary = [], {}
    for organ in args.organs:
        pairs = load_pairs(organ, args.split); pairs = pairs[:args.limit] if args.limit else pairs
        diam = gt_median_diameter(organ) if args.diam_mode == "train_median" else None
        t0 = time.time(); aps = []; tps = fps = fns = 0; cnt = []
        for ip, mp in pairs:
            img = np.array(Image.open(ip)); gt = np.array(Image.open(mp)).astype(np.int32)
            if img.ndim == 3: img = img.mean(axis=2).astype(np.uint8)
            d = diam
            if args.diam_mode == "per_image_gt":
                ids, c = np.unique(gt, return_counts=True); d = float(np.median(2 * np.sqrt(c[ids != 0] / np.pi)))
            out = model.eval(img, diameter=d, flow_threshold=args.flow_threshold, cellprob_threshold=args.cellprob_threshold)
            pred = out[0]
            ap_, tp, fp, fn = metrics.average_precision([gt], [pred], threshold=[0.5, 0.75, 0.9]); ap_, tp, fp, fn = ap_[0], tp[0], fp[0], fn[0]
            n_gt = len(np.unique(gt)) - 1; n_pred = len(np.unique(pred)) - 1
            tps += tp[0]; fps += fp[0]; fns += fn[0]; aps.append(ap_); cnt.append(abs(n_pred - n_gt) / max(n_gt, 1))
            rows.append(dict(model=name, organ=organ, split=args.split, image=os.path.basename(ip), n_gt=n_gt, n_pred=n_pred, diam_est=d or 0,
                             ap50=ap_[0], ap75=ap_[1], ap90=ap_[2], tp50=int(tp[0]), fp50=int(fp[0]), fn50=int(fn[0])))
        if not pairs: continue
        aps = np.array(aps); prec = tps / max(tps + fps, 1); rec = tps / max(tps + fns, 1)
        summary[organ] = dict(n_images=len(pairs), ap50=float(aps[:, 0].mean()), ap75=float(aps[:, 1].mean()), ap90=float(aps[:, 2].mean()),
                              precision50=float(prec), recall50=float(rec), f1_50=float(2 * prec * rec / max(prec + rec, 1e-9)), count_mape=float(np.mean(cnt)), sec_per_image=(time.time() - t0) / len(pairs))
        print(organ, json.dumps(summary[organ]), flush=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    json.dump(dict(args=vars(args), summary=summary), open(out_csv.replace(".csv", ".summary.json"), "w"), indent=2); print("saved", out_csv)

if __name__ == "__main__":
    main()
