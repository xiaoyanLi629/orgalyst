# -*- coding: utf-8 -*-
"""全景流程图 v2：蛇形三行（→ / ← / →），行尾用短的向下箭头接到下一行，不再有长的回折箭头；
节点分四档大小（XL 核心模型 / L 关键结果 / M 主要工具 / S 细节步骤），关键环节大、细节小；每个节点有大号序号；
页面单栏、图更宽。其余交互沿用 v1（亮点沿链路走、机器内部小动画、字幕）。"""
import base64, json, re
S = "/private/tmp/claude-501/-Users-xiaoyanli/0850d9a1-4ef3-4938-beed-610f045d4857/scratchpad"
src = open(f"{S}/build_overview_page.py", encoding="utf-8").read()
# 复用 v1 的数据装载、UNET/GAUGE、TAIL、JS（只改布局与节点定义）
ns = {}
exec(src.split("EXTRA = ")[0], ns)   # 载入 P, C, DATA, CSS, UNET, GAUGE, GAUGE2, TAIL, wid, r2, t3, m8, q9, di, db, rs, df
P, DATA, CSS, UNET, GAUGE2, TAIL, wid = ns["P"], ns["DATA"], ns["CSS"], ns["UNET"], ns["GAUGE2"], ns["TAIL"], ns["wid"]
r2, t3, m8, q9, di, db, rs, df = ns["r2"], ns["t3"], ns["m8"], ns["q9"], ns["di"], ns["db"], ns["rs"], ns["df"]
JS = src.split("<script>")[1].split("__DIFFJS__")[0]          # v1 的主 JS（到 __DIFFJS__ 之前）
DIFFJS = "/* ---- 热扩散 ---- */" + open(f"{S}/build_scene_page2.py", encoding="utf-8").read().split("/* ---- 热扩散 ---- */")[1].split("</script>")[0]

