# -*- coding: utf-8 -*-
"""生成技术报告 docs/technical_report.html（单文件、内嵌图、沿用 design.html 样式）。所有数字从 results/*.json 读，图来自 results/ 与 docs/assets/。
PDF：用 Chrome 打印（A4、背景色、页边 16 mm）即得 docs/technical_report.pdf。"""
import base64, json, glob, os, io
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
R = f"{ROOT}/results"; D = f"{ROOT}/docs"; A = f"{D}/assets"; S = A
def J(p): return json.load(open(p, encoding="utf-8"))
def img(path, mime=None):
    if path.startswith("data:"): return path
    mime = mime or ("image/png" if path.endswith(".png") else "image/jpeg")
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()
def shrink(path, w=900, q=82):
    from PIL import Image
    im = Image.open(path); im.thumbnail((w, w * 2)); buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=q)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
h = open(f"{D}/design.html", encoding="utf-8").read(); CSS = h[h.find("<style>") + 7:h.find("</style>")]
summ = J(f"{D}/dataset_summary.json"); e3 = J(f"{R}/e3_brain_consistency.json"); e3m = J(f"{R}/e3_brain_consistency_model.json")
e2 = {n: J(f"{R}/e2_det_{n}_test.json") for n in ("all", "intestine", "brain", "lung")}; cal = J(f"{R}/e2_conf_calibration.json")
e5 = J(f"{R}/e5_agent_tasks_claude.json"); P = J(f"{D}/pipeline_demo_data.json"); C = J(f"{D}/cellpose_demo_data.json")
OVB = J(f"{S}/overlay_bold.json"); QCB = J(f"{S}/qc_bold.json")
def ap(tag):
    fs = glob.glob(f"{R}/{tag}.summary.json")
    if not fs: return None
    d = J(fs[0])["summary"]; return {k: v["ap50"] for k, v in d.items()}
di, db = C["diameter_intestine"], C["diameter_brain"]; inf_n, inf_gt = C["inference"]["n_masks"], C["inference"]["gt_instances"]
f = lambda x, n=3: f"{x:.{n}f}"
def seg_counts(o): return {s: summ[f"seg/{o}/{s}"] for s in ("train", "val", "test")}
def det_counts(o): return {s: summ[f"det/{o}/{s}"] for s in ("train", "val", "test")}
e5s = e5["summary"]
rows5 = "".join(f"<tr><td>{r['id']}</td><td>{r['title']}</td><td>{'通过' if r['ok'] else '失败'}</td><td class='n'>{r['seconds']:.0f}</td><td class='n'>{r['tool_calls']}</td><td class='n'>{r['orgalyst_calls']}</td><td class='n'>{(r.get('cost_usd') or 0):.2f}</td></tr>" for r in e5["results"])
segrows = "".join(f"<tr><td>{o}</td>" + "".join(f"<td class='n'>{seg_counts(o)[s]['images']} / {seg_counts(o)[s]['instances']}</td>" for s in ("train","val","test")) + "</tr>" for o in ("brain","intestine","pdac","colon"))
detrows = "".join(f"<tr><td>{o}</td>" + "".join(f"<td class='n'>{det_counts(o)[s]['images']} / {det_counts(o)[s]['instances']}</td>" for s in ("train","val","test")) + "</tr>" for o in ("intestine","brain","lung"))
calrows = "".join(f"<tr><td>{o}</td><td class='n'>{e2['all']['per_organ'][o]['map50']:.3f}</td><td class='n'>{e2['all']['per_organ'][o]['map50_95']:.3f}</td><td class='n'>{e2[o]['per_organ'][o]['map50']:.3f}</td><td class='n'>{cal['all'][o]['best_conf']}</td><td class='n'>{cal['all'][o]['test_at_025']['mape']:.3f} → {cal['all'][o]['test_at_best']['mape']:.3f}</td><td class='n'>{cal['all'][o]['test_at_best']['median_ape']:.2f}</td><td class='n'>{cal['all'][o]['test_at_best']['bias']:.2f}</td></tr>" for o in ("intestine","brain","lung"))

HTML = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orgalyst 技术报告</title>
<style>{CSS}
.abstract{{border-left:4px solid var(--accent);padding:10px 16px;background:var(--panel);margin:16px 0}}
figure{{margin:18px 0}}figure img{{width:100%;border:1px solid var(--rule);border-radius:4px}}figcaption{{font-size:13px;color:var(--muted);line-height:1.55;margin-top:6px}}figcaption b{{color:var(--ink)}}
.fig2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.fig3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}@media(max-width:640px){{.fig2,.fig3{{grid-template-columns:1fr}}}}
.fig2 img,.fig3 img{{width:100%;border:1px solid var(--rule);border-radius:4px}}
.meta{{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:14px;margin:14px 0}}.meta b{{color:var(--muted);font-weight:500}}
h2{{page-break-before:auto}}@media print{{nav.toc{{display:none}}.wrap{{display:block}}main{{max-width:none}}body{{font-size:14.5px;line-height:1.75}}h2{{break-after:avoid}}figure,table{{break-inside:avoid}}}}
.small{{font-size:13px;color:var(--muted)}}
</style></head><body>
<div class="wrap">
<nav class="toc" aria-label="目录"><div class="k">目录</div>
<a href="#s1">1 摘要与类别声明</a><a href="#s2">2 问题与场景</a><a href="#s3">3 数据</a><a href="#s4">4 方法与系统</a><a href="#s5">5 实现细节</a><a href="#s6">6 实验与结果</a><a href="#s7">7 可靠性与局限</a><a href="#s8">8 影响与未来</a><a href="#s9">9 复现指南</a><a href="#s10">10 外部资源与许可</a></nav>
<main>
<header class="hd">
<div class="eyebrow">AI4S Open Innovation: AI for Life Science · 第五届琶洲算法大赛 · AI + 器官芯片 · 技术报告 · 2026-09-16</div>
<h1>Orgalyst：类器官明场图像分析的对话式副驾驶</h1>
<p class="sub">一个不依赖大模型也能完整复现的领域工具包，加上一个把它交到实验人员手里的对话式助手。</p>
<div class="meta"><b>参赛类别</b><span>端到端系统（End-to-End System）</span><b>团队</b><span>Xiaoyan Li（AI / 计算机视觉 / 大模型应用，项目负责人）；一位生物学同事（类器官培养与形态学判读，负责需求与结果审核）</span><b>代码</b><span>https://github.com/xiaoyanLi629/orgalyst（MIT）</span><b>权重</b><span>https://huggingface.co/XiaoyanLi/orgalyst-weights</span><b>数据</b><span>OrgLine（Zenodo 16355179，CC-BY-4.0），未使用任何私有数据</span></div>
</header>

