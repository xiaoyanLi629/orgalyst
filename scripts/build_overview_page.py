# -*- coding: utf-8 -*-
"""Orgalyst 全景流程图：整条链路一次性摊开（三行，从左到右、行尾折到下一行），数据卡片与机器盒子交替，全部同时可见；
动画是一个高亮沿链路移动，走到机器时机器内部播放小动画，走到卡片时卡片弹一下；下方字幕解释当前节点。"""
import base64, json, re
S = "/private/tmp/claude-501/-Users-xiaoyanli/0850d9a1-4ef3-4938-beed-610f045d4857/scratchpad"
P = json.load(open(f"{S}/pipeline_demo_data.json", encoding="utf-8"))
C = json.load(open(f"{S}/cellpose_demo_data.json", encoding="utf-8"))
P["report_thumb"] = "data:image/jpeg;base64," + base64.b64encode(open(f"{S}/report_thumb_small.jpg", "rb").read()).decode()
P["growth_png"] = "data:image/png;base64," + base64.b64encode(open(f"{S}/growth_brain_test.png", "rb").read()).decode()
DATA = json.dumps(dict(P=P, diffusion=C["diffusion"], diam_i=C["diameter_intestine"], diam_b=C["diameter_brain"], rescale=C["rescale"]), ensure_ascii=False)
assert "</script" not in DATA
prev = open(f"{S}/build_scene_page2.py", encoding="utf-8").read()
story = open(f"{S}/build_story_page.py", encoding="utf-8").read()
CSS = open(f"{S}/design.html", encoding="utf-8").read().split("<style>")[1].split("</style>")[0]
r2, t3, m8, q9, m10 = P["s2_rescale"], P["s3_tiles"], P["s8_measure"], P["s9_qc"], P["s10_manifest"]
di, db, rs, df = C["diameter_intestine"], C["diameter_brain"], C["rescale"], C["diffusion"]
wid = m10["model"].split(":")[-1][:8]
UNET = prev.split('UNET = """')[1].split('"""')[0]
GAUGE = prev.split('GAUGE = """')[1].split('"""')[0]
GAUGE2 = GAUGE.replace('class="gv" id="gv"', 'style="position:absolute;left:0;right:0;bottom:4px;text-align:center;font-family:ui-monospace;font-size:9px;color:#E3E9E6" id="gv"')
TAIL = story.split('<h2 id="diff">')[1].split('<script id="data"')[0]   # 补充两节 + 阅读说明（沿用故事板版）

