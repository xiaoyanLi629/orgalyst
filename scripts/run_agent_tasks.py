#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E5：Agent 端到端任务集。用 bioagent 的 Agent（Claude Agent SDK + orgalyst MCP）无终端地跑 12 个自然语言任务，
每个任务有可自动判定的成功标准（对照 e5/ref/refs.json 里命令行路径算出的参考值、产物文件是否存在、回答里的关键内容）。
输出 results/e5_agent_tasks_<backend>.json（逐任务：成功与否、工具调用次数、耗时、费用、回答摘录）。
运行：/root/autodl-fs/bioagent/.venv/bin/python scripts/run_agent_tasks.py [--model claude-opus-5] [--only t01,t02] [--tag claude]
"""
import argparse, asyncio, glob, json, os, re, sys, time, traceback
sys.path.insert(0, "/root/autodl-fs/bioagent")
from pathlib import Path
AI4S = "/root/autodl-fs/AI4S"; E = f"{AI4S}/e5"; DATA = f"{E}/data"
REFS = json.load(open(f"{E}/ref/refs.json", encoding="utf-8"))

# ---------- 判定辅助 ----------
def nums(text):
    """回答里出现的所有数字（去掉千分位逗号）。"""
    return [float(x) for x in re.findall(r"\d[\d,]*\.?\d*", text.replace("，", ",")) if x.replace(",", "").replace(".", "").isdigit() for x in [x.replace(",", "")]]
def near(text, ref, tol):
    return any(abs(v - ref) <= tol * max(abs(ref), 1e-9) for v in nums(text))
def has_int(text, k): return any(abs(v - k) < 1e-9 for v in nums(text))
def any_re(text, pat): return re.search(pat, text) is not None
def files(outputs, pattern): return glob.glob(os.path.join(outputs, "**", pattern), recursive=True)
def tool_calls(evts, name): return [e for e in evts if e["kind"] == "tool_use" and e["name"] == name]
def orgalyst_calls(evts): return [e for e in evts if e["kind"] == "tool_use" and e["name"].startswith("mcp__orgalyst__")]

# ---------- 任务定义 ----------
# 每项：id、标题、prompt、follow_of（在哪个任务的对话里接着问）、check(text, evts, outputs) -> (ok, why)
def T(id, title, prompt, check, follow_of=None): return dict(id=id, title=title, prompt=prompt, check=check, follow_of=follow_of)

def c01(text, ev, out):
    r = REFS["single"]; ok_n = near(text, r["n"], 0.10) or near(text, r["n_all"], 0.10)
    ok_d = near(text, r["diam_median"], 0.10)
    return (bool(orgalyst_calls(ev)) and ok_n and ok_d, f"计数≈{r['n']}/{r['n_all']}:{ok_n} 直径≈{r['diam_median']:.0f}:{ok_d}")
def c02(text, ev, out):
    r = REFS["intestine"]; rep = files(out, "report.html")
    return (bool(rep) and (near(text, r["n"], 0.10) or near(text, r["n_all"], 0.10)), f"report.html:{len(rep)} 总数≈{r['n']}/{r['n_all']}")
def c03(text, ev, out):
    r = REFS["brain_um"]; calls = tool_calls(ev, "mcp__orgalyst__analyze_images")
    px_ok = any(abs(float(c["input"].get("pixel_size_um") or 0) - 3.1646) < 1e-3 for c in calls)
    v_ok = near(text, r["area_um2_median"], 0.05) or any(near(text, v, 0.05) for v in r["per_image"].values() if v)
    return (px_ok and v_ok and any_re(text, "µm|μm|um²|微米|平方微米"), f"像素尺寸传入:{px_ok} 面积≈{r['area_um2_median']:.0f}µm²:{v_ok}")
def c04(text, ev, out):
    r = REFS["lung"]; calls = tool_calls(ev, "mcp__orgalyst__count_organoids")
    hit = sum(has_int(text, k) for k in r["per_image"].values())
    return (bool(calls) and hit >= max(3, len(r["per_image"]) - 1), f"count 工具:{len(calls)} 逐图计数命中 {hit}/{len(r['per_image'])}")
def c05(text, ev, out):
    r = REFS["groups"]; calls = tool_calls(ev, "mcp__orgalyst__compare_groups"); cmp = files(out, "compare.html")
    meds = list(r["median_by_group"].values()); med_ok = any(near(text, v, 0.10) for v in meds); stat_ok = any_re(text, r"p\s*[=<>≈]|显著|P 值|p 值")
    return (bool(calls) and bool(cmp) and med_ok and stat_ok, f"compare 工具:{len(calls)} compare.html:{len(cmp)} 中位数命中:{med_ok} 检验措辞:{stat_ok}")
def c06(text, ev, out):
    r = REFS["series"]; calls = tool_calls(ev, "mcp__orgalyst__growth_curves"); g = files(out, "growth_curves.csv")
    trend = any_re(text, "增大|增长|上升|变大|扩大|长大") if r["fold"] > 1 else any_re(text, "缩小|减小|下降|变小")
    return (bool(calls) and bool(g) and trend and (near(text, r["fold"], 0.15) or near(text, r["last"]["v"], 0.10)), f"growth 工具:{len(calls)} 曲线文件:{len(g)} 趋势:{trend} 倍数≈{r['fold']:.1f}")
def c07(text, ev, out):
    r = REFS["intestine"]; calls = [c for c in tool_calls(ev, "mcp__orgalyst__analyze_images") if c["input"].get("qc")]; q = files(out, "qc.csv")
    return (bool(calls) and bool(q) and any_re(text, "不可靠|低可信|可信度|一致性|质控|质检"), f"qc=True 调用:{len(calls)} qc.csv:{len(q)} 参考低可信 {r['n_low_confidence']}")
def c08(text, ev, out):
    return (any_re(text, "4\s*π|4π|周长") and any_re(text, "贴边|边缘|不完整|被截"), "解释含 4π/周长 与 贴边/不完整")
def c09(text, ev, out):
    calls = tool_calls(ev, "mcp__orgalyst__analyze_images"); asked = (not calls) and any_re(text, "器官|哪种|什么类型") and any_re(text, "[?？]")
    ran = bool(calls) and all(c["input"].get("organ", "generic") in ("generic", "pdac") for c in calls) and (near(text, REFS["pdac"]["n_all"], 0.2) or near(text, REFS["pdac"]["n_generic_all"], 0.2) or near(text, REFS["pdac"]["n"], 0.2))
    return (asked or ran, f"追问器官:{asked} 或 用 generic/pdac 跑出计数:{ran}")
def c10(text, ev, out):
    paths = [p for p in re.findall(r"/[\w./\-]+manifest\.json", text) if os.path.exists(p)]
    return (bool(paths) and any_re(text, "cyto3|微调|权重|模型|diam|直径策略|哈希|md5|版本"), f"manifest 路径存在:{len(paths)}")
def c11(text, ev, out):
    return (any_re(text, "没有|未找到|找不到|没找到|不存在|为空|空目录|0 张|零张"), "说明没有图片")
def c12(text, ev, out):
    calls = tool_calls(ev, "mcp__orgalyst__analyze_images"); organs = {c["input"].get("organ") for c in calls}
    return ({"intestine", "brain"} <= organs and len(files(out, "features.csv")) >= 2, f"器官集合 {sorted(o for o in organs if o)} run 目录 {len(files(out, 'features.csv'))}")

TASKS = [
    T("t01", "单图计数与大小", f"分析这张肠类器官明场照片：{DATA}/single/ 里唯一的一张 png。告诉我一共分割出多少个类器官，以及它们等效直径的中位数是多少像素。", c01),
    T("t02", "批量分析并出报告", f"{DATA}/intestine/ 下有 4 张肠类器官照片，请做形态分析并生成报告，告诉我总共有多少个类器官、每张图各多少个，以及报告文件的路径。", c02),
    T("t08", "追问：指标含义", "你刚才报告里的“圆度”是怎么算的？为什么贴着照片边缘的类器官要排除？用两三句话解释。", c08, follow_of="t02"),
    T("t03", "带物理尺寸的分析", f"{DATA}/brain_um/ 里是 3 张脑类器官照片，每张一个类器官，像素尺寸是 3.1646 µm/px。请分析并告诉我面积中位数是多少平方微米。", c03),
    T("t10", "追问：可复现性", "这次分析用了哪个模型、什么直径策略？把这次运行的 manifest.json 完整路径给我，并说明里面记录了哪些可复现信息。", c10, follow_of="t03"),
    T("t04", "只数数（检测）", f"{DATA}/lung/ 里有 5 张肺类器官照片，我只想知道每张图里有几个类器官，不需要量大小，越快越好。请逐张列出数量。", c04),
    T("t05", "组间比较", f"{DATA}/groups/ 有 6 张第 30 天的脑类器官照片（像素尺寸 3.1646 µm/px），分组见同目录 groups.csv（wt2D 组 3 张、TH2-7 组 3 张）。请比较两组的面积有没有差异，给出中位数、检验结果和结论。", c05),
    T("t06", "生长曲线", f"{DATA}/series/ 是同一个脑类器官 org01 从第 2 天到第 30 天的连续照片，元数据在同目录 meta.csv（含像素尺寸、时间点）。请分析并画出面积随时间的生长曲线，告诉我从第一个到最后一个时间点面积变化了多少倍。", c06),
    T("t07", "质控", f"请分析 {DATA}/intestine/ 下的 4 张肠类器官照片，并做质量检查：标出哪些分割结果不可靠，告诉我不可靠的有几个、图像质量有没有问题。", c07),
    T("t09", "器官未知", f"帮我分析 {DATA}/pdac/ 里的 3 张类器官照片，数一下每张有多少个。", c09),
    T("t11", "空目录", f"分析 {DATA}/empty/ 目录下的类器官照片并告诉我数量。", c11),
    T("t12", "混合器官批次", f"{DATA}/mixed/ 里有 4 张照片：文件名以 org 开头的 2 张是脑类器官（像素尺寸 3.1646 µm/px），另外 2 张是肠类器官。请分别用对应的模型分析，各自报告数量和面积中位数。", c12),
]

# ---------- Agent 驱动 ----------
async def run_all(args):
    from bioagent.config import load_settings, scrub_environment
    from bioagent.proxy import ProxyManager
    from bioagent.permissions import make_can_use_tool
    from bioagent.agent import Agent
    from bioagent.cli import build_system_prompt, ROOT
    from bioagent.chats import create_chat
    from bioagent.modules import normalize
    scrub_environment()
    s = load_settings(ROOT); s.user = args.user; s.store.ensure(); s.memory.enabled = False
    if args.model: s.model = args.model
    s.biomni.all_modules = list(s.biomni.modules); s.biomni.modules = normalize(list(s.biomni.default_modules), s.biomni.all_modules)
    pm = ProxyManager(s); proxy_env = {}
    if s.proxy.enabled:
        pm.ensure_running(); ok, why = pm.health_check(); assert ok, why; pm.register_session(); proxy_env = pm.env
    async def confirm(summary): return True
    only = set(args.only.split(",")) if args.only else None
    agents, results = {}, []
    try:
        for t in TASKS:
            if only and t["id"] not in only and not (t["follow_of"] and t["follow_of"] in only): continue
            rec = dict(id=t["id"], title=t["title"], prompt=t["prompt"], follow_of=t["follow_of"], model=s.model)
            t0 = time.time(); evts = []; text = []
            try:
                if t["follow_of"] and t["follow_of"] in agents:
                    agent, chat = agents[t["follow_of"]]
                else:
                    chat = create_chat(s.store, model=s.model, source="e5", title=f"E5 {t['id']} {t['title']}")
                    s.cwd = chat.outputs_dir
                    cb = make_can_use_tool(s, confirm, set(), mode=lambda: "auto")
                    agent = Agent(s, proxy_env, cb, build_system_prompt(s)); await agent.start(); agents[t["id"]] = (agent, chat)
                async def consume():
                    async for ev in agent.send(t["prompt"]):
                        if ev.kind == "text": text.append(ev.text)
                        elif ev.kind == "tool_use": evts.append(dict(kind="tool_use", name=ev.name, input=ev.data.get("input", {})))
                        elif ev.kind == "tool_result": evts.append(dict(kind="tool_result", error=ev.data.get("error", False), text=ev.text[:300]))
                        elif ev.kind == "result": evts.append(dict(kind="result", **{k: ev.data.get(k) for k in ("cost", "turns", "error", "session_id")}))
                await asyncio.wait_for(consume(), timeout=args.timeout)
                final = "".join(text); res = [e for e in evts if e["kind"] == "result"]
                ok, why = t["check"](final, evts, str(chat.outputs_dir))
                rec.update(ok=bool(ok), why=why, seconds=round(time.time() - t0, 1), tool_calls=sum(e["kind"] == "tool_use" for e in evts),
                           orgalyst_calls=len(orgalyst_calls(evts)), tools=[e["name"] for e in evts if e["kind"] == "tool_use"],
                           cost_usd=(res[-1]["cost"] if res else None), turns=(res[-1]["turns"] if res else None), sdk_error=bool(res and res[-1]["error"]),
                           tool_errors=sum(1 for e in evts if e["kind"] == "tool_result" and e["error"]), chat=str(chat.outputs_dir), answer=final[-1500:])
            except Exception as e:
                rec.update(ok=False, why=f"异常 {e!r}", seconds=round(time.time() - t0, 1), tool_calls=sum(e2["kind"] == "tool_use" for e2 in evts), orgalyst_calls=len(orgalyst_calls(evts)),
                           tools=[e2["name"] for e2 in evts if e2["kind"] == "tool_use"], answer="".join(text)[-1500:], traceback=traceback.format_exc()[-800:])
            print(f"[{t['id']}] {'PASS' if rec['ok'] else 'FAIL'} {rec['seconds']}s tools={rec['tool_calls']} ({rec['orgalyst_calls']} orgalyst) — {rec['why']}", flush=True)
            results.append(rec)
            json.dump(dict(model=s.model, tag=args.tag, results=results), open(f"{AI4S}/results/e5_agent_tasks_{args.tag}.json", "w"), indent=1, ensure_ascii=False)
    finally:
        for agent, _ in agents.values():
            try: await agent.close()
            except Exception: pass
        if s.proxy.enabled: pm.unregister_session_and_maybe_stop()
    n = len(results); k = sum(r["ok"] for r in results)
    summ = dict(model=s.model, tag=args.tag, n_tasks=n, n_pass=k, success_rate=(k / n if n else None),
                mean_tool_calls=(sum(r["tool_calls"] for r in results) / n if n else None), mean_orgalyst_calls=(sum(r["orgalyst_calls"] for r in results) / n if n else None),
                mean_seconds=(sum(r["seconds"] for r in results) / n if n else None), total_cost_usd=sum((r.get("cost_usd") or 0) for r in results))
    json.dump(dict(summary=summ, results=results), open(f"{AI4S}/results/e5_agent_tasks_{args.tag}.json", "w"), indent=1, ensure_ascii=False)
    print("SUMMARY", json.dumps(summ, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default=None); ap.add_argument("--user", default="e5"); ap.add_argument("--only", default=None)
    ap.add_argument("--tag", default="claude"); ap.add_argument("--timeout", type=float, default=900)
    asyncio.run(run_all(ap.parse_args()))