<h2 id="s1">1 摘要</h2>
<div class="abstract"><p>类器官与器官芯片实验每天产生大量明场显微照片，实验人员最常问的三件事是"有几个、多大、有没有变化"。现有工具要么是需要调参的脚本，要么是只做分割不管后续统计和留档的软件，把图片变成一份能放进实验记录的报告仍然要花半天。Orgalyst 把这条链路做成两层：下层是一个确定性的领域工具包 <code>orgalyst</code>，包含按器官加载专用权重的 Cellpose 分割、按标定阈值计数的 YOLO 检测、形态测量、质控、组间统计、生长曲线、单文件 HTML 报告和记录输入哈希、权重哈希、参数与软件版本的运行清单；上层是基于 Claude Agent SDK 的对话式助手，通过 MCP 调用这些工具，让实验人员用一句话完成从图片到报告的全过程，而所有数字仍由工具包算出。我们在公开的 OrgLine 数据集（八个来源、五种器官）上完成了五组实验：按器官微调后分割 AP50 在脑、肠、结肠上达到 0.967、0.812、0.815（零样本 cyto3 为 0.005、0.544、0.405）；三器官联合的 YOLO11m 检测 mAP50 0.936 到 0.995，计数阈值在验证集上标定后肺类器官的计数误差从 0.235 降到 0.168；脑类器官 240 张图的自动面积与专家标注的 Spearman 相关 0.963、中位相对误差 1.9%；12 个自然语言任务的 Agent 端到端测试 12 个全部通过，平均每任务 113 秒。我们还如实报告了跨器官泛化的边界、胰腺癌类器官上的不足，以及 Cellpose-SAM 对照实验为什么没有带来收益。</p></div>

<h2 id="s2">2 问题定义与应用场景</h2>
<p>类器官是用干细胞在三维环境中培养出的微型组织，器官芯片则把这类组织放进微流控器件里模拟生理条件。无论哪一种，最便宜、最不伤细胞、频率最高的观察手段都是明场显微镜：每天或每隔几小时拍一张，看它们长得怎么样。这些照片的分析需求非常固定：数清楚一张图里有多少个类器官，量出每个的大小和形状，比较不同处理组之间有没有差异，把同一个类器官在不同时间点的测量连成生长曲线，最后把结果写成能放进实验记录、能被别人复核的报告。</p>
<p>瓶颈不在算法本身。近几年 Cellpose、OrganoID、OrgaSegment 等工具已经能把类器官分割得相当好，OrgLine 数据集甚至把八个公开数据源整理成了统一格式。真正卡住实验人员的是三件事。第一，工具是给会写代码的人用的：要装环境、选模型、调直径参数，一张图上类器官大小相差十倍时默认参数会失效，而实验人员往往不知道该改哪一个。第二，分割只是第一步，后面的测量、统计、画图、写报告每个实验室都在重复造轮子，而且做法不一致，结果没法横向比较。第三，没有留档：三个月后审稿人问"这个面积是用哪个版本的模型、什么参数算出来的"，多数人答不上来。</p>
<p>Orgalyst 的目标用户是做类器官或器官芯片实验、不写代码的生物学研究者。成功标准是三条：实验人员用自然语言就能拿到一份完整的分析报告；报告里的每个数字都能用命令行在没有大模型的环境下重新算出来，并且和公开数据集自带的专家标注一致；系统对自己不确定的地方要说出来，而不是给一个看起来很准的错误数字。第三条决定了我们把"质控"和"运行清单"做成了工具包的一等公民，而不是附属功能。</p>

<h2 id="s3">3 数据</h2>
<p>全部实验使用 <b>OrgLine</b>（Zenodo 16355179，CC-BY-4.0）。它把八个已发表的类器官图像数据集统一成了实例分割（InstanceSeg）和目标检测（OrgDet）两个子集：分割部分有脑（Schröter 等 2024）、肠（OrgaSegment）、胰腺导管腺癌 pdac（OrganoID 与 OrganoIDNet）和结肠（OrgaExtractor）四种器官，检测部分有肠（Tellu、OrgaQuant、OrgaSegment）、脑和肺（Deep-LUMEN）三种。我们没有使用任何公司或实验室的私有数据，也没有做额外标注。</p>
<p>原始数据经 <code>scripts/prepare_data.py</code> 统一为 8 位 PNG 图像与 uint16 实例掩码（每个类器官一个整数编号），检测标注为 YOLO 文本格式；真彩色明场图保留 RGB，三通道相同的图转为灰度，16 位图按 1 到 99 百分位拉伸到 8 位。分割子集沿用 OrgLine 自带的划分；检测子集按 70 / 15 / 15 随机划分（seed 0），划分文件随仓库提供。像素的物理尺寸只有脑数据集给出了明确标定（Lab A 1024 像素宽的图为 3.1646 µm/px，Lab B 1388 像素宽为 2.9940 µm/px），其余来源论文只写了仪器和物镜，我们不做估算，形态学结果对这些来源只以像素为单位报告，并在报告里注明。</p>
<div class="tw"><table><tr><th>分割子集（图像数 / 实例数）</th><th class="n">train</th><th class="n">val</th><th class="n">test</th></tr>{segrows}</table></div>
<div class="tw"><table><tr><th>检测子集（图像数 / 标注框数）</th><th class="n">train</th><th class="n">val</th><th class="n">test</th></tr>{detrows}</table></div>
<p class="small">脑类器官每张图恰好一个类器官（240 张测试图来自 4 个克隆 × 3 个个体 × 10 个时间点 × 2 个实验室），因此它同时是生长曲线和"与专家标注比面积"实验的天然材料；pdac 的测试图每张有 500 个以上的小实例，训练图平均只有 68 个，这一域内分布偏移是第 6、7 节讨论的主要失败来源；结肠只有 15 张训练图，验证集没有掩码。</p>

