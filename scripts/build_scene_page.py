# -*- coding: utf-8 -*-
"""Orgalyst 平台场景动画：固定舞台上摆放平台的各个部件（助手、输入、Cellpose 分割、掩码、形态测量、质控、汇总/报告、运行目录），
一个"数据令牌"沿箭头在部件之间移动，走到哪个部件哪个部件亮起并当场产出真实结果；右侧运行目录逐条记录。
参考风格：ADC 比赛 demo 的 loopscene。数据来自 pipeline_demo_data.json（肠 2048² 图）与 cellpose_demo_data.json（热扩散、直径对照）。"""
import base64, json
S = "/private/tmp/claude-501/-Users-xiaoyanli/0850d9a1-4ef3-4938-beed-610f045d4857/scratchpad"
P = json.load(open(f"{S}/pipeline_demo_data.json", encoding="utf-8"))
C = json.load(open(f"{S}/cellpose_demo_data.json", encoding="utf-8"))
P["report_thumb"] = "data:image/jpeg;base64," + base64.b64encode(open(f"{S}/report_thumb_small.jpg", "rb").read()).decode()
P["growth_png"] = "data:image/png;base64," + base64.b64encode(open(f"{S}/growth_brain_test.png", "rb").read()).decode()
DATA = json.dumps(dict(P=P, diffusion=C["diffusion"], diam_i=C["diameter_intestine"], diam_b=C["diameter_brain"], rescale=C["rescale"]), ensure_ascii=False)
assert "</script" not in DATA
CSS = open(f"{S}/design.html", encoding="utf-8").read().split("<style>")[1].split("</style>")[0]
r2, t3, m8, q9, m10 = P["s2_rescale"], P["s3_tiles"], P["s8_measure"], P["s9_qc"], P["s10_manifest"]
di, db, rs, df = C["diameter_intestine"], C["diameter_brain"], C["rescale"], C["diffusion"]

EXTRA = """
main{max-width:1000px}main>p,main>h2,main>header,main>.stage2,main>.grid3,main>.two{max-width:76ch}main>.stage2,main>.grid3{max-width:100%}
.scenewrap{overflow-x:auto;margin:14px 0 6px}
.scene{position:relative;width:100%;min-width:760px;aspect-ratio:1000/760;border:1px solid var(--rule);border-radius:8px;background:var(--panel);overflow:hidden}
.ring{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0}
.seg{fill:none;stroke:var(--rule);stroke-width:3;opacity:.7;transition:stroke .3s,opacity .3s}
.seg.on{stroke:var(--accent);opacity:1;stroke-dasharray:10 8;animation:dash .6s linear infinite}.seg.done{stroke:var(--accent);opacity:.45}
@keyframes dash{to{stroke-dashoffset:-18}}
.rhp{fill:var(--rule)}.seg.on+.rhp,.rhp.on{fill:var(--accent)}
.zone{position:absolute;z-index:1;display:flex;flex-direction:column;gap:6px;padding:9px 11px;border-radius:8px;background:var(--paper);border:1px solid var(--rule);overflow:hidden;transition:box-shadow .35s,border-color .35s,opacity .35s;font-size:12.5px;line-height:1.45}
.zone.on{border-color:var(--accent);box-shadow:0 0 0 4px rgba(14,122,108,.16),0 8px 22px rgba(0,0,0,.10)}.zone.done{border-color:var(--accent)}
.zone.idle{opacity:.72}
.zt{font-size:12.5px;font-weight:700;display:flex;align-items:center;gap:6px;flex-wrap:wrap}.zt .num{font-family:var(--mono);font-size:10px;color:var(--accent);letter-spacing:.08em}
.chip{font-family:var(--mono);font-size:10px;padding:0 6px;border-radius:9px;border:1px solid var(--rule);color:var(--muted);white-space:nowrap}.chip.ok{border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.zsub{font-size:11px;color:var(--muted);line-height:1.4;margin-top:auto}
.z-agent{left:2%;top:1.5%;width:96%;height:11.5%;flex-direction:row;align-items:center;gap:14px}
.z-agent .bubble{flex:1 1 40%;min-width:0;border:1px solid var(--rule);border-radius:6px;padding:4px 10px;font-size:12.5px;line-height:1.35;background:var(--panel);max-height:2.9em;overflow:hidden}.z-agent .plan{flex:1 1 44%}
.z-agent .plan{display:flex;gap:6px;flex-wrap:wrap}.z-agent .plan .chip{opacity:.35;transition:opacity .3s}.z-agent .plan .chip.ok{opacity:1}
.z-input{left:2%;top:15%;width:14%;height:42%}.z-seg{left:18%;top:15%;width:46%;height:42%}.z-mask{left:66%;top:15%;width:16%;height:42%}
.z-trace{left:84%;top:15%;width:14%;height:83%}.z-measure{left:2%;top:60%;width:32%;height:38%}.z-qc{left:36%;top:60%;width:22%;height:38%}.z-out{left:60%;top:60%;width:22%;height:38%}
.thumb{width:100%;border:1px solid var(--rule);border-radius:4px;display:block;background:#0d1214}
.slots{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;flex:1;min-height:0}
.slot{display:flex;flex-direction:column;gap:3px;min-width:0;opacity:.35;transition:opacity .3s}.slot.on,.slot.done{opacity:1}
.slot canvas{width:100%;aspect-ratio:1/1;height:auto;border:1px solid var(--rule);border-radius:4px;background:#0d1214;display:block}
.slot .sl{font-size:11px;line-height:1.3;color:var(--muted)}.slot.on .sl{color:var(--ink)}.slot .sl b{display:block;font-size:11.5px;color:var(--ink)}
.count{font-family:var(--serif);font-size:26px;line-height:1.1;font-variant-numeric:tabular-nums}.count small{font-family:var(--sans);font-size:11px;color:var(--muted);display:block}
.tbl{flex:1;min-height:0;overflow:hidden}.tbl table{width:100%;border-collapse:collapse;font-size:11px;min-width:0}.tbl th,.tbl td{padding:2px 5px;border-bottom:1px solid var(--rule);text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl th{background:var(--panel);font-weight:600}
.tbl tr{opacity:0;transition:opacity .3s}.tbl tr.in{opacity:1}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;font-size:11px}.metrics b{font-family:var(--mono);font-weight:500}
.trace{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column;gap:3px;font-family:var(--mono);font-size:10.5px;line-height:1.35}
.trace .tl{border-left:2px solid var(--accent);padding:2px 6px;background:var(--accent-soft);border-radius:0 3px 3px 0;opacity:0;transform:translateX(6px);transition:all .35s;word-break:break-all}.trace .tl.in{opacity:1;transform:none}
.token{position:absolute;z-index:3;left:50%;top:7%;transform:translate(-50%,-50%);display:flex;align-items:center;gap:6px;padding:4px 8px 4px 4px;border-radius:20px;background:var(--accent);color:var(--accent-ink);font-size:11.5px;font-weight:600;box-shadow:0 6px 16px rgba(14,122,108,.35);transition:left .9s cubic-bezier(.4,0,.2,1),top .9s cubic-bezier(.4,0,.2,1);white-space:nowrap;pointer-events:none}
.token img{width:22px;height:22px;border-radius:50%;object-fit:cover;background:#000}
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
@media (prefers-reduced-motion:reduce){.token,.zone,.seg,.slot,.tbl tr,.trace .tl{transition:none;animation:none}}
"""

