#!/usr/bin/env python3
"""E1 零样本基线：Cellpose 预训练模型（默认 cyto3）在 processed/seg/<organ>/test 上的实例分割指标。
用法：python eval_seg_zeroshot.py --model cyto3 [--organs intestine pdac brain colon] [--split test] [--diameter 0]
输出：results/e1_zeroshot_<model>_<split>.csv（每图一行）与 .summary.json（每器官汇总）。
指标：AP@0.5/0.75/0.9（cellpose.metrics.average_precision，与 Cellpose 论文一致）、IoU0.5 下的 precision/recall/F1、
      计数误差（|pred-gt|/gt）。
"""
import argparse, csv, glob, json, os, time
import numpy as np
from PIL import Image

ROOT = "/root/autodl-fs/AI4S"
D = f"{ROOT}/data/processed"
_LOCAL = "/root/autodl-tmp/AI4S_data/processed"          # 本地盘缓存（scripts/cache_data_local.sh 生成），存在且完整则优先
if os.path.exists(os.path.join(_LOCAL, ".complete")): D = _LOCAL

def load_pairs(organ, split):
    imgs = sorted(glob.glob(f"{D}/seg/{organ}/{split}/images/*.png"))
    pairs = []
    for ip in imgs:
        mp = f"{D}/seg/{organ}/{split}/masks/{os.path.basename(ip)}"
        if os.path.exists(mp): pairs.append((ip, mp))
    return pairs

def gt_median_diameter(organ, split="train", max_images=200):
    ds = []
    for _, mp in load_pairs(organ, split)[:max_images]:
        m = np.array(Image.open(mp)); ids, counts = np.unique(m, return_counts=True)
        ds.extend(2 * np.sqrt(counts[ids != 0] / np.pi))
    return float(np.median(ds)) if ds else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cyto3")
    ap.add_argument("--organs", nargs="+", default=["intestine", "pdac", "brain", "colon"])
    ap.add_argument("--split", default="test")
    ap.add_argument("--diameter", type=float, default=0, help="0 = 用 Cellpose 的尺寸估计器自动估计")
    ap.add_argument("--flow_threshold", type=float, default=0.4)
    ap.add_argument("--cellprob_threshold", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=0, help="调试用：每器官只跑前 N 张")
    ap.add_argument("--diameter_from_gt", action="store_true", help="用该器官 train 集真值掩码的中位等效直径作为 diameter（尺寸先验对照）")
    ap.add_argument("--tag", default="", help="输出文件名后缀")
    ap.add_argument("--pretrained", default=None, help="自定义权重路径（微调模型）；给出时忽略 --model，直径默认取模型的 diam_labels")
    ap.add_argument("--diam_mode", default="model", choices=["model", "train_median", "per_image_gt", "sizemodel", "refine"],
                    help="直径来源：model=模型 diam_labels/自动；train_median=训练集真值中位数；per_image_gt=每图真值中位数（上限）；sizemodel=cyto3 尺寸估计器逐图估计")
    args = ap.parse_args()

    from cellpose import models, metrics
    import torch
    refiner = None
    if args.diam_mode == "refine":
        import sys as _s; _s.path.insert(0, ROOT)
        from orgalyst.segment import Segmenter
        refiner = Segmenter(args.organs[0] if len(args.organs) == 1 else "generic", diam_mode="refine", pretrained_path=args.pretrained)
    if args.pretrained:
        model = models.CellposeModel(gpu=torch.cuda.is_available(), pretrained_model=args.pretrained)
        model_name = os.path.basename(args.pretrained.rstrip("/"))
        model_diam = float(model.net.diam_labels.item()) if hasattr(model.net, "diam_labels") else None
        print(f"custom model {args.pretrained}, diam_labels={model_diam}", flush=True)
    else:
        model = models.Cellpose(gpu=torch.cuda.is_available(), model_type=args.model)
        model_name = args.model; model_diam = None
    sizer = models.Cellpose(gpu=torch.cuda.is_available(), model_type="cyto3").sz if args.diam_mode == "sizemodel" else None
    os.makedirs(f"{ROOT}/results", exist_ok=True)
    if args.diameter_from_gt: args.diam_mode = "train_median"
    tag = ("_" + args.tag) if args.tag else ("" if args.diam_mode == "model" else "_" + args.diam_mode)
    prefix = "e1_ft" if args.pretrained else "e1_zeroshot"
    out_csv = f"{ROOT}/results/{prefix}_{model_name}_{args.split}{tag}.csv"
    rows, summary = [], {}
    for organ in args.organs:
        pairs = load_pairs(organ, args.split)
        if args.limit: pairs = pairs[:args.limit]
        diam = args.diameter or model_diam or None
        if args.diam_mode == "train_median":
            diam = gt_median_diameter(organ); print(f"{organ}: GT median equivalent diameter (train) = {diam:.1f} px", flush=True)
        t0 = time.time(); aps = []; tps = fps = fns = 0; cnt_err = []
        for ip, mp in pairs:
            img = np.array(Image.open(ip)); gt = np.array(Image.open(mp)).astype(np.int32)
            if img.ndim == 3: img = img.mean(axis=2).astype(np.uint8)
            d_img = diam
            if args.diam_mode == "per_image_gt":
                ids, cnts = np.unique(gt, return_counts=True); d_img = float(np.median(2 * np.sqrt(cnts[ids != 0] / np.pi)))
            elif args.diam_mode == "sizemodel":
                d_img = float(sizer.eval(img, channels=[0, 0])[0])
            if refiner is not None:
                pred, info = refiner.run(img, args.flow_threshold, args.cellprob_threshold); diams = info["diameter_px"] or 0
            else:
                out = model.eval(img, diameter=d_img, channels=[0, 0],
                                 flow_threshold=args.flow_threshold, cellprob_threshold=args.cellprob_threshold)
                pred, diams = out[0], (out[3] if len(out) > 3 else (d_img or 0))
            ap_, tp, fp, fn = metrics.average_precision([gt], [pred], threshold=[0.5, 0.75, 0.9])
            ap_, tp, fp, fn = ap_[0], tp[0], fp[0], fn[0]
            n_gt = len(np.unique(gt)) - 1; n_pred = len(np.unique(pred)) - 1
            tps += tp[0]; fps += fp[0]; fns += fn[0]; aps.append(ap_)
            cnt_err.append(abs(n_pred - n_gt) / max(n_gt, 1))
            rows.append(dict(model=model_name, organ=organ, split=args.split, image=os.path.basename(ip), n_gt=n_gt, n_pred=n_pred,
                             diam_est=float(diams) if np.ndim(diams) == 0 else float(np.mean(diams)),
                             ap50=ap_[0], ap75=ap_[1], ap90=ap_[2], tp50=int(tp[0]), fp50=int(fp[0]), fn50=int(fn[0])))
        if not pairs: continue
        aps = np.array(aps); prec = tps / max(tps + fps, 1); rec = tps / max(tps + fns, 1)
        summary[organ] = dict(n_images=len(pairs), ap50=float(aps[:, 0].mean()), ap75=float(aps[:, 1].mean()), ap90=float(aps[:, 2].mean()),
                              precision50=float(prec), recall50=float(rec), f1_50=float(2 * prec * rec / max(prec + rec, 1e-9)),
                              count_mape=float(np.mean(cnt_err)), sec_per_image=(time.time() - t0) / len(pairs))
        print(organ, json.dumps(summary[organ]), flush=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    json.dump(dict(args=vars(args), summary=summary), open(out_csv.replace(".csv", ".summary.json"), "w"), indent=2)
    print("saved", out_csv)

if __name__ == "__main__":
    main()