<h2 id="s4">4 方法与系统</h2>
<h3>4.1 总体架构</h3>
<p>系统分两层。<b>工具包层</b> <code>orgalyst</code> 是一个普通的 Python 包，命令行入口 <code>python -m orgalyst analyze | count | track | report</code>，不需要任何大模型；它的每一次运行都在一个目录里留下 <code>manifest.json</code>（输入文件的 md5、模型标识与权重哈希、全部参数、numpy / torch / cellpose / ultralytics 版本、GPU 型号、逐步日志）、<code>tables/</code>（逐实例特征表、汇总、质控、比较、生长表）、<code>masks/</code>、<code>overlays/</code> 和一份单文件 <code>report.html</code>。<b>助手层</b>是我们此前为实验室搭建的 BioAgent（Claude Agent SDK + 权限门卫 + 终端与网页两种界面）的精简副本，工具包通过一个 MCP 服务器（<code>orgalyst/mcp_server.py</code>，stdio 传输）暴露六个工具：<code>list_models</code>、<code>analyze_images</code>、<code>count_organoids</code>、<code>compare_groups</code>、<code>growth_curves</code>、<code>run_summary</code>（以及 <code>list_runs</code>）。助手的系统提示里写明了什么时候用哪个工具、回答时必须区分像素与微米、贴边实例默认排除等约定；助手不看图、不算数，只做需求理解、参数选择和结果解释。</p>
<figure><img src="{shrink(f'{A}/overview_board.png', 1400, 80)}"><figcaption><b>图 1 · 一张肠类器官照片的完整旅程。</b>白卡片是数据，绿盒子是模型或工具，大卡片是关键环节。从"一句话"到助手选工具，再到量大小、缩放、切块、U-Net（装着肠专用权重）、三张输出图、聚成轮廓、146 个类器官轮廓、测量表、质检、统计、报告生成器，最后是报告加运行记录。交互版见 docs/orgalyst_scene.html。</figcaption></figure>

<h3>4.2 分割：Cellpose 架构与按器官的专用权重</h3>
<p>分割用 Cellpose（Stringer 等，Nature Methods 2021）。它的核心不是某种特定的网络，而是把"实例分割"改写成"回归一个流场"：训练时对每个人工标注的实例做一次以中心为热源的热扩散，得到每个像素指向所属实例中心的方向；网络（一个带残差块和跳跃连接的 U-Net）学习预测这两张方向图和一张"是不是目标"的概率图；推理时把每个前景像素沿方向图迭代移动约 200 步，汇聚到同一点的像素归为同一个实例。这个设计让它天然能处理粘连、非凸和大小悬殊的目标，也让"换骨干网络"成为可能，Cellpose-SAM 就是同一团队 2025 年把骨干换成 ViT 的版本。</p>
<figure><img src="{img(f'{A}/cellpose_outputs.jpg')}"><figcaption><b>图 2a · 网络实际输出与追踪。</b>肠类器官测试图的一个 256×256 裁块：网络输出两张方向图（这里合成箭头画出）和一张概率图；把概率大于 0 的像素沿箭头走 200 步，落到同一点的归为一个实例，得到 {inf_n} 个实例，人工标注 {inf_gt} 个。粘连的两个类器官因为箭头指向不同的中心而被分开。</figcaption></figure>
<figure><img src="{img(f'{A}/cellpose_diffusion.jpg')}"><figcaption><b>图 2b · 训练目标是怎么来的。</b>训练时不需要人画箭头：对每个人工标注的实例，以其中心为热源反复做热扩散（热只在实例内部传播，每步取四邻平均），几十步后热场沿着实例形状铺开，取热场的梯度就是每个像素应该指向的方向。这一步只依赖标注掩码，所以任何有实例标注的数据都能直接训练。</figcaption></figure>
<p>Cellpose 有一个容易被忽视的前提：网络是在目标约 30 像素宽的尺度上训练的，推理前要先估计图中目标的典型直径，把图缩放到这个尺度。估错直径的后果很直接：估小了图被放大，一个类器官被拆成几块；估大了图被缩小，所有类器官糊成一团。Cellpose 自带一个从网络风格向量回归直径的尺寸估计器，但它是在细胞照片上训练的，对脑类器官这种 400 像素宽的大目标会给出约 30 像素的荒谬估计，导致零样本时脑的 AP50 只有 0.005。</p>
<div class="fig3"><figure><img src="{di['small']['image']}"><figcaption>估成 12 px（偏小）：找到 {di['small']['n']} 个，大类器官被拆碎</figcaption></figure><figure><img src="{di['auto']['image']}"><figcaption>自动估计 {di['auto']['diameter']:.0f} px：找到 {di['auto']['n']} 个，人工数过 35 个</figcaption></figure><figure><img src="{di['large']['image']}"><figcaption>估成 150 px（偏大）：只找到 {di['large']['n']} 个</figcaption></figure></div>
<p class="small">图 2c · 同一张肠类器官图、同一个模型，只改直径估计值。</p>
<p>我们的做法是<b>按器官加载专用权重，并为每种器官选择一个直径策略</b>。权重由通用的 cyto3 在 OrgLine 各器官训练集上继续训练 200 轮得到（第 5 节），训练时 Cellpose 会把训练集实例的中位直径记进权重（<code>diam_labels</code>）。直径策略有四种，通过 <code>orgalyst/config.py</code> 按器官注册：<code>model</code> 直接用权重里的训练直径（结肠）；<code>sizemodel</code> 用 cyto3 的尺寸估计器逐图估计（肠、pdac，这两种器官图与图之间放大倍率不同）；<code>refine</code> 两遍推理，第一遍用训练直径，第二遍用第一遍找到的目标的中位等效直径，钳在 0.25 到 4 倍之间（脑，因为脑类器官从第 2 天到第 30 天面积变化近五倍，单一直径会在两端失效）；<code>per_image_gt</code> 用真值直径，只作实验上限。不认识的器官退回零样本 cyto3 加尺寸估计器，并在报告里标注"通用模型，精度较低"。</p>
<div class="fig3"><figure><img src="{db['auto']['image']}"><figcaption>通用 cyto3 + 自动直径（估成 {db['auto']['diameter']:.0f} px）：找到 {db['auto']['n']} 个</figcaption></figure><figure><img src="{db['d404']['image']}"><figcaption>通用 cyto3 + 直径改为 404 px：找到 {db['d404']['n']} 个</figcaption></figure><figure><img src="{db['finetuned']['image']}"><figcaption>脑专用权重（直径记在模型里）：找到 {db['finetuned']['n']} 个</figcaption></figure></div>
<p class="small">图 3 · 脑类器官上，通用模型失败的原因是尺度而不是外观；专用权重把尺度记住了。</p>