EXTRA = """
main{max-width:1060px}main>p,main>h2,main>header,main>.two{max-width:76ch}
.legend2{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);margin:8px 0 6px}.legend2 i{display:inline-block;width:14px;height:10px;border-radius:3px;vertical-align:-1px;margin-right:5px}
.boardwrap{overflow-x:auto}
.board{position:relative;min-width:900px;border:1px solid var(--rule);border-radius:10px;background:var(--panel);padding:14px 14px 10px}
.rows{display:flex;flex-direction:column;gap:22px}
.rowl{display:flex;align-items:stretch;gap:0}
.node{position:relative;flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:4px;border-radius:8px;padding:7px 8px 6px;transition:box-shadow .35s,transform .35s;z-index:1}
.node.data{border:1.5px solid var(--rule);background:var(--paper)}
.node.mach{border:2px solid var(--accent);background:var(--accent-soft)}
.node.on{box-shadow:0 0 0 4px rgba(14,122,108,.22),0 10px 24px rgba(14,122,108,.22);transform:translateY(-3px)}
.node.on.mach{animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{50%{box-shadow:0 0 0 8px rgba(14,122,108,.12),0 10px 24px rgba(14,122,108,.22)}}
.node .k{font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}.node.mach .k{color:var(--accent)}
.node h5{margin:0;font-size:12.5px;line-height:1.25}
.node .vis{width:100%;aspect-ratio:1/1;border-radius:5px;background:#0d1214;border:1px solid var(--rule);position:relative;overflow:hidden}
.node.mach .vis{aspect-ratio:4/3}
.node .vis canvas,.node .vis svg,.node .vis img{position:absolute;inset:0;width:100%;height:100%}.node .vis img{object-fit:cover}.node .vis img.fit{object-fit:contain;background:#fff}
.node .d{font-size:10.5px;line-height:1.3;color:var(--muted)}.node .d b{color:var(--ink)}
.ar{flex:0 0 26px;display:flex;align-items:center;justify-content:center;color:var(--muted);transition:color .3s;z-index:0}.ar svg{width:22px;height:18px}.ar.on{color:var(--accent)}.ar.on svg path{stroke-dasharray:6 4;animation:dash .5s linear infinite}
@keyframes dash{to{stroke-dashoffset:-10}}
.wrapar{position:absolute;right:16px;height:26px;width:60%;pointer-events:none;color:var(--muted)}.wrapar svg{width:100%;height:100%}.wrapar.on{color:var(--accent)}
.gauge .needle{transform-origin:50px 60px;transform:rotate(-90deg);transition:transform 1.2s cubic-bezier(.3,.8,.3,1)}
.unet .blk{fill:#1B2529;stroke:#5A6A70;stroke-width:1;transition:fill .25s,stroke .25s}.unet .blk.lit{fill:#3FB59F;stroke:#E3E9E6}
.unet .skip{stroke:#5A6A70;stroke-width:1;stroke-dasharray:3 2;fill:none}.unet .skip.lit{stroke:#3FB59F}
.unet .plug{fill:#9A6A12;stroke:#F5E9CF;stroke-width:1}.unet .plug.ft{fill:#0E7A6C;stroke:#D9EEE9}
.unet text{font-family:ui-monospace,Menlo,monospace;font-size:7px;fill:#E3E9E6}
.three{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:2px;padding:2px;box-sizing:border-box;position:absolute;inset:0}.three img{position:static!important;width:100%;height:100%;object-fit:cover}
.tbl{width:100%;font-size:8.5px;border-collapse:collapse;position:absolute;inset:0;background:var(--paper)}.tbl th,.tbl td{padding:1px 3px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl th{background:var(--panel)}
.token{position:absolute;z-index:5;width:18px;height:18px;border-radius:50%;background:var(--accent);border:3px solid #fff;box-shadow:0 4px 12px rgba(14,122,108,.5);transform:translate(-50%,-50%);transition:left .8s cubic-bezier(.4,0,.2,1),top .8s cubic-bezier(.4,0,.2,1);pointer-events:none}
.cap{margin:10px 0 0;padding:10px 16px;border-radius:6px;background:var(--ink);color:var(--paper);font-size:14px;line-height:1.55;min-height:3em}
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
@media (prefers-reduced-motion:reduce){.node,.ar svg path,.token,.gauge .needle{transition:none;animation:none}}
"""
AR = '<svg viewBox="0 0 22 18" aria-hidden="true"><path d="M2 9 H14" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><path d="M11 3 L18 9 L11 15" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'
WRAP = '<svg viewBox="0 0 400 26" preserveAspectRatio="none" aria-hidden="true"><path d="M395 0 C395 18 380 18 360 18 L20 18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/><path d="M28 12 L18 18 L28 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>'

