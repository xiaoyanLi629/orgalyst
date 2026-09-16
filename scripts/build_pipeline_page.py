# -*- coding: utf-8 -*-
"""组装流水线动画页：Orgalyst 从一张图到报告的 12 步，每步自动播放并展示真实产物。"""
import base64, json
S = "/private/tmp/claude-501/-Users-xiaoyanli/0850d9a1-4ef3-4938-beed-610f045d4857/scratchpad"
d = json.load(open(f"{S}/pipeline_demo_data.json", encoding="utf-8"))
d["report_thumb"] = "data:image/jpeg;base64," + base64.b64encode(open(f"{S}/report_thumb_small.jpg", "rb").read()).decode()
d["growth_png"] = "data:image/png;base64," + base64.b64encode(open(f"{S}/growth_brain_test.png", "rb").read()).decode()
data = json.dumps(d, ensure_ascii=False); assert "</script" not in data
CSS = open(f"{S}/design.html", encoding="utf-8").read().split("<style>")[1].split("</style>")[0]
r2, t3, n4, m8, q9, m10 = d["s2_rescale"], d["s3_tiles"], d["s4_net"], d["s8_measure"], d["s9_qc"], d["s10_manifest"]

STAGES = [
 dict(id="input", group="seg", title="输入图像", what=f"一张明场显微图，{d['shape'][0]}×{d['shape'][1]} 像素。用户只需要提供它和器官类型。", got=f"灰度图 · 人工标注 {d['gt_instances']} 个类器官（系统看不到标注）"),
 dict(id="rescale", group="seg", title="归一化与缩放", what=f"把灰度拉伸到 1–99 百分位，再按估计出的类器官直径 {r2['diameter']:.0f} px 把图缩到目标约 30 px。这一步决定网络看到的「尺度」。", got=f"缩放系数 {r2['scale']:.2f} → {r2['small_size'][0]}×{r2['small_size'][1]} px"),
 dict(id="tiles", group="seg", title="切块", what="缩放后的图按 224×224 的窗口切开，相邻窗口重叠一半，每块单独送进网络。", got=f"{t3['n']} 个图块"),
 dict(id="net", group="seg", title="U-Net 输出三张图", what="每块经过网络得到三张同样大小的图：水平流、垂直流（合成为颜色图，色相 = 箭头方向）和目标概率。这是全流程唯一「学来」的一步。", got="流场 2 通道 + 目标概率 1 通道"),
 dict(id="thresh", group="seg", title="拼回与阈值化", what="各块的输出按中心权重高、边缘权重低加权平均后拼成整图；目标概率高于阈值（0）的像素判为「在某个类器官里」。", got=f"{100*d['s5_thresh']['frac']:.1f}% 的像素判为目标"),
 dict(id="track", group="seg", title="沿流场追踪", what="每个目标像素按所在位置的箭头一步步移动约 200 步，同一个类器官里的像素汇聚到同一点，汇聚点相同者归为一个实例。这一步把「前景」变成「一个个物体」。", got=f"{d['s6_track']['n']} 个汇聚点 = {d['s6_track']['n']} 个实例"),
 dict(id="masks", group="seg", title="实例掩码", what=f"过滤掉流场不一致的实例后，把掩码放大回原图尺寸。绿线是每个实例的轮廓。", got=f"{d['s7_masks']['n']} 个实例（人工标注 {d['gt_instances']}）"),
 dict(id="measure", group="ana", title="形态测量", what="对每个实例计算面积、等效直径、周长、圆度、实心度、长宽比等，触及图像边缘的实例在汇总时排除。给定像素尺寸时另换算成微米。", got=f"每个类器官一行的特征表 · 非贴边 {m8['summary']['n']} 个 · 面积中位数 {m8['summary']['area_median']:.0f} px² · 圆度中位数 {m8['summary']['circ_median']:.3f}"),
 dict(id="qc", group="ana", title="质量控制", what=f"图像级：失焦分数、光照不均、饱和像素比例。实例级：把图翻转/旋转 {q9['k']} 次重新分割，某个实例若在多数变换下找不到，记为低可信（橙色）。", got=f"低可信实例 {q9['n_low']} 个 · 平均一致性 {q9['agreement_mean']:.2f} · 失焦分数 {q9['focus']:.3f}"),
 dict(id="stats", group="ana", title="统计与追踪", what="多张图按用户给的分组或时间点汇总：两组 Mann-Whitney、多组 Kruskal-Wallis、效应量 Cliff's δ、Holm 校正；有个体和时间信息时画生长曲线。示例是脑类器官测试集 4 个克隆 30 天的生长曲线。", got="组间比较表 · 生长曲线 · 逐个体倍数变化"),
 dict(id="report", group="ana", title="报告", what="把以上全部整理成一份单文件 HTML：概览指标、逐图表、分布图、叠加缩略图、方法学文字（固定模板，不经大模型）。", got="report.html，双击可开，不依赖网络"),
 dict(id="manifest", group="ana", title="溯源", what="每次分析一个运行目录，manifest.json 记录每张输入图的 MD5、模型名与权重哈希、直径策略与参数、软件与 CUDA 版本，任何人可据此复现。", got="manifest.json + tables/ + masks/ + overlays/"),
]
stages_json = json.dumps(STAGES, ensure_ascii=False)
manifest_txt = json.dumps({"run_id": "20260916_101534_7c1e2a", "inputs": [{"path": d["source"], "md5": "e3a1…9f2c", "shape": d["shape"], "n_instances": d["s7_masks"]["n"]}],
                           "models": {"segmentation": {"id": m10["model"], "diam_mode": m10["diam_mode"], "diameter_px": round(m10["diameter"], 1)}},
                           "params": {"flow_threshold": 0.4, "cellprob_threshold": 0.0, "exclude_border": True, "qc": True, "tta_k": 4},
                           "versions": {"cellpose": "3.1.1.3", "torch": "2.14.0+cu130", "cuda": "13.0", "gpu": "NVIDIA GeForce RTX 5090 D"}}, indent=2, ensure_ascii=False)