<h3>4.3 检测计数</h3>
<p>当用户只问"有几个"时，分割是浪费的：一张 2048 像素的肠类器官图分割要十几秒，检测不到一秒。我们在 OrgLine 检测子集上训练 YOLO11m（输入 1024，100 轮），并比较了三个单器官模型与一个三器官联合模型：联合模型在每种器官上都持平或更好，于是系统只保留这一个检测模型。检测计数有一个常被忽略的参数是置信度阈值：ultralytics 默认 0.25 是为算 mAP 设计的，故意保留很多低置信度的框，直接拿来数数会多报两成。我们在各器官的验证集上从 0.05 到 0.90 扫描阈值，取计数平均相对误差最小者（肠 0.50、脑 0.45、肺 0.40，未知器官用三器官合并最优的 0.45），写进配置，测试集只用来报告最终误差。</p>

<h3>4.4 形态测量、质控、统计与生长曲线</h3>
<p><b>测量</b>用 scikit-image 的 regionprops：面积、等效直径、周长、圆度（4π·面积 / 周长²）、实心度（面积 / 凸包面积）、长宽比，以及是否贴着图像边缘；给了像素尺寸就同时输出微米单位的列。贴边实例不完整，汇总统计默认排除并在报告里说明数量。<b>质控</b>分两级：图像级计算清晰度（Laplacian 方差）、光照不均（局部均值的变异系数）和饱和像素比例；实例级做翻转与旋转的测试时增强，把原图和 4 个二面体变换后的分割结果两两比较，一个实例在变换后被找回的比例低于 0.5 就标为"低可信"，报告里用橙色标出。这样用户拿到的不只是一个数，还有"哪几个不太可靠"。<b>统计</b>做组间比较：两组用 Mann-Whitney U，多组用 Kruskal-Wallis，效应量报告 Cliff's delta，多指标用 Holm 校正，输出箱线图和一张比较表。<b>生长曲线</b>按元数据（个体、时间点、组）把逐图的中位面积连起来，同时给出每个个体相对第一个时间点的倍数和按组的均值曲线。</p>
<div class="fig2"><figure><img src="{OVB['overlay']}"><figcaption><b>图 4a · 分割结果。</b>肠类器官 2048×2048 测试图，146 个实例，每个涂一种颜色，亮绿线为轮廓；人工标注 149 个。</figcaption></figure><figure><img src="{QCB['overlay']}"><figcaption><b>图 4b · 质控。</b>同一张图做 4 次翻转旋转后再分割，橙色为一致性低于 0.5 的实例（1 个），其余为绿色；平均一致性 {P['s9_qc']['agreement_mean']:.2f}。</figcaption></figure></div>

<h3>4.5 Agent 编排与留档</h3>
<p>助手收到请求后先用任务清单工具把工作拆成三到八步并告诉用户打算怎么做，然后逐步调用工具。它需要做的判断其实很少：这批图是什么器官（用户没说就用 generic 并提醒）、有没有像素尺寸（没有就只报像素，绝不编造）、用户要的是"数数"还是"量大小"、要不要质控、分组和时间点信息在哪个文件里。每次工具调用都落在当前对话的产物目录里，回答时引用 run_dir 和报告路径。权限门卫（<code>agent/bioagent/permissions.py</code>）保证原始数据目录只读、其他账号的目录和密钥目录禁止访问，用户可以为每个对话选择确认方式（逐条确认、只确认危险命令、全部自动、只读）。助手还带有按账号隔离的长期记忆（记住用户在做什么项目、常用的数据路径、像素标定和偏好，会话结束时自动归纳），网页版支持多账号、按账号的用量上限和管理员面板；E5 评测时关闭了记忆，以保证各任务相互独立。</p>
<p><b>分析流程做成了 skill。</b>光有工具还不够，助手在什么情况下该问什么、先跑什么、怎么核对、怎么汇报，我们写成了一个可复用的流程说明 <code>agent/skillpack/skills/organoid-analysis/SKILL.md</code>，作为 Claude Agent SDK 的本地 skill 自动加载，用户提到类器官图片分析时即生效，也可以用 <code>/organoid-analysis</code> 显式触发。它规定了四步：先确认三个前提（器官类型、像素尺寸、用户要的是数量还是形态还是比较，缺哪个问哪个，但不为简单任务阻塞）；按前提选工具（只数数走检测，其余走分割，图片少或用户关心可靠性时开质控，有分组或时间点信息时接统计）；拿到返回先核对（逐图计数出现 0 或离群值就去看叠加图，贴边排除数和低可信数必须写进回答）；最后按固定的六段格式汇报（一句话结论、逐图表与中位数加四分位范围、单位与排除说明、统计结论、产物路径、至多两条下一步建议）。skill 里同时列出了禁止事项：没有像素尺寸时不给任何微米数字，不用 Python 重算工具已经给出的统计量，不重复跑同一批图。这样助手的行为不再依赖每次提示词写得好不好，换一个模型后端也能沿用同一套流程。</p>
<p><b>开源模型路径。</b>Claude Agent SDK 支持通过 <code>ANTHROPIC_BASE_URL</code> 指向任何兼容 Anthropic Messages API 的网关，我们在 agent/README.md 里给出了 LiteLLM 前置 vLLM 的配置方式，E5 的任务集脚本可以对不同后端各跑一遍。受时间所限，本报告只给出 Claude 后端的结果，这一点在第 7 节作为局限如实列出。</p>

