#!/usr/bin/env python3
"""E2 检测：在 processed/det/<organ>/{train,val,test} 上训练 YOLO11 并在 test 上评测（mAP50 / mAP50-95 / 计数误差）。
用法：
  python train_det_yolo.py --organs intestine                 # 单器官
  python train_det_yolo.py --organs intestine brain lung --name all   # 三器官联合
  python train_det_yolo.py --eval_only --name intestine       # 只评测已训模型
输出：weights/yolo/<name>/（ultralytics 的 run 目录，best.pt）、results/e2_det_<name>_test.json
"""
import argparse, glob, json, os, time
import numpy as np

ROOT = "/root/autodl-fs/AI4S"
D = f"{ROOT}/data/processed"
_LOCAL = "/root/autodl-tmp/AI4S_data/processed"
if os.path.exists(os.path.join(_LOCAL, ".complete")): D = _LOCAL
WEIGHTS = f"{ROOT}/weights/yolo"

def write_yaml(organs, name):
    os.makedirs(f"{ROOT}/configs", exist_ok=True)
    y = f"{ROOT}/configs/det_{name}.yaml"
    def lst(split): return "[" + ", ".join(f"'{D}/det/{o}/{split}/images'" for o in organs) + "]"
    open(y, "w").write(f"path: {D}/det\ntrain: {lst('train')}\nval: {lst('val')}\ntest: {lst('test')}\nnames:\n  0: organoid\n")
    return y

def count_error(model, organs, imgsz, conf=0.25):
    errs, n_gt_all, n_pred_all = [], 0, 0
    for o in organs:
        for ip in sorted(glob.glob(f"{D}/det/{o}/test/images/*.png")):
            lp = ip.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
            n_gt = sum(1 for l in open(lp) if l.strip()) if os.path.exists(lp) else 0
            r = model.predict(ip, imgsz=imgsz, conf=conf, verbose=False, max_det=1000)[0]
            n_pred = len(r.boxes); errs.append(abs(n_pred - n_gt) / max(n_gt, 1)); n_gt_all += n_gt; n_pred_all += n_pred
    return dict(count_mape=float(np.mean(errs)), n_gt=n_gt_all, n_pred=n_pred_all, n_images=len(errs))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--organs", nargs="+", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--model", default=f"{WEIGHTS}/yolo11m.pt")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--eval_only", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    organs = args.organs or ([args.name] if args.name in ("intestine", "brain", "lung") else ["intestine", "brain", "lung"])
    name = args.name or (organs[0] if len(organs) == 1 else "_".join(organs))
    from ultralytics import YOLO
    yaml = write_yaml(organs, name)
    run_dir = f"{WEIGHTS}/{name}"
    t0 = time.time()
    if not args.eval_only:
        model = YOLO(args.model)
        model.train(data=yaml, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, seed=args.seed, deterministic=True,
                    project=WEIGHTS, name=name, exist_ok=True, plots=False, verbose=False, workers=8, single_cls=True)
    best = f"{run_dir}/weights/best.pt"
    model = YOLO(best)
    per_organ = {}
    for o in organs:
        y_o = write_yaml([o], f"{name}__eval_{o}")
        m = model.val(data=y_o, split="test", imgsz=args.imgsz, batch=args.batch, plots=False, verbose=False,
                      project=f"{ROOT}/results/yolo_val", name=f"{name}__{o}", exist_ok=True)
        per_organ[o] = dict(map50=float(m.box.map50), map50_95=float(m.box.map), precision=float(m.box.mp), recall=float(m.box.mr),
                            **count_error(model, [o], args.imgsz))
        print(o, json.dumps(per_organ[o]), flush=True)
    out = dict(args=vars(args), name=name, organs=organs, best=best, minutes=(time.time() - t0) / 60, per_organ=per_organ)
    os.makedirs(f"{ROOT}/results", exist_ok=True)
    json.dump(out, open(f"{ROOT}/results/e2_det_{name}_test.json", "w"), indent=2)
    print("saved", f"{ROOT}/results/e2_det_{name}_test.json", flush=True)

if __name__ == "__main__":
    main()
