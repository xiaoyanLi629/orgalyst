"""把 Orgalyst 的领域工具暴露为 MCP 服务器（stdio），供 bioagent 的 Agent SDK 调用。
沿用 biomni/mcp_server.py 的做法：先把 stdout 改道到 stderr，只留一个私有句柄给 MCP 协议，避免库的 print 污染协议流。
启动：/root/autodl-fs/AI4S/.venv/bin/python /root/autodl-fs/AI4S/orgalyst/mcp_server.py
环境变量：ORGALYST_RUNS（运行目录根，默认 <cwd>/orgalyst_runs）、CELLPOSE_LOCAL_MODELS_PATH
"""
import io, os, sys
_real_stdout_fd = os.dup(1); os.dup2(2, 1); sys.stdout = sys.stderr
_protocol_out = io.TextIOWrapper(os.fdopen(_real_stdout_fd, "wb", buffering=0), encoding="utf-8", write_through=True)

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", "/root/autodl-tmp/.cellpose/models")
RUNS = os.environ.get("ORGALYST_RUNS", os.path.join(os.getcwd(), "orgalyst_runs"))
os.makedirs(RUNS, exist_ok=True)

import json, glob  # noqa: E402
import anyio  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

mcp = FastMCP("orgalyst")
_segmenters = {}

def _seg(organ, diam_mode=None):
    from orgalyst.segment import Segmenter
    key = (organ, diam_mode)
    if key not in _segmenters: _segmenters[key] = Segmenter(organ, diam_mode=diam_mode)
    return _segmenters[key]

@mcp.tool()
def list_models() -> dict:
    """列出可用的类器官分割模型（按器官）与检测计数模型（含按器官标定的置信度阈值），以及每个器官的默认直径策略。用户未说明器官类型时用 'generic'（零样本 cyto3）。"""
    from orgalyst.config import SEG_MODELS, DET_MODELS, DET_CONF
    return dict(segmentation={k: dict(path=v["path"], available=os.path.exists(v["path"]) or v["path"] == "cyto3", diam_mode=v["diam_mode"]) for k, v in SEG_MODELS.items()},
                detection={k: dict(path=p, available=os.path.exists(p)) for k, p in DET_MODELS.items()}, detection_conf=DET_CONF)

@mcp.tool()
def analyze_images(images: str, organ: str = "generic", pixel_size_um: float | None = None, name: str = "analysis",
                   diam_mode: str | None = None, limit: int = 0, make_report: bool = True, qc: bool = False, meta_csv: str | None = None) -> dict:
    """对一批明场类器官图像做实例分割 + 形态学测量，生成可追溯的运行目录（含 features.csv、summary.json、掩码、叠加图、report.html）。
    images: 目录路径或 glob（如 /data/exp1/*.png）。organ: brain/intestine/pdac/colon/generic。pixel_size_um: 每像素微米数，未知留空则只报像素单位。
    qc=True 时额外做图像级质控和实例级 TTA 一致性检查（标出不可靠的分割，产物 tables/qc.csv，耗时约 4 倍）。meta_csv：逐图元数据 CSV（列 image_id 及可选 pixel_size_um/subject/timepoint/group），给了它 growth_curves 才能按时间点连线。
    返回 run_dir、总体汇总（计数、面积/直径/圆度中位数等）与逐图计数；后续 compare_groups / growth_curves / run_summary 都以 run_dir 为输入。"""
    from orgalyst.cli import main as cli_main
    import contextlib
    argv = ["analyze", "--organ", organ, "--images", images, "--out", RUNS, "--name", name]
    if pixel_size_um: argv += ["--pixel-size", str(pixel_size_um)]
    if diam_mode: argv += ["--diam-mode", diam_mode]
    if limit: argv += ["--limit", str(limit)]
    if not make_report: argv += ["--no-report"]
    if qc: argv += ["--qc"]
    if meta_csv: argv += ["--meta", meta_csv]
    before = set(glob.glob(os.path.join(RUNS, f"{name}_*")))
    with contextlib.redirect_stdout(sys.stderr): cli_main(argv)
    new = sorted(set(glob.glob(os.path.join(RUNS, f"{name}_*"))) - before)
    run_dir = new[-1] if new else sorted(glob.glob(os.path.join(RUNS, f"{name}_*")))[-1]
    out = run_summary(run_dir)
    qp = os.path.join(run_dir, "tables", "qc.csv")
    if qc and os.path.exists(qp):
        import pandas as pd
        q = pd.read_csv(qp); out["qc"] = dict(table=qp, per_image=q.to_dict(orient="records"))
        fp = os.path.join(run_dir, "tables", "features.csv"); f = pd.read_csv(fp)
        if "low_confidence" in f.columns: out["qc"]["n_low_confidence"] = int(f["low_confidence"].sum()); out["qc"]["low_confidence_ids"] = f.loc[f["low_confidence"], ["image_id", "label"]].values.tolist()[:50]
    return out

