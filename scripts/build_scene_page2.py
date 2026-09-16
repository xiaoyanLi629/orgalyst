# -*- coding: utf-8 -*-
"""Orgalyst 平台场景动画 v2：分割流水线横贯舞台，每个模块有形象的图形（尺寸估计表盘、缩放器、切块器、U-Net 网络图 + cyto3 权重插件、
三张输出图、流场追踪器），图块飞入 U-Net、脉冲穿过网络、输出弹出；下排为掩码 → 形态测量 → 质控 → 报告；右列运行目录。"""
import base64, json, re
S = "/private/tmp/claude-501/-Users-xiaoyanli/0850d9a1-4ef3-4938-beed-610f045d4857/scratchpad"
P = json.load(open(f"{S}/pipeline_demo_data.json", encoding="utf-8"))
C = json.load(open(f"{S}/cellpose_demo_data.json", encoding="utf-8"))
P["report_thumb"] = "data:image/jpeg;base64," + base64.b64encode(open(f"{S}/report_thumb_small.jpg", "rb").read()).decode()
P["growth_png"] = "data:image/png;base64," + base64.b64encode(open(f"{S}/growth_brain_test.png", "rb").read()).decode()
DATA = json.dumps(dict(P=P, diffusion=C["diffusion"], diam_i=C["diameter_intestine"], diam_b=C["diameter_brain"], rescale=C["rescale"]), ensure_ascii=False)
assert "</script" not in DATA
base = open(f"{S}/build_scene_page.py", encoding="utf-8").read()
CSS = open(f"{S}/design.html", encoding="utf-8").read().split("<style>")[1].split("</style>")[0]
r2, t3, m8, q9, m10 = P["s2_rescale"], P["s3_tiles"], P["s8_measure"], P["s9_qc"], P["s10_manifest"]
di, db, rs, df = C["diameter_intestine"], C["diameter_brain"], C["rescale"], C["diffusion"]
wid = m10["model"].split(":")[-1][:8]