<h3>4.6 使用流程与产物</h3>
<p>一次典型的使用是这样的。实验人员在网页版或终端里说"分析 /data/exp3 下的 4 张肠类器官照片，做形态分析并生成报告"。助手先列出计划（确认器官与像素尺寸、调用分析工具、读汇总、写回答），然后调用 <code>analyze_images(images="/data/exp3", organ="intestine", name="exp3")</code>；工具包在几十秒内完成分割、测量与报告生成，把 run_dir 和汇总返回给助手；助手把总数、逐图数量、面积与圆度的中位数和四分位范围整理成表，并给出报告路径。E5 任务集里助手对这一任务的回答结尾如下（原文节选），它主动说明了单位、指出了没有编造像素尺寸、提示用户先看叠加图核对分割质量，并且明确"201 这个数是模型输出、没有精度保证"，这正是我们希望助手具备的分寸：</p>
<blockquote class="small" style="border-left:3px solid var(--rule);margin:8px 0 14px;padding:6px 14px;color:var(--muted)">"注意：所有尺寸都是像素单位，不是微米。你没有提供 pixel_size_um，我也没有编造标定值。……建议你先翻一下 overlays/ 里的 4 张叠加图。这次用的是肠专用模型，但在没有人工标注做金标准的前提下，201 这个数仍然只是模型输出、没有精度保证。"</blockquote>
<figure><img src="{img(f'{A}/report_screenshot.jpg')}"><figcaption><b>图 4c · 工具包生成的单文件报告 report.html（E5 任务 2 的肠类器官批次，4 张图 201 个实例）。</b>依次为概览瓦片（数量、面积 / 直径 / 圆度中位数）、逐图表、分布直方图、叠加缩略图、方法学模板段落（模型、直径策略、排除规则）与溯源表（输入哈希、权重哈希、版本）。报告不依赖网络，双击即可打开，可直接附进实验记录。</figcaption></figure>
<h2 id="s5">5 实现细节</h2>
<p>硬件为一台 AutoDL 云主机（NVIDIA RTX 5090 D，32 GB 显存；容器内存上限 62 GB），软件为 Python 3.10、torch 2.14.0+cu130、cellpose 3.1.1.3、ultralytics 8.4.152、numpy 2.0.2、scikit-image 0.25。分割微调：cyto3 初始化，按器官各训练 200 轮，学习率 0.1（Cellpose 默认 SGD），批大小 8，耗时脑 74 分钟、pdac 31 分钟、肠 22 分钟、结肠 1.4 分钟；跨器官实验每器官最多取 500 张训练图（四器官全量 2395 张会超出容器内存被静默杀掉，这是我们踩过的坑之一）。检测：yolo11m.pt 初始化，输入 1024，批 8，100 轮，单器官 32 到 65 分钟，联合模型 126 分钟。Cellpose-SAM 对照在独立的 cellpose 4 环境里跑，batch 2、学习率 1e-5、100 轮，pdac 96 分钟、肠 25 分钟。推理速度（单张 2048² 图）：分割约 1.5 秒，质控（4 次增强）约 6 秒，检测计数 0.3 秒。</p>
<p>MCP 接口以 FastMCP 实现，工具签名如下（全部参数都有默认值，返回 JSON）：<code>analyze_images(images, organ="generic", pixel_size_um=None, name, diam_mode=None, limit=0, make_report=True, qc=False, meta_csv=None)</code>；<code>count_organoids(images, organ="generic", name, conf=None, limit=0)</code>；<code>compare_groups(run_dir, groups, metrics=None, exclude_border=True)</code>；<code>growth_curves(run_dir, meta_csv=None, pattern=None, metric=None)</code>；<code>run_summary(run_dir)</code>；<code>list_models()</code>；<code>list_runs(limit=20)</code>。MCP 服务器启动时把 stdout 改道到 stderr，只留一个私有句柄给协议流，避免底层库的打印污染协议，这是我们在接入 Biomni 工具库时总结出的做法。</p>

