"""命令行入口（不依赖大模型的可复现路径）：
  python -m orgalyst analyze --organ brain --images DIR_OR_GLOB --out runs [--pixel-size 3.1646] [--diam-mode model|sizemodel]
  python -m orgalyst report --run runs/analysis_<id>
产物：runs/analysis_<id>/{manifest.json, report.html, tables/features.csv, tables/summary.json, masks/*.png, overlays/*.png}
"""
import argparse, glob, json, os
import numpy as np
from PIL import Image

def cmd_analyze(a):
    from .segment import Segmenter, to_gray
    from .morphometry import measure, summarize
    from .overlay import overlay
    from .run import Run
    from .qc import image_qc, tta_agreement, flag_low_confidence
    import pandas as pd
    paths = sorted(p for pat in a.images for p in (glob.glob(pat) if any(c in pat for c in "*?[") else
                   (glob.glob(os.path.join(pat, "*")) if os.path.isdir(pat) else [pat])))
    paths = [p for p in paths if p.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff"))]
    if a.limit: paths = paths[:a.limit]
    meta = None
    if a.meta:
        meta = pd.read_csv(a.meta); meta["image_id"] = meta["image_id"].astype(str).str.replace(r"\.[A-Za-z0-9]+$", "", regex=True)
    run = Run(a.out, name=a.name)
    run.manifest["params"] = dict(organ=a.organ, diam_mode=a.diam_mode, pixel_size_um=a.pixel_size, flow_threshold=a.flow_threshold,
                                  cellprob_threshold=a.cellprob_threshold, exclude_border=not a.keep_border, qc=a.qc, tta_k=a.tta_k)
    seg = Segmenter(a.organ, diam_mode=a.diam_mode)
    run.manifest["models"]["segmentation"] = dict(id=seg.model_id, organ=seg.organ, diam_mode=seg.diam_mode, diam_labels=seg.model_diam)
    run.log(f"segmenter {seg.model_id} ({seg.organ}, diam_mode={seg.diam_mode}); {len(paths)} images")
    tables, per_image, qc_rows = [], {}, []
    for p in paths:
        img = np.array(Image.open(p)); gray = to_gray(img); image_id = os.path.splitext(os.path.basename(p))[0]
        masks, info = seg.run(img, a.flow_threshold, a.cellprob_threshold)
        run.add_input(p, image_id=image_id, shape=list(img.shape), **{k: info[k] for k in ("diameter_px", "n_instances")})
        px = a.pixel_size
        if meta is not None and "pixel_size_um" in meta:
            row = meta.loc[meta["image_id"] == image_id, "pixel_size_um"]
            if len(row) and pd.notna(row.iloc[0]): px = float(row.iloc[0])
        df = measure(masks, gray, px, image_id)
        if a.qc:
            q = image_qc(gray); q["image_id"] = image_id; q["n_instances"] = int(masks.max())
            if masks.max() > 0:
                agr = tta_agreement(seg, img, masks, k=a.tta_k, flow_threshold=a.flow_threshold, cellprob_threshold=a.cellprob_threshold)
                df["tta_agreement"] = agr[df["label"].values - 1]; df = flag_low_confidence(df)
                q["low_confidence_frac"] = float(df["low_confidence"].mean())
            qc_rows.append(q)
        tables.append(df)
        per_image[image_id] = summarize(df, exclude_border=not a.keep_border)
        Image.fromarray(masks).save(run.path("masks", image_id + ".png"))
        if not a.no_overlay: overlay(img, masks).save(run.path("overlays", image_id + ".png"))
        run.log(f"{image_id}: {info['n_instances']} instances (diam {info['diameter_px']:.1f} px)" if info["diameter_px"] else f"{image_id}: {info['n_instances']} instances")
    feats = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    if meta is not None and len(feats):
        extra = [c for c in meta.columns if c not in ("pixel_size_um",) and c not in feats.columns]
        feats = feats.merge(meta[["image_id"] + extra], on="image_id", how="left")
        meta.to_csv(run.path("tables", "meta.csv"), index=False); run.add_output(run.path("tables", "meta.csv"), "meta")
    feats.to_csv(run.path("tables", "features.csv"), index=False); run.add_output(run.path("tables", "features.csv"), "features")
    if qc_rows:
        pd.DataFrame(qc_rows).to_csv(run.path("tables", "qc.csv"), index=False); run.add_output(run.path("tables", "qc.csv"), "qc")
    overall = summarize(feats, exclude_border=not a.keep_border) if len(feats) else dict(n=0)
    json.dump(dict(overall=overall, per_image=per_image), open(run.path("tables", "summary.json"), "w"), indent=2)
    run.add_output(run.path("tables", "summary.json"), "summary")
    m = run.save()
    if not a.no_report:
        from .report import build_report
        rp = build_report(run.dir, title=a.title); run.add_output(rp, "report"); run.save(); run.log(f"report → {rp}")
    run.log(f"done → {run.dir}")
    return run.dir

def cmd_count(a):
    """检测计数（YOLO）：每张图一行 n_detected；不做分割，速度快，适合只问“有几个”的场景。"""
    from .detect import Detector, draw_boxes
    from .run import Run
    import pandas as pd
    paths = sorted(p for pat in a.images for p in (glob.glob(pat) if any(c in pat for c in "*?[") else
                   (glob.glob(os.path.join(pat, "*")) if os.path.isdir(pat) else [pat])))
    paths = [p for p in paths if p.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff"))]
    if a.limit: paths = paths[:a.limit]
    run = Run(a.out, name=a.name)
    det = Detector(a.organ, conf=a.conf)
    run.manifest["params"] = dict(organ=a.organ, conf=det.conf, imgsz=det.imgsz, task="count")
    run.manifest["models"]["detection"] = dict(id=det.model_id, model=det.model_name, conf=det.conf, imgsz=det.imgsz)
    run.log(f"detector {det.model_id} (organ={det.organ}, conf={det.conf}); {len(paths)} images")
    rows, box_rows = [], []
    for p in paths:
        img = np.array(Image.open(p)); image_id = os.path.splitext(os.path.basename(p))[0]
        r = det.run(img)
        run.add_input(p, image_id=image_id, shape=list(img.shape), n_detected=r["n"])
        rows.append(dict(image_id=image_id, n_detected=r["n"], conf_threshold=r["conf"], mean_conf=float(r["boxes"][:, 4].mean()) if r["n"] else None))
        for x1, y1, x2, y2, c in r["boxes"]: box_rows.append(dict(image_id=image_id, x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), conf=float(c)))
        if not a.no_overlay: draw_boxes(img, r["boxes"]).save(run.path("overlays", image_id + ".png"))
        run.log(f"{image_id}: {r['n']} detected")
    counts = pd.DataFrame(rows); counts.to_csv(run.path("tables", "counts.csv"), index=False); run.add_output(run.path("tables", "counts.csv"), "counts")
    pd.DataFrame(box_rows).to_csv(run.path("tables", "boxes.csv"), index=False); run.add_output(run.path("tables", "boxes.csv"), "boxes")
    summ = dict(task="count", n_images=len(rows), total=int(counts["n_detected"].sum()) if len(rows) else 0,
                per_image_median=float(counts["n_detected"].median()) if len(rows) else 0, conf_threshold=det.conf,
                per_image={r["image_id"]: r["n_detected"] for r in rows})
    json.dump(summ, open(run.path("tables", "summary.json"), "w"), indent=2); run.add_output(run.path("tables", "summary.json"), "summary")
    run.save(); run.log(f"done → {run.dir}")
    return run.dir

def cmd_track(a):
    import pandas as pd
    from .track import parse_name, growth_table, group_curves, plot_growth
    from .report import CSS
    import html as _h
    feats = pd.read_csv(os.path.join(a.run, "tables", "features.csv"))
    if a.meta: meta = pd.read_csv(a.meta); meta["image_id"] = meta["image_id"].astype(str).str.replace(r"\.[A-Za-z0-9]+$", "", regex=True)
    elif os.path.exists(os.path.join(a.run, "tables", "meta.csv")) and not a.pattern: meta = pd.read_csv(os.path.join(a.run, "tables", "meta.csv"))
    else: meta = parse_name(feats["image_id"].unique(), a.pattern) if a.pattern else parse_name(feats["image_id"].unique())
    if "timepoint" not in meta or meta["timepoint"].isna().all(): raise SystemExit("元数据里没有 timepoint，无法做生长曲线（给 --meta 或 --pattern）")
    g = growth_table(feats, meta, metric=a.metric); c = group_curves(g)
    g.to_csv(os.path.join(a.run, "tables", "growth.csv"), index=False); c.to_csv(os.path.join(a.run, "tables", "growth_curves.csv"), index=False)
    label = g["metric"].iloc[0]; img = plot_growth(g, c, label)
    H = [f"<title>生长曲线</title><style>{CSS}</style><main><div class='eyebrow'>Orgalyst · track</div><h1>生长曲线</h1>",
         f"<p class='sub'>指标 {label}；细线为每个个体，粗线为组均值；相对第一个时间点的倍数见 tables/growth.csv。</p><img src='{img}' style='max-width:100%'>",
         "<div class='tw'><table><tr><th>组</th><th class='n'>时间点</th><th class='n'>均值</th><th class='n'>中位数</th><th class='n'>标准差</th><th class='n'>n</th></tr>"]
    for _, r in c.iterrows():
        H.append(f"<tr><td>{_h.escape(str(r.get('group','')))}</td><td class='n'>{r['timepoint']:g}</td><td class='n'>{r['mean']:,.1f}</td><td class='n'>{r['median']:,.1f}</td><td class='n'>{0 if r['std'] != r['std'] else r['std']:,.1f}</td><td class='n'>{int(r['n'])}</td></tr>")
    H.append("</table></div></main>")
    out = os.path.join(a.run, "growth.html"); open(out, "w", encoding="utf-8").write("\n".join(H)); print("growth →", out)

def cmd_report(a):
    from .report import build_report
    print("report →", build_report(a.run, title=a.title, max_thumbs=a.max_thumbs))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="orgalyst")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("analyze", help="分割 + 形态测量，生成可追溯的 run 目录")
    s.add_argument("--organ", default="generic"); s.add_argument("--images", nargs="+", required=True)
    s.add_argument("--out", default="runs"); s.add_argument("--name", default="analysis")
    s.add_argument("--pixel-size", type=float, default=None, dest="pixel_size"); s.add_argument("--diam-mode", default=None, dest="diam_mode")
    s.add_argument("--flow-threshold", type=float, default=0.4, dest="flow_threshold"); s.add_argument("--cellprob-threshold", type=float, default=0.0, dest="cellprob_threshold")
    s.add_argument("--keep-border", action="store_true", dest="keep_border"); s.add_argument("--no-overlay", action="store_true", dest="no_overlay")
    s.add_argument("--limit", type=int, default=0); s.add_argument("--no-report", action="store_true", dest="no_report"); s.add_argument("--title", default=None)
    s.add_argument("--meta", default=None, help="按图像元数据 CSV：image_id[,pixel_size_um,subject,timepoint,group,...]")
    s.add_argument("--qc", action="store_true", help="图像级质控 + 实例级 TTA 一致性（约 K 倍推理时间）"); s.add_argument("--tta-k", type=int, default=4, dest="tta_k")
    c = sub.add_parser("count", help="检测计数（YOLO 联合模型，阈值按器官标定），不分割")
    c.add_argument("--organ", default="generic"); c.add_argument("--images", nargs="+", required=True)
    c.add_argument("--out", default="runs"); c.add_argument("--name", default="count"); c.add_argument("--conf", type=float, default=None)
    c.add_argument("--limit", type=int, default=0); c.add_argument("--no-overlay", action="store_true", dest="no_overlay")
    r = sub.add_parser("report", help="把已有 run 目录渲染成 HTML 报告")
    r.add_argument("--run", required=True); r.add_argument("--title", default=None); r.add_argument("--max-thumbs", type=int, default=12, dest="max_thumbs")
    t = sub.add_parser("track", help="按元数据（subject/timepoint/group）生成生长曲线")
    t.add_argument("--run", required=True); t.add_argument("--meta", default=None); t.add_argument("--pattern", default=None, help="从 image_id 提取元数据的正则（命名组 subject/timepoint/group）")
    t.add_argument("--metric", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "analyze": cmd_analyze(a)
    elif a.cmd == "report": cmd_report(a)
    elif a.cmd == "track": cmd_track(a)
    elif a.cmd == "count": cmd_count(a)

if __name__ == "__main__":
    main()