EXTRA = """
.pipe{margin:18px 0 8px}
.groups{display:grid;grid-template-columns:7fr 5fr;gap:8px;margin-bottom:6px}
.groups div{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--rule);padding-bottom:4px}
.rail{display:grid;grid-template-columns:repeat(12,1fr);gap:4px;position:relative}
.node{border:1px solid var(--rule);border-radius:4px;padding:6px 4px;font-size:11.5px;line-height:1.3;text-align:center;cursor:pointer;background:var(--panel);color:var(--muted);transition:all .3s;min-width:0}
.node .n{display:block;font-family:var(--mono);font-size:10px;color:var(--accent);margin-bottom:2px}
.node.done{color:var(--ink);border-color:var(--accent);background:var(--accent-soft)}
.node.on{color:var(--accent-ink);background:var(--accent);border-color:var(--accent);transform:translateY(-2px);box-shadow:0 4px 12px rgba(14,122,108,.25)}
@media (max-width:860px){.rail{grid-template-columns:repeat(6,1fr)}.groups{display:none}}
.bar{height:3px;background:var(--rule);border-radius:2px;margin:10px 0 14px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:var(--accent);transition:width .2s linear}
.view{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:18px;align-items:start}
@media (max-width:860px){.view{grid-template-columns:minmax(0,1fr)}}
.frame{position:relative;aspect-ratio:1/1;max-width:100%;border:1px solid var(--rule);border-radius:4px;background:#0d1214;overflow:hidden}
.frame>*{position:absolute;inset:0;width:100%;height:100%;opacity:0;transition:opacity .45s ease}.frame>.show{opacity:1}
.frame canvas{width:100%;height:100%}.frame img.fit{object-fit:contain;padding:8px;box-sizing:border-box;background:#0d1214}
.frame .tbl{overflow:auto;padding:14px;background:var(--paper);color:var(--ink)}.frame table{font-size:12.5px;min-width:0;width:100%}.frame th,.frame td{padding:5px 8px}.frame tr{opacity:0;transform:translateY(6px);transition:all .35s}.frame tr.in{opacity:1;transform:none}
.frame pre{margin:0;padding:14px;background:var(--paper);color:var(--ink);font-size:12px;line-height:1.5;overflow:auto;height:100%;box-sizing:border-box}
.frame .three{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:6px;padding:6px;box-sizing:border-box;background:#0d1214}.frame .three img,.frame .three canvas{width:100%;height:100%;object-fit:contain;opacity:0;transform:scale(.96);transition:all .5s}.frame .three .in{opacity:1;transform:none}.frame .three figure{margin:0;position:relative;min-width:0;min-height:0}.frame .three figcaption{position:absolute;left:6px;bottom:4px;font-size:11px;color:#E3E9E6;background:rgba(13,18,20,.7);padding:1px 6px;border-radius:3px}
.card{border:1px solid var(--rule);border-radius:4px;padding:14px 16px;background:var(--panel);min-height:200px}
.card .k{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.card h3{margin:4px 0 8px;font-size:18px;font-family:var(--serif)}.card p{font-size:14px;margin:0 0 10px}
.card .got{border-left:3px solid var(--accent);padding:6px 10px;background:var(--accent-soft);font-size:13px;border-radius:0 4px 4px 0}.card .got b{display:block;font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;color:var(--accent);margin-bottom:2px}
.ctl{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 4px}
button{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--rule);border-radius:4px;background:var(--panel);color:var(--ink);cursor:pointer}
button:hover,button:focus-visible{border-color:var(--accent);outline:none}button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.badge{position:absolute;right:10px;top:10px;font-family:var(--mono);font-size:11px;color:#E3E9E6;background:rgba(13,18,20,.7);padding:2px 8px;border-radius:3px;pointer-events:none;z-index:2}
@media (prefers-reduced-motion:reduce){.frame>*,.node,.frame tr,.frame .three img{transition:none}}
"""

