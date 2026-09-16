# -*- coding: utf-8 -*-
"""Orgalyst 故事板动画：每一步都是同一个三格结构 —— [进去的东西] ══送入══► [模型/机器] ══得到══► [出来的东西]。
进去的卡片从左滑入机器，机器亮起并"工作"（内部小动画），输出卡片从机器右侧弹出；下一步时输出卡片滑到左边变成新的输入。
面向没有背景的观众：机器用大图标，文字用大白话，箭头粗大且带字。"""
import base64, json, re
S = "/private/tmp/claude-501/-Users-xiaoyanli/0850d9a1-4ef3-4938-beed-610f045d4857/scratchpad"
P = json.load(open(f"{S}/pipeline_demo_data.json", encoding="utf-8"))
C = json.load(open(f"{S}/cellpose_demo_data.json", encoding="utf-8"))
P["report_thumb"] = "data:image/jpeg;base64," + base64.b64encode(open(f"{S}/report_thumb_small.jpg", "rb").read()).decode()
P["growth_png"] = "data:image/png;base64," + base64.b64encode(open(f"{S}/growth_brain_test.png", "rb").read()).decode()
DATA = json.dumps(dict(P=P, diffusion=C["diffusion"], diam_i=C["diameter_intestine"], diam_b=C["diameter_brain"], rescale=C["rescale"]), ensure_ascii=False)
assert "</script" not in DATA
prev = open(f"{S}/build_scene_page2.py", encoding="utf-8").read()
CSS = open(f"{S}/design.html", encoding="utf-8").read().split("<style>")[1].split("</style>")[0]
r2, t3, m8, q9, m10 = P["s2_rescale"], P["s3_tiles"], P["s8_measure"], P["s9_qc"], P["s10_manifest"]
di, db, rs, df = C["diameter_intestine"], C["diameter_brain"], C["rescale"], C["diffusion"]
wid = m10["model"].split(":")[-1][:8]
UNET = prev.split('UNET = """')[1].split('"""')[0]
GAUGE = prev.split('GAUGE = """')[1].split('"""')[0]

