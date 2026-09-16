"""报告生成：把一个 run 目录渲染成单文件 HTML（图表内嵌 base64，双击可开，不依赖网络）。
用法：python -m orgalyst report --run runs/analysis_xxx [--title ...]
内容：概览指标 → 每图计数表 → 面积/直径/圆度分布图 → 叠加图缩略 → 方法学说明（模板生成，不经大模型） → 溯源（输入 MD5、模型哈希、参数、版本）。
"""
from __future__ import annotations
import base64, glob, html, io, json, os
import numpy as np
import pandas as pd

CSS = """
:root{--paper:#F6F8F7;--ink:#1B262C;--muted:#5A6A70;--rule:#D3DAD7;--panel:#EDF1EF;--accent:#0E7A6C;--accent-soft:#D9EEE9;--warn:#9A6A12;--warn-soft:#F5E9CF}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#131A1D;--ink:#E3E9E6;--muted:#98A7AB;--rule:#2C3A3F;--panel:#1B2529;--accent:#3FB59F;--accent-soft:#173430;--warn:#D9A648;--warn-soft:#3A2E14}}
:root[data-theme="dark"]{--paper:#131A1D;--ink:#E3E9E6;--muted:#98A7AB;--rule:#2C3A3F;--panel:#1B2529;--accent:#3FB59F;--accent-soft:#173430;--warn:#D9A648;--warn-soft:#3A2E14}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:ui-sans-serif,-apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;font-size:15px;line-height:1.7;padding-inline:16px;padding-block:0 48px}
main{max-width:900px;margin:0 auto;padding-top:32px}h1{font-family:"Songti SC","STSong",serif;font-size:30px;margin:0 0 6px;line-height:1.25}h2{font-family:"Songti SC","STSong",serif;font-size:21px;margin:40px 0 12px;padding-top:6px;border-top:1px solid var(--rule)}
.eyebrow{font-family:ui-monospace,Menlo,monospace;font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}.sub{color:var(--muted);margin:0 0 18px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0 6px}.tile{border:1px solid var(--rule);border-radius:4px;padding:10px 12px;background:var(--panel)}.tile .k{font-size:12px;color:var(--muted)}.tile .v{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}.tile .u{font-size:12px;color:var(--muted)}
.tw{overflow-x:auto;border:1px solid var(--rule);border-radius:4px;margin:10px 0 16px}table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:520px}th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule);vertical-align:top}th{background:var(--panel);font-weight:600;white-space:nowrap}tr:last-child td{border-bottom:0}td.n{font-family:ui-monospace,Menlo,monospace;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}.figs img,.thumbs img{max-width:100%;border:1px solid var(--rule);border-radius:4px}.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}.thumbs figcaption{font-size:12px;color:var(--muted);margin-top:4px}
.callout{border-left:3px solid var(--warn);background:var(--warn-soft);padding:10px 14px;border-radius:0 4px 4px 0;margin:12px 0}code{font-family:ui-monospace,Menlo,monospace;font-size:.9em;background:var(--panel);padding:1px 5px;border-radius:3px}.small{font-size:12.5px;color:var(--muted)}p{margin:0 0 12px}
"""

def _b64png(fig) -> str:
    import matplotlib, warnings; matplotlib.use("Agg"); warnings.filterwarnings("ignore", message="Glyph")
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=110, bbox_inches="tight", facecolor="white"); import matplotlib.pyplot as plt; plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def _img_b64(path, max_side=480) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGB"); im.thumbnail((max_side, max_side)); buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

def _hist(series, title, unit):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4.2, 2.8)); ax.hist(series.dropna(), bins=30, color="#0E7A6C", alpha=.85)
    ax.set_title(title, fontsize=11); ax.set_xlabel(unit, fontsize=9); ax.set_ylabel("count", fontsize=9); ax.tick_params(labelsize=8)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    return _b64png(fig)

def _fmt(x, nd=1):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else (f"{x:,.{nd}f}" if isinstance(x, (int, float, np.floating)) else str(x))