def data(id, k, title, vis, d): return f'<div class="node data" id="{id}"><div class="k">{k}</div><h5>{title}</h5><div class="vis">{vis}</div><div class="d">{d}</div></div>'
def mach(id, k, title, vis, d): return f'<div class="node mach" id="{id}"><div class="k">{k}</div><h5>{title}</h5><div class="vis">{vis}</div><div class="d">{d}</div></div>'
ar = lambda i: f'<div class="ar" id="a{i}">{AR}</div>'
sw = r2["small_size"][0]
three = f'<div class="three"><img src="{P["s4_net"]["flow"]}"><img src="{P["s4_net"]["prob"]}"><img src="{P["s5_thresh"]["image"]}"><img src="{P["s1_input"]["image"]}" style="opacity:.35"></div>'
cols = ["编号", "面积", "直径", "圆度"]
tbl = '<table class="tbl"><tr>' + "".join(f"<th>{c}</th>" for c in cols) + "</tr>" + "".join(f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[4]}</td></tr>" for r in m8["rows"][:6]) + "</table>"
ROW1 = (data("n0", "输入", "你的一句话", '<div style="position:absolute;inset:6px;color:#E3E9E6;font-size:10px;line-height:1.4">"分析这批肠类器官照片，告诉我大小和形状，给我一份报告。"</div>', "不需要懂参数") + ar(0) +
        mach("n1", "大模型", "助手", '<div style="position:absolute;inset:4px;display:flex;flex-direction:column;gap:2px;justify-content:center" id="planchips"><span style="font-size:8.5px;line-height:1.25;color:#E3E9E6;border:1px solid #3FB59F;border-radius:5px;padding:1px 4px;opacity:.35">任务：形态分析</span><span style="font-size:8.5px;line-height:1.25;color:#E3E9E6;border:1px solid #3FB59F;border-radius:5px;padding:1px 4px;opacity:.35">工具：分析图像</span><span style="font-size:8.5px;line-height:1.25;color:#E3E9E6;border:1px solid #3FB59F;border-radius:5px;padding:1px 4px;opacity:.35">肠 → 肠专用权重</span></div>', "不看图不算数，只选工具和参数") + ar(1) +
        data("n2", "输入", "显微照片", f'<img src="{P["s1_input"]["image"]}">', f"<b>{P['shape'][0]}×{P['shape'][1]}</b> 像素，灰度") + ar(2) +
        mach("n3", "小模型 + 缩放", "量大小 · 缩到合适尺寸", '<div class="gauge" style="position:absolute;inset:0">' + GAUGE2 + '</div>', f"估出约 <b>{r2['diameter']:.0f} px</b> 宽 → 缩到 <b>{r2['scale']:.2f}</b> 倍") + ar(3) +
        data("n4", "中间结果", "缩小后的照片", f'<img src="{P["s2_rescale"]["small"]}">', f"<b>{sw}×{sw}</b> 像素，类器官约 30 px") + ar(4) +
        mach("n5", "工具", "切块机", '<canvas id="tc" width="120" height="90"></canvas>', f"224×224 一块，重叠一半") + ar(5) +
        data("n6", "中间结果", f"{t3['n']} 张小图块", '<canvas id="oc" width="120" height="120"></canvas>', "逐块送进网络"))
ROW2 = (mach("n7", "神经网络", "U-Net（装着肠专用权重）", f'<div class="unet" style="position:absolute;inset:3px">{UNET}</div>', "先压缩再还原；权重 cyto3 → 肠微调") + ar(6) +
        data("n8", "中间结果", "三张图", three, "方向图 ×2 + 哪里像类器官") + ar(7) +
        mach("n9", "后处理", "聚成轮廓", '<canvas id="kc" width="120" height="90"></canvas>', "像素沿箭头走 200 步，汇到同一点的归为一个") + ar(8) +
        data("n10", "结果", f"{P['s7_masks']['n']} 个类器官轮廓", f'<img src="{P["s7_masks"]["overlay"]}">', f"人工数过 <b>{P['gt_instances']}</b> 个") + ar(9) +
        mach("n11", "工具", "测量尺", '<div style="position:absolute;inset:4px;display:flex;flex-direction:column;gap:2px;justify-content:center" id="mchips"><span class="d" style="color:#E3E9E6;opacity:.35">面积 · 直径 · 周长</span><span class="d" style="color:#E3E9E6;opacity:.35">圆度 · 实心度</span><span class="d" style="color:#E3E9E6;opacity:.35">长宽比 · 贴边</span></div>', "纯几何计算，不猜") + ar(10) +
        data("n12", "结果", "一张表，每个类器官一行", tbl, f"共 {m8['n']} 行；面积中位数 <b>{m8['summary']['area_median']:.0f} px²</b>"))
