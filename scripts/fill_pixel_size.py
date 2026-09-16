#!/usr/bin/env python3
"""按 sources.json 的规则把 pixel_size_um 写回 manifest.csv（只填 verified=true 的来源）。"""
import csv, json
D = "/root/autodl-fs/AI4S/data/processed"
src = json.load(open(f"{D}/sources.json"))["sources"]
rows = list(csv.DictReader(open(f"{D}/manifest.csv")))
by_w = {int(k): v for k, v in src["brain"]["pixel_size_um_by_width"].items()}
n = 0
for r in rows:
    r["pixel_size_um"] = ""
    if r["organ"] == "brain" and int(r["width"]) in by_w:
        r["pixel_size_um"] = f"{by_w[int(r['width'])]:.4f}"; n += 1
with open(f"{D}/manifest.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(f"filled pixel_size_um for {n} brain rows; others left empty (pixel units only)")