@mcp.tool()
def count_organoids(images: str, organ: str = "generic", name: str = "count", conf: float | None = None, limit: int = 0) -> dict:
    """只数数：用检测模型（YOLO11m，三器官联合训练）统计每张明场图里有几个类器官，不做分割和形态测量，比 analyze_images 快得多。
    images: 目录或 glob。organ: intestine/brain/lung/generic，决定置信度阈值（已在验证集上标定：肠 0.50、脑 0.45、肺 0.40、未知 0.45）；conf 可手动覆盖。
    返回 run_dir、总数、逐图计数、所用阈值；产物 tables/counts.csv（逐图）、tables/boxes.csv（每个框）、overlays/（画了框的图）。
    要量大小、形状或比较分组时请改用 analyze_images。"""
    from orgalyst.cli import main as cli_main
    import contextlib
    argv = ["count", "--organ", organ, "--images", images, "--out", RUNS, "--name", name]
    if conf is not None: argv += ["--conf", str(conf)]
    if limit: argv += ["--limit", str(limit)]
    before = set(glob.glob(os.path.join(RUNS, f"{name}_*")))
    with contextlib.redirect_stdout(sys.stderr): cli_main(argv)
    new = sorted(set(glob.glob(os.path.join(RUNS, f"{name}_*"))) - before)
    run_dir = new[-1] if new else sorted(glob.glob(os.path.join(RUNS, f"{name}_*")))[-1]
    m = json.load(open(os.path.join(run_dir, "manifest.json"))); s = json.load(open(os.path.join(run_dir, "tables", "summary.json")))
    return dict(run_dir=run_dir, total=s["total"], n_images=s["n_images"], per_image=s["per_image"], conf_threshold=s["conf_threshold"],
                model=m["models"].get("detection"), overlays_dir=os.path.join(run_dir, "overlays"), note="检测计数在验证集上的误差：肠/肺每图约 20%（中位 13%），脑 <1%。")

@mcp.tool()
def growth_curves(run_dir: str, meta_csv: str | None = None, pattern: str | None = None, metric: str | None = None) -> dict:
    """按时间点把同一批 analyze_images 的结果连成生长曲线（每个个体一条，按组汇总均值）。
    需要知道每张图属于哪个个体 / 哪个时间点 / 哪个组：给 meta_csv（列 image_id, subject, timepoint, group），或 pattern（从文件名提取的正则，命名组 subject/timepoint/group）；
    脑类器官公开数据的文件名形如 org01_wt2D_d02_LabA，不给 pattern 时会尝试内置的这种格式。
    产物：tables/growth.csv（逐图）、tables/growth_curves.csv（按组×时间点）、figures/growth.png、growth.html。返回每个个体首末时间点的数值和变化倍数。"""
    from orgalyst.cli import main as cli_main
    import contextlib, pandas as pd
    argv = ["track", "--run", run_dir]
    if meta_csv: argv += ["--meta", meta_csv]
    if pattern: argv += ["--pattern", pattern]
    if metric: argv += ["--metric", metric]
    with contextlib.redirect_stdout(sys.stderr): cli_main(argv)
    g = pd.read_csv(os.path.join(run_dir, "tables", "growth.csv"))
    col = "value"; metric_name = str(g["metric"].iloc[0]) if len(g) else metric
    per_subject = {}
    if len(g) and "subject" in g.columns and "timepoint" in g.columns:
        for sub, d in g.sort_values("timepoint").groupby("subject"):
            d = d.dropna(subset=[col])
            if len(d): per_subject[str(sub)] = dict(group=str(d["group"].iloc[0]) if "group" in d else None, first=dict(t=float(d["timepoint"].iloc[0]), v=float(d[col].iloc[0])), last=dict(t=float(d["timepoint"].iloc[-1]), v=float(d[col].iloc[-1])), fold=float(d[col].iloc[-1] / d[col].iloc[0]) if d[col].iloc[0] else None)
    outs = {k: os.path.join(run_dir, v) for k, v in dict(growth="tables/growth.csv", curves="tables/growth_curves.csv", figure="figures/growth.png", html="growth.html").items() if os.path.exists(os.path.join(run_dir, v))}
    return dict(run_dir=run_dir, metric=metric_name, per_subject=per_subject, outputs=outs)

@mcp.tool()
def run_summary(run_dir: str) -> dict:
    """读取一次运行的汇总：总体统计、逐图计数、模型与参数、报告路径。"""
    m = json.load(open(os.path.join(run_dir, "manifest.json"))); s = json.load(open(os.path.join(run_dir, "tables", "summary.json")))
    per = {k: dict(n=v.get("n"), area_median=(v.get("area_um2") or v.get("area_px") or {}).get("median"), circularity_median=(v.get("circularity") or {}).get("median")) for k, v in s.get("per_image", {}).items()}
    return dict(run_dir=run_dir, n_images=len(m["inputs"]), models=m["models"], params=m["params"], overall=s.get("overall"), per_image=per,
                features_csv=os.path.join(run_dir, "tables", "features.csv"),
                report_html=os.path.join(run_dir, "report.html") if os.path.exists(os.path.join(run_dir, "report.html")) else None)