EXTRA = """
.wrap{grid-template-columns:minmax(0,1fr);gap:0}nav.toc{position:static;display:flex;gap:14px;flex-wrap:wrap;padding:18px 0 0;max-height:none}nav.toc .k{margin:0;align-self:center}nav.toc a{border-left:0;padding:2px 8px;border:1px solid var(--rule);border-radius:12px}
main{max-width:none}main>p,main>h2,main>header,main>.two{max-width:80ch}
.legend2{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--muted);margin:8px 0 6px}.legend2 i{display:inline-block;width:14px;height:10px;border-radius:3px;vertical-align:-1px;margin-right:5px}
.boardwrap{overflow-x:auto}
.board{position:relative;min-width:1080px;border:1px solid var(--rule);border-radius:12px;background:var(--panel);padding:18px 18px 14px}
.rows{display:flex;flex-direction:column;gap:50px}
.rowl{display:flex;align-items:stretch;gap:0;position:relative}.rowl.rev{flex-direction:row-reverse}
.rowl.rev .ar svg{transform:scaleX(-1)}
.node{position:relative;min-width:0;display:flex;flex-direction:column;gap:5px;border-radius:10px;padding:10px 11px 9px;transition:box-shadow .35s,transform .35s;z-index:1}
.node.data{border:1.5px solid var(--rule);background:var(--paper)}
.node.mach{border:2px solid var(--accent);background:var(--accent-soft)}
.node.s{flex:1 1 0}.node.m{flex:1.35 1 0}.node.l{flex:1.9 1 0}.node.xl{flex:2.4 1 0;border-width:3px}
.node.s .k,.node.s h5,.node.s .d{opacity:.85}.node.s h5{font-size:12px}.node.s .d{font-size:10.5px}
.node.on{box-shadow:0 0 0 5px rgba(14,122,108,.22),0 12px 28px rgba(14,122,108,.22);transform:translateY(-4px)}
.node.on.mach{animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{50%{box-shadow:0 0 0 9px rgba(14,122,108,.12),0 12px 28px rgba(14,122,108,.22)}}
.node .num{position:absolute;left:-10px;top:-10px;width:26px;height:26px;border-radius:50%;background:var(--ink);color:var(--paper);font-family:var(--mono);font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;z-index:2;box-shadow:0 2px 6px rgba(0,0,0,.25)}
.node.mach .num{background:var(--accent);color:var(--accent-ink)}
.node .k{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.node.mach .k{color:var(--accent)}
.node h5{margin:0;font-size:13.5px;line-height:1.25}.node.l h5,.node.xl h5{font-size:16px}.node.xl h5{font-family:var(--serif);font-size:19px}
.node .vis{width:100%;aspect-ratio:1/1;border-radius:6px;background:#0d1214;border:1px solid var(--rule);position:relative;overflow:hidden}
.node.mach .vis{aspect-ratio:4/3}.node.xl .vis{aspect-ratio:16/10}#n13 .vis{aspect-ratio:1/1}#n12 .vis{aspect-ratio:auto;height:auto;background:var(--paper);overflow-x:auto}#n12 .tbl{position:static}
.node .vis canvas,.node .vis svg,.node .vis img{position:absolute;inset:0;width:100%;height:100%}.node .vis img{object-fit:cover}.node .vis img.fit{object-fit:contain;background:#fff}
.node .d{font-size:11.5px;line-height:1.35;color:var(--muted)}.node .d b{color:var(--ink)}.node.l .d,.node.xl .d{font-size:12.5px}
.ar{flex:0 0 30px;display:flex;align-items:center;justify-content:center;color:var(--muted);transition:color .3s;z-index:0}.ar svg{width:26px;height:20px}.ar.on{color:var(--accent)}.ar.on svg path{stroke-dasharray:6 4;animation:dash .5s linear infinite}
@keyframes dash{to{stroke-dashoffset:-10}}
.down{position:absolute;width:44px;height:46px;color:var(--muted);z-index:0}.down svg{width:100%;height:100%}.down.on{color:var(--accent)}.down.on svg path{stroke-dasharray:6 4;animation:dash .5s linear infinite}
.grp{position:absolute;top:-24px;font-size:11px;color:var(--muted);letter-spacing:.04em;border-top:1px dashed var(--rule);padding-top:3px;text-align:center;pointer-events:none}
.gauge .needle{transform-origin:50px 60px;transform:rotate(-90deg);transition:transform 1.2s cubic-bezier(.3,.8,.3,1)}
.unet .blk{fill:#1B2529;stroke:#5A6A70;stroke-width:1;transition:fill .25s,stroke .25s}.unet .blk.lit{fill:#3FB59F;stroke:#E3E9E6}
.unet .skip{stroke:#5A6A70;stroke-width:1;stroke-dasharray:3 2;fill:none}.unet .skip.lit{stroke:#3FB59F}
.unet .plug{fill:#9A6A12;stroke:#F5E9CF;stroke-width:1}.unet .plug.ft{fill:#0E7A6C;stroke:#D9EEE9}
.unet text{font-family:ui-monospace,Menlo,monospace;font-size:7px;fill:#E3E9E6}
.three{display:grid;grid-template-rows:repeat(3,minmax(0,1fr));gap:3px;padding:3px;box-sizing:border-box;position:absolute;inset:0}.three figure{margin:0;min-height:0;height:100%;display:flex;align-items:center;gap:5px}.node .vis .three img{position:static;height:100%;aspect-ratio:1/1;width:auto;flex:0 0 auto;object-fit:cover;border-radius:2px}.three figcaption{font-size:10px;line-height:1.2;color:#E3E9E6;white-space:nowrap}
.tbl{width:100%;min-width:0;font-size:8px;table-layout:fixed;border-collapse:collapse;position:absolute;inset:0;background:var(--paper)}.tbl th,.tbl td{padding:1px 1px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap;overflow:hidden;font-variant-numeric:tabular-nums}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl th{background:var(--panel);font-size:inherit;font-weight:600;padding:2px 1px}
.token{position:absolute;z-index:5;width:20px;height:20px;border-radius:50%;background:var(--accent);border:3px solid #fff;box-shadow:0 4px 12px rgba(14,122,108,.5);transform:translate(-50%,-50%);transition:left .8s cubic-bezier(.4,0,.2,1),top .8s cubic-bezier(.4,0,.2,1);pointer-events:none}
.cap{margin:10px 0 0;padding:10px 16px;border-radius:6px;background:var(--ink);color:var(--paper);font-size:14.5px;line-height:1.55;min-height:3em}
.ctl{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px;align-items:center}
button{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);color:var(--ink);cursor:pointer}
button:hover,button:focus-visible{border-color:var(--accent);outline:none}button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.bar{height:3px;background:var(--rule);border-radius:2px;margin:8px 0 0;overflow:hidden}.bar i{display:block;height:100%;width:0;background:var(--accent)}
.stage2{display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:16px;align-items:start;margin:12px 0;max-width:80ch}
@media (max-width:700px){.stage2{grid-template-columns:minmax(0,1fr)}}
.stage2 canvas{max-width:100%;height:auto;border:1px solid var(--rule);border-radius:4px;background:#000;display:block}
.legend{font-size:13px;color:var(--muted);line-height:1.6}.legend b{color:var(--ink)}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0 18px;max-width:80ch}.grid3 figure{margin:0}.grid3 img{width:100%;border:1px solid var(--rule);border-radius:4px}.grid3 figcaption{font-size:13px;color:var(--muted);margin-top:4px;line-height:1.5}.grid3 figcaption b{color:var(--ink)}
.two{display:grid;grid-template-columns:1fr auto;gap:16px;align-items:center;margin:12px 0}.two img{border:1px solid var(--rule);border-radius:4px;image-rendering:pixelated}
@media (max-width:600px){.two{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){.node,.ar svg path,.token,.gauge .needle,.down svg path{transition:none;animation:none}}
"""
AR = '<svg viewBox="0 0 26 20" aria-hidden="true"><path d="M2 10 H17" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/><path d="M13 3 L21 10 L13 17" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
DOWN = '<svg viewBox="0 0 44 40" aria-hidden="true"><path d="M22 2 V28" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/><path d="M12 20 L22 32 L32 20" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'
def node(kind, size, id, num, k, title, vis, d): return f'<div class="node {kind} {size}" id="{id}"><div class="num">{num}</div><div class="k">{k}</div><h5>{title}</h5><div class="vis">{vis}</div><div class="d">{d}</div></div>'
ar = lambda i: f'<div class="ar" id="a{i}">{AR}</div>'
sw = r2["small_size"][0]
DXDY = json.load(open(f"{S}/dxdy_imgs.json"))
OVB = json.load(open(f"{S}/overlay_bold.json"))
QCB = json.load(open(f"{S}/qc_bold.json"))
three = f'<div class="three"><figure><img src="{DXDY["dx"]}"><figcaption>① 左右方向</figcaption></figure><figure><img src="{DXDY["dy"]}"><figcaption>② 上下方向</figcaption></figure><figure><img src="{P["s4_net"]["prob"]}"><figcaption>③ 哪里像</figcaption></figure></div>'
cols = ["编号", "面积", "直径", "周长", "圆度", "实心"]
tbl = '<table class="tbl"><colgroup><col style="width:13%"><col style="width:23%"><col style="width:16%"><col style="width:16%"><col style="width:16%"><col style="width:16%"></colgroup><tr>' + "".join(f"<th>{c}</th>" for c in cols) + "</tr>" + "".join(f"<tr><td>{r[0]}</td><td>{r[1]:,}</td><td>{r[2]:.0f}</td><td>{r[3]:.0f}</td><td>{r[4]:.2f}</td><td>{r[5]:.2f}</td></tr>" for r in m8["rows"][:8]) + '</table>'
chip = lambda t: f'<span style="font-size:9.5px;line-height:1.25;color:#E3E9E6;border:1px solid #3FB59F;border-radius:5px;padding:1px 5px;opacity:.35">{t}</span>'
ROW1 = (node("data", "s", "n0", 1, "输入", "你的一句话", '<div style="position:absolute;inset:6px;color:#E3E9E6;font-size:10.5px;line-height:1.4">"分析这批肠类器官照片，告诉我大小和形状，给我一份报告。"</div>', "不需要懂参数") + ar(0) +
        node("mach", "m", "n1", 2, "大模型 · 对话式助手", "助手：听懂并安排", f'<div style="position:absolute;inset:5px;display:flex;flex-direction:column;gap:3px;justify-content:center" id="planchips">{chip("任务：形态分析")}{chip("工具：分析图像")}{chip("器官=肠 → 肠专用权重")}</div>', "不看图、不算数，只选工具和参数") + ar(1) +
        node("data", "l", "n2", 3, "输入", "显微照片", f'<img src="{P["s1_input"]["image"]}">', f"<b>{P['shape'][0]}×{P['shape'][1]}</b> 像素，灰度；人工数过 <b>{P['gt_instances']}</b> 个") + ar(2) +
        node("mach", "s", "n3", 4, "细节 · 小模型", "量大小、缩放", '<div class="gauge" style="position:absolute;inset:0">' + GAUGE2 + '</div>', f"约 <b>{r2['diameter']:.0f} px</b> → 缩到 {r2['scale']:.2f} 倍") + ar(3) +
        node("data", "s", "n4", 5, "细节 · 中间结果", "缩小后的照片", f'<img src="{P["s2_rescale"]["small"]}">', f"{sw}×{sw}，类器官约 30 px") + ar(4) +
        node("mach", "s", "n5", 6, "细节 · 工具", "切块", '<canvas id="tc" width="120" height="90"></canvas>', "224×224，重叠一半") + ar(5) +
        node("data", "s", "n6", 7, "细节 · 中间结果", f"{t3['n']} 张小图块", '<canvas id="oc" width="120" height="120"></canvas>', "逐块送进网络"))