EXTRA = """
main{max-width:1040px}main>p,main>h2,main>header,main>.two{max-width:76ch}
.scenewrap{overflow-x:auto;margin:14px 0 6px}
.scene{position:relative;width:100%;min-width:920px;aspect-ratio:1000/720;border:1px solid var(--rule);border-radius:8px;background:var(--panel);overflow:hidden;font-size:12px;line-height:1.4}
.ring{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0}
.seg{fill:none;stroke:var(--rule);stroke-width:3;opacity:.7;transition:stroke .3s,opacity .3s}
.seg.on{stroke:var(--accent);opacity:1;stroke-dasharray:10 8;animation:dash .6s linear infinite}.seg.done{stroke:var(--accent);opacity:.45}
@keyframes dash{to{stroke-dashoffset:-18}}
.rhp{fill:var(--rule)}
.zone{position:absolute;z-index:1;display:flex;flex-direction:column;gap:5px;padding:8px 10px;border-radius:8px;background:var(--paper);border:1px solid var(--rule);overflow:hidden;transition:box-shadow .35s,border-color .35s,opacity .35s}
.zone.on{border-color:var(--accent);box-shadow:0 0 0 4px rgba(14,122,108,.16),0 8px 22px rgba(0,0,0,.10)}.zone.done{border-color:var(--accent)}.zone.idle{opacity:.7}
.zt{font-size:12.5px;font-weight:700;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.zt .num{font-family:var(--mono);font-size:10px;color:var(--accent);letter-spacing:.08em}
.chip{font-family:var(--mono);font-size:10px;padding:0 6px;border-radius:9px;border:1px solid var(--rule);color:var(--muted);white-space:nowrap}.chip.ok{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.zsub{font-size:10.5px;color:var(--muted);line-height:1.35;margin-top:auto}
.z-agent{left:2%;top:1.5%;width:80%;height:11%;flex-direction:row;align-items:center;gap:12px}
.z-agent .bubble{flex:1 1 38%;min-width:0;border:1px solid var(--rule);border-radius:6px;padding:4px 10px;line-height:1.35;background:var(--panel);max-height:2.9em;overflow:hidden}
.z-agent .plan{flex:1 1 46%;display:flex;gap:5px;flex-wrap:wrap}.z-agent .plan .chip{opacity:.35;transition:opacity .3s}.z-agent .plan .chip.ok{opacity:1}
.z-seg{left:2%;top:14.5%;width:80%;height:36%}
.z-trace{left:84%;top:1.5%;width:14%;height:97%}
.z-mask{left:2%;top:53%;width:17%;height:45.5%}.z-measure{left:21%;top:53%;width:27%;height:45.5%}.z-qc{left:50%;top:53%;width:15%;height:45.5%}.z-out{left:67%;top:53%;width:15%;height:45.5%}
.conv{display:flex;gap:6px;align-items:stretch;flex:1;min-height:0}
.st{display:flex;flex-direction:column;gap:3px;min-width:0;opacity:.4;transition:opacity .3s;position:relative}.st.on,.st.done{opacity:1}
.st .sl{font-size:10.5px;line-height:1.25;color:var(--muted)}.st.on .sl{color:var(--ink)}.st .sl b{display:block;font-size:11px;color:var(--ink)}
.st canvas,.st .box{width:100%;border:1px solid var(--rule);border-radius:4px;background:#0d1214;display:block}
.st canvas{aspect-ratio:1/1;height:auto}
.st.w1,.st.w2,.st.wo{flex:1 1 0}.st.wu{flex:1.9 1 0}
.arrowc{flex:0 0 10px;align-self:center;color:var(--muted);font-size:13px;text-align:center;padding-bottom:26px}
.thumb{width:100%;border:1px solid var(--rule);border-radius:4px;display:block;background:#0d1214}
/* 表盘 */
.gauge{aspect-ratio:1/1;position:relative}.gauge svg{width:100%;height:100%}.gauge .needle{transform-origin:50px 60px;transform:rotate(-90deg);transition:transform 1.4s cubic-bezier(.3,.8,.3,1)}
.gauge .gv{position:absolute;left:0;right:0;bottom:6px;text-align:center;font-family:var(--mono);font-size:11px;color:#E3E9E6}
/* U-Net */
.unet{aspect-ratio:176/96;position:relative}.unet svg{width:100%;height:100%}
.unet .blk{fill:#1B2529;stroke:#5A6A70;stroke-width:1;transition:fill .25s,stroke .25s}.unet .blk.lit{fill:#3FB59F;stroke:#E3E9E6}
.unet .skip{stroke:#5A6A70;stroke-width:1;stroke-dasharray:3 2;fill:none}.unet .skip.lit{stroke:#3FB59F}
.unet .plug{fill:#9A6A12;stroke:#F5E9CF;stroke-width:1}.unet .plug.ft{fill:#0E7A6C;stroke:#D9EEE9}
.unet text{font-family:ui-monospace,Menlo,monospace;font-size:7px;fill:#E3E9E6}
/* 三张输出图 */
.st .box.outs{display:grid;grid-template-columns:1fr 1fr;gap:3px;padding:3px;box-sizing:border-box;align-content:start}.outs img{width:100%;aspect-ratio:1/1;height:auto;object-fit:cover;opacity:0;transform:scale(.7);transition:all .4s;border-radius:2px}.outs img.in{opacity:1;transform:none}
.outs .lab{grid-column:1/3;font-size:9px;color:#E3E9E6;font-family:ui-monospace,Menlo,monospace;text-align:center;align-self:center}
/* 飞行图块 */
.fly{position:absolute;z-index:4;width:14px;height:14px;border:1px solid #E3E9E6;background:rgba(63,181,159,.85);border-radius:2px;left:0;top:0;opacity:0;transition:left .7s ease-in,top .7s ease-in,opacity .2s;pointer-events:none}
.count{font-family:var(--serif);font-size:24px;line-height:1.1;font-variant-numeric:tabular-nums}.count small{font-family:var(--sans);font-size:10.5px;color:var(--muted);display:block}
.tbl{flex:1;min-height:0;overflow:hidden}.tbl table{width:100%;border-collapse:collapse;font-size:10.5px;min-width:0}.tbl th,.tbl td{padding:2px 4px;border-bottom:1px solid var(--rule);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl th{background:var(--panel);font-weight:600}
.tbl tr{opacity:0;transition:opacity .3s}.tbl tr.in{opacity:1}
.metrics{display:grid;grid-template-columns:1fr;gap:2px;font-size:10.5px}.metrics b{font-family:var(--mono);font-weight:500;float:right}
.trace{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;gap:3px;font-family:var(--mono);font-size:10px;line-height:1.3}
.trace .tl{border-left:2px solid var(--accent);padding:2px 5px;background:var(--accent-soft);border-radius:0 3px 3px 0;opacity:0;transform:translateX(6px);transition:all .35s;word-break:break-all}.trace .tl.in{opacity:1;transform:none}
.token{position:absolute;z-index:3;left:50%;top:7%;transform:translate(-50%,-50%);display:flex;align-items:center;gap:6px;padding:3px 8px 3px 3px;border-radius:20px;background:var(--accent);color:var(--accent-ink);font-size:11px;font-weight:600;box-shadow:0 6px 16px rgba(14,122,108,.35);transition:left .9s cubic-bezier(.4,0,.2,1),top .9s cubic-bezier(.4,0,.2,1);white-space:nowrap;pointer-events:none}
.token img{width:20px;height:20px;border-radius:50%;object-fit:cover;background:#000}
.cap{margin:8px 0 0;padding:8px 14px;border-radius:6px;background:var(--ink);color:var(--paper);font-size:13.5px;line-height:1.5;min-height:2.6em}
.ctl{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px;align-items:center}
button{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);color:var(--ink);cursor:pointer}
button:hover,button:focus-visible{border-color:var(--accent);outline:none}button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.bar{height:3px;background:var(--rule);border-radius:2px;margin:8px 0 0;overflow:hidden}.bar i{display:block;height:100%;width:0;background:var(--accent)}
.stage2{display:grid;grid-template-columns:minmax(0,1fr) 230px;gap:16px;align-items:start;margin:12px 0}
@media (max-width:700px){.stage2{grid-template-columns:minmax(0,1fr)}}
.stage2 canvas{max-width:100%;height:auto;border:1px solid var(--rule);border-radius:4px;background:#000;display:block}
.legend{font-size:13px;color:var(--muted);line-height:1.6}.legend b{color:var(--ink)}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:12px 0 18px}.grid3 figure{margin:0}.grid3 img{width:100%;border:1px solid var(--rule);border-radius:4px}.grid3 figcaption{font-size:13px;color:var(--muted);margin-top:4px;line-height:1.5}.grid3 figcaption b{color:var(--ink)}
.two{display:grid;grid-template-columns:1fr auto;gap:16px;align-items:center;margin:12px 0}.two img{border:1px solid var(--rule);border-radius:4px;image-rendering:pixelated}
@media (max-width:600px){.two{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){.token,.zone,.seg,.st,.tbl tr,.trace .tl,.fly,.gauge .needle,.outs img{transition:none;animation:none}}
"""