@mcp.tool()
def compare_groups(run_dir: str, groups: dict | str, metrics: list[str] | None = None, exclude_border: bool = True) -> dict:
    """在一次运行的逐实例特征表上做组间比较（两组 Mann-Whitney U，多组 Kruskal-Wallis，Cliff's delta 效应量，Holm 校正）。
    groups: {image_id: group} 的映射，或一个 CSV 路径（两列 image_id,group；image_id 为文件名去扩展名）。
    metrics 默认：area_um2/equiv_diameter_um（有像素尺寸时）或 area/equiv_diameter，及 circularity/solidity/aspect_ratio。
    结果写入 run_dir/tables/compare.csv 与 run_dir/compare.html，并返回每指标的中位数、p 值、效应量。"""
    import pandas as pd
    from orgalyst.compare import compare_groups as _cmp, attach_groups
    feats = pd.read_csv(os.path.join(run_dir, "tables", "features.csv"))
    g = pd.read_csv(groups) if isinstance(groups, str) else pd.DataFrame(dict(image_id=list(groups.keys()), group=list(groups.values())))
    df = attach_groups(feats, g)
    res = _cmp(df, metrics=tuple(metrics) if metrics else __import__("orgalyst.compare", fromlist=["DEFAULT_METRICS"]).DEFAULT_METRICS, exclude_border=exclude_border)
    res["table"].to_csv(os.path.join(run_dir, "tables", "compare.csv"), index=False)
    _write_compare_html(run_dir, res)
    cols = [c for c in res["table"].columns if c != "description"]
    return dict(run_dir=run_dir, groups=res["groups"], n_per_group=res["n_per_group"], table=res["table"][cols].to_dict(orient="records"),
                pairwise=(res["pairwise"].to_dict(orient="records") if res["pairwise"] is not None else None),
                compare_html=os.path.join(run_dir, "compare.html"))

def _write_compare_html(run_dir, res):
    import html
    from orgalyst.report import CSS
    t = res["table"]
    H = [f"<title>组间比较</title><style>{CSS}</style><main><div class='eyebrow'>Orgalyst · compare</div><h1>组间比较</h1>",
         f"<p class='sub'>分组：{html.escape(', '.join(f'{g} (n={n})' for g, n in res['n_per_group'].items()))}；每个类器官为一个观测，贴边实例已排除；多指标 Holm 校正。</p>",
         "<div class='tw'><table><tr><th>指标</th><th>检验</th><th>各组中位数</th><th class='n'>p</th><th class='n'>p (Holm)</th><th class='n'>Cliff's δ</th><th>显著</th></tr>"]
    for _, r in t.iterrows():
        H.append(f"<tr><td>{html.escape(str(r['metric']))}</td><td>{r['test']}</td><td>{html.escape(str(r['description']))}</td><td class='n'>{r['p_value']:.3g}</td><td class='n'>{r['p_holm']:.3g}</td><td class='n'>{'' if r['cliffs_delta'] != r['cliffs_delta'] else f'{r[chr(99)+chr(108)+chr(105)+chr(102)+chr(102)+chr(115)+chr(95)+chr(100)+chr(101)+chr(108)+chr(116)+chr(97)]:.2f}'}</td><td>{'是' if r['significant_0.05'] else '否'}</td></tr>")
    H.append("</table></div><div class='figs'>" + "".join(f"<img src='{src}'>" for src in res["figures"].values()) + "</div></main>")
    open(os.path.join(run_dir, "compare.html"), "w", encoding="utf-8").write("\n".join(H))

@mcp.tool()
def list_runs(limit: int = 20) -> list:
    """列出最近的运行目录（最新在前），便于用户追问"上一次分析"。"""
    runs = sorted(glob.glob(os.path.join(RUNS, "*", "manifest.json")), key=os.path.getmtime, reverse=True)[:limit]
    out = []
    for p in runs:
        m = json.load(open(p)); out.append(dict(run_dir=os.path.dirname(p), name=m.get("name"), created=m.get("created"), n_images=len(m.get("inputs", [])), organ=m.get("models", {}).get("segmentation", {}).get("organ")))
    return out

print(f"[orgalyst-mcp] ready, runs={RUNS}", file=sys.stderr)

async def main():
    async with stdio_server(stdout=anyio.wrap_file(_protocol_out)) as (r, w):
        server = mcp._mcp_server
        await server.run(r, w, server.create_initialization_options())

if __name__ == "__main__":
    anyio.run(main)
