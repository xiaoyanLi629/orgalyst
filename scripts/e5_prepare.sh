#!/usr/bin/env bash
# E5 准备：从 processed 抽一小批测试图组成 8 个任务数据集（e5/data/），并用命令行路径算出参考值（e5/ref/refs.json）。
set -e
cd /root/autodl-fs/AI4S
P=/root/autodl-tmp/AI4S_data/processed; [ -f $P/.complete ] || P=/root/autodl-fs/AI4S/data/processed
E=/root/autodl-fs/AI4S/e5; rm -rf $E/data $E/ref; mkdir -p $E/data/{single,intestine,brain_um,lung,groups,series,pdac,mixed,empty} $E/ref
I=$P/seg/intestine/test/images; B=$P/seg/brain/test/images; L=$P/det/lung/test/images; D=$P/seg/pdac/test/images
ls $I/*.png | head -1 | xargs -I{} cp {} $E/data/single/
ls $I/*.png | head -4 | xargs -I{} cp {} $E/data/intestine/
for s in org01 org02 org03; do cp $B/${s}_wt2D_d16_LabA.png $E/data/brain_um/; done
ls "$L"/*.png | head -5 | while read f; do cp "$f" $E/data/lung/; done
for s in org01 org02 org03; do cp $B/${s}_wt2D_d30_LabA.png $E/data/groups/; done
for s in org17 org18 org19; do cp $B/${s}_TH2-7_d30_LabA.png $E/data/groups/; done
cp $B/org01_wt2D_d*_LabA*.png $E/data/series/
ls $D/*.png | head -3 | xargs -I{} cp {} $E/data/pdac/
ls $I/*.png | head -2 | xargs -I{} cp {} $E/data/mixed/; cp $B/org02_wt2D_d16_LabA.png $B/org03_wt2D_d16_LabA.png $E/data/mixed/
( echo "image_id,group"; for s in org01 org02 org03; do echo "${s}_wt2D_d30_LabA,wt2D"; done; for s in org17 org18 org19; do echo "${s}_TH2-7_d30_LabA,TH2-7"; done ) > $E/data/groups/groups.csv
( echo "image_id,pixel_size_um,subject,timepoint,group"; for f in $E/data/series/*.png; do b=$(basename $f .png); t=$(echo $b | sed -E "s/.*_d([0-9]+)_.*/\1/"); echo "$b,3.1646,org01,$t,wt2D"; done ) > $E/data/series/meta.csv
echo "data ready"; find $E/data -name "*.png" | wc -l
export CELLPOSE_LOCAL_MODELS_PATH=/root/autodl-tmp/.cellpose/models YOLO_OFFLINE=1
PY=.venv/bin/python
$PY -m orgalyst analyze --organ intestine --images "$E/data/single/*.png" --out $E/ref --name single --no-report >/dev/null 2>&1
$PY -m orgalyst analyze --organ intestine --images "$E/data/intestine/*.png" --out $E/ref --name intestine --qc --no-report >/dev/null 2>&1
$PY -m orgalyst analyze --organ brain --images "$E/data/brain_um/*.png" --out $E/ref --name brain_um --pixel-size 3.1646 --no-report >/dev/null 2>&1
$PY -m orgalyst count --organ lung --images "$E/data/lung/*.png" --out $E/ref --name lung >/dev/null 2>&1
$PY -m orgalyst analyze --organ brain --images "$E/data/groups/*.png" --out $E/ref --name groups --pixel-size 3.1646 --no-report >/dev/null 2>&1
$PY -m orgalyst analyze --organ brain --images "$E/data/series/*.png" --out $E/ref --name series --meta $E/data/series/meta.csv --no-report >/dev/null 2>&1
$PY -m orgalyst track --run $(ls -d $E/ref/series_* | tail -1) --meta $E/data/series/meta.csv >/dev/null 2>&1
$PY -m orgalyst analyze --organ pdac --images "$E/data/pdac/*.png" --out $E/ref --name pdac --no-report >/dev/null 2>&1
$PY -m orgalyst analyze --organ generic --images "$E/data/pdac/*.png" --out $E/ref --name pdac_generic --no-report >/dev/null 2>&1
$PY - <<'PYEOF'
import json, glob, os, pandas as pd, numpy as np
E="/root/autodl-fs/AI4S/e5"
def run(name): return sorted(glob.glob(f"{E}/ref/{name}_[0-9]*"))[-1]
def summ(name): return json.load(open(os.path.join(run(name), "tables", "summary.json")))
refs = {}
s = summ("single"); refs["single"] = dict(n=s["overall"]["n"], n_all=int(pd.read_csv(os.path.join(run("single"),"tables","features.csv")).shape[0]), diam_median=s["overall"]["equiv_diameter_px"]["median"])
s = summ("intestine"); f = pd.read_csv(os.path.join(run("intestine"),"tables","features.csv"))
refs["intestine"] = dict(n=s["overall"]["n"], n_all=int(len(f)), per_image={k: v["n"] for k, v in s["per_image"].items()}, n_low_confidence=int(f["low_confidence"].sum()) if "low_confidence" in f else None)
s = summ("brain_um"); refs["brain_um"] = dict(area_um2_median=s["overall"]["area_um2"]["median"], per_image={k: (v.get("area_um2") or {}).get("median") for k, v in s["per_image"].items()})
s = summ("lung"); refs["lung"] = dict(per_image=s["per_image"], total=s["total"])
from orgalyst.compare import compare_groups, attach_groups
f = pd.read_csv(os.path.join(run("groups"),"tables","features.csv")); g = pd.read_csv(f"{E}/data/groups/groups.csv")
f = attach_groups(f, g)
res = compare_groups(f, metrics=["area_um2"], make_figures=False)
refs["groups"] = dict(raw=json.loads(json.dumps(res, default=lambda o: float(o) if hasattr(o, "__float__") else str(o))))
med = f[~f["touches_border"].fillna(False).astype(bool)].groupby("group")["area_um2"].median().to_dict(); refs["groups"]["median_by_group"] = {k: float(v) for k, v in med.items()}; refs["groups"]["larger"] = max(med, key=med.get)
gr = pd.read_csv(os.path.join(run("series"),"tables","growth.csv")).sort_values("timepoint")
refs["series"] = dict(first=dict(t=float(gr.timepoint.iloc[0]), v=float(gr.value.iloc[0])), last=dict(t=float(gr.timepoint.iloc[-1]), v=float(gr.value.iloc[-1])), fold=float(gr.value.iloc[-1]/gr.value.iloc[0]), n_points=int(len(gr)))
refs["pdac"] = dict(n=summ("pdac")["overall"]["n"], n_all=int(pd.read_csv(os.path.join(run("pdac"),"tables","features.csv")).shape[0]), n_generic_all=int(pd.read_csv(os.path.join(run("pdac_generic"),"tables","features.csv")).shape[0]))
json.dump(refs, open(f"{E}/ref/refs.json", "w"), indent=1, ensure_ascii=False); print(json.dumps(refs, ensure_ascii=False)[:1500])
PYEOF
echo "=== E5 prepare DONE $(date)"
