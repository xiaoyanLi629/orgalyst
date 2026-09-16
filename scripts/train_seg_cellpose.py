#!/usr/bin/env python3
"""Cellpose cyto3 微调（E1）：在 processed/seg/<organ>/train 上训练，val 上做早停参考，权重存 weights/cellpose_ft/<name>/。
用法：
  python train_seg_cellpose.py --organs intestine            # 单器官专用模型
  python train_seg_cellpose.py --organs intestine pdac brain colon --name all   # 跨器官联合模型
  python train_seg_cellpose.py --organs pdac brain colon --name loo_intestine   # 留一器官（不含 intestine）
说明：
  - 图像读为灰度（RGB 取均值），掩码为 uint16 实例编号；Cellpose 训练时按每张图的真值直径把目标缩放到 diam_mean=30。
  - 大图（2048²）直接喂给 cellpose 的训练器（它按 224 或 bsize 随机裁剪），不必预先切块。
  - 训练记录写 weights/cellpose_ft/<name>/train_log.json（每轮 train/val loss 由 cellpose 打印，这里只记配置与耗时）。
"""
import argparse, glob, json, os, time
import numpy as np
from PIL import Image

ROOT = "/root/autodl-fs/AI4S"
D = f"{ROOT}/data/processed"
_LOCAL = "/root/autodl-tmp/AI4S_data/processed"          # 本地盘缓存（scripts/cache_data_local.sh 生成），存在且完整则优先
if os.path.exists(os.path.join(_LOCAL, ".complete")): D = _LOCAL

def load_split(organ, split):
    imgs, masks = [], []
    for ip in sorted(glob.glob(f"{D}/seg/{organ}/{split}/images/*.png")):
        mp = f"{D}/seg/{organ}/{split}/masks/{os.path.basename(ip)}"
        if not os.path.exists(mp): continue
        a = np.array(Image.open(ip))
        if a.ndim == 3: a = a.mean(axis=2).astype(np.uint8)
        m = np.array(Image.open(mp)).astype(np.int32)
        if m.max() == 0: continue
        imgs.append(a); masks.append(m)
    return imgs, masks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--organs", nargs="+", required=True)
    ap.add_argument("--name", default=None, help="模型名，默认取单器官名")
    ap.add_argument("--pretrained", default="cyto3")
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--lr", type=float, default=0.005)
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--weight_decay", type=float, default=1e-5)
    ap.add_argument("--max_val", type=int, default=100, help="验证集最多用多少张（大图省内存）")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max_per_organ", type=int, default=0, help="每个器官最多取多少张训练图（0=不限）。容器内存上限 62 GB，cellpose 把全部图与流场常驻内存，四器官联合约 2400 张会 OOM；500/器官约 35 GB")
    args = ap.parse_args()
    name = args.name or (args.organs[0] if len(args.organs) == 1 else "_".join(args.organs))
    out_dir = f"{ROOT}/weights/cellpose_ft/{name}"; os.makedirs(out_dir, exist_ok=True)

    import torch
    from cellpose import models, train, io
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    tr_x, tr_y, va_x, va_y = [], [], [], []
    rng = np.random.RandomState(args.seed)
    for o in args.organs:
        x, y = load_split(o, "train")
        if args.max_per_organ and len(x) > args.max_per_organ:
            idx = sorted(rng.choice(len(x), args.max_per_organ, replace=False)); x = [x[i] for i in idx]; y = [y[i] for i in idx]
            print(f"[{name}] {o}: subsampled train to {len(x)}", flush=True)
        tr_x += x; tr_y += y
        x, y = load_split(o, "val"); va_x += x; va_y += y
    if len(va_x) > args.max_val:
        idx = rng.choice(len(va_x), args.max_val, replace=False); va_x = [va_x[i] for i in idx]; va_y = [va_y[i] for i in idx]
    print(f"[{name}] train {len(tr_x)} imgs, val {len(va_x)} imgs; organs={args.organs}", flush=True)

    model = models.CellposeModel(gpu=torch.cuda.is_available(), pretrained_model=args.pretrained)
    t0 = time.time()
    model_path, train_losses, test_losses = train.train_seg(
        model.net, train_data=tr_x, train_labels=tr_y, test_data=(va_x or None), test_labels=(va_y or None),
        channels=[0, 0], normalize=True, weight_decay=args.weight_decay, learning_rate=args.lr,
        n_epochs=args.epochs, batch_size=args.batch_size, save_path=out_dir, model_name=name,
        min_train_masks=1, SGD=False, rescale=True)
    dt = time.time() - t0
    if not va_x: print(f"[{name}] no validation masks available (e.g. colon/val has none); trained without val", flush=True)
    # cellpose 把权重存在 save_path/models/<name>；统一复制到 out_dir/<name>
    src = os.path.join(out_dir, "models", name)
    if os.path.exists(src):
        import shutil; shutil.copy(src, os.path.join(out_dir, name))
    diam_labels = float(model.net.diam_labels.item()) if hasattr(model.net, "diam_labels") else None
    json.dump(dict(args=vars(args), name=name, n_train=len(tr_x), n_val=len(va_x), seconds=dt,
                   model_path=str(model_path), diam_labels=diam_labels,
                   train_losses=[float(v) for v in np.ravel(train_losses)],
                   val_losses=[float(v) for v in np.ravel(test_losses)] if test_losses is not None else None),
              open(f"{out_dir}/train_log.json", "w"), indent=2)
    print(f"[{name}] done in {dt/60:.1f} min → {model_path}; diam_labels={diam_labels}", flush=True)

if __name__ == "__main__":
    main()