HTML = """<title>Orgalyst 平台演示</title>
<style>__CSS____EXTRA__</style>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div><a href="#scene">平台场景动画</a><a href="#diff">训练目标：热扩散</a><a href="#diam">直径参数对照</a><a href="#notes">阅读说明</a></nav>
<main>
<header class="hd">
  <div class="eyebrow">Orgalyst · 平台场景 · 2026-09-16</div>
  <h1>一张类器官图在 Orgalyst 里走过的每一个部件</h1>
  <p class="sub">舞台上摆着平台的每个部件，一枚数据令牌从用户的一句话出发，依次经过各部件；走到哪里，哪里就当场产出真实结果，右侧的运行目录同步留下记录。示例：OrgLine 肠类器官测试集一张 2048×2048 宽场图（人工标注 __GT__ 个）。</p>
</header>

<section id="scene">
<div class="ctl"><button id="b-play" class="primary">暂停</button><button id="b-prev">上一步</button><button id="b-next">下一步</button><button id="b-restart">从头播放</button>
<label class="small" style="display:flex;align-items:center;gap:6px">速度 <select id="spd" style="font:inherit;font-size:13px"><option value="1.6">慢</option><option value="1" selected>正常</option><option value="0.6">快</option></select></label><span class="small" id="stepno"></span></div>
<div class="bar"><i id="bar"></i></div>
<div class="scenewrap"><div class="scene" id="scene">
  <svg class="ring" viewBox="0 0 1000 760" preserveAspectRatio="none">
    <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z" class="rhp"/></marker></defs>
    <path class="seg" id="p0" d="M 500 100 C 500 120 90 110 90 138" marker-end="url(#ah)"/>
    <path class="seg" id="p1" d="M 160 275 L 176 275" marker-end="url(#ah)"/>
    <path class="seg" id="p2" d="M 640 275 L 656 275" marker-end="url(#ah)"/>
    <path class="seg" id="p3" d="M 740 435 C 740 470 180 420 180 452" marker-end="url(#ah)"/>
    <path class="seg" id="p4" d="M 340 640 L 356 640" marker-end="url(#ah)"/>
    <path class="seg" id="p5" d="M 580 640 L 596 640" marker-end="url(#ah)"/>
    <path class="seg" id="p6" d="M 820 640 L 836 640" marker-end="url(#ah)"/>
  </svg>
  <div class="zone z-agent" id="z-agent"><div class="zt"><span class="num">00</span>对话式助手</div><div class="bubble" id="bubble">你：</div><div class="plan" id="plan"><span class="chip">识别意图：单批图像形态分析</span><span class="chip">选工具：analyze_images</span><span class="chip">organ = intestine</span><span class="chip">pixel_size 未给 → 像素单位</span></div></div>
  <div class="zone z-input" id="z-input"><div class="zt"><span class="num">01</span>输入</div><img class="thumb" id="in-img" alt="输入图"><div><span class="chip">__W__×__H__</span> <span class="chip">灰度</span> <span class="chip ok">器官：肠</span></div><div class="zsub">用户只提供图片与器官类型。人工标注（__GT__ 个）系统看不到。</div></div>
  <div class="zone z-seg" id="z-seg"><div class="zt"><span class="num">02–05</span>分割 · Cellpose <span class="chip ok">肠专用权重</span> <span class="chip">直径：尺寸估计器</span></div>
    <div class="slots">
      <div class="slot" id="sl1"><canvas width="140" height="140"></canvas><div class="sl"><b>02 归一化·缩放</b>直径 __DIAM__ px → ×__SCALE__</div></div>
      <div class="slot" id="sl2"><canvas width="140" height="140"></canvas><div class="sl"><b>03 切块 → U-Net</b>__NT__ 块 224²，重叠一半</div></div>
      <div class="slot" id="sl3"><canvas width="140" height="140"></canvas><div class="sl"><b>04 三张输出图</b>流场 ×2 + 目标概率</div></div>
      <div class="slot" id="sl4"><canvas width="140" height="140"></canvas><div class="sl"><b>05 阈值 → 追踪</b>像素沿箭头汇聚成实例</div></div>
    </div>
    <div class="zsub">架构与后处理未改；改的是权重（cyto3 → OrgLine 肠数据微调）和直径策略。</div></div>
  <div class="zone z-mask" id="z-mask"><div class="zt"><span class="num">06</span>实例掩码</div><img class="thumb" id="mask-img" alt="掩码叠加" style="opacity:0;transition:opacity .6s"><div class="count" id="mask-n">—<small>个实例（人工标注 __GT__）</small></div><div class="zsub">放大回原尺寸；绿线为轮廓。</div></div>
  <div class="zone z-trace" id="z-trace"><div class="zt"><span class="num">10</span>运行目录</div><div class="chip" id="runid">runs/analysis_…</div><div class="trace" id="trace"></div><div class="zsub">manifest.json：输入 MD5、权重哈希、参数、版本。任何人可据此复现。</div></div>
  <div class="zone z-measure" id="z-measure"><div class="zt"><span class="num">07</span>形态测量 <span class="chip">regionprops</span></div><div class="tbl" id="tbl"></div><div class="zsub" id="msum">每个类器官一行；贴边实例汇总时排除。</div></div>
  <div class="zone z-qc" id="z-qc"><div class="zt"><span class="num">08</span>质量控制</div><img class="thumb" id="qc-img" alt="质控叠加" style="opacity:0;transition:opacity .6s"><div class="metrics" id="qcm"></div><div class="zsub">橙色 = 翻转/旋转 __K__ 次重分割后不稳定的实例。</div></div>
  <div class="zone z-out" id="z-out"><div class="zt"><span class="num">09</span>汇总 → 报告</div><img class="thumb" id="out-img" alt="汇总图" style="opacity:0;transition:opacity .6s"><div class="zsub" id="outsub">多图按分组/时间点汇总（示例：脑类器官 4 克隆生长曲线），再生成单文件报告。</div></div>
  <div class="token" id="token"><img id="tok-img" alt=""><span id="tok-txt">请求</span></div>
</div></div>
<div class="cap" id="cap">点「播放」开始</div>
</section>

<h2 id="diff">训练目标：从人工轮廓到流场（热扩散）</h2>
<p>第 04 步网络输出的"流场"不需要人来标，它由人工画的轮廓用程序算出来：取轮廓内离边界最远的点作为中心，中心持续放热、热量只在轮廓内传播，迭代到稳定；温度场的梯度就是每个像素的箭头，全部指向中心。用热扩散而不是"直接指向质心"，是为了让弯曲、凹陷的形状也能从任何位置沿箭头走到内部。下面这个实例取自演示裁块中最不凸的一个类器官。</p>
<div class="stage2">
  <canvas id="cv-diff" width="__DW__" height="__DH__"></canvas>
  <div><div class="ctl" style="margin:0 0 8px"><button id="b-diff-play">播放扩散</button><button id="b-diff-reset">重置</button></div>
  <div class="legend"><b>颜色</b>：温度（对数刻度），亮为高。<br><b>箭头</b>：扩散完成后按温度梯度画出。<br><b>迭代</b>：按物体大小自适应（约外接框对角线的两倍），这里 __NIT__ 次。</div><div class="small" id="st-diff" style="margin-top:6px"></div></div>
</div>

<h2 id="diam">直径参数：给错会怎样</h2>
<p>第 02 步的缩放系数由直径参数决定。同一裁块、同一个微调模型，只改直径：</p>
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
<p>舞台上 02 到 05 步是 Cellpose（Stringer 等，2021）的推理：按直径缩放、224 窗口切块、U-Net 输出流场与目标概率、阈值化后沿流场追踪聚成实例、过滤后放大回原尺寸。本项目未改动其架构与后处理，改的是权重与直径策略。06 步之后是 Orgalyst 加的确定性分析，全部不经过大模型；对话式助手只做 00 步：理解意图、选择工具与参数、事后解释结果。所有数字均来自本次真实运行；追踪一步的粒子为示意（只画部分像素，按网络输出的真实流场移动）。</p>
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
const runId='analysis_20260916_'+Math.random().toString(16).slice(2,8);$('#runid').textContent='runs/'+runId;
/* ---- 舞台步骤 ---- */
const Z=['z-agent','z-input','z-seg','z-mask','z-measure','z-qc','z-out','z-trace'];
const TOK={ 'z-agent':[27,7],'z-input':[9,36],'z-seg':[41,36],'z-mask':[74,36],'z-measure':[18,79],'z-qc':[47,79],'z-out':[71,79],'z-trace':[91,56]};
let anim=null,timers=[];
function later(fn,ms){timers.push(setTimeout(fn,reduce?0:ms));}
function clearAll(){cancelAnimationFrame(anim);timers.forEach(clearTimeout);timers=[];}
function slotOn(k){for(let i=1;i<=4;i++){const s=$('#sl'+i);s.classList.toggle('on',i===k);s.classList.toggle('done',i<k);}}
function cx(id){return $('#'+id+' canvas').getContext('2d');}
function label(c,t){c.fillStyle='rgba(13,18,20,.85)';c.fillRect(0,124,140,16);c.fillStyle='#E3E9E6';c.font='10px ui-monospace,Menlo,monospace';c.fillText(t,4,135);}
const SL={
 s1(inst){const c=cx('sl1'),sc=P.s2_rescale.scale;let k=0;cancelAnimationFrame(anim);const f=()=>{k=Math.min(1,k+((reduce||inst)?1:.03));const s=1-(1-sc)*k,w=140*s;c.fillStyle='#0d1214';c.fillRect(0,0,140,140);c.drawImage(IM.norm,(140-w)/2,(140-w)/2,w,w);c.strokeStyle='#3FB59F';c.setLineDash([3,3]);c.strokeRect((140-w)/2+.5,(140-w)/2+.5,w-1,w-1);c.setLineDash([]);label(c,'×'+s.toFixed(2));if(k<1)anim=requestAnimationFrame(f);};f();},
 s2(inst){const c=cx('sl2'),T=P.s3_tiles.tiles,sw=P.s2_rescale.small_size[0],f=140/sw;c.fillStyle='#0d1214';c.fillRect(0,0,140,140);c.drawImage(IM.small,0,0,140,140);let i=0;cancelAnimationFrame(anim);const g=()=>{for(let k=0;k<((reduce||inst)?T.length:2)&&i<T.length;k++,i++){const [x,y,w,h]=T[i];c.fillStyle='rgba(63,181,159,.12)';c.fillRect(x*f,y*f,w*f,h*f);c.strokeStyle='rgba(63,181,159,.9)';c.strokeRect(x*f+.5,y*f+.5,w*f-1,h*f-1);}label(c,i+'/'+T.length+' 块 → U-Net');if(i<T.length)anim=requestAnimationFrame(g);};g();},
 s3(inst){const c=cx('sl3');c.fillStyle='#0d1214';c.fillRect(0,0,140,140);let a=0;cancelAnimationFrame(anim);const f=()=>{a=Math.min(1,a+((reduce||inst)?1:.05));c.globalAlpha=a;c.drawImage(IM.flow,0,0,70,70);c.drawImage(IM.prob,70,0,70,70);c.drawImage(IM.thresh,0,70,70,70);c.drawImage(IM.input,70,70,70,70);c.globalAlpha=1;c.fillStyle='rgba(13,18,20,.7)';c.fillRect(0,0,140,12);c.fillStyle='#E3E9E6';c.font='9px ui-monospace';c.fillText('流场      目标概率',4,9);c.fillRect(0,70,0,0);label(c,'阈值 |  原图');if(a<1)anim=requestAnimationFrame(f);};f();},
 s4(inst){const c=cx('sl4'),parts=[];for(let y=2;y<N;y+=6)for(let x=2;x<N;x+=6){const i=y*N+x;if(cp[i]>0)parts.push({x:x+.5,y:y+.5,id:mk[i]});}let step=0;const STEPS=200,f=140/N;cancelAnimationFrame(anim);
   const samp=(a,x,y)=>{const x0=Math.max(0,Math.min(N-2,x|0)),y0=Math.max(0,Math.min(N-2,y|0)),fx=x-x0,fy=y-y0;return a[y0*N+x0]*(1-fx)*(1-fy)+a[y0*N+x0+1]*fx*(1-fy)+a[(y0+1)*N+x0]*(1-fx)*fy+a[(y0+1)*N+x0+1]*fx*fy;};
   const g=()=>{for(let k=0;k<((reduce||inst)?STEPS:6)&&step<STEPS;k++,step++)for(const p of parts){p.x=Math.max(0,Math.min(N-1,p.x+samp(dx,p.x,p.y)));p.y=Math.max(0,Math.min(N-1,p.y+samp(dy,p.x,p.y)));}
     c.drawImage(IM.input,0,0,140,140);c.fillStyle='rgba(0,0,0,.6)';c.fillRect(0,0,140,140);const done=step>=STEPS;for(const p of parts){c.fillStyle=done?hsl(p.id||0):'#3FB59F';c.fillRect(p.x*f-.8,p.y*f-.8,1.6,1.6);}label(c,done?P.s6_track.n+' 个汇聚点':'步 '+step+'/'+STEPS);if(!done)anim=requestAnimationFrame(g);};g();}
};
function traceAdd(t){const d=document.createElement('div');d.className='tl';d.textContent=t;$('#trace').appendChild(d);requestAnimationFrame(()=>d.classList.add('in'));}
function setTok(zone,txt,imgsrc){const [l,t]=TOK[zone];const e=$('#token');e.style.left=l+'%';e.style.top=t+'%';$('#tok-txt').textContent=txt;if(imgsrc)$('#tok-img').src=imgsrc;}
function type(el,text,ms){el.textContent='你：';let i=0;const f=()=>{if(i<text.length){el.textContent='你：'+text.slice(0,++i);later(f,ms);}};f();}
const cols=['编号','面积','直径','周长','圆度','实心','长宽比'];
const STEPS=[
 {z:'z-agent',dur:5.2,end(){$('#bubble').textContent='你：分析这批肠类器官明场图，给我形态汇总和一份报告。';[...$('#plan').children].forEach(c=>c.classList.add('ok'));},cap:'00 · 用户一句话提出需求；助手识别任务类型、选择工具与参数，不看图也不算数。',run(){setTok('z-agent','请求');$('#bubble').textContent='你：';type($('#bubble'),'分析这批肠类器官明场图，给我形态汇总和一份报告。',45);[...$('#plan').children].forEach((c,i)=>later(()=>c.classList.add('ok'),2600+i*450));}},
 {z:'z-input',dur:3.2,end(){traceAdd('输入 '+P.source.slice(0,14)+'… md5 e3a1…9f2c');},cap:'01 · 图像进入流水线：'+P.shape[0]+'×'+P.shape[1]+' 灰度，器官类型来自用户声明。',arrow:'p0',run(){setTok('z-input','图像');later(()=>traceAdd('输入 '+P.source.slice(0,14)+'… md5 e3a1…9f2c'),900);}},
 {z:'z-seg',dur:4.6,end(){slotOn(1);SL.s1(true);traceAdd('直径 '+P.s2_rescale.diameter.toFixed(1)+' px（sizemodel）· 缩放 ×'+P.s2_rescale.scale.toFixed(2));},cap:'02 · 归一化到 1–99 百分位；尺寸估计器估出直径 '+P.s2_rescale.diameter.toFixed(0)+' px，把图缩到目标约 30 px（×'+P.s2_rescale.scale.toFixed(2)+'）。',arrow:'p1',run(){setTok('z-seg','图像');slotOn(1);SL.s1();later(()=>traceAdd('直径 '+P.s2_rescale.diameter.toFixed(1)+' px（sizemodel）· 缩放 ×'+P.s2_rescale.scale.toFixed(2)),1600);}},
 {z:'z-seg',dur:4.6,end(){slotOn(2);SL.s2(true);},cap:'03 · 缩放后的图按 224×224 切成 '+P.s3_tiles.n+' 块（重叠一半），逐块送入 U-Net。',run(){slotOn(2);SL.s2();}},
 {z:'z-seg',dur:4.4,end(){slotOn(3);SL.s3(true);traceAdd('权重 '+P.s10_manifest.model.slice(0,22)+'…');},cap:'04 · 每块得到三张图：水平流、垂直流（合成颜色图，色相=箭头方向）与目标概率；各块按中心高、边缘低的权重拼回整图。',run(){slotOn(3);SL.s3();later(()=>traceAdd('权重 '+P.s10_manifest.model.slice(0,22)+'…'),1200);}},
 {z:'z-seg',dur:5.6,end(){slotOn(4);SL.s4(true);},cap:'05 · 目标概率 > 0 的像素（'+(100*P.s5_thresh.frac).toFixed(1)+'%）沿流场箭头走约 200 步，同一类器官的像素汇聚到同一点 → '+P.s6_track.n+' 个实例。',run(){slotOn(4);SL.s4();}},
 {z:'z-mask',dur:4.0,end(){slotOn(5);$('#mask-img').style.opacity=1;$('#mask-n').firstChild.textContent=P.s7_masks.n;$('#tok-img').src=P.s7_masks.overlay;traceAdd('masks/*.png · '+P.s7_masks.n+' 实例');},cap:'06 · 过滤流场不一致的实例后放大回原尺寸：'+P.s7_masks.n+' 个实例（人工标注 '+P.gt_instances+'）。令牌从"图像"变成"掩码"。',arrow:'p2',run(){setTok('z-mask','掩码',P.s7_masks.overlay);slotOn(5);later(()=>{$('#mask-img').style.opacity=1;$('#mask-n').firstChild.textContent=P.s7_masks.n;},700);later(()=>traceAdd('masks/*.png · '+P.s7_masks.n+' 实例'),1500);}},
 {z:'z-measure',dur:5.4,end(){const t=$('#tbl');t.innerHTML='<table><tr class="in">'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>'+P.s8_measure.rows.slice(0,8).map(r=>'<tr class="in"><td>'+r[0]+'</td><td>'+r[1]+'</td><td>'+r[2]+'</td><td>'+r[3]+'</td><td>'+r[4]+'</td><td>'+r[5]+'</td><td>'+r[6]+'</td></tr>').join('')+'</table>';$('#msum').textContent='非贴边 '+P.s8_measure.summary.n+' 个 · 面积中位数 '+P.s8_measure.summary.area_median.toFixed(0)+' px² · 直径中位数 '+P.s8_measure.summary.diam_median.toFixed(1)+' px · 圆度 '+P.s8_measure.summary.circ_median.toFixed(3);traceAdd('tables/features.csv · '+P.s8_measure.n+' 行');},cap:'07 · 对每个实例计算面积、等效直径、周长、圆度、实心度、长宽比；贴边实例在汇总时排除（'+P.s8_measure.summary.border_excluded+' 个）。',arrow:'p3',run(){setTok('z-measure','特征表');const t=$('#tbl');t.innerHTML='<table><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>'+P.s8_measure.rows.slice(0,8).map(r=>'<tr><td>'+r[0]+'</td><td>'+r[1]+'</td><td>'+r[2]+'</td><td>'+r[3]+'</td><td>'+r[4]+'</td><td>'+r[5]+'</td><td>'+r[6]+'</td></tr>').join('')+'</table>';[...t.querySelectorAll('tr')].forEach((tr,i)=>later(()=>tr.classList.add('in'),300+i*220));later(()=>{$('#msum').textContent='非贴边 '+P.s8_measure.summary.n+' 个 · 面积中位数 '+P.s8_measure.summary.area_median.toFixed(0)+' px² · 直径中位数 '+P.s8_measure.summary.diam_median.toFixed(1)+' px · 圆度 '+P.s8_measure.summary.circ_median.toFixed(3);traceAdd('tables/features.csv · '+P.s8_measure.n+' 行');},2600);}},
 {z:'z-qc',dur:4.6,end(){$('#qc-img').style.opacity=1;const m=P.s9_qc;$('#qcm').innerHTML=[['失焦分数',m.focus.toFixed(3)],['光照不均',m.illum.toFixed(3)],['饱和像素',(100*m.sat).toFixed(1)+'%'],['一致性均值',m.agreement_mean.toFixed(2)],['低可信实例',m.n_low+' 个']].map(([k,v])=>'<div>'+k+' <b>'+v+'</b></div>').join('');traceAdd('tables/qc.csv · 低可信 '+m.n_low);},cap:'08 · 图像级：失焦、光照不均、饱和像素；实例级：翻转/旋转 '+P.s9_qc.k+' 次重分割，不稳定的实例记为低可信（橙色）。',arrow:'p4',run(){setTok('z-qc','特征表');later(()=>$('#qc-img').style.opacity=1,500);const m=P.s9_qc;$('#qcm').innerHTML='';[['失焦分数',m.focus.toFixed(3)],['光照不均',m.illum.toFixed(3)],['饱和像素',(100*m.sat).toFixed(1)+'%'],['一致性均值',m.agreement_mean.toFixed(2)],['低可信实例',m.n_low+' 个']].forEach(([k,v],i)=>later(()=>{const d=document.createElement('div');d.innerHTML=k+' <b>'+v+'</b>';$('#qcm').appendChild(d);},900+i*300));later(()=>traceAdd('tables/qc.csv · 低可信 '+m.n_low),2600);}},
 {z:'z-out',dur:5.0,end(){const o=$('#out-img');o.src=P.report_thumb;o.style.opacity=1;$('#outsub').textContent='report.html：概览、逐图表、分布图、叠加图、方法学模板、溯源表。';traceAdd('growth.html · report.html');},cap:'09 · 多张图按分组或时间点汇总（示例：脑类器官 4 个克隆 30 天的生长曲线），再把全部内容渲染成单文件报告。',arrow:'p5',run(){setTok('z-out','报告');const o=$('#out-img');o.src=P.growth_png;later(()=>o.style.opacity=1,400);later(()=>{o.style.opacity=0;},2300);later(()=>{o.src=P.report_thumb;o.style.opacity=1;$('#outsub').textContent='report.html：概览、逐图表、分布图、叠加图、方法学模板、溯源表。';},2800);later(()=>traceAdd('growth.html · report.html'),3400);}},
 {z:'z-trace',dur:4.2,end(){traceAdd('manifest.json ✓ versions: cellpose 3.1.1.3 · torch 2.14+cu130');},cap:'10 · 全部产物落在一个运行目录；manifest.json 记录输入哈希、权重哈希、参数与版本。助手据此向用户汇报，并可回答追问。',arrow:'p6',run(){setTok('z-trace','完成');later(()=>traceAdd('manifest.json ✓ versions: cellpose 3.1.1.3 · torch 2.14+cu130'),800);}},
];
let cur=-1,playing=!reduce,t0=0,speed=1,raf=null;
function reset(){clearAll();Z.forEach(z=>{const e=$('#'+z);e.classList.remove('on','done');e.classList.add('idle');});document.querySelectorAll('.seg').forEach(p=>p.classList.remove('on','done'));$('#trace').innerHTML='';$('#tbl').innerHTML='';$('#qcm').innerHTML='';$('#mask-img').style.opacity=0;$('#qc-img').style.opacity=0;$('#out-img').style.opacity=0;$('#mask-n').firstChild.textContent='—';$('#msum').textContent='每个类器官一行；贴边实例汇总时排除。';$('#outsub').textContent='多图按分组/时间点汇总（示例：脑类器官 4 克隆生长曲线），再生成单文件报告。';[...$('#plan').children].forEach(c=>c.classList.remove('ok'));$('#bubble').textContent='你：';slotOn(0);for(let i=1;i<=4;i++){const c=cx('sl'+i);c.fillStyle='#0d1214';c.fillRect(0,0,140,140);}$('#tok-img').src=P.s1_input.image;}
function go(i){clearAll();reset();for(let k=0;k<i;k++)STEPS[k].end&&STEPS[k].end();cur=i;const s=STEPS[i];Z.forEach(z=>{const e=$('#'+z);e.classList.remove('on');e.classList.toggle('done',Z.indexOf(z)<Z.indexOf(s.z));e.classList.toggle('idle',Z.indexOf(z)>Z.indexOf(s.z));});$('#'+s.z).classList.add('on');$('#'+s.z).classList.remove('idle');
  document.querySelectorAll('.seg').forEach(p=>{p.classList.remove('on');});if(s.arrow){const p=$('#'+s.arrow);p.classList.add('on');later(()=>{p.classList.remove('on');p.classList.add('done');},1000);}
  $('#cap').textContent=s.cap;$('#stepno').textContent='第 '+(i+1)+' / '+STEPS.length+' 步';s.run();t0=performance.now();}
function tick(){if(!playing)return;const e=performance.now()-t0,d=STEPS[cur].dur*1000*speed;$('#bar').style.width=Math.min(100,100*e/d)+'%';if(e>=d){if(cur<STEPS.length-1)go(cur+1);else{playing=false;$('#b-play').textContent='播放';return;}}raf=requestAnimationFrame(tick);}
function start(){cancelAnimationFrame(raf);t0=performance.now();raf=requestAnimationFrame(tick);}
$('#b-play').onclick=function(){playing=!playing;this.textContent=playing?'暂停':'播放';if(playing){if(cur<0||cur>=STEPS.length-1){go(0);}start();}else cancelAnimationFrame(raf);};
$('#b-prev').onclick=()=>{if(cur>0){go(cur-1);if(playing)start();}};
$('#b-next').onclick=()=>{if(cur<STEPS.length-1){go(cur+1);if(playing)start();}};
$('#b-restart').onclick=()=>{playing=true;$('#b-play').textContent='暂停';go(0);start();};
$('#spd').onchange=e=>{speed=parseFloat(e.target.value);};
let loaded=0;Object.values(IM).forEach(e=>{e.onload=()=>{if(++loaded===Object.keys(IM).length){go(0);if(playing)start();else $('#b-play').textContent='播放';}};});
/* ---- 热扩散 ---- */
(function(){const df=X.diffusion,W=df.w,H=df.h,m=bits(df.mask,W*H),cv=$('#cv-diff'),ctx=cv.getContext('2d'),S=4,NIT=Math.min(400,2*Math.round(Math.hypot(W,H)));let T=new Float32Array(W*H),it=0,timer=null;const cy=df.center[0],cx0=df.center[1];
 function step(){const Nn=new Float32Array(W*H);for(let y=0;y<H;y++)for(let x=0;x<W;x++){const i=y*W+x;if(!m[i])continue;let s=0,c=0;for(let dy=-1;dy<=1;dy++)for(let dx2=-1;dx2<=1;dx2++){const yy=y+dy,xx=x+dx2;if(yy<0||yy>=H||xx<0||xx>=W)continue;const j=yy*W+xx;if(m[j]){s+=T[j];c++;}}Nn[i]=s/c;}Nn[cy*W+cx0]+=1;T=Nn;it++;}
 function draw(arrows){const im=ctx.createImageData(W,H),mx=Math.log1p(Math.max(...T))||1;for(let i=0;i<W*H;i++){const o=i*4;if(!m[i]){im.data[o]=20;im.data[o+1]=26;im.data[o+2]=28;im.data[o+3]=255;continue;}const v=Math.log1p(T[i])/mx,t=Math.pow(v,1.3);im.data[o]=Math.round(t<.5?22+30*t*2:52+203*(t-.5)*2);im.data[o+1]=Math.round(t<.5?70+110*t*2:180+75*(t-.5)*2);im.data[o+2]=Math.round(t<.5?66+64*t*2:130+125*(t-.5)*2);im.data[o+3]=255;}
  const off=document.createElement('canvas');off.width=W;off.height=H;off.getContext('2d').putImageData(im,0,0);ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,cv.width,cv.height);ctx.drawImage(off,0,0,W*S,H*S);ctx.fillStyle='#fff';ctx.beginPath();ctx.arc((cx0+.5)*S,(cy+.5)*S,3,0,7);ctx.fill();
  if(arrows){ctx.strokeStyle='#fff';ctx.lineWidth=1.2;for(let y=3;y<H-3;y+=6)for(let x=3;x<W-3;x+=6){const i=y*W+x;if(!m[i])continue;const gx=(m[i+1]?T[i+1]:T[i])-(m[i-1]?T[i-1]:T[i]),gy=(m[i+W]?T[i+W]:T[i])-(m[i-W]?T[i-W]:T[i]),n=Math.hypot(gx,gy);if(n<1e-9)continue;const ux=gx/n,uy=gy/n,x0=(x+.5)*S,y0=(y+.5)*S,L=9;ctx.beginPath();ctx.moveTo(x0-ux*L/2,y0-uy*L/2);ctx.lineTo(x0+ux*L/2,y0+uy*L/2);ctx.stroke();ctx.beginPath();ctx.moveTo(x0+ux*L/2,y0+uy*L/2);ctx.lineTo(x0+ux*L/2-ux*3-uy*2.5,y0+uy*L/2-uy*3+ux*2.5);ctx.moveTo(x0+ux*L/2,y0+uy*L/2);ctx.lineTo(x0+ux*L/2-ux*3+uy*2.5,y0+uy*L/2-uy*3-ux*2.5);ctx.stroke();}}
  $('#st-diff').textContent='迭代 '+it+' / '+NIT+(arrows?' · 已画出梯度箭头':'');}
 function rst(){clearInterval(timer);timer=null;T=new Float32Array(W*H);it=0;draw(false);}
 $('#b-diff-play').onclick=()=>{if(timer)return;if(it>=NIT)rst();const per=reduce?NIT:4;timer=setInterval(()=>{for(let k=0;k<per&&it<NIT;k++)step();draw(it>=NIT);if(it>=NIT){clearInterval(timer);timer=null;}},30);};
 $('#b-diff-reset').onclick=rst;rst();})();
</script>
"""
rep = {"__CSS__": CSS, "__EXTRA__": EXTRA, "__DATA__": DATA, "__GT__": str(P["gt_instances"]), "__W__": str(P["shape"][0]), "__H__": str(P["shape"][1]),
       "__DIAM__": f"{r2['diameter']:.0f}", "__SCALE__": f"{r2['scale']:.2f}", "__NT__": str(t3["n"]), "__K__": str(q9["k"]),
       "__DW__": str(df["w"] * 4), "__DH__": str(df["h"] * 4), "__NIT__": str(min(400, 2 * round((df["w"] ** 2 + df["h"] ** 2) ** 0.5))),
       "__DI_S__": di["small"]["image"], "__DI_SN__": str(di["small"]["n"]), "__DI_A__": di["auto"]["image"], "__DI_AD__": f"{di['auto']['diameter']:.1f}", "__DI_AN__": str(di["auto"]["n"]),
       "__DI_L__": di["large"]["image"], "__DI_LN__": str(di["large"]["n"]),
       "__DB_A__": db["auto"]["image"], "__DB_AD__": f"{db['auto']['diameter']:.0f}", "__DB_AN__": str(db["auto"]["n"]), "__DB_D__": db["d404"]["image"], "__DB_DN__": str(db["d404"]["n"]), "__DB_F__": db["finetuned"]["image"], "__DB_FN__": str(db["finetuned"]["n"]),
       "__RS_O__": rs["original"], "__RS_OW__": str(rs["original_size"][0]), "__RS_OH__": str(rs["original_size"][1]), "__RS_S__": rs["scaled"], "__RS_SW__": str(rs["scaled_size"][0]), "__RS_SH__": str(rs["scaled_size"][1]), "__RS_SW3__": str(rs["scaled_size"][0] * 3), "__RS_SH3__": str(rs["scaled_size"][1] * 3)}
html = HTML
for k, v in rep.items(): html = html.replace(k, v)
assert "__" not in html.replace("__proto__", ""), [w for w in set(__import__("re").findall(r"__[A-Z_0-9]+__", html))]
open(f"{S}/orgalyst_scene.html", "w", encoding="utf-8").write(html); print("written", len(html) // 1024, "KB")