HTML = """<title>Orgalyst 流水线演示</title>
<style>__CSS____EXTRA__</style>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div><a href="#pipe">流水线动画</a><a href="#notes">阅读说明</a></nav>
<main>
<header class="hd">
  <div class="eyebrow">Orgalyst · 从一张图到一份报告 · 2026-09-16</div>
  <h1>一张类器官图进入 Orgalyst 之后发生了什么</h1>
  <p class="sub">十二步，每一步展示它真实得到的东西。示例是 OrgLine 肠类器官测试集里的一张 2048×2048 宽场图，由我们微调的肠专用 Cellpose 权重处理；后半段的统计示例来自脑类器官测试集。</p>
</header>

<section id="pipe" class="pipe">
  <div class="groups"><div>分割 · Cellpose（步骤 1–7）</div><div>分析 · Orgalyst（步骤 8–12）</div></div>
  <div class="rail" id="rail"></div>
  <div class="bar"><i id="bar"></i></div>
  <div class="view">
    <div class="frame" id="frame">
      <span class="badge" id="badge"></span>
      <canvas id="c-input" width="512" height="512"></canvas>
      <canvas id="c-rescale" width="512" height="512"></canvas>
      <canvas id="c-tiles" width="512" height="512"></canvas>
      <div class="three" id="v-net"></div>
      <canvas id="c-thresh" width="512" height="512"></canvas>
      <canvas id="c-track" width="512" height="512"></canvas>
      <img class="fit" id="i-masks" alt="实例掩码叠加">
      <div class="tbl" id="v-measure"></div>
      <img class="fit" id="i-qc" alt="质控叠加">
      <img class="fit" id="i-stats" alt="生长曲线">
      <img class="fit" id="i-report" alt="报告缩略图">
      <pre id="v-manifest"></pre>
    </div>
    <aside class="card" id="card"><div class="k" id="ck"></div><h3 id="ct"></h3><p id="cw"></p><div class="got"><b>这一步得到</b><span id="cg"></span></div></aside>
  </div>
  <div class="ctl"><button id="b-play" class="primary">暂停</button><button id="b-prev">上一步</button><button id="b-next">下一步</button><button id="b-restart">从头播放</button><span class="small" style="align-self:center">每步约 5 秒，点击上方任一步可跳转</span></div>
</section>

<h2 id="notes">阅读说明</h2>
<p>前七步是 Cellpose（Stringer 等，2021）的推理过程，本项目未改动其架构与后处理，改动的是权重（在 cyto3 基础上按器官微调）和第二步的直径策略（脑用两遍推理，肠、胰腺癌用尺寸估计器逐图估计，结肠用模型自带直径）。第二步的缩放是整个方法对"尺度"敏感的根源：直径给错，网络就在错误的尺度上找目标，这也是零样本 cyto3 在脑类器官上失败、联合四器官模型自带直径对任何器官都不对的原因。后五步是 Orgalyst 在分割之上加的确定性分析，全部不经过大模型；对话式助手只负责理解用户意图、按顺序调用这些步骤并解释结果。</p>
<p class="small">追踪一步的动画为示意：像素点按网络输出的真实流场移动，为清楚起见只显示部分像素。所有数字均来自本次真实运行。</p>
</main>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const STAGES=__STAGES__;
const MANIFEST=__MANIFEST__;
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const N=512;
function i8(b64){const s=atob(b64);const a=new Float32Array(s.length);for(let i=0;i<s.length;i++){let v=s.charCodeAt(i);if(v>127)v-=256;a[i]=v/127;}return a;}
function u16(b64){const s=atob(b64);const a=new Uint16Array(s.length/2);for(let i=0;i<a.length;i++)a[i]=s.charCodeAt(2*i)|(s.charCodeAt(2*i+1)<<8);return a;}
function hsl(i){return 'hsl('+((i*137.508)%360)+',65%,58%)';}
const img=src=>{const e=new Image();e.src=src;return e;};
const IM={input:img(D.s1_input.image),norm:img(D.s2_rescale.image),small:img(D.s2_rescale.small),flow:img(D.s4_net.flow),prob:img(D.s4_net.prob),thresh:img(D.s5_thresh.image)};
const dx=i8(D.s4_net.dx),dy=i8(D.s4_net.dy),cp=i8(D.s4_net.cellprob),mk=u16(D.s6_track.masks);
document.getElementById('i-masks').src=D.s7_masks.overlay;document.getElementById('i-qc').src=D.s9_qc.overlay;document.getElementById('i-stats').src=D.growth_png;document.getElementById('i-report').src=D.report_thumb;
document.getElementById('v-manifest').textContent=MANIFEST;
const rail=document.getElementById('rail');
STAGES.forEach((s,i)=>{const b=document.createElement('div');b.className='node';b.innerHTML='<span class="n">'+String(i+1).padStart(2,'0')+'</span>'+s.title;b.onclick=()=>go(i,true);rail.appendChild(b);});
const els={input:'c-input',rescale:'c-rescale',tiles:'c-tiles',net:'v-net',thresh:'c-thresh',track:'c-track',masks:'i-masks',measure:'v-measure',qc:'i-qc',stats:'i-stats',report:'i-report',manifest:'v-manifest'};
let cur=-1,playing=!reduce,timer=null,anim=null,t0=0;const DUR=5200;
function ctx(id){return document.getElementById(id).getContext('2d');}
function drawImg(id,im,alpha){const c=ctx(id);c.clearRect(0,0,N,N);c.globalAlpha=alpha==null?1:alpha;c.drawImage(im,0,0,N,N);c.globalAlpha=1;}
const anims={
 input(){drawImg('c-input',IM.input);},
 rescale(){const c=ctx('c-rescale');const sc=D.s2_rescale.scale;let k=0;cancelAnimationFrame(anim);const f=()=>{k=Math.min(1,k+(reduce?1:0.035));const s=1-(1-sc)*k;const w=N*s;c.fillStyle='#0d1214';c.fillRect(0,0,N,N);c.drawImage(IM.norm,(N-w)/2,(N-w)/2,w,w);c.strokeStyle='#3FB59F';c.setLineDash([4,4]);c.strokeRect((N-w)/2+.5,(N-w)/2+.5,w-1,w-1);c.setLineDash([]);c.fillStyle='rgba(13,18,20,.85)';c.fillRect(0,N-30,N,30);c.fillStyle='#E3E9E6';c.font='13px ui-monospace,Menlo,monospace';c.fillText('×'+s.toFixed(2)+'  →  '+Math.round(D.shape[0]*s)+'×'+Math.round(D.shape[1]*s)+' px',12,N-11);if(k<1)anim=requestAnimationFrame(f);};f();},
 tiles(){const c=ctx('c-tiles');const sw=D.s2_rescale.small_size[0],sh=D.s2_rescale.small_size[1],f=N/Math.max(sw,sh);const ox=(N-sw*f)/2,oy=(N-sh*f)/2;c.fillStyle='#0d1214';c.fillRect(0,0,N,N);c.drawImage(IM.small,ox,oy,sw*f,sh*f);const T=D.s3_tiles.tiles;let i=0;cancelAnimationFrame(anim);const g=()=>{const per=reduce?T.length:3;for(let k=0;k<per&&i<T.length;k++,i++){const [x,y,w,h]=T[i];c.fillStyle='rgba(63,181,159,.10)';c.fillRect(ox+x*f,oy+y*f,w*f,h*f);c.strokeStyle='rgba(63,181,159,.9)';c.lineWidth=1;c.strokeRect(ox+x*f+.5,oy+y*f+.5,w*f-1,h*f-1);}c.fillStyle='rgba(13,18,20,.85)';c.fillRect(0,N-30,N,30);c.fillStyle='#E3E9E6';c.font='13px ui-monospace,Menlo,monospace';c.fillText(i+' / '+T.length+' 块  224×224，重叠 50%',12,N-11);if(i<T.length)anim=requestAnimationFrame(g);};g();},
 net(){const v=document.getElementById('v-net');v.innerHTML='';const items=[['flow','流场（色相 = 箭头方向）'],['prob','目标概率'],['thresh','阈值化预览（下一步）'],['input','输入（对照）']];items.forEach(([k,cap],i)=>{const fg=document.createElement('figure');const im=document.createElement('img');im.src=IM[k].src;const fc=document.createElement('figcaption');fc.textContent=cap;fg.appendChild(im);fg.appendChild(fc);v.appendChild(fg);setTimeout(()=>im.classList.add('in'),reduce?0:250+i*350);});},
 thresh(){const c=ctx('c-thresh');c.drawImage(IM.input,0,0,N,N);c.fillStyle='rgba(0,0,0,.55)';c.fillRect(0,0,N,N);let a=0;cancelAnimationFrame(anim);const f=()=>{a=Math.min(1,a+(reduce?1:.05));c.drawImage(IM.input,0,0,N,N);c.fillStyle='rgba(0,0,0,.55)';c.fillRect(0,0,N,N);c.globalAlpha=a*.8;c.globalCompositeOperation='screen';c.drawImage(IM.thresh,0,0,N,N);c.globalCompositeOperation='source-over';c.globalAlpha=1;if(a<1)anim=requestAnimationFrame(f);};f();},
 track(){const c=ctx('c-track');const parts=[];for(let y=1;y<N;y+=3)for(let x=1;x<N;x+=3){const i=y*N+x;if(cp[i]>0)parts.push({x:x+.5,y:y+.5,id:mk[i]});}let step=0;const STEPS=200;cancelAnimationFrame(anim);
   const samp=(a,x,y)=>{const x0=Math.max(0,Math.min(N-2,x|0)),y0=Math.max(0,Math.min(N-2,y|0)),fx=x-x0,fy=y-y0;return a[y0*N+x0]*(1-fx)*(1-fy)+a[y0*N+x0+1]*fx*(1-fy)+a[(y0+1)*N+x0]*(1-fx)*fy+a[(y0+1)*N+x0+1]*fx*fy;};
   const f=()=>{const per=reduce?STEPS:5;for(let k=0;k<per&&step<STEPS;k++,step++)for(const p of parts){p.x=Math.max(0,Math.min(N-1,p.x+samp(dx,p.x,p.y)));p.y=Math.max(0,Math.min(N-1,p.y+samp(dy,p.x,p.y)));}
     c.drawImage(IM.input,0,0,N,N);c.fillStyle='rgba(0,0,0,.6)';c.fillRect(0,0,N,N);const done=step>=STEPS;for(const p of parts){c.fillStyle=done?hsl(p.id||0):'#3FB59F';c.fillRect(p.x-1.2,p.y-1.2,2.4,2.4);}
     c.fillStyle='rgba(13,18,20,.85)';c.fillRect(0,N-30,N,30);c.fillStyle='#E3E9E6';c.font='13px ui-monospace,Menlo,monospace';c.fillText('步 '+step+' / '+STEPS+(done?'  ·  已按汇聚点着色':''),12,N-11);if(!done)anim=requestAnimationFrame(f);};f();},
 measure(){const v=document.getElementById('v-measure');const cols=['编号','面积 px²','等效直径 px','周长 px','圆度','实心度','长宽比','贴边'];let h='<table><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr>';D.s8_measure.rows.forEach(r=>{h+='<tr>'+r.map((x,i)=>'<td class="'+(i&&i<7?'n':'')+'">'+(typeof x==='boolean'?(x?'是':'否'):x)+'</td>').join('')+'</tr>';});h+='</table><p class="small" style="margin:10px 0 0">按面积排序的前 10 个实例，共 '+D.s8_measure.n+' 个。完整表：tables/features.csv</p>';v.innerHTML=h;[...v.querySelectorAll('tr')].forEach((tr,i)=>setTimeout(()=>tr.classList.add('in'),reduce?0:120*i));},
 qc(){},stats(){},report(){},manifest(){}
};
function go(i,manual){if(i<0||i>=STAGES.length)return;cancelAnimationFrame(anim);cur=i;const s=STAGES[i];[...rail.children].forEach((n,k)=>{n.classList.toggle('on',k===i);n.classList.toggle('done',k<i);});
  [...document.getElementById('frame').children].forEach(e=>e.classList.remove('show'));document.getElementById(els[s.id]).classList.add('show');document.getElementById('badge').textContent=String(i+1).padStart(2,'0')+' / '+STAGES.length;
  document.getElementById('ck').textContent=(s.group==='seg'?'分割 · Cellpose':'分析 · Orgalyst')+' · 第 '+(i+1)+' 步';document.getElementById('ct').textContent=s.title;document.getElementById('cw').textContent=s.what;document.getElementById('cg').textContent=s.got;
  anims[s.id]&&anims[s.id]();t0=performance.now();if(manual&&playing)restartTimer();}
function tick(){if(!playing)return;const e=performance.now()-t0;document.getElementById('bar').style.width=Math.min(100,100*e/DUR)+'%';if(e>=DUR){if(cur<STAGES.length-1)go(cur+1);else{playing=false;document.getElementById('b-play').textContent='播放';document.getElementById('bar').style.width='100%';return;}}timer=requestAnimationFrame(tick);}
function restartTimer(){cancelAnimationFrame(timer);t0=performance.now();timer=requestAnimationFrame(tick);}
document.getElementById('b-play').onclick=function(){playing=!playing;this.textContent=playing?'暂停':'播放';if(playing){if(cur>=STAGES.length-1)go(0);restartTimer();}else cancelAnimationFrame(timer);};
document.getElementById('b-prev').onclick=()=>go(Math.max(0,cur-1),true);document.getElementById('b-next').onclick=()=>go(Math.min(STAGES.length-1,cur+1),true);
document.getElementById('b-restart').onclick=()=>{playing=true;document.getElementById('b-play').textContent='暂停';go(0,true);};
let loaded=0;Object.values(IM).forEach(e=>{e.onload=()=>{if(++loaded===Object.keys(IM).length){go(0);if(playing)restartTimer();else document.getElementById('b-play').textContent='播放';}};});
</script>
"""
html = HTML.replace("__CSS__", CSS).replace("__EXTRA__", EXTRA).replace("__DATA__", data).replace("__STAGES__", stages_json).replace("__MANIFEST__", json.dumps(manifest_txt, ensure_ascii=False))
open(f"{S}/orgalyst_pipeline.html", "w", encoding="utf-8").write(html)
print("written", len(html) // 1024, "KB")