def build_report(run_dir: str, title: str | None = None, max_thumbs: int = 12) -> str:
    m = json.load(open(os.path.join(run_dir, "manifest.json")))
    feats = pd.read_csv(os.path.join(run_dir, "tables", "features.csv")) if os.path.exists(os.path.join(run_dir, "tables", "features.csv")) else pd.DataFrame()
    summ = json.load(open(os.path.join(run_dir, "tables", "summary.json")))
    ov, per = summ.get("overall", {}), summ.get("per_image", {})
    seg = m.get("models", {}).get("segmentation", {}); prm = m.get("params", {}); ver = m.get("versions", {})
    has_um = "area_um2" in feats and feats["area_um2"].notna().any()
    title = title or f"类器官形态学分析报告 · {m.get('name','analysis')}"
    H = []
    H.append(f"<title>{html.escape(title)}</title><style>{CSS}</style><main>")
    H.append(f"<div class='eyebrow'>Orgalyst · run {html.escape(m['run_id'])}</div><h1>{html.escape(title)}</h1>")
    H.append(f"<p class='sub'>生成于 {m.get('created','')}，{len(m.get('inputs',[]))} 张图像，器官类型 {html.escape(str(seg.get('organ','')))}，分割模型 <code>{html.escape(str(seg.get('id','')))}</code></p>")
    # 概览
    H.append("<h2>概览</h2><div class='tiles'>")
    tiles = [("类器官总数", ov.get("n", 0), ""), ("排除贴边实例", ov.get("n_border_excluded", 0), "")]
    if has_um: tiles += [("面积中位数", _fmt(ov.get("area_um2", {}).get("median")), "µm²"), ("等效直径中位数", _fmt(ov.get("equiv_diameter_um", {}).get("median")), "µm")]
    else: tiles += [("面积中位数", _fmt(ov.get("area_px", {}).get("median"), 0), "px²"), ("等效直径中位数", _fmt(ov.get("equiv_diameter_px", {}).get("median")), "px")]
    tiles += [("圆度中位数", _fmt(ov.get("circularity", {}).get("median"), 3), "0–1"), ("实心度中位数", _fmt(ov.get("solidity", {}).get("median"), 3), "0–1")]
    for k, v, u in tiles: H.append(f"<div class='tile'><div class='k'>{k}</div><div class='v'>{v}</div><div class='u'>{u}</div></div>")
    H.append("</div>")
    if not has_um: H.append("<div class='callout'>本次运行未提供像素物理尺寸，所有长度与面积以像素为单位。要得到微米结果，请在分析时指定 <code>--pixel-size</code>（µm/px）。</div>")
    # 每图表
    H.append("<h2>逐图结果</h2><div class='tw'><table><tr><th>图像</th><th class='n'>实例数</th><th class='n'>贴边排除</th><th class='n'>面积中位数</th><th class='n'>直径中位数</th><th class='n'>圆度中位数</th><th class='n'>直径提示 (px)</th></tr>")
    diam_by = {i["image_id"]: i.get("diameter_px") for i in m.get("inputs", [])}
    for iid, s in per.items():
        ak, dk = ("area_um2", "equiv_diameter_um") if has_um and "area_um2" in s else ("area_px", "equiv_diameter_px")
        H.append(f"<tr><td>{html.escape(iid)}</td><td class='n'>{s.get('n',0)}</td><td class='n'>{s.get('n_border_excluded',0)}</td><td class='n'>{_fmt(s.get(ak,{}).get('median'))}</td><td class='n'>{_fmt(s.get(dk,{}).get('median'))}</td><td class='n'>{_fmt(s.get('circularity',{}).get('median'),3)}</td><td class='n'>{_fmt(diam_by.get(iid))}</td></tr>")
    H.append("</table></div>")
    # 分布图
    if len(feats):
        d = feats[~feats["touches_border"].fillna(False).astype(bool)] if prm.get("exclude_border", True) else feats
        H.append("<h2>形态分布</h2><div class='figs'>")
        if has_um: H.append(f"<img src='{_hist(d['area_um2'], 'Area', 'µm²')}'><img src='{_hist(d['equiv_diameter_um'], 'Equivalent diameter', 'µm')}'>")
        else: H.append(f"<img src='{_hist(d['area'], 'Area', 'px²')}'><img src='{_hist(d['equiv_diameter'], 'Equivalent diameter', 'px')}'>")
        H.append(f"<img src='{_hist(d['circularity'], 'Circularity', '4πA/P²')}'><img src='{_hist(d['solidity'], 'Solidity', 'area / convex area')}'></div>")
    # 质控
    qc_path = os.path.join(run_dir, "tables", "qc.csv")
    if os.path.exists(qc_path):
        qc = pd.read_csv(qc_path)
        H.append("<h2>质量控制</h2>")
        low = feats["low_confidence"].sum() if "low_confidence" in feats else 0
        H.append(f"<p>失焦分数为归一化拉普拉斯方差（同批内相对比较，明显偏低者可能失焦）；光照不均为大尺度背景的变异系数；实例一致性为 {prm.get('tta_k', 4)} 次翻转/旋转重分割后该实例仍被找到的比例，低于 0.5 记为低可信。本次共 {int(low)} 个低可信实例（占 {100*low/max(len(feats),1):.1f}%）。</p>")
        H.append("<div class='tw'><table><tr><th>图像</th><th class='n'>失焦分数</th><th class='n'>光照不均</th><th class='n'>饱和像素</th><th class='n'>实例数</th><th class='n'>低可信比例</th></tr>")
        for _, q in qc.iterrows():
            H.append(f"<tr><td>{html.escape(str(q['image_id']))}</td><td class='n'>{q['focus_score']:.3f}</td><td class='n'>{q['illumination_cv']:.3f}</td><td class='n'>{100*q['saturation_frac']:.2f}%</td><td class='n'>{int(q['n_instances'])}</td><td class='n'>{_fmt(100*q.get('low_confidence_frac', float('nan')))}%</td></tr>")
        H.append("</table></div>")
    # 缩略图
    ovs = sorted(glob.glob(os.path.join(run_dir, "overlays", "*.png")))[:max_thumbs]
    if ovs:
        H.append(f"<h2>分割叠加（前 {len(ovs)} 张）</h2><div class='thumbs'>")
        for p in ovs:
            iid = os.path.splitext(os.path.basename(p))[0]
            H.append(f"<figure style='margin:0'><img src='{_img_b64(p)}'><figcaption>{html.escape(iid)} · {per.get(iid,{}).get('n','?')} 个</figcaption></figure>")
        H.append("</div>")
    # 方法学（模板）
    dm = {"model": "微调模型的训练直径", "sizemodel": "Cellpose cyto3 尺寸估计器逐图估计", "train_median": "训练集真值中位直径", None: "自动"}.get(seg.get("diam_mode"), str(seg.get("diam_mode")))
    H.append("<h2>方法</h2>")
    H.append(f"<p>图像转为单通道灰度后，用 Cellpose 3 架构的实例分割模型（权重 <code>{html.escape(str(seg.get('id','')))}</code>，器官 {html.escape(str(seg.get('organ','')))}）逐图分割，目标尺寸由“{dm}”给出，流场阈值 {prm.get('flow_threshold')}，细胞概率阈值 {prm.get('cellprob_threshold')}。"
             f"对每个实例用 scikit-image 的 regionprops 计算面积、等效直径、周长、长短轴、离心率、实心度、圆度（4πA/P²）、长宽比及灰度均值/标准差；触及图像边缘的实例在汇总统计中{'排除' if prm.get('exclude_border', True) else '保留'}。"
             f"{'像素尺寸 ' + str(prm.get('pixel_size_um')) + ' µm/px 用于换算微米单位。' if prm.get('pixel_size_um') else '未提供像素尺寸，结果以像素为单位。'}</p>")
    # 溯源
    H.append("<h2>溯源</h2><div class='tw'><table><tr><th>项目</th><th>值</th></tr>")
    H.append(f"<tr><td>运行目录</td><td><code>{html.escape(os.path.abspath(run_dir))}</code></td></tr>")
    H.append(f"<tr><td>分割模型</td><td><code>{html.escape(str(seg.get('id','')))}</code>（diam_labels {_fmt(seg.get('diam_labels'))}）</td></tr>")
    H.append(f"<tr><td>参数</td><td><code>{html.escape(json.dumps(prm, ensure_ascii=False))}</code></td></tr>")
    H.append(f"<tr><td>软件版本</td><td><code>{html.escape(json.dumps(ver, ensure_ascii=False))}</code></td></tr></table></div>")
    H.append("<div class='tw'><table><tr><th>输入图像</th><th>MD5</th><th class='n'>尺寸</th><th class='n'>实例数</th></tr>")
    for i in m.get("inputs", []):
        H.append(f"<tr><td>{html.escape(os.path.basename(i['path']))}</td><td><code>{i['md5']}</code></td><td class='n'>{'×'.join(map(str, i.get('shape', [])[:2]))}</td><td class='n'>{i.get('n_instances','')}</td></tr>")
    H.append("</table></div>")
    H.append("<p class='small'>本报告由 Orgalyst 自动生成；方法学文字来自固定模板，数值直接取自运行目录中的表格文件，未经语言模型改写。</p></main>")
    out = os.path.join(run_dir, "report.html")
    open(out, "w", encoding="utf-8").write("\n".join(H))
    return out