UNET = """<svg viewBox="0 0 176 96" aria-label="U-Net 结构示意">
 <rect class="blk" id="e1" x="8" y="6" width="26" height="12"/><rect class="blk" id="e2" x="20" y="24" width="22" height="12"/><rect class="blk" id="e3" x="32" y="42" width="18" height="12"/><rect class="blk" id="e4" x="44" y="60" width="14" height="12"/>
 <rect class="blk" id="bt" x="70" y="72" width="36" height="12"/>
 <rect class="blk" id="d4" x="118" y="60" width="14" height="12"/><rect class="blk" id="d3" x="126" y="42" width="18" height="12"/><rect class="blk" id="d2" x="134" y="24" width="22" height="12"/><rect class="blk" id="d1" x="142" y="6" width="26" height="12"/>
 <path class="skip" id="k1" d="M34 12 H142"/><path class="skip" id="k2" d="M42 30 H134"/><path class="skip" id="k3" d="M50 48 H126"/><path class="skip" id="k4" d="M58 66 H118"/>
 <text x="12" y="15">编码</text><text x="146" y="15">解码</text><text x="73" y="81">风格向量</text>
 <rect class="plug" id="plug" x="60" y="88" width="56" height="7" rx="2"/><text id="plugt" x="63" y="94" style="font-size:5.5px">权重: cyto3 (通用)</text>
</svg>"""
GAUGE = """<svg viewBox="0 0 100 70" aria-label="尺寸估计表盘">
 <path d="M10 60 A40 40 0 0 1 90 60" fill="none" stroke="#5A6A70" stroke-width="6"/>
 <path d="M10 60 A40 40 0 0 1 50 20" fill="none" stroke="#3FB59F" stroke-width="6"/>
 <g stroke="#E3E9E6" stroke-width="1"><line x1="10" y1="60" x2="15" y2="60"/><line x1="50" y1="20" x2="50" y2="25"/><line x1="90" y1="60" x2="85" y2="60"/></g>
 <text x="4" y="68" font-size="6" fill="#E3E9E6" font-family="ui-monospace">0</text><text x="45" y="14" font-size="6" fill="#E3E9E6" font-family="ui-monospace">75</text><text x="84" y="68" font-size="6" fill="#E3E9E6" font-family="ui-monospace">150 px</text>
 <line class="needle" id="needle" x1="50" y1="60" x2="50" y2="26" stroke="#F5E9CF" stroke-width="2"/><circle cx="50" cy="60" r="3" fill="#F5E9CF"/>
</svg><div class="gv" id="gv">直径 —</div>"""