# 第二行从右往左读（row-reverse）：写入顺序仍按流程顺序
ROW2 = (node("mach", "xl", "n7", 8, "核心 · 神经网络", "U-Net（装着肠专用权重）", f'<div class="unet" style="position:absolute;inset:4px">{UNET}</div>', "先压缩提取特征，再还原到每个像素。<b>结构不变，换的是权重</b>：通用的 cyto3 权重认识细胞，我们在公开肠类器官数据上继续训练成肠专用权重。") + ar(6) +
        node("data", "m", "n8", 9, "细节 · 中间结果", "网络给出的三张图", three, "两张方向图 + 一张“哪里像类器官”") + ar(7) +
        node("mach", "m", "n9", 10, "后处理", "聚成轮廓", '<canvas id="kc" width="120" height="90"></canvas>', "像素沿箭头走 200 步，汇到同一点的归为一个") + ar(8) +
        node("data", "l", "n10", 11, "关键结果", f"{P['s7_masks']['n']} 个类器官轮廓", f'<img src="{OVB["overlay"]}"><div style="position:absolute;right:4px;bottom:4px;width:44%;aspect-ratio:1/1;border:2px solid #fff;border-radius:4px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.5)"><img src="{OVB["zoom"]}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"><span style="position:absolute;left:3px;top:2px;font-size:9px;color:#fff;text-shadow:0 0 3px #000">局部放大</span></div>', f"每个类器官涂一种颜色、亮绿线是自动画出的轮廓；右下角是局部放大。人工数过 <b>{P['gt_instances']}</b> 个。分割到此结束。") + ar(9) +
        node("mach", "m", "n11", 12, "分析 · 工具", "测量尺", f'<div style="position:absolute;inset:6px;display:flex;flex-direction:column;gap:3px;justify-content:center" id="mchips">{chip("面积 · 直径 · 周长")}{chip("圆度 · 实心度")}{chip("长宽比 · 贴边")}</div>', "纯几何计算，不猜") + ar(10) +
        node("data", "l", "n12", 13, "结果", "一张表，每个类器官一行", tbl, f"单位像素；共 <b>{m8['n']}</b> 行（这里只列前 8 行），面积中位数 <b>{m8['summary']['area_median']:.0f} px²</b>"))