EXTRA = """
main{max-width:1040px}main>p,main>h2,main>header,main>.two{max-width:76ch}
.strip{display:grid;grid-template-columns:repeat(9,1fr);gap:4px;margin:10px 0 8px}
.strip div{font-size:11.5px;line-height:1.3;text-align:center;padding:6px 4px;border:1px solid var(--rule);border-radius:6px;background:var(--panel);color:var(--muted);cursor:pointer;transition:all .3s}
.strip div b{display:block;font-family:var(--mono);font-size:10px;color:var(--accent);letter-spacing:.06em}
.strip div.on{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}.strip div.on b{color:var(--accent-ink)}.strip div.done{border-color:var(--accent);background:var(--accent-soft);color:var(--ink)}
@media (max-width:760px){.strip{grid-template-columns:repeat(3,1fr)}}
.board{position:relative;border:1px solid var(--rule);border-radius:10px;background:var(--panel);padding:18px 16px 14px;overflow:hidden}
.row{display:grid;grid-template-columns:1fr 120px 1.35fr 120px 1fr;gap:0;align-items:center;min-height:330px}
@media (max-width:760px){.row{grid-template-columns:1fr;min-height:0}.arrow{transform:rotate(90deg);height:60px}}
.card{position:relative;border:2px solid var(--rule);border-radius:10px;background:var(--paper);padding:10px;display:flex;flex-direction:column;gap:8px;min-width:0;transition:transform .7s cubic-bezier(.4,0,.2,1),opacity .5s,border-color .3s}
.card .ck{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.card h4{margin:0;font-size:15px;line-height:1.3}
.card .pic{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:6px;border:1px solid var(--rule);background:#0d1214;display:block}
.card .desc{font-size:13px;color:var(--muted);line-height:1.5}.card .desc b{color:var(--ink)}
.card.in.enter{transform:translateX(-40px);opacity:0}.card.out.hide{transform:translateX(30px) scale(.9);opacity:0}
.card.in.gone{transform:translateX(70%) scale(.6);opacity:0}
.machine{position:relative;border:2px solid var(--accent);border-radius:14px;background:var(--paper);padding:12px 14px;display:flex;flex-direction:column;gap:8px;min-width:0;box-shadow:0 0 0 0 rgba(14,122,108,0);transition:box-shadow .4s}
.machine.busy{box-shadow:0 0 0 6px rgba(14,122,108,.18),0 12px 30px rgba(14,122,108,.22);animation:pulse 1.2s ease-in-out infinite}
@keyframes pulse{50%{box-shadow:0 0 0 10px rgba(14,122,108,.10),0 12px 30px rgba(14,122,108,.22)}}
.machine .mk{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.machine h3{margin:0;font-size:19px;font-family:var(--serif);line-height:1.25}
.machine .body{width:100%;aspect-ratio:16/10;border-radius:8px;background:#0d1214;border:1px solid var(--rule);position:relative;overflow:hidden}
.machine .body canvas,.machine .body svg,.machine .body img{position:absolute;inset:0;width:100%;height:100%}
.machine .body img{object-fit:contain}
.machine .what{font-size:13px;line-height:1.5}.machine .what b{color:var(--accent)}
.machine .status{font-family:var(--mono);font-size:11px;color:var(--muted);min-height:1.4em}
.arrow{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:var(--muted);transition:color .3s}
.arrow svg{width:96px;height:44px}.arrow .al{font-size:13px;font-weight:700;letter-spacing:.1em}
.arrow.on{color:var(--accent)}.arrow.on svg path{stroke-dasharray:8 6;animation:dash .5s linear infinite}
@keyframes dash{to{stroke-dashoffset:-14}}
.gauge{position:absolute;inset:0}.gauge .needle{transform-origin:50px 60px;transform:rotate(-90deg);transition:transform 1.4s cubic-bezier(.3,.8,.3,1)}
.unet .blk{fill:#1B2529;stroke:#5A6A70;stroke-width:1;transition:fill .25s,stroke .25s}.unet .blk.lit{fill:#3FB59F;stroke:#E3E9E6}
.unet .skip{stroke:#5A6A70;stroke-width:1;stroke-dasharray:3 2;fill:none}.unet .skip.lit{stroke:#3FB59F}
.unet .plug{fill:#9A6A12;stroke:#F5E9CF;stroke-width:1}.unet .plug.ft{fill:#0E7A6C;stroke:#D9EEE9}
.unet text{font-family:ui-monospace,Menlo,monospace;font-size:7px;fill:#E3E9E6}
.chips{display:flex;flex-wrap:wrap;gap:5px}.chip{font-family:var(--mono);font-size:10.5px;padding:1px 7px;border-radius:9px;border:1px solid var(--rule);color:var(--muted);opacity:.35;transition:opacity .3s}.chip.ok{opacity:1;border-color:var(--accent);color:var(--accent);background:var(--accent-soft)}
.tbl{width:100%;font-size:11px;border-collapse:collapse}.tbl th,.tbl td{padding:2px 5px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.tbl th:first-child,.tbl td:first-child{text-align:left}.tbl th{background:var(--panel)}
.tbl tr{opacity:0;transition:opacity .3s}.tbl tr.in{opacity:1}
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
@media (prefers-reduced-motion:reduce){.card,.machine,.arrow svg path,.gauge .needle,.tbl tr,.chip{transition:none;animation:none}}
"""
ARROW = '<svg viewBox="0 0 96 44" aria-hidden="true"><path d="M4 22 H70" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="M62 8 L86 22 L62 36" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></svg>'