ROW3 = (mach("n13", "检查", "质检员", f'<img id="qi" src="{P["s1_input"]["image"]}" style="transition:transform .5s">', f"翻转旋转 {q9['k']} 次再找一遍") + ar(11) +
        data("n14", "结果", "标出不可靠的", f'<img src="{P["s9_qc"]["overlay"]}">', f"橙色 <b>{q9['n_low']}</b> 个不可靠；一致性 {q9['agreement_mean']:.2f}") + ar(12) +
        mach("n15", "统计", "多张照片放一起比", '<div style="position:absolute;inset:4px;display:flex;flex-direction:column;gap:2px;justify-content:center" id="schips"><span class="d" style="color:#E3E9E6;opacity:.35">按组比较（检验 + 效应量）</span><span class="d" style="color:#E3E9E6;opacity:.35">按时间连成生长曲线</span></div>', "示例：脑类器官 30 天") + ar(13) +
        data("n16", "结果", "曲线与比较", f'<img class="fit" src="{P["growth_png"]}">', "4 个克隆的面积变化") + ar(14) +
        mach("n17", "输出", "报告生成器", '<div style="position:absolute;inset:6px 14%;background:#F6F8F7;border-radius:3px;padding:5px;display:flex;flex-direction:column;gap:3px" id="doc"></div>', "写报告 + 记录权重/参数/版本") + ar(15) +
        data("n18", "最终结果", "报告 + 运行记录", f'<img src="{P["report_thumb"]}" style="object-fit:cover;object-position:top">', "report.html + manifest.json"))