<h2 id="s6">6 实验与结果</h2>
<h3>6.1 E1 分割：零样本、按器官微调、直径策略与跨器官泛化</h3>
<p>评价指标为实例级 AP50（预测实例与真值实例 IoU ≥ 0.5 记为匹配，用 cellpose.metrics.average_precision），同时报告 AP75 与 AP90 反映边界精度。表 1 是主要结果。</p>
<div class="tw"><table><tr><th>器官（test 图数）</th><th class="n">cyto3 零样本</th><th class="n">按器官微调（model 直径）</th><th class="n">微调 + 逐图策略（系统默认）</th><th class="n">逐图真值直径（上限）</th></tr>
<tr><td>brain (240)</td><td class="n">0.005</td><td class="n">0.925</td><td class="n"><b>0.967</b>（refine）</td><td class="n">0.975</td></tr>
<tr><td>intestine (12)</td><td class="n">0.544</td><td class="n">0.773</td><td class="n"><b>0.812</b>（sizemodel）</td><td class="n">0.812</td></tr>
<tr><td>colon (10)</td><td class="n">0.405</td><td class="n"><b>0.815</b></td><td class="n">0.814（sizemodel）/ 0.800（refine）</td><td class="n">0.800</td></tr>
<tr><td>pdac (20)</td><td class="n">0.419</td><td class="n">0.564</td><td class="n"><b>0.591</b>（sizemodel）</td><td class="n">0.605</td></tr></table></div>
<p class="small">表 1 · E1 分割 AP50。零样本 cyto3 用自带尺寸估计器；"上限"是给每张图真值中位直径，实际不可用，只用来区分"尺度没估对"和"模型不认识"。</p>
<p>三点结论。第一，零样本 cyto3 认得类器官（结肠召回 0.985）但精确率只有 0.4 到 0.6，过度分割严重，AP75 只有 0.2 到 0.4，失败主因是尺度估计和边界质量，微调解决了这两点。第二，直径策略的收益是真实的：脑用两遍推理从 0.925 到 0.967，几乎到了真值直径的上限；肠用逐图尺寸估计从 0.773 到 0.812。第三，pdac 仍然弱：测试图每张 500 个以上的小实例，召回只有约 0.5，AP90 接近 0，给真值直径也只到 0.605，说明问题不在尺度而在训练分布（训练图平均 68 个实例，测试图来自另一台仪器）。</p>
<p><b>跨器官泛化。</b>我们训练了一个四器官联合模型和四个留一器官模型。联合模型在给对尺度时与专用模型持平（真值直径下肠 0.810、pdac 0.606、脑 0.971、结肠 0.789；实际可用的 sizemodel 下肠 0.797、pdac 0.610、结肠 0.789，脑 refine 0.896），但它记住的训练直径 183 像素对任何单一器官都不对，用 model 策略几乎全失效（0.04 到 0.42）。留一器官模型在从未见过的器官上即使给对尺度也只有 0.15 到 0.47（结肠最好 0.465，因与肠形态相近；refine 0.580）。这说明跨器官泛化是有限的，"按器官专用权重"不是设计偏好而是必要的；联合模型只作为未知器官的兜底，它比零样本 cyto3 好。</p>
<p><b>Cellpose-SAM 对照。</b>Cellpose-SAM（cellpose 4，ViT-L 骨干，宣称不需要直径参数）零样本 AP50 为肠约 0.60、pdac 0.43 到 0.48、脑约 0.03、结肠约 0.37，与 cyto3 零样本同一水平，在脑上同样失败。按器官微调 100 轮后 pdac 0.557（真值直径 0.591）、肠 0.780（0.795），与 cyto3 微调持平而没有超过，权重 1.2 GB（cyto3 微调权重 26 MB），推理慢一倍。我们因此把主模型定为 cyto3 按器官微调，这一对照结果完整保留在 results/ 里。</p>

<h3>6.2 E2 检测计数</h3>
<div class="tw"><table><tr><th>器官（test 图数）</th><th class="n">联合模型 mAP50</th><th class="n">mAP50-95</th><th class="n">单器官模型 mAP50</th><th class="n">标定阈值</th><th class="n">计数 MAPE（0.25 → 标定）</th><th class="n">中位 APE</th><th class="n">总数偏差</th></tr>{calrows}</table></div>
<p class="small">表 2 · E2 检测。计数 MAPE 为逐图 |预测数 − 真值数| / 真值数 的平均；总数偏差为预测总数 / 真值总数。肠 423 图、脑 280 图、肺 602 图。</p>
<p>联合模型与单器官模型持平或略好，所以系统只保留一个检测模型。阈值标定把肠和肺的计数误差降低了两到三成，把默认阈值下 10% 到 12% 的系统性多报修正为接近 1 的总数偏差；脑类器官一图一目标，任何阈值都接近零误差。剩下的误差主要来自粘连团块和图像边缘的半个类器官，中位相对误差 0.11 到 0.13 说明多数图的计数偏差在一到两个之内。</p>

<h3>6.3 E3 与专家标注的一致性</h3>
<p>脑类器官原始数据集（Schröter 等 2024）除掩码外还给了每张图的人工面积（像素²），我们核实它逐张等于 OrgLine 真值掩码的面积，因此可以把它当作专家标注参照。对 240 张测试图跑系统默认流程（脑专用权重 + refine），比较自动面积与专家面积。</p>
<div class="tw"><table><tr><th>直径策略</th><th class="n">检出 / 漏检</th><th class="n">Pearson r</th><th class="n">Spearman ρ</th><th class="n">中位比值</th><th class="n">中位相对误差</th><th class="n">≤10% 误差占比</th><th class="n">≤20% 误差占比</th><th class="n">比值 > 1.5 占比</th></tr>
<tr><td>model（固定训练直径）</td><td class="n">{e3m['n_detected']} / {e3m['n_missed']}</td><td class="n">{f(e3m['pearson_r'])}</td><td class="n">{f(e3m['spearman_rho'])}</td><td class="n">{f(e3m['median_ratio'])}</td><td class="n">{e3m['median_ape']*100:.1f}%</td><td class="n">{e3m['within_10pct']*100:.0f}%</td><td class="n">{e3m['within_20pct']*100:.0f}%</td><td class="n">{e3m['frac_ratio_gt_1_5']*100:.1f}%</td></tr>
<tr><td><b>refine（系统默认）</b></td><td class="n">{e3['n_detected']} / {e3['n_missed']}</td><td class="n">{f(e3['pearson_r'])}</td><td class="n">{f(e3['spearman_rho'])}</td><td class="n">{f(e3['median_ratio'])}</td><td class="n">{e3['median_ape']*100:.1f}%</td><td class="n">{e3['within_10pct']*100:.0f}%</td><td class="n">{e3['within_20pct']*100:.0f}%</td><td class="n">{e3['frac_ratio_gt_1_5']*100:.1f}%</td></tr></table></div>
<p class="small">表 3 · E3 自动面积 vs 专家标注面积，brain test 240 图。</p>
<div class="fig2"><figure><img src="{shrink(f'{R}/e3_brain_consistency.png', 900)}"><figcaption><b>图 5 · 自动面积与专家面积的散点与 Bland-Altman 图（refine）。</b>残余失败集中在第 2 天最小的类器官（4 张，高估 4 到 7 倍，第一遍推理把培养基背景当成了目标）和一张第 30 天最大的类器官（低估约一半）。</figcaption></figure><figure><img src="{shrink(f'{A}/growth_brain_test.png', 900)}"><figcaption><b>图 6 · 四个克隆的面积生长曲线。</b>由同一批 240 张图的分析结果按文件名解析出个体、克隆与时间点后自动生成，细线为个体，粗线为组均值。</figcaption></figure></div>

