#!/usr/bin/env python3
"""把 OrgLine 原始数据整理成统一格式，写到 data/processed/。

原则：
- 不修改 OrgLine 原始目录（唯一例外：删除 Thumbs.db 等垃圾文件）。
- 图像统一为 PNG；三通道且三通道完全相同的转为单通道灰度，否则保留 RGB 并在清单中标记。
- 分割掩码统一为 uint16 PNG 实例掩码（0 = 背景，1..N = 实例编号）。
- OrgDet 没有官方划分，按器官分层做 70/15/15 划分，随机种子 0，划分结果写入 splits/*.txt。
- 每张图一行清单（manifest.csv），包含来源数据集与像素物理尺寸（未知留空）。
可重复运行：已存在且大小非零的输出文件会跳过。
"""
import csv, glob, hashlib, json, os, random, sys, time
import numpy as np
from PIL import Image

ROOT = "/root/autodl-fs/AI4S/data"
SRC = f"{ROOT}/OrgLine"
DST = f"{ROOT}/processed"
LOG = "/root/autodl-fs/AI4S/logs/prepare_data.log"
JUNK = {"Thumbs.db", ".DS_Store", "desktop.ini"}
SEED = 0
WORKERS = 12

# OrgLine 子目录名 -> (标准器官名, 原始数据集, 像素尺寸 µm/px 或 None)
# 像素尺寸需从原始论文核实后填入 sources.json，此处先留空。
DET_ORGANS = {"Inestine": "intestine", "brain": "brain", "lung": "lung"}
SEG_ORGANS = {"Intestine": "intestine", "PDAC": "pdac", "brain": "brain", "colon": "colon"}
SOURCES = {
    ("det", "intestine"): "Tellu / OrgaQuant / OrgaSegment (via OrgLine)",
    ("det", "brain"): "Schroeter et al. 2024 brain organoid (via OrgLine)",
    ("det", "lung"): "DeepLUMEN (via OrgLine)",
    ("seg", "intestine"): "OrgaSegment (via OrgLine)",
    ("seg", "pdac"): "OrganoID / OrganoidNet (via OrgLine)",
    ("seg", "brain"): "Schroeter et al. 2024 brain organoid (via OrgLine)",
    ("seg", "colon"): "OrgaExtractor (via OrgLine)",
}

def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def remove_junk():
    n = 0
    for dp, dn, fn in os.walk(SRC):
        for f in fn:
            if f in JUNK:
                os.remove(os.path.join(dp, f)); n += 1; log(f"removed junk {os.path.join(dp, f)}")
    log(f"junk files removed: {n}")

def load_image(p):
    im = Image.open(p)
    mode = im.mode
    if mode in ("I;16", "I"):
        a = np.array(im).astype(np.float32)
        a = (255 * (a - a.min()) / max(1e-6, a.max() - a.min())).astype(np.uint8)
        return a, 1, "gray16->8"
    im = im.convert("RGB") if mode not in ("L", "RGB") else im
    a = np.array(im)
    if a.ndim == 2: return a, 1, "gray"
    if np.array_equal(a[..., 0], a[..., 1]) and np.array_equal(a[..., 1], a[..., 2]):
        return a[..., 0], 1, "rgb_identical->gray"
    return a, 3, "rgb"

def load_mask(p):
    if p.endswith(".npy"):
        a = np.load(p)
        if a.dtype == bool: a = a.astype(np.uint16)
        return a.astype(np.uint16)
    a = np.array(Image.open(p))
    if a.ndim == 3: a = a[..., 0]
    return a.astype(np.uint16)

def relabel(m):
    """把实例编号压缩成 1..N 连续整数。"""
    ids, inv = np.unique(m, return_inverse=True)
    out = inv.reshape(m.shape).astype(np.uint16)
    if ids[0] != 0: out += 1          # 没有背景值 0 时整体后移
    n = len(ids) - (1 if ids[0] == 0 else 0)
    return out, n

def save_png(a, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p) and os.path.getsize(p) > 0: return False
    Image.fromarray(a).save(p, compress_level=1)
    return True

def stem(p): return os.path.splitext(os.path.basename(p))[0]

def find_mask(mask_dir, s):
    for ext in (".png", ".tif", ".tiff", ".npy", ".jpg"):
        p = os.path.join(mask_dir, s + ext)
        if os.path.exists(p): return p
    c = glob.glob(os.path.join(mask_dir, s + ".*"))
    return c[0] if c else None

def seg_one(args):
    d, organ, split, ip = args
    s = stem(ip); mp = find_mask(f"{d}/masks", s)
    a, ch, conv = load_image(ip)
    out_img = f"{DST}/seg/{organ}/{split}/images/{s}.png"
    save_png(a, out_img)
    n_inst = ""; out_mask = ""; warn = ""
    if mp:
        m, n_inst = relabel(load_mask(mp))
        if m.shape != a.shape[:2]: warn = f"WARN mask/image shape mismatch {ip} {a.shape[:2]} vs {m.shape}"
        out_mask = f"{DST}/seg/{organ}/{split}/masks/{s}.png"
        save_png(m, out_mask)
    row = dict(task="seg", organ=organ, split=split, image_id=f"seg_{organ}_{split}_{s}",
               image=os.path.relpath(out_img, DST), mask=os.path.relpath(out_mask, DST) if out_mask else "",
               src_image=os.path.relpath(ip, SRC), src_mask=os.path.relpath(mp, SRC) if mp else "",
               width=a.shape[1], height=a.shape[0], channels=ch, conversion=conv,
               n_instances=n_inst, source=SOURCES[("seg", organ)], pixel_size_um="")
    return row, warn