HTML = """<title>Orgalyst 平台演示</title>
<style>__CSS____EXTRA__</style>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div><a href="#flow">全景流程</a><a href="#diff">补充：方向图是怎么来的</a><a href="#diam">补充：量错大小会怎样</a><a href="#notes">阅读说明</a></nav>
<main>
<header class="hd">
  <div class="eyebrow">Orgalyst · 一张照片的完整旅程 · 2026-09-16</div>
  <h1>从一句话到一份报告：整条链路一次看全</h1>
  <p class="sub">白色卡片是<b>东西</b>（照片、图块、轮廓、表、报告），绿色盒子是<b>处理它的模型或工具</b>。从左上读到右下，每个盒子左边是进去的、右边是出来的。播放时一个亮点沿链路走，走到哪里哪里动起来。示例是一张真实的肠类器官显微照片（人工数过 __GT__ 个），所有结果都来自这次真实运行。</p>
</header>
<section id="flow">
<div class="ctl"><button id="b-play" class="primary">暂停</button><button id="b-prev">上一步</button><button id="b-next">下一步</button><button id="b-restart">从头播放</button>
<label class="small" style="display:flex;align-items:center;gap:6px">速度 <select id="spd" style="font:inherit;font-size:13px"><option value="1.6">慢</option><option value="1" selected>正常</option><option value="0.6">快</option></select></label><span class="small" id="stepno"></span></div>
<div class="legend2"><span><i style="background:var(--paper);border:1.5px solid var(--rule)"></i>东西（数据）</span><span><i style="background:var(--accent-soft);border:2px solid var(--accent)"></i>模型 / 工具</span><span>箭头：左边的东西送进盒子，盒子右边是得到的东西</span></div>
<div class="bar"><i id="bar"></i></div>
<div class="boardwrap"><div class="board" id="board">
  <div class="rows">
    <div class="rowl">__ROW1__</div>
    <div class="rowl">__ROW2__</div>
    <div class="rowl">__ROW3__</div>
  </div>
  <div class="wrapar" id="w1" style="top:calc(33.3% - 24px)">__WRAP__</div>
  <div class="wrapar" id="w2" style="top:calc(66.6% - 20px)">__WRAP__</div>
  <div class="token" id="token"></div>
</div></div>
<div class="cap" id="cap">点「播放」开始；也可以直接看图：每个绿盒子左边是进去的，右边是出来的。</div>
</section>
<h2 id="diff">__TAIL__
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
const IM={input:img(P.s1_input.image),small:img(P.s2_rescale.small)};
const N=512,dx=i8(P.s4_net.dx),dy=i8(P.s4_net.dy),cp=i8(P.s4_net.cellprob),mk=u16(P.s6_track.masks);
const sw=P.s2_rescale.small_size[0],d1=P.s2_rescale.diameter;
let anim=null,timers=[];function later(fn,ms){timers.push(setTimeout(fn,reduce?0:ms));}function clearAll(){cancelAnimationFrame(anim);timers.forEach(clearTimeout);timers=[];}
function drawTilesStatic(){const c=$('#oc').getContext('2d'),T=P.s3_tiles.tiles,f=120/sw;c.drawImage(IM.small,0,0,120,120);T.forEach(([x,y,w,h])=>{c.strokeStyle='rgba(63,181,159,.9)';c.strokeRect(x*f+.5,y*f+.5,w*f-1,h*f-1);});}
function tilesAnim(inst){const c=$('#tc').getContext('2d'),T=P.s3_tiles.tiles,f=86/sw,ox=(120-86)/2;c.fillStyle='#0d1214';c.fillRect(0,0,120,90);c.drawImage(IM.small,ox,2,86,86);let i=0;cancelAnimationFrame(anim);const g=()=>{for(let k=0;k<((reduce||inst)?T.length:3)&&i<T.length;k++,i++){const [x,y,w,h]=T[i];c.fillStyle='rgba(63,181,159,.12)';c.fillRect(ox+x*f,2+y*f,w*f,h*f);c.strokeStyle='rgba(63,181,159,.95)';c.strokeRect(ox+x*f+.5,2+y*f+.5,w*f-1,h*f-1);}if(i<T.length)anim=requestAnimationFrame(g);};g();}
function trackAnim(inst){const c=$('#kc').getContext('2d'),parts=[];for(let y=2;y<N;y+=7)for(let x=2;x<N;x+=7){const i=y*N+x;if(cp[i]>0)parts.push({x:x+.5,y:y+.5,id:mk[i]});}let step=0;const STEPS=200,f=86/N,ox=(120-86)/2;cancelAnimationFrame(anim);
  const samp=(a,x,y)=>{const x0=Math.max(0,Math.min(N-2,x|0)),y0=Math.max(0,Math.min(N-2,y|0)),fx=x-x0,fy=y-y0;return a[y0*N+x0]*(1-fx)*(1-fy)+a[y0*N+x0+1]*fx*(1-fy)+a[(y0+1)*N+x0]*(1-fx)*fy+a[(y0+1)*N+x0+1]*fx*fy;};
  const g=()=>{for(let k=0;k<((reduce||inst)?STEPS:6)&&step<STEPS;k++,step++)for(const p of parts){p.x=Math.max(0,Math.min(N-1,p.x+samp(dx,p.x,p.y)));p.y=Math.max(0,Math.min(N-1,p.y+samp(dy,p.x,p.y)));}c.fillStyle='#0d1214';c.fillRect(0,0,120,90);c.drawImage(IM.input,ox,2,86,86);c.fillStyle='rgba(0,0,0,.6)';c.fillRect(ox,2,86,86);const done=step>=STEPS;for(const p of parts){c.fillStyle=done?hsl(p.id||0):'#3FB59F';c.fillRect(ox+p.x*f-.8,2+p.y*f-.8,1.6,1.6);}if(!done)anim=requestAnimationFrame(g);};g();}
function trackStatic(){const c=$('#kc').getContext('2d'),ox=(120-86)/2;c.fillStyle='#0d1214';c.fillRect(0,0,120,90);c.drawImage(IM.input,ox,2,86,86);c.fillStyle='rgba(0,0,0,.55)';c.fillRect(ox,2,86,86);const f=86/N;for(let y=2;y<N;y+=7)for(let x=2;x<N;x+=7){const i=y*N+x;if(cp[i]>0){c.fillStyle='#3FB59F';c.fillRect(ox+x*f,2+y*f,1.4,1.4);}}}
const UB=['e1','e2','e3','e4','bt','d4','d3','d2','d1'];
function unetReset(){UB.forEach(b=>$('#'+b).classList.remove('lit'));['k1','k2','k3','k4'].forEach(k=>$('#'+k).classList.remove('lit'));$('#plug').classList.remove('ft');$('#plugt').textContent='权重: cyto3 (通用)';}
function unetAnim(inst){later(()=>{$('#plug').classList.add('ft');$('#plugt').textContent='权重: 肠微调 __WID__';},inst?0:200);UB.forEach((b,i)=>later(()=>{$('#'+b).classList.add('lit');if(i>=5)$('#k'+(9-i)).classList.add('lit');},inst?0:500+i*260));}
function chips(sel,inst){[...$(sel).children].forEach((c,i)=>later(()=>c.style.opacity=1,inst?0:300+i*450));}
function chipsReset(sel){[...$(sel).children].forEach(c=>c.style.opacity=.35);}
function qcAnim(inst){const e=$('#qi');const tf=['scaleX(-1)','scaleY(-1)','rotate(90deg)','rotate(180deg)','none'];tf.forEach((t,i)=>later(()=>{e.style.transform=t;},inst?0:200+i*550));later(()=>{e.src=P.s9_qc.overlay;},inst?0:3100);}
function qcReset(){const e=$('#qi');e.style.transform='none';e.src=P.s1_input.image;}
function docAnim(inst){const d=$('#doc');d.innerHTML='';['概览','逐图结果','分布图','质控','方法','溯源'].forEach((t,i)=>later(()=>{const l=document.createElement('div');l.style.cssText='font-size:7px;color:#1B262C;border-left:2px solid #0E7A6C;padding-left:3px;width:'+(55+i*7)+'%';l.textContent=t;d.appendChild(l);},inst?0:200+i*380));}
function gaugeAnim(inst){const ang=-90+180*Math.min(1,d1/150);later(()=>{$('#n3 .needle').style.transform='rotate('+ang+'deg)';},inst?0:150);later(()=>{$('#gv').textContent=d1.toFixed(0)+' px';},inst?0:1200);}
function gaugeReset(){$('#n3 .needle').style.transform='rotate(-90deg)';$('#gv').textContent='直径 —';}
const NODES=[
 {id:'n0',cap:'0 · 你只需要说一句话。不需要知道任何参数。'},
 {id:'n1',cap:'1 · 助手（大模型）听懂任务、选择「分析图像」工具、填参数：器官是肠，所以后面的网络会装上肠专用权重。它不看照片、不算数。',run(i){chips('#planchips',i);}},
 {id:'n2',cap:'2 · 照片进入流水线：2048×2048 像素的灰度显微照片。'},
 {id:'n3',cap:'3 · 神经网络只认识大约 30 像素宽的东西，所以先用一个小模型估计类器官多大（约 '+d1.toFixed(0)+' 像素），再把照片缩小到 '+P.s2_rescale.scale.toFixed(2)+' 倍。',run(i){gaugeAnim(i);}},
 {id:'n4',cap:'4 · 得到缩小后的照片，'+sw+'×'+sw+' 像素，类器官现在约 30 像素宽。'},
 {id:'n5',cap:'5 · 切块机把照片切成 224×224 的小块，相邻块重叠一半，免得类器官正好卡在边上。',run(i){tilesAnim(i);}},
 {id:'n6',cap:'6 · 得到 '+P.s3_tiles.n+' 张小图块，逐块送进网络。'},
 {id:'n7',cap:'7 · U-Net：先压缩提取特征，再还原到每个像素。装在它上面的权重决定它认识什么——通用的 cyto3 权重认识细胞，我们在公开的肠类器官数据上继续训练成肠专用权重。结构不变，换的是权重。',run(i){unetAnim(i);}},
 {id:'n8',cap:'8 · 每块图得到三张图，拼回整图：两张方向图（每个像素朝它所属类器官中心的方向）和一张「哪里像类器官」。'},
 {id:'n9',cap:'9 · 每个「像类器官」的像素按自己的箭头走 200 步，同一个类器官里的像素走到同一个点；走到同一点的归为一个。相邻的两个各有各的中心，所以能分开。',run(i){trackAnim(i);}},
 {id:'n10',cap:'10 · 得到 '+P.s7_masks.n+' 个类器官的轮廓（人工数过 '+P.gt_instances+' 个）。到这里分割结束，后面是 Orgalyst 的分析。'},
 {id:'n11',cap:'11 · 测量尺对每个轮廓算面积、直径、周长、圆度、实心度、长宽比。纯几何计算，没有任何猜测；知道像素大小时换算成微米。',run(i){chips('#mchips',i);}},
 {id:'n12',cap:'12 · 得到一张表，每个类器官一行，共 '+P.s8_measure.n+' 行；贴着照片边缘的 '+P.s8_measure.summary.border_excluded+' 个不完整，汇总时排除。'},
 {id:'n13',cap:'13 · 质检员把照片翻转、旋转后再让网络找一遍：真正的类器官怎么转都能找到，翻一下就消失的说明网络没把握。另外检查失焦、光照不均。',run(i){qcAnim(i);}},
 {id:'n14',cap:'14 · 得到标记：'+P.s9_qc.n_low+' 个不可靠（橙色），整体一致性 '+P.s9_qc.agreement_mean.toFixed(2)+'。'},
 {id:'n15',cap:'15 · 很多张照片的表放在一起：按分组做统计检验和效应量，按时间点连成生长曲线。示例是另一批脑类器官 30 天的数据。',run(i){chips('#schips',i);}},
 {id:'n16',cap:'16 · 得到曲线与比较结果：4 个克隆 30 天的面积变化，细线是个体，粗线是平均。'},
 {id:'n17',cap:'17 · 报告生成器把所有内容排成一份单文件网页，并记下这次用的照片校验码、权重、参数、版本，任何人可以照着复现。',run(i){docAnim(i);}},
 {id:'n18',cap:'18 · 最终得到报告和运行记录。助手据此向你汇报，并能回答追问。'},
];
const board=$('#board');
function center(id){const b=board.getBoundingClientRect(),r=$('#'+id).getBoundingClientRect();return [r.left-b.left+r.width/2,r.top-b.top+10];}
let cur=-1,playing=!reduce,t0=0,speed=1,raf=null;const DUR=4200;
function resetAll(){clearAll();chipsReset('#planchips');chipsReset('#mchips');chipsReset('#schips');gaugeReset();unetReset();qcReset();$('#doc').innerHTML='';trackStatic();const c=$('#tc').getContext('2d');c.fillStyle='#0d1214';c.fillRect(0,0,120,90);c.drawImage(IM.small,17,2,86,86);}
function go(i){clearAll();resetAll();for(let k=0;k<i;k++){const n=NODES[k];n.run&&n.run(true);}cur=i;
  NODES.forEach((n,k)=>$('#'+n.id).classList.toggle('on',k===i));document.querySelectorAll('.ar').forEach((a,k)=>a.classList.toggle('on',k===i-1));$('#w1').classList.toggle('on',i===7);$('#w2').classList.toggle('on',i===13);
  const [x,y]=center(NODES[i].id);const t=$('#token');t.style.left=x+'px';t.style.top=y+'px';
  $('#cap').textContent=NODES[i].cap;$('#stepno').textContent='第 '+(i+1)+' / '+NODES.length+' 站';NODES[i].run&&later(()=>NODES[i].run(false),600);t0=performance.now();}
function tick(){if(!playing)return;const e=performance.now()-t0,d=DUR*speed*(NODES[cur].run?1.25:0.7);$('#bar').style.width=Math.min(100,100*e/d)+'%';if(e>=d){if(cur<NODES.length-1)go(cur+1);else{playing=false;$('#b-play').textContent='播放';return;}}raf=requestAnimationFrame(tick);}
function start(){cancelAnimationFrame(raf);t0=performance.now();raf=requestAnimationFrame(tick);}
$('#b-play').onclick=function(){playing=!playing;this.textContent=playing?'暂停':'播放';if(playing){if(cur<0||cur>=NODES.length-1)go(0);start();}else cancelAnimationFrame(raf);};
$('#b-prev').onclick=()=>{if(cur>0){go(cur-1);if(playing)start();}};$('#b-next').onclick=()=>{if(cur<NODES.length-1){go(cur+1);if(playing)start();}};
$('#b-restart').onclick=()=>{playing=true;$('#b-play').textContent='暂停';go(0);start();};
$('#spd').onchange=e=>{speed=parseFloat(e.target.value);};
NODES.forEach((n,i)=>{$('#'+n.id).style.cursor='pointer';$('#'+n.id).onclick=()=>{go(i);if(playing)start();};});
window.addEventListener('resize',()=>{if(cur>=0){const [x,y]=center(NODES[cur].id);$('#token').style.left=x+'px';$('#token').style.top=y+'px';}});
let loaded=0;Object.values(IM).forEach(e=>{e.onload=()=>{if(++loaded===Object.keys(IM).length){drawTilesStatic();resetAll();go(0);if(playing)start();else $('#b-play').textContent='播放';}};});
__DIFFJS__
</script>
"""
diffjs = prev.split("/* ---- 热扩散 ---- */")[1].split("</script>")[0]
rep = {"__CSS__": CSS, "__EXTRA__": EXTRA, "__DATA__": DATA, "__ROW1__": ROW1, "__ROW2__": ROW2, "__ROW3__": ROW3, "__WRAP__": WRAP, "__WID__": wid, "__TAIL__": TAIL,
       "__DIFFJS__": "/* ---- 热扩散 ---- */" + diffjs, "__GT__": str(P["gt_instances"]),
       "__DW__": str(df["w"] * 4), "__DH__": str(df["h"] * 4), "__NIT__": str(min(400, 2 * round((df["w"] ** 2 + df["h"] ** 2) ** 0.5))),
       "__DI_S__": di["small"]["image"], "__DI_SN__": str(di["small"]["n"]), "__DI_A__": di["auto"]["image"], "__DI_AD__": f"{di['auto']['diameter']:.0f}", "__DI_AN__": str(di["auto"]["n"]),
       "__DI_L__": di["large"]["image"], "__DI_LN__": str(di["large"]["n"]),
       "__DB_A__": db["auto"]["image"], "__DB_AD__": f"{db['auto']['diameter']:.0f}", "__DB_AN__": str(db["auto"]["n"]), "__DB_D__": db["d404"]["image"], "__DB_DN__": str(db["d404"]["n"]), "__DB_F__": db["finetuned"]["image"], "__DB_FN__": str(db["finetuned"]["n"]),
       "__RS_O__": rs["original"], "__RS_OW__": str(rs["original_size"][0]), "__RS_OH__": str(rs["original_size"][1]), "__RS_S__": rs["scaled"], "__RS_SW__": str(rs["scaled_size"][0]), "__RS_SH__": str(rs["scaled_size"][1]), "__RS_SW3__": str(rs["scaled_size"][0] * 3), "__RS_SH3__": str(rs["scaled_size"][1] * 3)}
html = HTML
for k, v in rep.items(): html = html.replace(k, v)
left = set(re.findall(r"__[A-Z_0-9]+__", html)); assert not left, left
open(f"{S}/orgalyst_scene.html", "w", encoding="utf-8").write(html); print("written", len(html) // 1024, "KB")