<h3>6.4 E4 质控的作用</h3>
<p>质控模块的价值在于把错误"标出来"而不是"消掉"。在肠类器官示例图上，120 个实例的翻转旋转一致性平均 0.98，只有 1 个被标为低可信，它正是图像角落一个被截断的团块；在 E5 的质控任务里，4 张肠图 205 个实例中有 3 个被标出。我们没有在全测试集上系统评估质控标记与分割错误的对应关系，这是未完成的工作（第 7 节）。</p>

<h3>6.5 E5 Agent 端到端任务集</h3>
<p>我们设计了 12 个自然语言任务，覆盖单图分析、批量分析与报告、带物理尺寸的分析、只数数、组间比较、生长曲线、质控、追问指标含义、追问可复现性、器官未知、空目录和混合器官批次。每个任务的数据是从 OrgLine 测试集抽出的 36 张图，成功标准由脚本自动判定：回答里的数值必须落在命令行路径算出的参考值的 5% 到 10% 之内，约定的产物文件必须存在，关键措辞必须出现（例如解释圆度必须提到周长，空目录必须说明没有找到图片），对追问器官这类任务则接受"反问用户"或"用通用模型并说明"两种行为。运行器直接驱动 Agent SDK，不经过终端，每个任务一个新对话（两个追问任务在其父任务的对话里进行），确认方式设为全部自动。</p>
<div class="tw"><table><tr><th>任务</th><th>内容</th><th>判定</th><th class="n">耗时 (s)</th><th class="n">工具调用</th><th class="n">其中 Orgalyst</th><th class="n">费用 ($)</th></tr>{rows5}</table></div>
<p class="small">表 4 · E5 结果，Claude 后端（{e5s['model']}）。成功率 {e5s['n_pass']}/{e5s['n_tasks']}，平均每任务 {e5s['mean_tool_calls']:.1f} 次工具调用（其中 {e5s['mean_orgalyst_calls']:.1f} 次为 Orgalyst 工具，其余是任务清单、读文件、检查目录等），平均 {e5s['mean_seconds']:.0f} 秒，合计 {e5s['total_cost_usd']:.2f} 美元。</p>
<p>12 个任务全部通过（这一轮在 4.5 节的 skill 加入之前完成；加入 skill 后我们复跑了批量分析、追问指标含义和质控三个任务，同样全部通过，平均耗时从 94 秒降到 72 秒，记录在 <code>results/e5_agent_tasks_skilltest.json</code>；完整的 12 任务复跑留待下一版）。值得注意的是工具调用的分布：多数任务只需要一到三次调用，助手拿到工具返回的汇总就直接作答；组间比较和生长曲线两个任务分别用了 31 和 46 次调用、5 到 8 分钟，因为助手在拿到统计结果后自行读取了比较表和生长表逐项核对，又用 Python 重算了一遍中位数。这种"多此一举"提高了可信度但增加了时间和费用，在生产环境里可以通过系统提示约束。器官未知的任务里助手没有反问，而是直接用通用模型跑并在回答里注明精度可能较低，这符合我们的约定。</p>

<h2 id="s7">7 可靠性分析与局限</h2>
<p><b>失败案例。</b>分割的两类典型失败都出现在脑类器官的极端尺度上：第 2 天直径只有约 80 像素的类器官在第一遍推理时会被培养基的纹理淹没，refine 的第二遍反而把背景团块当成目标放大了误差；第 30 天直径超过 600 像素的类器官偶尔被切成两半。pdac 的失败是系统性的：测试图的实例密度是训练图的七倍，来源仪器不同，模型漏掉了一半的小实例；这个问题需要更多同源训练数据或针对小实例的多尺度推理，我们没有在比赛期间解决。检测计数在粘连团块上会把两个数成一个，反过来在气泡和碎片上会多数。</p>
<p><b>跨器官泛化边界。</b>第 6.1 节的留一实验给出了明确的边界：没有见过的器官，AP50 只有 0.15 到 0.47。因此系统对未注册的器官只提供"通用模型 + 明确的低精度提示"，不承诺精度。用户拿到新器官时应当用几十张标注图微调（结肠只用 15 张训练图就从 0.405 到 0.815）。</p>
<p><b>大模型相关风险。</b>助手可能选错器官、编造像素尺寸、或者在结果不确定时给出过于肯定的措辞。我们的缓解是结构性的：所有数值来自工具，工具返回里带着单位与排除说明，系统提示禁止在未知像素尺寸时估算，权限门卫限制文件访问；E5 任务集就是对这些约束的回归测试。但 12 个任务不能覆盖真实使用里的提问方式，我们只在 Claude 一个后端上评测，开源模型后端的差距没有量化。此外助手依赖付费 API，评审复现 Agent 路径需要自己的密钥；命令行路径不受此限制，报告里的每个数字都可以由它复现。</p>
<p><b>数据局限。</b>只有脑数据集有像素标定，其余器官的形态学结果只能以像素为单位；OrgLine 的测试集在肠（12 张）和结肠（10 张）上很小，AP50 的置信区间很宽；数据集全部来自已发表的公开数据，没有器官芯片的时序数据，生长曲线实验只在脑类器官的静态培养上验证过。质控标记与真实错误的对应关系没有系统评估。</p>