def process_seg(rows):
    from concurrent.futures import ProcessPoolExecutor
    for sub, organ in SEG_ORGANS.items():
        for split in ("train", "val", "test"):
            d = f"{SRC}/InstanceSeg/InstanceSeg/{sub}/{split}"
            imgs = sorted(p for p in glob.glob(f"{d}/images/*") if os.path.basename(p) not in JUNK)
            with ProcessPoolExecutor(WORKERS) as ex:
                for row, warn in ex.map(seg_one, [(d, organ, split, ip) for ip in imgs], chunksize=4):
                    rows.append(row)
                    if warn: log(warn)
            log(f"seg {organ}/{split}: {len(imgs)} images")

def det_one(args):
    d, organ, split, ip = args
    s = stem(ip)
    a, ch, conv = load_image(ip)
    out_img = f"{DST}/det/{organ}/{split}/images/{s}.png"
    save_png(a, out_img)
    lp = f"{d}/labels/{s}.txt"; n_box = ""
    out_lab = f"{DST}/det/{organ}/{split}/labels/{s}.txt"
    if os.path.exists(lp):
        lines = [l for l in open(lp) if l.strip()]
        n_box = len(lines)
        os.makedirs(os.path.dirname(out_lab), exist_ok=True)
        if not os.path.exists(out_lab):
            with open(out_lab, "w") as f: f.writelines(lines)
    else:
        out_lab = ""
    return dict(task="det", organ=organ, split=split, image_id=f"det_{organ}_{s}",
                image=os.path.relpath(out_img, DST), mask=os.path.relpath(out_lab, DST) if out_lab else "",
                src_image=os.path.relpath(ip, SRC), src_mask=os.path.relpath(lp, SRC) if out_lab else "",
                width=a.shape[1], height=a.shape[0], channels=ch, conversion=conv,
                n_instances=n_box, source=SOURCES[("det", organ)], pixel_size_um="")

def process_det(rows):
    rng = random.Random(SEED)
    os.makedirs(f"{DST}/det/splits", exist_ok=True)
    for sub, organ in DET_ORGANS.items():
        d = f"{SRC}/OrgDet/OrgDet/{sub}/all"
        imgs = sorted(p for p in glob.glob(f"{d}/images/*") if os.path.basename(p) not in JUNK)
        idx = list(range(len(imgs))); rng.shuffle(idx)
        n = len(idx); n_tr = int(0.70 * n); n_va = int(0.15 * n)
        split_of = {}
        for k, i in enumerate(idx):
            split_of[i] = "train" if k < n_tr else ("val" if k < n_tr + n_va else "test")
        counts = {"train": 0, "val": 0, "test": 0}
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(WORKERS) as ex:
            for row in ex.map(det_one, [(d, organ, split_of[i], ip) for i, ip in enumerate(imgs)], chunksize=8):
                rows.append(row); counts[row["split"]] += 1
        for split in counts:
            with open(f"{DST}/det/splits/{organ}_{split}.txt", "w") as f:
                f.write("\n".join(f"det/{organ}/{split}/images/{stem(imgs[i])}.png" for i in range(n) if split_of[i] == split) + "\n")
        log(f"det {organ}: {counts} (seed {SEED})")

def main():
    os.makedirs(DST, exist_ok=True)
    log("=== prepare_data start")
    remove_junk()
    rows = []
    process_seg(rows)
    process_det(rows)
    cols = ["task", "organ", "split", "image_id", "image", "mask", "src_image", "src_mask", "width", "height",
            "channels", "conversion", "n_instances", "source", "pixel_size_um"]
    with open(f"{DST}/manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    # 汇总
    summ = {}
    for r in rows:
        k = f"{r['task']}/{r['organ']}/{r['split']}"
        s = summ.setdefault(k, {"images": 0, "instances": 0, "sizes": set(), "conversions": {}})
        s["images"] += 1; s["instances"] += int(r["n_instances"] or 0)
        s["sizes"].add(f"{r['width']}x{r['height']}"); s["conversions"][r["conversion"]] = s["conversions"].get(r["conversion"], 0) + 1
    for k, s in summ.items(): s["sizes"] = sorted(s["sizes"])
    with open(f"{DST}/summary.json", "w") as f: json.dump(summ, f, indent=2, ensure_ascii=False)
    with open(f"{DST}/sources.json", "w") as f:
        json.dump({"note": "pixel_size_um 需从各原始数据集论文核实后填写；填好后运行 fill_pixel_size.py 写回 manifest。",
                   "sources": {f"{k[0]}/{k[1]}": {"dataset": v, "pixel_size_um": None, "reference": ""} for k, v in SOURCES.items()}},
                  f, indent=2, ensure_ascii=False)
    log(f"manifest rows: {len(rows)}")
    log("=== prepare_data DONE")

if __name__ == "__main__":
    main()