HTML = """<title>Orgalyst 平台演示</title>
<style>__CSS____EXTRA__</style>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div><a href="#scene">平台场景动画</a><a href="#diff">训练目标：热扩散</a><a href="#diam">直径参数对照</a><a href="#notes">阅读说明</a></nav>
<main>
<header class="hd">
  <div class="eyebrow">Orgalyst · 平台场景 · 2026-09-16</div>
  <h1>一张类器官图在 Orgalyst 里走过的每一个部件</h1>
  <p class="sub">舞台上摆着平台的每个部件——包括看得见的 U-Net 网络和装在它上面的权重——一枚数据令牌从用户的一句话出发，依次经过各部件；走到哪里，哪里就当场产出真实结果，右侧运行目录同步留下记录。示例：OrgLine 肠类器官测试集一张 2048×2048 宽场图（人工标注 __GT__ 个）。</p>
</header>

<section id="scene">
<div class="ctl"><button id="b-play" class="primary">暂停</button><button id="b-prev">上一步</button><button id="b-next">下一步</button><button id="b-restart">从头播放</button>
<label class="small" style="display:flex;align-items:center;gap:6px">速度 <select id="spd" style="font:inherit;font-size:13px"><option value="1.6">慢</option><option value="1" selected>正常</option><option value="0.6">快</option></select></label><span class="small" id="stepno"></span></div>
<div class="bar"><i id="bar"></i></div>
<div class="scenewrap"><div class="scene" id="scene">
  <svg class="ring" viewBox="0 0 1000 720" preserveAspectRatio="none">
    <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z" class="rhp"/></marker></defs>
    <path class="seg" id="p0" d="M 420 90 C 420 100 60 96 60 104" marker-end="url(#ah)"/>
    <path class="seg" id="p1" d="M 760 364 C 760 400 110 340 110 380" marker-end="url(#ah)"/>
    <path class="seg" id="p2" d="M 190 545 L 206 545" marker-end="url(#ah)"/>
    <path class="seg" id="p3" d="M 480 545 L 496 545" marker-end="url(#ah)"/>
    <path class="seg" id="p4" d="M 650 545 L 666 545" marker-end="url(#ah)"/>
    <path class="seg" id="p5" d="M 820 545 L 836 545" marker-end="url(#ah)"/>
  </svg>
  <div class="zone z-agent" id="z-agent"><div class="zt"><span class="num">00</span>对话式助手</div><div class="bubble" id="bubble">你：</div><div class="plan" id="plan"><span class="chip">识别意图：单批图像形态分析</span><span class="chip">选工具：analyze_images</span><span class="chip">organ = intestine → 肠专用权重</span><span class="chip">pixel_size 未给 → 像素单位</span></div></div>

  <div class="zone z-seg" id="z-seg"><div class="zt"><span class="num">01–07</span>分割流水线 · Cellpose <span class="chip">架构与后处理未改</span> <span class="chip ok">权重：cyto3 → OrgLine 肠微调 __WID__</span></div>
    <div class="conv">
      <div class="st w1" id="st-in"><img class="thumb" id="in-img" alt="输入图" style="aspect-ratio:1/1;object-fit:cover"><div class="sl"><b>01 输入</b>__W__×__H__ · 灰度 · 肠</div></div>
      <div class="arrowc">→</div>
      <div class="st w1" id="st-gauge"><div class="box gauge">__GAUGE__</div><div class="sl"><b>02 尺寸估计器</b>风格向量→直径</div></div>
      <div class="arrowc">→</div>
      <div class="st w2" id="st-scale"><canvas width="140" height="140"></canvas><div class="sl"><b>03 缩放器</b>目标缩到 ≈30 px</div></div>
      <div class="arrowc">→</div>
      <div class="st w2" id="st-tiles"><canvas width="140" height="140"></canvas><div class="sl"><b>04 切块器</b>__NT__ 块 224²，重叠一半</div></div>
      <div class="arrowc">→</div>
      <div class="st wu" id="st-unet"><div class="box unet">__UNET__</div><div class="sl"><b>05 U-Net</b>4 级编解码+跳跃连接；权重可换</div></div>
      <div class="arrowc">→</div>
      <div class="st wo" id="st-outs"><div class="box outs"><img id="o-flow" alt="流场"><img id="o-prob" alt="目标概率"><img id="o-thr" alt="阈值化"><div class="lab">流场 · 概率 · 阈值</div></div><div class="sl"><b>06 三张输出图</b>拼回整图，阈值化</div></div>
      <div class="arrowc">→</div>
      <div class="st w2" id="st-track"><canvas width="140" height="140"></canvas><div class="sl"><b>07 流场追踪器</b>像素沿箭头汇聚</div></div>
    </div>
  </div>
  <div class="zone z-trace" id="z-trace"><div class="zt"><span class="num">12</span>运行目录</div><div class="chip" id="runid">runs/analysis_…</div><div class="trace" id="trace"></div><div class="zsub">manifest.json：输入 MD5、权重哈希、参数、版本。</div></div>
  <div class="zone z-mask" id="z-mask"><div class="zt"><span class="num">08</span>实例掩码</div><img class="thumb" id="mask-img" alt="掩码叠加" style="opacity:0;transition:opacity .6s"><div class="count" id="mask-n">—<small>个实例（人工标注 __GT__）</small></div></div>
  <div class="zone z-measure" id="z-measure"><div class="zt"><span class="num">09</span>形态测量 <span class="chip">📏 regionprops</span></div><div class="tbl" id="tbl"></div><div class="zsub" id="msum">每个类器官一行；贴边实例汇总时排除。</div></div>
  <div class="zone z-qc" id="z-qc"><div class="zt"><span class="num">10</span>质量控制 <span class="chip">🔍</span></div><img class="thumb" id="qc-img" alt="质控叠加" style="opacity:0;transition:opacity .6s"><div class="metrics" id="qcm"></div></div>
  <div class="zone z-out" id="z-out"><div class="zt"><span class="num">11</span>汇总 → 报告 <span class="chip">📄</span></div><img class="thumb" id="out-img" alt="汇总图" style="opacity:0;transition:opacity .6s"><div class="zsub" id="outsub">多图按分组/时间点汇总，再生成单文件报告。</div></div>
  <div class="token" id="token"><img id="tok-img" alt=""><span id="tok-txt">请求</span></div>
  <div class="fly" id="f0"></div><div class="fly" id="f1"></div><div class="fly" id="f2"></div><div class="fly" id="f3"></div><div class="fly" id="f4"></div>
</div></div>
<div class="cap" id="cap">点「播放」开始</div>
</section>

<h2 id="diff">训练目标：从人工轮廓到流场（热扩散）</h2>
<p>第 05 步 U-Net 输出的"流场"不需要人来标，它由人工画的轮廓用程序算出来：取轮廓内离边界最远的点作为中心，中心持续放热、热量只在轮廓内传播，迭代到稳定；温度场的梯度就是每个像素的箭头，全部指向中心。用热扩散而不是"直接指向质心"，是为了让弯曲、凹陷的形状也能从任何位置沿箭头走到内部。微调时网络学的就是"从原图预测这张流场"。下面这个实例取自演示裁块中最不凸的一个类器官。</p>
<div class="stage2">
  <canvas id="cv-diff" width="__DW__" height="__DH__"></canvas>
  <div><div class="ctl" style="margin:0 0 8px"><button id="b-diff-play">播放扩散</button><button id="b-diff-reset">重置</button></div>
  <div class="legend"><b>颜色</b>：温度（对数刻度），亮为高。<br><b>箭头</b>：扩散完成后按温度梯度画出。<br><b>迭代</b>：按物体大小自适应（约外接框对角线的两倍），这里 __NIT__ 次。</div><div class="small" id="st-diff" style="margin-top:6px"></div></div>
</div>

<h2 id="diam">直径参数：给错会怎样</h2>
<p>第 02–03 步的缩放系数由直径决定。同一裁块、同一个微调模型，只改直径：</p>
<div class="grid3">
  <figure><img src="__DI_S__"><figcaption><b>直径 12（偏小）</b>：图被放大，网络在放大后的图里找 30 px 的东西，大类器官被拆碎或丢失，得到 __DI_SN__ 个实例</figcaption></figure>
  <figure><img src="__DI_A__"><figcaption><b>直径 __DI_AD__（尺寸估计器）</b>：__DI_AN__ 个实例，人工标注 35 个</figcaption></figure>
  <figure><img src="__DI_L__"><figcaption><b>直径 150（偏大）</b>：图被缩得很小，所有类器官糊成一团，只得到 __DI_LN__ 个实例</figcaption></figure>
</div>
<p>脑类器官更极端：cyto3 自带的尺寸估计器在细胞图上训练，看到 400 px 的大团块猜出 __DB_AD__ px，按此放大十几倍后网络什么也找不到；把直径改成 404，同一套 cyto3 权重立刻分出来；微调后的脑专用权重把这个直径记在了模型里。</p>
<div class="two"><div><img src="__RS_O__" alt="脑类器官原图" style="max-width:100%"><div class="small">脑类器官原图 __RS_OW__×__RS_OH__ px，目标约 404 px</div></div><div><img src="__RS_S__" width="__RS_SW3__" height="__RS_SH3__" alt="缩放后"><div class="small">按直径 404 缩放到目标 30 px 后：__RS_SW__×__RS_SH__ px（放大 3 倍显示）</div></div></div>
<div class="grid3">
  <figure><img src="__DB_A__"><figcaption><b>cyto3 零样本，自动直径 __DB_AD__</b>：__DB_AN__ 个实例</figcaption></figure>
  <figure><img src="__DB_D__"><figcaption><b>cyto3 零样本，直径 404</b>：__DB_DN__ 个实例</figcaption></figure>
  <figure><img src="__DB_F__"><figcaption><b>脑专用微调权重（自带直径 404）</b>：__DB_FN__ 个实例</figcaption></figure>
</div>
<p>这解释了 E1 里的三个现象：cyto3 零样本在脑上 AP50 只有 0.005、给对直径后到 0.63；联合四器官模型自带直径 183 px 对任何器官都不对；胰腺癌测试图里大小目标混在一起时召回只有一半。Orgalyst 按器官选直径策略：脑用两遍推理，肠和胰腺癌用尺寸估计器逐图估计，结肠用模型自带直径。</p>

<h2 id="notes">阅读说明</h2>
<p>舞台上 01 到 07 是 Cellpose（Stringer 等，2021）的推理：尺寸估计、按直径缩放、224 窗口切块、U-Net 输出流场与目标概率、阈值化后沿流场追踪聚成实例、过滤后放大回原尺寸。本项目未改动其架构与后处理，改的是装在 U-Net 上的权重（cyto3 → 按器官微调）和直径策略；U-Net 本身也可以整体换成其他能做逐像素预测的网络（Cellpose-SAM 即把编码器换成 ViT）。08 之后是 Orgalyst 加的确定性分析，全部不经过大模型；对话式助手只做 00 步。所有数字均来自本次真实运行；追踪一步的粒子为示意。</p>
<p class="small">参考：Stringer C 等，Cellpose: a generalist algorithm for cellular segmentation，Nat Methods 2021 · Stringer C, Pachitariu M，Cellpose3，Nat Methods 2025 · Pachitariu M 等，Cellpose-SAM，bioRxiv 2025。</p>
</main>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const X=JSON.parse(document.getElementById('data').textContent),P=X.P;
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const $=s=>document.querySelector(s);
function i8(b64){const s=atob(b64);const a=new Float32Array(s.length);for(let i=0;i<s.length;i++){let v=s.charCodeAt(i);if(v>127)v-=256;a[i]=v/127;}return a;}
function u16(b64){const s=atob(b64);const a=new Uint16Array(s.length/2);for(let i=0;i<a.length;i++)a[i]=s.charCodeAt(2*i)|(s.charCodeAt(2*i+1)<<8);return a;}
function bits(b64,n){const s=atob(b64);const a=new Uint8Array(n);for(let i=0;i<n;i++)a[i]=(s.charCodeAt(i>>3)>>(7-(i&7)))&1;return a;}
const hsl=i=>'hsl('+((i*137.508)%360)+',65%,58%)';
const img=src=>{const e=new Image();e.src=src;return e;};
const IM={input:img(P.s1_input.image),norm:img(P.s2_rescale.image),small:img(P.s2_rescale.small),flow:img(P.s4_net.flow),prob:img(P.s4_net.prob),thresh:img(P.s5_thresh.image)};
const N=512,dx=i8(P.s4_net.dx),dy=i8(P.s4_net.dy),cp=i8(P.s4_net.cellprob),mk=u16(P.s6_track.masks);
$('#in-img').src=P.s1_input.image;$('#mask-img').src=P.s7_masks.overlay;$('#qc-img').src=P.s9_qc.overlay;$('#tok-img').src=P.s1_input.image;
$('#o-flow').src=P.s4_net.flow;$('#o-prob').src=P.s4_net.prob;$('#o-thr').src=P.s5_thresh.image;
$('#runid').textContent='runs/analysis_20260916_'+Math.random().toString(16).slice(2,8);
const Z=['z-agent','z-seg','z-mask','z-measure','z-qc','z-out','z-trace'];
const ST=['st-in','st-gauge','st-scale','st-tiles','st-unet','st-outs','st-track'];
const TOK={'z-agent':[24,7],'st-in':[7.5,22],'st-gauge':[16.5,22],'st-scale':[26,22],'st-tiles':[36,22],'st-unet':[51,22],'st-outs':[66,22],'st-track':[76,22],'z-mask':[10.5,68],'z-measure':[34.5,68],'z-qc':[57.5,68],'z-out':[74.5,68],'z-trace':[91,50]};
let anim=null,timers=[];
function later(fn,ms){timers.push(setTimeout(fn,reduce?0:ms));}
function clearAll(){cancelAnimationFrame(anim);timers.forEach(clearTimeout);timers=[];}
function stOn(id){ST.forEach((s,i)=>{const e=$('#'+s);e.classList.toggle('on',s===id);e.classList.toggle('done',ST.indexOf(id)>i);});}
function cx(id){return $('#'+id+' canvas').getContext('2d');}
function label(c,t){c.fillStyle='rgba(13,18,20,.85)';c.fillRect(0,124,140,16);c.fillStyle='#E3E9E6';c.font='10px ui-monospace,Menlo,monospace';c.fillText(t,4,135);}
const SL={
 scale(inst){const c=cx('st-scale'),sc=P.s2_rescale.scale;let k=0;cancelAnimationFrame(anim);const f=()=>{k=Math.min(1,k+((reduce||inst)?1:.03));const s=1-(1-sc)*k,w=140*s;c.fillStyle='#0d1214';c.fillRect(0,0,140,140);c.drawImage(IM.norm,(140-w)/2,(140-w)/2,w,w);c.strokeStyle='#3FB59F';c.setLineDash([3,3]);c.strokeRect((140-w)/2+.5,(140-w)/2+.5,w-1,w-1);c.setLineDash([]);label(c,'×'+s.toFixed(2)+' → '+Math.round(P.shape[0]*s)+'²');if(k<1)anim=requestAnimationFrame(f);};f();},
 tiles(inst){const c=cx('st-tiles'),T=P.s3_tiles.tiles,sw=P.s2_rescale.small_size[0],f=140/sw;c.fillStyle='#0d1214';c.fillRect(0,0,140,140);c.drawImage(IM.small,0,0,140,140);let i=0;cancelAnimationFrame(anim);const g=()=>{for(let k=0;k<((reduce||inst)?T.length:3)&&i<T.length;k++,i++){const [x,y,w,h]=T[i];c.fillStyle='rgba(63,181,159,.12)';c.fillRect(x*f,y*f,w*f,h*f);c.strokeStyle='rgba(63,181,159,.9)';c.strokeRect(x*f+.5,y*f+.5,w*f-1,h*f-1);}label(c,i+'/'+T.length+' 块');if(i<T.length)anim=requestAnimationFrame(g);};g();},
 track(inst){const c=cx('st-track'),parts=[];for(let y=2;y<N;y+=6)for(let x=2;x<N;x+=6){const i=y*N+x;if(cp[i]>0)parts.push({x:x+.5,y:y+.5,id:mk[i]});}let step=0;const STEPS=200,f=140/N;cancelAnimationFrame(anim);
   const samp=(a,x,y)=>{const x0=Math.max(0,Math.min(N-2,x|0)),y0=Math.max(0,Math.min(N-2,y|0)),fx=x-x0,fy=y-y0;return a[y0*N+x0]*(1-fx)*(1-fy)+a[y0*N+x0+1]*fx*(1-fy)+a[(y0+1)*N+x0]*(1-fx)*fy+a[(y0+1)*N+x0+1]*fx*fy;};
   const g=()=>{for(let k=0;k<((reduce||inst)?STEPS:6)&&step<STEPS;k++,step++)for(const p of parts){p.x=Math.max(0,Math.min(N-1,p.x+samp(dx,p.x,p.y)));p.y=Math.max(0,Math.min(N-1,p.y+samp(dy,p.x,p.y)));}
     c.drawImage(IM.input,0,0,140,140);c.fillStyle='rgba(0,0,0,.6)';c.fillRect(0,0,140,140);const done=step>=STEPS;for(const p of parts){c.fillStyle=done?hsl(p.id||0):'#3FB59F';c.fillRect(p.x*f-.8,p.y*f-.8,1.6,1.6);}label(c,done?P.s6_track.n+' 个汇聚点':'步 '+step+'/'+STEPS);if(!done)anim=requestAnimationFrame(g);};g();}
};
function gauge(inst){const d=P.s2_rescale.diameter,ang=-90+180*Math.min(1,d/150);$('#needle').style.transform='rotate('+(inst?ang:-90)+'deg)';if(!inst)later(()=>{$('#needle').style.transform='rotate('+ang+'deg)';},150);later(()=>{$('#gv').textContent='直径 '+d.toFixed(0)+' px';},inst?0:1300);}
function gaugeReset(){$('#needle').style.transform='rotate(-90deg)';$('#gv').textContent='直径 —';}
const UB=['e1','e2','e3','e4','bt','d4','d3','d2','d1'];
function unetReset(){UB.forEach(b=>$('#'+b).classList.remove('lit'));['k1','k2','k3','k4'].forEach(k=>$('#'+k).classList.remove('lit'));$('#plug').classList.remove('ft');$('#plugt').textContent='权重: cyto3 (通用)';['o-flow','o-prob','o-thr'].forEach(o=>$('#'+o).classList.remove('in'));for(let i=0;i<5;i++){const f=$('#f'+i);f.style.opacity=0;}}
function unetPlug(inst){const set=()=>{$('#plug').classList.add('ft');$('#plugt').textContent='权重: 肠微调 __WID__';};if(inst)set();else later(set,400);}
function flyTiles(inst){if(inst)return;for(let i=0;i<5;i++){const f=$('#f'+i);f.style.transition='none';f.style.left=(31+(i%3)*2.2)+'%';f.style.top=(24+Math.floor(i/3)*4)+'%';f.style.opacity=1;later(()=>{f.style.transition='';f.style.left='43%';f.style.top='24%';},80+i*220);later(()=>{f.style.opacity=0;},900+i*220);}}
function unetPulse(inst){UB.forEach((b,i)=>later(()=>{$('#'+b).classList.add('lit');if(i>=5)$('#k'+(9-i)).classList.add('lit');},inst?0:250+i*180));later(()=>{['o-flow','o-prob','o-thr'].forEach((o,i)=>later(()=>$('#'+o).classList.add('in'),i*300));},inst?0:2100);}
function traceAdd(t){const d=document.createElement('div');d.className='tl';d.textContent=t;$('#trace').appendChild(d);requestAnimationFrame(()=>d.classList.add('in'));}
function setTok(key,txt,imgsrc){const [l,t]=TOK[key];const e=$('#token');e.style.left=l+'%';e.style.top=t+'%';$('#tok-txt').textContent=txt;if(imgsrc)$('#tok-img').src=imgsrc;}
function type(el,text,ms){el.textContent='你：';let i=0;const f=()=>{if(i<text.length){el.textContent='你：'+text.slice(0,++i);later(f,ms);}};f();}
const cols=['编号','面积','直径','周长','圆度','实心','长宽比'];
const REQ='分析这批肠类器官明场图，给我形态汇总和一份报告。';
function tableHTML(cls){return '<table><tr class="'+cls+'">'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>'+P.s8_measure.rows.slice(0,7).map(r=>'<tr class="'+cls+'"><td>'+r[0]+'</td><td>'+r[1]+'</td><td>'+r[2]+'</td><td>'+r[3]+'</td><td>'+r[4]+'</td><td>'+r[5]+'</td><td>'+r[6]+'</td></tr>').join('')+'</table>';}
const msumTxt='非贴边 '+P.s8_measure.summary.n+' 个 · 面积中位数 '+P.s8_measure.summary.area_median.toFixed(0)+' px² · 直径中位数 '+P.s8_measure.summary.diam_median.toFixed(1)+' px · 圆度 '+P.s8_measure.summary.circ_median.toFixed(3);
const qcRows=()=>{const m=P.s9_qc;return [['失焦分数',m.focus.toFixed(3)],['光照不均',m.illum.toFixed(3)],['饱和像素',(100*m.sat).toFixed(1)+'%'],['一致性均值',m.agreement_mean.toFixed(2)],['低可信实例',m.n_low+' 个']];};
const STEPS=[
 {z:'z-agent',dur:5.0,cap:'00 · 用户一句话提出需求；助手识别任务类型、选择工具与参数（器官=肠 → 装载肠专用权重），它不看图也不算数。',run(){setTok('z-agent','请求');type($('#bubble'),REQ,40);[...$('#plan').children].forEach((c,i)=>later(()=>c.classList.add('ok'),2400+i*450));},end(){$('#bubble').textContent='你：'+REQ;[...$('#plan').children].forEach(c=>c.classList.add('ok'));}},
 {z:'z-seg',st:'st-in',dur:3.0,arrow:'p0',cap:'01 · 图像进入分割流水线：'+P.shape[0]+'×'+P.shape[1]+' 灰度。',run(){setTok('st-in','图像');stOn('st-in');later(()=>traceAdd('输入 '+P.source.slice(0,14)+'… md5 e3a1…9f2c'),800);},end(){traceAdd('输入 '+P.source.slice(0,14)+'… md5 e3a1…9f2c');}},
 {z:'z-seg',st:'st-gauge',dur:3.6,cap:'02 · 尺寸估计器（cyto3 的"风格向量 → 直径"小模型）看一眼整图，估出类器官约 '+P.s2_rescale.diameter.toFixed(0)+' px。这个数决定下一步的缩放系数。',run(){setTok('st-gauge','图像');stOn('st-gauge');gauge(false);later(()=>traceAdd('直径 '+P.s2_rescale.diameter.toFixed(1)+' px（sizemodel）'),1800);},end(){gauge(true);traceAdd('直径 '+P.s2_rescale.diameter.toFixed(1)+' px（sizemodel）');}},
 {z:'z-seg',st:'st-scale',dur:3.6,cap:'03 · 缩放器把图缩到目标约 30 px（×'+P.s2_rescale.scale.toFixed(2)+' → '+P.s2_rescale.small_size[0]+'²），灰度归一化到 1–99 百分位。网络只见过 30 px 尺度的目标。',run(){setTok('st-scale','图像');stOn('st-scale');SL.scale(false);later(()=>traceAdd('缩放 ×'+P.s2_rescale.scale.toFixed(2)),1600);},end(){stOn('st-scale');SL.scale(true);traceAdd('缩放 ×'+P.s2_rescale.scale.toFixed(2));}},
 {z:'z-seg',st:'st-tiles',dur:4.4,cap:'04 · 切块器按 224×224 切成 '+P.s3_tiles.n+' 块（重叠一半），图块逐块送进 U-Net。',run(){setTok('st-tiles','图块');stOn('st-tiles');SL.tiles(false);later(()=>flyTiles(false),1400);},end(){stOn('st-tiles');SL.tiles(true);}},
 {z:'z-seg',st:'st-unet',dur:5.4,cap:'05 · U-Net：4 级编码下采样、瓶颈处的风格向量、4 级解码上采样加跳跃连接。装在它上面的权重是 cyto3 在 OrgLine 肠数据上微调的版本；换权重不换架构。每块输出三张图。',run(){setTok('st-unet','图块');stOn('st-unet');unetPlug(false);unetPulse(false);later(()=>traceAdd('权重 intestine:'+P.s10_manifest.model.split(':')[1].slice(0,12)),3200);},end(){stOn('st-unet');unetPlug(true);unetPulse(true);traceAdd('权重 intestine:'+P.s10_manifest.model.split(':')[1].slice(0,12));}},
 {z:'z-seg',st:'st-outs',dur:3.8,cap:'06 · 三张输出图：水平流与垂直流（合成颜色图，色相 = 箭头方向）和目标概率；各块按中心高、边缘低的权重拼回整图，概率 > 0 的像素（'+(100*P.s5_thresh.frac).toFixed(1)+'%）判为目标。',run(){setTok('st-outs','三张图');stOn('st-outs');},end(){stOn('st-outs');}},
 {z:'z-seg',st:'st-track',dur:5.4,cap:'07 · 流场追踪器：目标像素沿箭头走约 200 步，同一类器官的像素汇聚到同一点 → '+P.s6_track.n+' 个实例；流场不一致的实例被过滤。',run(){setTok('st-track','流场');stOn('st-track');SL.track(false);},end(){stOn('st-track');SL.track(true);}},
 {z:'z-mask',dur:3.8,arrow:'p1',cap:'08 · 掩码放大回原尺寸：'+P.s7_masks.n+' 个实例（人工标注 '+P.gt_instances+'）。令牌从"图像"变成"掩码"。',run(){setTok('z-mask','掩码',P.s7_masks.overlay);stOn('');later(()=>{$('#mask-img').style.opacity=1;$('#mask-n').firstChild.textContent=P.s7_masks.n;},600);later(()=>traceAdd('masks/*.png · '+P.s7_masks.n+' 实例'),1400);},end(){ST.forEach(s=>$('#'+s).classList.add('done'));$('#mask-img').style.opacity=1;$('#mask-n').firstChild.textContent=P.s7_masks.n;$('#tok-img').src=P.s7_masks.overlay;traceAdd('masks/*.png · '+P.s7_masks.n+' 实例');}},
 {z:'z-measure',dur:5.2,arrow:'p2',cap:'09 · 形态测量：对每个实例算面积、等效直径、周长、圆度、实心度、长宽比；贴边实例汇总时排除（'+P.s8_measure.summary.border_excluded+' 个）。',run(){setTok('z-measure','特征表');$('#tbl').innerHTML=tableHTML('');[...$('#tbl').querySelectorAll('tr')].forEach((tr,i)=>later(()=>tr.classList.add('in'),300+i*230));later(()=>{$('#msum').textContent=msumTxt;traceAdd('tables/features.csv · '+P.s8_measure.n+' 行');},2500);},end(){$('#tbl').innerHTML=tableHTML('in');$('#msum').textContent=msumTxt;traceAdd('tables/features.csv · '+P.s8_measure.n+' 行');}},
 {z:'z-qc',dur:4.4,arrow:'p3',cap:'10 · 质量控制：图像级失焦/光照/饱和；实例级翻转旋转 '+P.s9_qc.k+' 次重分割，不稳定的实例记为低可信（橙色）。',run(){setTok('z-qc','特征表');later(()=>$('#qc-img').style.opacity=1,500);$('#qcm').innerHTML='';qcRows().forEach(([k,v],i)=>later(()=>{const d=document.createElement('div');d.innerHTML=k+' <b>'+v+'</b>';$('#qcm').appendChild(d);},900+i*280));later(()=>traceAdd('tables/qc.csv · 低可信 '+P.s9_qc.n_low),2500);},end(){$('#qc-img').style.opacity=1;$('#qcm').innerHTML=qcRows().map(([k,v])=>'<div>'+k+' <b>'+v+'</b></div>').join('');traceAdd('tables/qc.csv · 低可信 '+P.s9_qc.n_low);}},
 {z:'z-out',dur:4.8,arrow:'p4',cap:'11 · 汇总与报告：多张图按分组或时间点汇总（示例：脑类器官 4 个克隆的生长曲线），再渲染成单文件报告。',run(){setTok('z-out','报告');const o=$('#out-img');o.src=P.growth_png;later(()=>o.style.opacity=1,400);later(()=>{o.style.opacity=0;},2200);later(()=>{o.src=P.report_thumb;o.style.opacity=1;$('#outsub').textContent='report.html：概览、逐图表、分布图、叠加图、方法学模板、溯源表。';},2700);later(()=>traceAdd('growth.html · report.html'),3300);},end(){const o=$('#out-img');o.src=P.report_thumb;o.style.opacity=1;$('#outsub').textContent='report.html：概览、逐图表、分布图、叠加图、方法学模板、溯源表。';traceAdd('growth.html · report.html');}},
 {z:'z-trace',dur:4.0,arrow:'p5',cap:'12 · 全部产物落在一个运行目录；manifest.json 记录输入哈希、权重哈希、参数与版本。助手据此向用户汇报并回答追问。',run(){setTok('z-trace','完成');later(()=>traceAdd('manifest.json ✓ cellpose 3.1.1.3 · torch 2.14+cu130'),700);},end(){traceAdd('manifest.json ✓ cellpose 3.1.1.3 · torch 2.14+cu130');}},
];
let cur=-1,playing=!reduce,t0=0,speed=1,raf=null;
function reset(){clearAll();Z.forEach(z=>{const e=$('#'+z);e.classList.remove('on','done');e.classList.add('idle');});document.querySelectorAll('.seg').forEach(p=>p.classList.remove('on','done'));$('#trace').innerHTML='';$('#tbl').innerHTML='';$('#qcm').innerHTML='';$('#mask-img').style.opacity=0;$('#qc-img').style.opacity=0;$('#out-img').style.opacity=0;$('#mask-n').firstChild.textContent='—';$('#msum').textContent='每个类器官一行；贴边实例汇总时排除。';$('#outsub').textContent='多图按分组/时间点汇总，再生成单文件报告。';[...$('#plan').children].forEach(c=>c.classList.remove('ok'));$('#bubble').textContent='你：';ST.forEach(s=>$('#'+s).classList.remove('on','done'));['st-scale','st-tiles','st-track'].forEach(id=>{const c=cx(id);c.fillStyle='#0d1214';c.fillRect(0,0,140,140);});gaugeReset();unetReset();$('#tok-img').src=P.s1_input.image;}
function go(i){clearAll();reset();for(let k=0;k<i;k++)STEPS[k].end&&STEPS[k].end();cur=i;const s=STEPS[i];Z.forEach(z=>{const e=$('#'+z);e.classList.remove('on');e.classList.toggle('done',Z.indexOf(z)<Z.indexOf(s.z));e.classList.toggle('idle',Z.indexOf(z)>Z.indexOf(s.z));});$('#'+s.z).classList.add('on');$('#'+s.z).classList.remove('idle');
  document.querySelectorAll('.seg').forEach(p=>p.classList.remove('on'));for(let k=0;k<i;k++)if(STEPS[k].arrow)$('#'+STEPS[k].arrow).classList.add('done');if(s.arrow){const p=$('#'+s.arrow);p.classList.remove('done');p.classList.add('on');later(()=>{p.classList.remove('on');p.classList.add('done');},1000);}
  $('#cap').textContent=s.cap;$('#stepno').textContent='第 '+(i+1)+' / '+STEPS.length+' 步';s.run();t0=performance.now();}
function tick(){if(!playing)return;const e=performance.now()-t0,d=STEPS[cur].dur*1000*speed;$('#bar').style.width=Math.min(100,100*e/d)+'%';if(e>=d){if(cur<STEPS.length-1)go(cur+1);else{playing=false;$('#b-play').textContent='播放';return;}}raf=requestAnimationFrame(tick);}
function start(){cancelAnimationFrame(raf);t0=performance.now();raf=requestAnimationFrame(tick);}
$('#b-play').onclick=function(){playing=!playing;this.textContent=playing?'暂停':'播放';if(playing){if(cur<0||cur>=STEPS.length-1)go(0);start();}else cancelAnimationFrame(raf);};
$('#b-prev').onclick=()=>{if(cur>0){go(cur-1);if(playing)start();}};
$('#b-next').onclick=()=>{if(cur<STEPS.length-1){go(cur+1);if(playing)start();}};
$('#b-restart').onclick=()=>{playing=true;$('#b-play').textContent='暂停';go(0);start();};
$('#spd').onchange=e=>{speed=parseFloat(e.target.value);};
let loaded=0;Object.values(IM).forEach(e=>{e.onload=()=>{if(++loaded===Object.keys(IM).length){go(0);if(playing)start();else $('#b-play').textContent='播放';}};});
__DIFFJS__
</script>
"""
# 复用上一版的热扩散 JS
diffjs = base.split("/* ---- 热扩散 ---- */")[1].split("</script>")[0]
rep = {"__CSS__": CSS, "__EXTRA__": EXTRA, "__DATA__": DATA, "__UNET__": UNET, "__GAUGE__": GAUGE, "__WID__": wid, "__DIFFJS__": "/* ---- 热扩散 ---- */" + diffjs,
       "__GT__": str(P["gt_instances"]), "__W__": str(P["shape"][0]), "__H__": str(P["shape"][1]), "__NT__": str(t3["n"]),
       "__DW__": str(df["w"] * 4), "__DH__": str(df["h"] * 4), "__NIT__": str(min(400, 2 * round((df["w"] ** 2 + df["h"] ** 2) ** 0.5))),
       "__DI_S__": di["small"]["image"], "__DI_SN__": str(di["small"]["n"]), "__DI_A__": di["auto"]["image"], "__DI_AD__": f"{di['auto']['diameter']:.1f}", "__DI_AN__": str(di["auto"]["n"]),
       "__DI_L__": di["large"]["image"], "__DI_LN__": str(di["large"]["n"]),
       "__DB_A__": db["auto"]["image"], "__DB_AD__": f"{db['auto']['diameter']:.0f}", "__DB_AN__": str(db["auto"]["n"]), "__DB_D__": db["d404"]["image"], "__DB_DN__": str(db["d404"]["n"]), "__DB_F__": db["finetuned"]["image"], "__DB_FN__": str(db["finetuned"]["n"]),
       "__RS_O__": rs["original"], "__RS_OW__": str(rs["original_size"][0]), "__RS_OH__": str(rs["original_size"][1]), "__RS_S__": rs["scaled"], "__RS_SW__": str(rs["scaled_size"][0]), "__RS_SH__": str(rs["scaled_size"][1]), "__RS_SW3__": str(rs["scaled_size"][0] * 3), "__RS_SH3__": str(rs["scaled_size"][1] * 3)}
html = HTML
for k, v in rep.items(): html = html.replace(k, v)
left = set(re.findall(r"__[A-Z_0-9]+__", html)); assert not left, left
open(f"{S}/orgalyst_scene.html", "w", encoding="utf-8").write(html); print("written", len(html) // 1024, "KB")