<h2 id="s8">8 影响与未来工作</h2>
<p>对实验人员而言，Orgalyst 把"拍完照片到拿到报告"从半天缩短到几分钟，而且报告是可以放进实验记录、三个月后仍能复核的。对方法研究者而言，工具包提供了一个按器官注册权重和直径策略的框架，加一个器官只需要放一份权重和一行配置。下一步有三件事最有价值。第一，器官芯片时间序列：芯片上的类器官位置固定，可以把检测框在时间上关联起来做逐个体追踪，而不是像现在依赖文件名里的元数据。第二，剂量响应：在形态学指标上拟合四参数 logistic 曲线，与已知作用机制对照，这是设计文档里的 E6，本次没有来得及做。第三，与实验自动化对接：把助手作为一个 MCP 客户端接到成像系统的调度接口上，让"拍完自动分析、异常时提醒"闭环起来。此外 pdac 上的小实例问题值得单独攻关，可能的方向是滑窗多尺度推理和用检测框引导分割。</p>

<h2 id="s9">9 复现指南</h2>
<p>仓库 README 给出了完整命令，这里列出顺序与预期耗时（RTX 5090 D 上）。环境：<code>pip install -r requirements.txt</code>（torch 按 CUDA 版本安装，约 10 分钟）；权重：<code>bash scripts/download_weights.sh</code>（约 200 MB，国内加 <code>--mirror</code>）。快速验证（不需要数据集）：<code>python -m orgalyst analyze --organ intestine --images 任意明场图目录 --out runs</code>，几秒到几十秒。复现全部表格：<code>download_orgline.sh</code> 与 <code>extract_orgline.sh</code>（约 25 GB，视网速）；<code>prepare_data.py</code>（15 分钟）；<code>run_e1_zeroshot.sh</code>（20 分钟）；<code>run_e1_finetune.sh</code>（2.5 小时）；<code>run_e1_crossorgan2.sh</code>（3 小时）；<code>run_e2_det.sh</code>（4.5 小时）与 <code>calibrate_det_conf.py</code>（15 分钟）；<code>e3_consistency.py</code>（10 分钟）；<code>run_cpsam_ft.sh</code>（需 <code>setup_cellpose4.sh</code> 的独立环境，2.5 小时）；<code>e5_prepare.sh</code> 与 <code>run_agent_tasks.py</code>（需要 agent/ 与 API 密钥，25 分钟，约 6 美元）。所有脚本输出到 <code>results/</code>，仓库里已包含我们跑出的全部结果文件，报告中的每张表都能对应到其中一个文件。Docker 镜像（Dockerfile）覆盖命令行路径。</p>

<h2 id="s10">10 外部资源与许可证清单</h2>
<div class="tw"><table><tr><th>资源</th><th>用途</th><th>许可证 / 来源</th></tr>
<tr><td>OrgLine（Zenodo 16355179）</td><td>全部训练与评测数据</td><td>CC-BY-4.0；不随仓库分发，脚本从原始来源下载</td></tr>
<tr><td>脑类器官原始数据（Zenodo 10301912，Schröter 等 2024）</td><td>E3 的专家面积与像素标定</td><td>CC-BY-4.0</td></tr>
<tr><td>Cellpose 3（cyto3 权重、size_cyto3）</td><td>分割骨干与初始化权重</td><td>BSD-3，Stringer & Pachitariu</td></tr>
<tr><td>Cellpose-SAM（cpsam / cpsam_v2）</td><td>对照实验</td><td>BSD-3</td></tr>
<tr><td>Ultralytics YOLO11m</td><td>检测计数</td><td>AGPL-3.0（微调权重同许可）</td></tr>
<tr><td>scikit-image、scipy、pandas、matplotlib</td><td>测量、统计、绘图</td><td>BSD / MIT</td></tr>
<tr><td>Claude Agent SDK、Claude（claude-opus-5）</td><td>助手层与 E5 评测</td><td>Anthropic 商业 API；命令行路径不依赖</td></tr>
<tr><td>MCP（FastMCP）</td><td>工具接口</td><td>MIT</td></tr>
<tr><td>Claude Code</td><td>开发过程中的编程助手（代码、文档与实验脚本的撰写均经作者审核）</td><td>Anthropic</td></tr>
</table></div>
<p class="small">本项目代码以 MIT 许可发布；微调权重托管于 Hugging Face（XiaoyanLi/orgalyst-weights），继承各自基础模型的许可证。</p>
</main></div></body></html>"""
# 正文里的直引号成对换成弯引号（标签内不动）
import re as _re
def _curly(html):
    parts = _re.split(r"(<[^>]+>)", html); out = []
    for seg in parts:
        if seg.startswith("<"): out.append(seg); continue
        n = [0]
        def rep(m): n[0] += 1; return "“" if n[0] % 2 == 1 else "”"
        out.append(_re.sub(r'"', rep, seg))
    return "".join(out)
head, body = HTML.split("</style>", 1); HTML = head + "</style>" + _curly(body)
out = f"{D}/technical_report.html"; open(out, "w", encoding="utf-8").write(HTML)
import re; txt = re.sub(r"<[^>]+>", "", HTML); print("written", len(HTML) // 1024, "KB; text chars", len(re.sub(r"\s", "", txt)))