ROW3 = (node("mach", "s", "n13", 14, "分析 · 检查", "质检员", f'<img id="qi" src="{P["s1_input"]["image"]}" style="transition:transform .5s">', f"翻转旋转 {q9['k']} 次再找一遍") + ar(11) +
        node("data", "s", "n14", 15, "结果", "标出不可靠的", f'<img src="{QCB["overlay"]}"><div style="position:absolute;right:4px;bottom:4px;width:44%;aspect-ratio:1/1;border:2px solid #fff;border-radius:4px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.5)"><img src="{QCB["zoom"]}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"><span style="position:absolute;left:3px;top:2px;font-size:9px;color:#fff;text-shadow:0 0 3px #000">局部放大</span></div>', f"橙色 <b>{q9['n_low']}</b> 个不可靠（右下角放大）；其余绿色可靠，平均一致性 {q9['agreement_mean']:.2f}") + ar(12) +
        node("mach", "m", "n15", 16, "分析 · 统计", "多张照片放一起比", f'<div style="position:absolute;inset:6px;display:flex;flex-direction:column;gap:3px;justify-content:center" id="schips">{chip("按组比较（检验 + 效应量）")}{chip("按时间连成生长曲线")}</div>', "示例：脑类器官 30 天") + ar(13) +
        node("data", "s", "n16", 17, "结果", "曲线与比较", f'<img class="fit" src="{P["growth_png"]}">', "4 个克隆的面积变化") + ar(14) +
        node("mach", "m", "n17", 18, "输出", "报告生成器", '<div style="position:absolute;inset:6px 14%;background:#F6F8F7;border-radius:3px;padding:5px;display:flex;flex-direction:column;gap:3px" id="doc"></div>', "写报告 + 记录权重/参数/版本") + ar(15) +
        node("data", "l", "n18", 19, "最终结果", "报告 + 运行记录", f'<img src="{P["report_thumb"]}" style="object-fit:cover;object-position:top">', "report.html（双击可开）+ manifest.json（照片校验码、权重哈希、参数、版本），任何人可复现"))