HTML = """<title>Orgalyst 平台演示</title>
<style>__CSS____EXTRA__</style>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div><a href="#story">一步一步看</a><a href="#diff">补充：流场是怎么来的</a><a href="#diam">补充：直径给错会怎样</a><a href="#notes">阅读说明</a></nav>
<main>
<header class="hd">
  <div class="eyebrow">Orgalyst · 一张照片的旅程 · 2026-09-16</div>
  <h1>一张类器官照片，进去的是什么，经过了什么，出来的是什么</h1>
  <p class="sub">每一步都是同一个结构：左边是进去的东西，中间是处理它的模型或工具，右边是得到的东西。示例是一张真实的肠类器官显微照片（2048×2048 像素，人工数过有 __GT__ 个类器官），所有结果都是这次真实运行得到的。</p>
</header>

<section id="story">
<div class="ctl"><button id="b-play" class="primary">暂停</button><button id="b-prev">上一步</button><button id="b-next">下一步</button><button id="b-restart">从头播放</button>
<label class="small" style="display:flex;align-items:center;gap:6px">速度 <select id="spd" style="font:inherit;font-size:13px"><option value="1.6">慢</option><option value="1" selected>正常</option><option value="0.6">快</option></select></label><span class="small" id="stepno"></span></div>
<div class="strip" id="strip"></div>
<div class="bar"><i id="bar"></i></div>
<div class="board">
  <div class="row">
    <div class="card in" id="cin"><div class="ck">进去的东西</div><h4 id="in-title"></h4><div id="in-body"></div><div class="desc" id="in-desc"></div></div>
    <div class="arrow" id="ar1">__ARROW__<span class="al">送入</span></div>
    <div class="machine" id="mach"><div class="mk" id="m-kind"></div><h3 id="m-title"></h3><div class="body" id="m-body"></div><div class="what" id="m-what"></div><div class="status" id="m-status"></div></div>
    <div class="arrow" id="ar2">__ARROW__<span class="al">得到</span></div>
    <div class="card out" id="cout"><div class="ck">出来的东西</div><h4 id="out-title"></h4><div id="out-body"></div><div class="desc" id="out-desc"></div></div>
  </div>
</div>
<div class="cap" id="cap">点「播放」开始</div>
</section>

<h2 id="diff">补充：第 3 步网络学的"方向图"是怎么来的</h2>
<p>网络要学的"方向图"（每个像素指向所属类器官中心的箭头）不需要人来画，它由人工描的轮廓用程序算出来：在轮廓内离边界最远的点放一个热源，热量只在轮廓内扩散，等温度场稳定后，每个像素朝温度升高最快的方向就是它的箭头，全部指向中心。用热扩散而不是"直接指向中心点"，是为了让弯曲、凹陷的形状也能从任何位置沿箭头走到内部。下面这个例子取自示例照片里最不圆的一个类器官。</p>
<div class="stage2">
  <canvas id="cv-diff" width="__DW__" height="__DH__"></canvas>
  <div><div class="ctl" style="margin:0 0 8px"><button id="b-diff-play">播放扩散</button><button id="b-diff-reset">重置</button></div>
  <div class="legend"><b>颜色</b>：温度，亮为高。<br><b>箭头</b>：扩散完成后按温度梯度画出。<br><b>迭代</b>：按物体大小自适应，这里 __NIT__ 次。</div><div class="small" id="st-diff" style="margin-top:6px"></div></div>
</div>

<h2 id="diam">补充：第 1 步"量多大"量错了会怎样</h2>
<p>网络只认识大约 30 像素宽的东西，所以第 1 步要先估计类器官多大，再把照片缩到合适的比例。同一张照片、同一个模型，只改这个估计值：</p>
<div class="grid3">
  <figure><img src="__DI_S__"><figcaption><b>估成 12 像素（偏小）</b>：照片被放大，网络把大类器官拆碎或漏掉，只找到 __DI_SN__ 个</figcaption></figure>
  <figure><img src="__DI_A__"><figcaption><b>估成 __DI_AD__ 像素（自动估计）</b>：找到 __DI_AN__ 个，人工数过是 35 个</figcaption></figure>
  <figure><img src="__DI_L__"><figcaption><b>估成 150 像素（偏大）</b>：照片被缩得很小，所有类器官糊成一团，只找到 __DI_LN__ 个</figcaption></figure>
</div>
<p>脑类器官更极端：通用模型自带的估计器是在细胞照片上学的，看到 400 像素的大团块猜成 __DB_AD__ 像素，按这个放大十几倍后什么也找不到；把估计值改成 404，同一个通用模型立刻找到；我们微调过的脑专用模型把这个数记在了模型里。</p>
<div class="two"><div><img src="__RS_O__" alt="脑类器官原图" style="max-width:100%"><div class="small">脑类器官原图 __RS_OW__×__RS_OH__ 像素，目标约 404 像素宽</div></div><div><img src="__RS_S__" width="__RS_SW3__" height="__RS_SH3__" alt="缩放后"><div class="small">按 404 缩到目标 30 像素后：__RS_SW__×__RS_SH__ 像素（放大 3 倍显示）</div></div></div>
<div class="grid3">
  <figure><img src="__DB_A__"><figcaption><b>通用模型，自动估计 __DB_AD__</b>：__DB_AN__ 个</figcaption></figure>
  <figure><img src="__DB_D__"><figcaption><b>通用模型，手动给 404</b>：__DB_DN__ 个</figcaption></figure>
  <figure><img src="__DB_F__"><figcaption><b>脑专用微调模型（自带 404）</b>：__DB_FN__ 个</figcaption></figure>
</div>

<h2 id="notes">阅读说明</h2>
<p>第 1 到第 4 步是 Cellpose（Stringer 等，2021）这套分割方法的推理过程：估计大小并缩放、切块、U-Net 神经网络输出方向图和"哪里是类器官"图、按方向图把像素聚成一个个类器官。本项目没有改动这套方法的结构，改的是装进 U-Net 的权重（通用的 cyto3 权重在 OrgLine 公开数据上按器官微调）和第 1 步的估计策略。第 5 步以后是 Orgalyst 在分割之上加的分析，全部是确定性的计算，不经过大模型；对话式助手只做第 0 步：听懂用户要什么、选工具、事后解释。所有数字来自本次真实运行；第 4 步的粒子动画只画了部分像素，按网络输出的真实方向图移动。</p>
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
const UNET=`__UNET__`,GAUGE=`__GAUGE__`;
let anim=null,timers=[];
function later(fn,ms){timers.push(setTimeout(fn,reduce?0:ms));}
function clearAll(){cancelAnimationFrame(anim);timers.forEach(clearTimeout);timers=[];}
const pic=(src,alt)=>'<img class="pic" src="'+src+'" alt="'+(alt||'')+'">';
const three=()=>'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px"><img class="pic" src="'+P.s4_net.flow+'" style="aspect-ratio:1/1"><img class="pic" src="'+P.s4_net.prob+'" style="aspect-ratio:1/1"><img class="pic" src="'+P.s5_thresh.image+'" style="aspect-ratio:1/1"></div><div class="desc" style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;text-align:center;font-size:11px"><span>方向图（颜色=方向）</span><span>哪里像类器官</span><span>阈值化后</span></div>';
const cols=['编号','面积','直径','圆度'];
const tbl=(cls)=>'<table class="tbl"><tr class="'+cls+'">'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>'+P.s8_measure.rows.slice(0,6).map(r=>'<tr class="'+cls+'"><td>'+r[0]+'</td><td>'+r[1]+'</td><td>'+r[2]+'</td><td>'+r[4]+'</td></tr>').join('')+'</table>';
const d1=P.s2_rescale.diameter, sc=P.s2_rescale.scale, sw=P.s2_rescale.small_size[0];
/* 机器内部动画（画在 #m-body 里） */
const M={
 assistant(inst){const b=$('#m-body');b.innerHTML='<div style="position:absolute;inset:0;padding:12px 14px;color:#E3E9E6;font-size:13px;line-height:1.6"><div id="typed" style="border:1px solid #3FB59F;border-radius:6px;padding:6px 10px;min-height:2.6em">你：</div><div class="chips" id="chips" style="margin-top:10px"><span class="chip">这是一批显微照片，要做形态分析</span><span class="chip">用「分析图像」工具</span><span class="chip">器官是肠 → 装肠专用权重</span><span class="chip">没给像素大小 → 结果用像素</span></div></div>';const t='分析这批肠类器官照片，告诉我它们的大小和形状，给我一份报告。';const el=$('#typed');if(inst){el.textContent='你：'+t;[...$('#chips').children].forEach(c=>c.classList.add('ok'));return;}let i=0;const f=()=>{if(i<t.length){el.textContent='你：'+t.slice(0,++i);later(f,38);}};f();[...$('#chips').children].forEach((c,i)=>later(()=>c.classList.add('ok'),2200+i*420));},
 resize(inst){const b=$('#m-body');b.innerHTML='<div class="gauge" style="position:absolute;left:0;top:0;width:38%;height:100%">'+GAUGE.replace('class="gv" id="gv"','style="position:absolute;left:0;right:0;bottom:8px;text-align:center;font-family:ui-monospace;font-size:12px;color:#E3E9E6" id="gv"')+'</div><canvas id="rc" width="300" height="190" style="left:38%;width:62%"></canvas>';const c=$('#rc').getContext('2d');const ang=-90+180*Math.min(1,d1/150);later(()=>{$('#m-body .needle').style.transform='rotate('+ang+'deg)';},inst?0:200);later(()=>{$('#gv').textContent='约 '+d1.toFixed(0)+' 像素宽';},inst?0:1400);let k=0;cancelAnimationFrame(anim);const f=()=>{k=Math.min(1,k+((reduce||inst)?1:.02));const s=1-(1-sc)*Math.max(0,(k-.35)/.65),w=170*s;c.fillStyle='#0d1214';c.fillRect(0,0,300,190);c.drawImage(IM.norm,150-w/2,95-w/2,w,w);c.strokeStyle='#3FB59F';c.setLineDash([4,4]);c.strokeRect(150-w/2+.5,95-w/2+.5,w-1,w-1);c.setLineDash([]);c.fillStyle='#E3E9E6';c.font='12px ui-monospace,Menlo,monospace';c.fillText('缩小到 ×'+s.toFixed(2),150-w/2,185);if(k<1)anim=requestAnimationFrame(f);};later(f,inst?0:1500);$('#m-status').textContent='先量一下类器官多大，再把照片缩到网络习惯的尺寸';},
 tiles(inst){const b=$('#m-body');b.innerHTML='<canvas id="tc" width="320" height="200"></canvas>';const c=$('#tc').getContext('2d'),T=P.s3_tiles.tiles,f=190/sw,ox=(320-190)/2;c.fillStyle='#0d1214';c.fillRect(0,0,320,200);c.drawImage(IM.small,ox,5,190,190);let i=0;cancelAnimationFrame(anim);const g=()=>{for(let k=0;k<((reduce||inst)?T.length:2)&&i<T.length;k++,i++){const [x,y,w,h]=T[i];c.fillStyle='rgba(63,181,159,.12)';c.fillRect(ox+x*f,5+y*f,w*f,h*f);c.strokeStyle='rgba(63,181,159,.95)';c.strokeRect(ox+x*f+.5,5+y*f+.5,w*f-1,h*f-1);}$('#m-status').textContent='已切出 '+i+' / '+T.length+' 块';if(i<T.length)anim=requestAnimationFrame(g);};g();},
 unet(inst){const b=$('#m-body');b.innerHTML='<div class="unet" style="position:absolute;inset:6px">'+UNET+'</div>';const UB=['e1','e2','e3','e4','bt','d4','d3','d2','d1'];later(()=>{$('#plug').classList.add('ft');$('#plugt').textContent='权重: 肠微调 __WID__';},inst?0:300);UB.forEach((id,i)=>later(()=>{$('#'+id).classList.add('lit');if(i>=5)$('#k'+(9-i)).classList.add('lit');$('#m-status').textContent=i<4?'编码：一层层提取特征（'+(i+1)+'/4）':i===4?'瓶颈：整张图的"风格向量"':'解码：一层层还原到像素（'+(i-4)+'/4）';},inst?0:600+i*300));later(()=>{$('#m-status').textContent='每块图输出三张图，共 '+P.s3_tiles.n+' 块';},inst?0:3400);},
 track(inst){const b=$('#m-body');b.innerHTML='<canvas id="kc" width="320" height="200"></canvas>';const c=$('#kc').getContext('2d'),parts=[];for(let y=2;y<N;y+=5)for(let x=2;x<N;x+=5){const i=y*N+x;if(cp[i]>0)parts.push({x:x+.5,y:y+.5,id:mk[i]});}let step=0;const STEPS=200,f=190/N,ox=(320-190)/2;cancelAnimationFrame(anim);
   const samp=(a,x,y)=>{const x0=Math.max(0,Math.min(N-2,x|0)),y0=Math.max(0,Math.min(N-2,y|0)),fx=x-x0,fy=y-y0;return a[y0*N+x0]*(1-fx)*(1-fy)+a[y0*N+x0+1]*fx*(1-fy)+a[(y0+1)*N+x0]*(1-fx)*fy+a[(y0+1)*N+x0+1]*fx*fy;};
   const g=()=>{for(let k=0;k<((reduce||inst)?STEPS:5)&&step<STEPS;k++,step++)for(const p of parts){p.x=Math.max(0,Math.min(N-1,p.x+samp(dx,p.x,p.y)));p.y=Math.max(0,Math.min(N-1,p.y+samp(dy,p.x,p.y)));}
     c.fillStyle='#0d1214';c.fillRect(0,0,320,200);c.drawImage(IM.input,ox,5,190,190);c.fillStyle='rgba(0,0,0,.6)';c.fillRect(ox,5,190,190);const done=step>=STEPS;for(const p of parts){c.fillStyle=done?hsl(p.id||0):'#3FB59F';c.fillRect(ox+p.x*f-1,5+p.y*f-1,2,2);}$('#m-status').textContent=done?'汇聚完成：'+P.s6_track.n+' 个点 = '+P.s6_track.n+' 个类器官':'像素沿箭头走：第 '+step+' / '+STEPS+' 步';if(!done)anim=requestAnimationFrame(g);};g();},
 measure(inst){const b=$('#m-body');b.innerHTML='<div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:14px;padding:10px"><svg viewBox="0 0 120 120" style="position:static;width:42%;height:auto"><circle cx="60" cy="62" r="40" fill="none" stroke="#3FB59F" stroke-width="3"/><line id="mr" x1="20" y1="62" x2="20" y2="62" stroke="#F5E9CF" stroke-width="3" stroke-linecap="round"/><text x="60" y="30" text-anchor="middle" font-size="9" fill="#E3E9E6" font-family="ui-monospace" id="mt"></text></svg><div class="chips" id="mchips" style="position:static;width:50%;flex-direction:column;align-items:flex-start"><span class="chip">面积</span><span class="chip">等效直径</span><span class="chip">周长</span><span class="chip">圆度（多圆）</span><span class="chip">实心度（有无凹陷）</span><span class="chip">长宽比</span></div></div>';later(()=>{$('#mr').setAttribute('x2',100);$('#mt').textContent='直径';},inst?0:300);[...$('#mchips').children].forEach((c,i)=>later(()=>c.classList.add('ok'),inst?0:700+i*350));later(()=>{$('#m-status').textContent='对 '+P.s8_measure.n+' 个轮廓逐个测量';},inst?0:400);},
 qc(inst){const b=$('#m-body');b.innerHTML='<img id="qi" src="'+P.s1_input.image+'" style="object-fit:cover;transition:transform .5s">';const e=$('#qi');const tf=['scaleX(-1)','scaleY(-1)','rotate(90deg)','rotate(180deg)','none'];tf.forEach((t,i)=>later(()=>{e.style.transform=t;$('#m-status').textContent=i<4?'第 '+(i+1)+' 次：把照片翻转/旋转后重新找一遍':'比较 '+P.s9_qc.k+' 次结果，找不稳定的';},inst?0:300+i*650));later(()=>{e.src=P.s9_qc.overlay;$('#m-status').textContent='有 '+P.s9_qc.n_low+' 个类器官在翻转后就找不到了 → 标为不可靠';},inst?0:3700);},
 stats(inst){const b=$('#m-body');b.innerHTML='<img src="'+P.growth_png+'" style="object-fit:contain;background:#fff;padding:6px;box-sizing:border-box">';$('#m-status').textContent='多张照片放在一起：按组比较、按时间连线';},
 report(inst){const b=$('#m-body');b.innerHTML='<div style="position:absolute;inset:14px 30%;background:#F6F8F7;border-radius:4px;padding:10px;display:flex;flex-direction:column;gap:6px" id="doc"></div>';const lines=[['概览','60%'],['逐图结果','80%'],['形态分布图','70%'],['质控','50%'],['方法','75%'],['溯源：MD5 · 权重哈希 · 参数 · 版本','90%']];lines.forEach(([t,w],i)=>later(()=>{const d=document.createElement('div');d.style.cssText='font-size:9px;color:#1B262C;border-left:3px solid #0E7A6C;padding-left:6px;width:'+w;d.textContent=t;$('#doc').appendChild(d);$('#m-status').textContent='正在写入：'+t;},inst?0:300+i*450));}
};
const STEPS=[
 {k:'助手',kind:'对话式助手（大模型）',title:'听懂你要什么，选好工具',inT:'你的一句话',inB:'<div class="desc" style="font-size:14px;color:var(--ink);border:1px solid var(--rule);border-radius:6px;padding:8px">"分析这批肠类器官照片，告诉我它们的大小和形状，给我一份报告。"</div>',inD:'不需要懂任何参数。',
  what:'助手<b>不看照片、不算数</b>，只做三件事：判断这是什么任务、选哪个工具、填什么参数（器官是肠 → 用肠专用权重）。',outT:'一份执行计划',outB:'<div class="desc" style="font-size:13px;color:var(--ink)">① 用「分析图像」工具<br>② 器官 = 肠<br>③ 像素大小未知 → 结果按像素报告<br>④ 完成后生成报告</div>',outD:'接下来照片按这个计划进入流水线。',m:'assistant',dur:6.0},
 {k:'量大小·缩放',kind:'第 1 步 · 预处理',title:'量一下多大，再缩到合适尺寸',inT:'一张显微照片',inB:pic(P.s1_input.image),inD:'<b>'+P.shape[0]+'×'+P.shape[1]+' 像素</b>，灰度。',
  what:'神经网络只认识大约 30 像素宽的东西。先用一个小模型估计类器官多大（约 <b>'+d1.toFixed(0)+' 像素</b>），再把整张照片缩到 <b>'+sc.toFixed(2)+' 倍</b>。',outT:'缩小后的照片',outB:pic(P.s2_rescale.small),outD:'<b>'+sw+'×'+sw+' 像素</b>，类器官现在约 30 像素宽。',m:'resize',dur:6.0},
 {k:'切块',kind:'第 2 步 · 预处理',title:'切成小块',inT:'缩小后的照片',inB:pic(P.s2_rescale.small),inD:sw+'×'+sw+' 像素。',
  what:'网络一次只看 224×224 的一小块。照片被切成 <b>'+P.s3_tiles.n+' 块</b>，相邻块重叠一半，免得类器官正好卡在边上。',outT:P.s3_tiles.n+' 张小图块',outB:'<canvas id="oc" class="pic" width="256" height="256"></canvas>',outD:'每块 224×224 像素，逐块送进网络。',m:'tiles',dur:5.0},
 {k:'U-Net 网络',kind:'第 3 步 · 神经网络',title:'U-Net 看图，输出三张图',inT:'一张小图块',inB:'<canvas id="ic" class="pic" width="224" height="224"></canvas>',inD:'224×224 像素。',
  what:'U-Net 是一种<b>先压缩再还原</b>的卷积网络。装在它上面的<b>权重</b>决定它认识什么：通用的 cyto3 权重认识细胞，我们在公开的肠类器官数据上继续训练，得到<b>肠专用权重</b>。结构不变，换的是权重。',outT:'三张图',outB:three(),outD:'前两张告诉每个像素"你的类器官中心在哪个方向"，第三张告诉"这里像不像类器官"。',m:'unet',dur:6.5},
 {k:'聚成轮廓',kind:'第 4 步 · 后处理',title:'把像素按箭头聚成一个个类器官',inT:'三张图（已拼回整图）',inB:three(),inD:'"像类器官"的像素占 '+(100*P.s5_thresh.frac).toFixed(1)+'%。',
  what:'每个"像类器官"的像素按自己的箭头走 200 步，同一个类器官里的像素会走到<b>同一个点</b>；走到同一点的归为一个。相邻两个类器官各有各的中心，所以能分开。',outT:P.s7_masks.n+' 个类器官的轮廓',outB:pic(P.s7_masks.overlay),outD:'绿线是自动画出的轮廓。人工数过是 <b>'+P.gt_instances+'</b> 个。',m:'track',dur:6.5},
 {k:'测量',kind:'第 5 步 · 分析',title:'给每个类器官量尺寸',inT:P.s7_masks.n+' 个轮廓',inB:pic(P.s7_masks.overlay),inD:'贴着照片边缘的 '+P.s8_measure.summary.border_excluded+' 个不完整，汇总时排除。',
  what:'对每个轮廓算<b>面积、直径、周长、圆度、实心度、长宽比</b>。这一步是纯几何计算，没有任何"猜"。如果知道一个像素等于多少微米，就换算成微米。',outT:'一张表，每个类器官一行',outB:tbl(''),outD:'共 '+P.s8_measure.n+' 行。中位数：面积 <b>'+P.s8_measure.summary.area_median.toFixed(0)+' px²</b>，圆度 <b>'+P.s8_measure.summary.circ_median.toFixed(2)+'</b>。',m:'measure',dur:5.5},
 {k:'质检',kind:'第 6 步 · 分析',title:'检查哪些结果不可靠',inT:'照片 + 轮廓',inB:pic(P.s7_masks.overlay),inD:'',
  what:'把照片<b>翻转、旋转</b>后再让网络找一遍。真正的类器官怎么转都能找到；翻一下就消失的，说明网络其实没把握，标为<b>不可靠</b>。另外检查照片有没有失焦、光照不均。',outT:'标出不可靠的',outB:pic(P.s9_qc.overlay),outD:'橙色框：<b>'+P.s9_qc.n_low+'</b> 个不可靠。整体一致性 '+P.s9_qc.agreement_mean.toFixed(2)+'。',m:'qc',dur:6.0},
 {k:'统计',kind:'第 7 步 · 分析',title:'多张照片放在一起比',inT:'很多张表',inB:tbl('in'),inD:'每张照片一张表。',
  what:'按用户给的分组（对照组 / 加药组）或时间点（第 5 天、第 10 天…）汇总，做统计检验、画生长曲线。示例是另一批脑类器官 30 天的数据。',outT:'曲线与比较结果',outB:pic(P.growth_png),outD:'4 个克隆 30 天的面积变化，细线是每个个体，粗线是平均。',m:'stats',dur:5.0},
 {k:'报告',kind:'第 8 步 · 输出',title:'写成一份报告，并留下记录',inT:'以上全部结果',inB:'<div class="desc" style="font-size:13px;color:var(--ink)">轮廓 · 表格 · 质检 · 曲线</div>',inD:'',
  what:'把所有内容排成一份<b>单文件网页报告</b>；同时记下这次用了哪张照片（校验码）、哪个权重、哪些参数、什么版本，任何人可以照着<b>复现</b>。',outT:'报告 + 运行记录',outB:pic(P.report_thumb),outD:'report.html（双击可开）+ manifest.json。助手据此向你汇报，并能回答追问。',m:'report',dur:5.5},
];
const strip=$('#strip');STEPS.forEach((s,i)=>{const d=document.createElement('div');d.innerHTML='<b>'+(i===0?'00':'0'+i)+'</b>'+s.k;d.onclick=()=>{go(i);if(playing)start();};strip.appendChild(d);});
let cur=-1,playing=!reduce,t0=0,speed=1,raf=null;
function drawTiles(canvasId,size){const c=$('#'+canvasId).getContext('2d'),T=P.s3_tiles.tiles,f=size/sw;c.drawImage(IM.small,0,0,size,size);T.forEach(([x,y,w,h])=>{c.strokeStyle='rgba(63,181,159,.95)';c.strokeRect(x*f+.5,y*f+.5,w*f-1,h*f-1);});}
function drawTile(canvasId){const c=$('#'+canvasId).getContext('2d'),T=P.s3_tiles.tiles,[x,y,w,h]=T[Math.floor(T.length/2)],f=224/sw;c.drawImage(IM.small,-x*f*0+0,0,0,0);c.drawImage(IM.small,x*(224/sw)*(sw/224)*0+x,y,w,h,0,0,224,224);}
function go(i){clearAll();cur=i;const s=STEPS[i];[...strip.children].forEach((d,k)=>{d.classList.toggle('on',k===i);d.classList.toggle('done',k<i);});
  const cin=$('#cin'),cout=$('#cout'),mach=$('#mach');cin.classList.remove('gone');cin.classList.add('enter');cout.classList.add('hide');mach.classList.remove('busy');$('#ar1').classList.remove('on');$('#ar2').classList.remove('on');
  $('#in-title').textContent=s.inT;$('#in-body').innerHTML=s.inB;$('#in-desc').innerHTML=s.inD;$('#m-kind').textContent=s.kind;$('#m-title').textContent=s.title;$('#m-what').innerHTML=s.what;$('#m-status').textContent='';$('#m-body').innerHTML='';
  $('#out-title').textContent=s.outT;$('#out-body').innerHTML=s.outB;$('#out-desc').innerHTML=s.outD;
  if(i===2)later(()=>drawTiles('oc',256),50);if(i===3)later(()=>drawTile('ic'),50);
  $('#cap').textContent='第 '+i+' 步 · '+s.title+'：'+s.what.replace(/<[^>]+>/g,'');$('#stepno').textContent='第 '+(i+1)+' / '+STEPS.length+' 幕';
  later(()=>cin.classList.remove('enter'),60);later(()=>{$('#ar1').classList.add('on');},700);later(()=>{cin.classList.add('gone');},1100);later(()=>{$('#ar1').classList.remove('on');mach.classList.add('busy');M[s.m](false);},1500);
  const tOut=Math.max(2500,s.dur*1000*0.62);later(()=>{$('#ar2').classList.add('on');},tOut-500);later(()=>{mach.classList.remove('busy');cout.classList.remove('hide');cin.classList.remove('gone');cin.style.opacity=.55;},tOut);later(()=>{$('#ar2').classList.remove('on');cin.style.opacity='';},tOut+900);
  if(i===6)later(()=>{},0);
  t0=performance.now();}
function tick(){if(!playing)return;const e=performance.now()-t0,d=STEPS[cur].dur*1000*speed;$('#bar').style.width=Math.min(100,100*e/d)+'%';if(e>=d){if(cur<STEPS.length-1)go(cur+1);else{playing=false;$('#b-play').textContent='播放';return;}}raf=requestAnimationFrame(tick);}
function start(){cancelAnimationFrame(raf);t0=performance.now();raf=requestAnimationFrame(tick);}
$('#b-play').onclick=function(){playing=!playing;this.textContent=playing?'暂停':'播放';if(playing){if(cur<0||cur>=STEPS.length-1)go(0);start();}else cancelAnimationFrame(raf);};
$('#b-prev').onclick=()=>{if(cur>0){go(cur-1);if(playing)start();}};$('#b-next').onclick=()=>{if(cur<STEPS.length-1){go(cur+1);if(playing)start();}};
$('#b-restart').onclick=()=>{playing=true;$('#b-play').textContent='暂停';go(0);start();};
$('#spd').onchange=e=>{speed=parseFloat(e.target.value);};
let loaded=0;Object.values(IM).forEach(e=>{e.onload=()=>{if(++loaded===Object.keys(IM).length){go(0);if(playing)start();else $('#b-play').textContent='播放';}};});
__DIFFJS__
</script>
"""
diffjs = prev.split("/* ---- 热扩散 ---- */")[1].split("</script>")[0]
rep = {"__CSS__": CSS, "__EXTRA__": EXTRA, "__DATA__": DATA, "__UNET__": UNET, "__GAUGE__": GAUGE, "__ARROW__": ARROW, "__WID__": wid, "__DIFFJS__": "/* ---- 热扩散 ---- */" + diffjs,
       "__GT__": str(P["gt_instances"]), "__DW__": str(df["w"] * 4), "__DH__": str(df["h"] * 4), "__NIT__": str(min(400, 2 * round((df["w"] ** 2 + df["h"] ** 2) ** 0.5))),
       "__DI_S__": di["small"]["image"], "__DI_SN__": str(di["small"]["n"]), "__DI_A__": di["auto"]["image"], "__DI_AD__": f"{di['auto']['diameter']:.0f}", "__DI_AN__": str(di["auto"]["n"]),
       "__DI_L__": di["large"]["image"], "__DI_LN__": str(di["large"]["n"]),
       "__DB_A__": db["auto"]["image"], "__DB_AD__": f"{db['auto']['diameter']:.0f}", "__DB_AN__": str(db["auto"]["n"]), "__DB_D__": db["d404"]["image"], "__DB_DN__": str(db["d404"]["n"]), "__DB_F__": db["finetuned"]["image"], "__DB_FN__": str(db["finetuned"]["n"]),
       "__RS_O__": rs["original"], "__RS_OW__": str(rs["original_size"][0]), "__RS_OH__": str(rs["original_size"][1]), "__RS_S__": rs["scaled"], "__RS_SW__": str(rs["scaled_size"][0]), "__RS_SH__": str(rs["scaled_size"][1]), "__RS_SW3__": str(rs["scaled_size"][0] * 3), "__RS_SH3__": str(rs["scaled_size"][1] * 3)}
html = HTML
for k, v in rep.items(): html = html.replace(k, v)
left = set(re.findall(r"__[A-Z_0-9]+__", html)); assert not left, left
open(f"{S}/orgalyst_scene.html", "w", encoding="utf-8").write(html); print("written", len(html) // 1024, "KB")
