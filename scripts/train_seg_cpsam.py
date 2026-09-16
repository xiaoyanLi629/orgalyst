#!/usr/bin/env python3
"""Cellpose-SAM 微调（cellpose 4）。用法同 train_seg_cellpose.py，但在 cellpose4 环境运行：
  /root/autodl-tmp/cellpose4-env/bin/python scripts/train_seg_cpsam.py --organs pdac [--epochs 100 --batch_size 2 --lr 1e-5 --max_per_organ 500]
权重存 weights/cpsam_ft/<name>/<name>。ViT-L 骨干，显存约 batch 2 × 256² ≈ 12 GB。
"""
import argparse, glob, json, os, time
import numpy as np
from PIL import Image
ROOT = "/root/autodl-fs/AI4S"; D = f"{ROOT}/data/processed"
_LOCAL = "/root/autodl-tmp/AI4S_data/processed"
if os.path.exists(os.path.join(_LOCAL, ".complete")): D = _LOCAL

def load_split(organ, split):
    X, Y = [], []
    for ip in sorted(glob.glob(f"{D}/seg/{organ}/{split}/images/*.png")):
        mp = f"{D}/seg/{organ}/{split}/masks/{os.path.basename(ip)}"
        if not os.path.exists(mp): continue
        a = np.array(Image.open(ip)); a = a.mean(axis=2).astype(np.uint8) if a.ndim == 3 else a
        m = np.array(Image.open(mp)).astype(np.int32)
        if m.max() == 0: continue
        X.append(a); Y.append(m)
    return X, Y

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--organs", nargs="+", required=True); ap.add_argument("--name", default=None)
    ap.add_argument("--epochs", type=int, default=100); ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--batch_size", type=int, default=2); ap.add_argument("--weight_decay", type=float, default=0.1)
    ap.add_argument("--max_val", type=int, default=60); ap.add_argument("--max_per_organ", type=int, default=0); ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    name = args.name or (args.organs[0] if len(args.organs) == 1 else "_".join(args.organs))
    out_dir = f"{ROOT}/weights/cpsam_ft/{name}"; os.makedirs(out_dir, exist_ok=True)
    import torch
    from cellpose import models, train
    torch.manual_seed(args.seed); rng = np.random.RandomState(args.seed)
    tr_x, tr_y, va_x, va_y = [], [], [], []
    for o in args.organs:
        x, y = load_split(o, "train")
        if args.max_per_organ and len(x) > args.max_per_organ:
            idx = sorted(rng.choice(len(x), args.max_per_organ, replace=False)); x = [x[i] for i in idx]; y = [y[i] for i in idx]
        tr_x += x; tr_y += y; x, y = load_split(o, "val"); va_x += x; va_y += y
    if len(va_x) > args.max_val:
        idx = rng.choice(len(va_x), args.max_val, replace=False); va_x = [va_x[i] for i in idx]; va_y = [va_y[i] for i in idx]
    print(f"[{name}] train {len(tr_x)} imgs, val {len(va_x)}; organs={args.organs}", flush=True)
    model = models.CellposeModel(gpu=torch.cuda.is_available())
    t0 = time.time()
    model_path, train_losses, test_losses = train.train_seg(model.net, train_data=tr_x, train_labels=tr_y, test_data=(va_x or None), test_labels=(va_y or None),
        learning_rate=args.lr, weight_decay=args.weight_decay, n_epochs=args.epochs, batch_size=args.batch_size, save_path=out_dir, model_name=name, min_train_masks=1)
    dt = time.time() - t0
    src = os.path.join(out_dir, "models", name)
    if os.path.exists(src):
        import shutil; shutil.copy(src, os.path.join(out_dir, name))
    json.dump(dict(args=vars(args), name=name, n_train=len(tr_x), n_val=len(va_x), seconds=dt, model_path=str(model_path),
                   train_losses=[float(v) for v in np.ravel(train_losses)], val_losses=[float(v) for v in np.ravel(test_losses)] if test_losses is not None else None),
              open(f"{out_dir}/train_log.json", "w"), indent=2)
    print(f"[{name}] done in {dt/60:.1f} min → {model_path}", flush=True)

if __name__ == "__main__":
    main()