HTML = """<title>Orgalyst 平台演示</title>
<style>__CSS____EXTRA__</style>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div><a href="#flow">全景流程</a><a href="#diff">补充：方向图是怎么来的</a><a href="#diam">补充：量错大小会怎样</a><a href="#notes">阅读说明</a></nav>
<main>
<header class="hd">
  <div class="eyebrow">Orgalyst · 一张照片的完整旅程 · 2026-09-16</div>
  <h1>从一句话到一份报告：整条链路一次看全</h1>
  <p class="sub">按序号 ①→⑲ 读：第一行从左到右，行尾向下，第二行从右到左，再向下，第三行从左到右。白色卡片是<b>东西</b>，绿色盒子是<b>处理它的模型或工具</b>；<b>大的是关键环节，小的是中间细节</b>。示例是一张真实的肠类器官显微照片，所有结果都来自这次真实运行。</p>
</header>
<section id="flow">
<div class="ctl"><button id="b-play" class="primary">暂停</button><button id="b-prev">上一步</button><button id="b-next">下一步</button><button id="b-restart">从头播放</button>
<label class="small" style="display:flex;align-items:center;gap:6px">速度 <select id="spd" style="font:inherit;font-size:13px"><option value="1.6">慢</option><option value="1" selected>正常</option><option value="0.6">快</option></select></label><span class="small" id="stepno"></span></div>
<div class="legend2"><span><i style="background:var(--paper);border:1.5px solid var(--rule)"></i>东西（数据）</span><span><i style="background:var(--accent-soft);border:2px solid var(--accent)"></i>模型 / 工具</span><span>大卡片 = 关键环节（照片、U-Net、轮廓、报告），小卡片 = 中间细节</span><span>箭头：左边的东西送进盒子，盒子另一边是得到的东西</span></div>
<div class="bar"><i id="bar"></i></div>
<div class="boardwrap"><div class="board" id="board">
  <div class="rows">
    <div class="rowl" id="r1">__ROW1__</div>
    <div class="rowl rev" id="r2">__ROW2__</div>
    <div class="rowl" id="r3">__ROW3__</div>
  </div>
  <div class="down" id="dn1">__DOWN__</div><div class="down" id="dn2">__DOWN__</div>
  <div class="token" id="token"></div>
</div></div>
<div class="cap" id="cap">点「播放」开始；也可以直接按序号读图。</div>
</section>
<h2 id="diff">__TAIL__
</main>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>__JS__
function placeDown(){const b=board.getBoundingClientRect();const r1=$('#r1').getBoundingClientRect(),r2=$('#r2').getBoundingClientRect(),r3=$('#r3').getBoundingClientRect();const n6=$('#n6').getBoundingClientRect(),n12=$('#n12').getBoundingClientRect();
  const d1=$('#dn1'),d2=$('#dn2');d1.style.left=(n6.left-b.left+n6.width/2-22)+'px';d1.style.top=(r1.bottom-b.top-2)+'px';d2.style.left=(n12.left-b.left+n12.width/2-22)+'px';d2.style.top=(r2.bottom-b.top-2)+'px';}
window.addEventListener('resize',placeDown);setTimeout(placeDown,100);setTimeout(placeDown,800);
const _go=go;go=function(i){_go(i);placeDown();$('#dn1').classList.toggle('on',i===7);$('#dn2').classList.toggle('on',i===13);};
__DIFFJS__
</script>
"""
JS2 = JS.replace("$('#w1').classList.toggle('on',i===7);$('#w2').classList.toggle('on',i===13);", "")
JS2 = JS2.replace("function go(i){", "var go=function(i){").replace("$('#cap').textContent=NODES[i].cap;", "$('#cap').textContent=NODES[i].cap;")
rep = {"__CSS__": CSS, "__EXTRA__": EXTRA, "__DATA__": DATA, "__ROW1__": ROW1, "__ROW2__": ROW2, "__ROW3__": ROW3, "__DOWN__": DOWN, "__WID__": wid, "__TAIL__": TAIL, "__JS__": JS2, "__DIFFJS__": DIFFJS,
       "__GT__": str(P["gt_instances"]), "__DW__": str(df["w"] * 4), "__DH__": str(df["h"] * 4), "__NIT__": str(min(400, 2 * round((df["w"] ** 2 + df["h"] ** 2) ** 0.5))),
       "__DI_S__": di["small"]["image"], "__DI_SN__": str(di["small"]["n"]), "__DI_A__": di["auto"]["image"], "__DI_AD__": f"{di['auto']['diameter']:.0f}", "__DI_AN__": str(di["auto"]["n"]),
       "__DI_L__": di["large"]["image"], "__DI_LN__": str(di["large"]["n"]),
       "__DB_A__": db["auto"]["image"], "__DB_AD__": f"{db['auto']['diameter']:.0f}", "__DB_AN__": str(db["auto"]["n"]), "__DB_D__": db["d404"]["image"], "__DB_DN__": str(db["d404"]["n"]), "__DB_F__": db["finetuned"]["image"], "__DB_FN__": str(db["finetuned"]["n"]),
       "__RS_O__": rs["original"], "__RS_OW__": str(rs["original_size"][0]), "__RS_OH__": str(rs["original_size"][1]), "__RS_S__": rs["scaled"], "__RS_SW__": str(rs["scaled_size"][0]), "__RS_SH__": str(rs["scaled_size"][1]), "__RS_SW3__": str(rs["scaled_size"][0] * 3), "__RS_SH3__": str(rs["scaled_size"][1] * 3)}
html = HTML
for _ in range(2):
    for k, v in rep.items(): html = html.replace(k, v)
i = html.find('<h2 id="diff">'); j = html.find('<h2 id="diam">'); assert 0 < i < j; html = html[:i] + html[j:]
html = html.replace('<a href="#diff">补充：方向图是怎么来的</a>', '')
left = set(re.findall(r"__[A-Z_0-9]+__", html)); assert not left, left
open(f"{S}/orgalyst_scene.html", "w", encoding="utf-8").write(html); print("written", len(html) // 1024, "KB")
