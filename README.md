# Orgalyst — 类器官明场图像的对话式智能分析系统

**AI4S Open Innovation: AI for Life Science（第五届琶洲算法大赛，AI + 器官芯片赛道）参赛作品 · 类别：端到端系统（End-to-End System）**

Orgalyst = organoid + analyst。它把一条完整的类器官明场图像分析链路做成了两层：

- **`orgalyst` 工具包**（命令行，不需要任何大模型）：按器官加载专用的 Cellpose 分割权重 → 形态测量（面积、等效直径、周长、圆度、实心度、长宽比、贴边标记）→ 质控（图像级清晰度/光照/饱和，实例级翻转旋转一致性）→ 组间统计（Mann-Whitney / Kruskal、Cliff's delta、Holm 校正）→ 生长曲线 → 单文件 HTML 报告 + 可复现的运行清单（输入 md5、权重哈希、参数、软件版本）。另有一个 YOLO11m 检测模型只负责"数有几个"。
- **对话式助手**（`agent/`，基于 Claude Agent SDK 的 BioAgent）：把工具包通过 MCP 暴露给大模型，实验人员用一句话提需求（"分析这批肠类器官照片，比较两组面积，给我一份报告"），助手负责选工具、选器官权重、传参数、解释结果；所有数字仍由工具包算出，助手不看图、不算数。

全部实验在公开的 **OrgLine** 数据集（Zenodo 16355179，CC-BY-4.0，八个来源、五种器官）上完成，没有使用任何私有数据。

## English summary

Orgalyst is a conversational analysis system for organoid bright-field images. A deterministic toolkit (`orgalyst/`) performs organ-specific Cellpose segmentation (cyto3 fine-tuned per organ on OrgLine), YOLO11m counting with calibrated confidence thresholds, morphometry, QC (image-level metrics and flip/rotate test-time-augmentation agreement), group statistics, growth curves and single-file HTML reports with a full provenance manifest. An agent layer (`agent/`, Claude Agent SDK + MCP) lets a biologist drive the whole pipeline in natural language; every number still comes from the toolkit. Everything is reproducible from the command line without any LLM; the agent path is evaluated on a 12-task benchmark (E5). See `docs/` for the design document, the animated pipeline walkthrough and the technical report (Chinese `technical_report.html`, English `technical_report_en.html`), and `results/` for every table in the technical report.

## 30 分钟上手

```bash
git clone https://github.com/xiaoyanLi629/orgalyst && cd orgalyst
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # torch 请按自己的 CUDA 版本装（见 scripts/setup_env.sh）
bash scripts/download_weights.sh           # 国内加 --mirror；约 200 MB，权重托管在 HF: XiaoyanLi/orgalyst-weights
export CELLPOSE_LOCAL_MODELS_PATH=$PWD/weights/cellpose ORGALYST_ROOT=$PWD

# 1) 分割 + 形态测量 + 报告（任意一批明场 png/tif）
python -m orgalyst analyze --organ intestine --images /path/to/images --out runs --name demo
#    → runs/demo_<id>/{report.html, manifest.json, tables/features.csv, tables/summary.json, masks/, overlays/}
# 2) 只数数（检测模型，阈值已按器官标定）
python -m orgalyst count --organ lung --images /path/to/images --out runs
# 3) 带物理尺寸、质控、生长曲线
python -m orgalyst analyze --organ brain --images DIR --pixel-size 3.1646 --qc --meta meta.csv --out runs --name growth
python -m orgalyst track --run runs/growth_<id> --meta meta.csv
```

Docker：`docker build -t orgalyst . && docker run --gpus all -v /path/to/images:/data -v $PWD/runs:/runs -v $PWD/weights:/app/weights orgalyst analyze --organ intestine --images /data --out /runs`

器官参数取 `brain / intestine / pdac / colon`（分割）与 `intestine / brain / lung`（检测）；不知道器官用 `generic`（零样本 cyto3 兜底，精度明显更低，报告里会标注）。

## 复现报告里的全部数字

```bash
bash scripts/download_orgline.sh && bash scripts/extract_orgline.sh   # OrgLine 原始数据（约 25 GB）
python scripts/prepare_data.py                                          # → data/processed（统一 8 位 PNG + uint16 实例掩码 + YOLO 标注 + manifest.csv）
bash scripts/run_e1_zeroshot.sh; bash scripts/run_e1_finetune.sh        # E1 零样本 / 按器官微调（results/e1_*）
bash scripts/run_e1_crossorgan2.sh                                      # E1 跨器官：联合 + 留一（results/e1_ft_all_*, e1_ft_loo_*）
bash scripts/run_e2_det.sh; python scripts/calibrate_det_conf.py        # E2 检测 + 计数阈值标定（results/e2_*）
python scripts/e3_consistency.py                                        # E3 与专家标注面积的一致性（results/e3_*）
bash scripts/run_cpsam_ft.sh                                            # 对照：Cellpose-SAM 零样本与微调（需 scripts/setup_cellpose4.sh 的独立环境）
bash scripts/e5_prepare.sh; python scripts/run_agent_tasks.py           # E5 Agent 任务集（需要 agent/ 与 API key）
```

每个脚本都把结果写成 `results/*.json|csv`，仓库里已经包含我们跑出的全部结果文件，报告里的每张表都能对应到其中一个文件。

## 主要结果（test 集）

**E1 分割（AP50）**

| 器官 | cyto3 零样本 | 按器官微调 | 微调 + 逐图尺寸策略（系统默认） | 逐图真值直径（上限） |
|---|---|---|---|---|
| brain (240) | 0.005 | 0.925 | **0.967**（两遍推理 refine） | 0.975 |
| intestine (12) | 0.544 | 0.773 | **0.812**（sizemodel） | 0.812 |
| colon (10) | 0.405 | **0.815** | 0.814 | 0.800 |
| pdac (20) | 0.419 | 0.564 | **0.591**（sizemodel） | 0.605 |

四器官联合模型在给对尺度时与专用模型持平，但留一器官模型在没见过的器官上只有 0.15–0.47，所以系统按器官加载专用权重。Cellpose-SAM（cellpose 4）零样本与微调后都没有超过 cyto3 微调（pdac 0.557 / 0.591，intestine 0.780 / 0.795），且权重大 50 倍，只作对照。

**E2 检测计数（YOLO11m，三器官联合模型，阈值在 val 上标定）**

| 器官 | mAP50 | 标定阈值 | 计数 MAPE（默认 0.25 → 标定） | 中位 APE |
|---|---|---|---|---|
| intestine (423) | 0.948 | 0.50 | 0.262 → 0.207 | 0.13 |
| brain (280) | 0.995 | 0.45 | 0.018 → 0.004 | 0.00 |
| lung (602) | 0.936 | 0.40 | 0.235 → 0.168 | 0.11 |

**E3 与专家标注的一致性（brain，240 图，面积）**：Spearman 0.963，中位相对误差 1.9%，≤10% 误差的图占 93%，漏检 3/240。

**E5 Agent 任务集（12 个自然语言任务：单图 / 批量 / 物理尺寸 / 只数数 / 组间比较 / 生长曲线 / 质控 / 追问指标含义 / 追问可复现性 / 器官未知 / 空目录 / 混合器官；每个任务有对照命令行参考值与产物文件的自动判定，`scripts/run_agent_tasks.py`）**：Claude（claude-opus-5）后端 12/12 通过，平均每任务 10.5 次工具调用（其中 1.5 次是 Orgalyst 工具，其余是任务清单、读文件等），平均 113 s，12 个任务合计 5.6 美元；最慢的是组间比较（309 s）和生长曲线（458 s），因为助手在拿到结果后又自行核对了表格。逐任务记录在 `results/e5_agent_tasks_claude.json`。

## 目录

```
orgalyst/        工具包：config（模型注册表 + 标定阈值）· segment · detect · morphometry · qc · compare · track · overlay · run · report · cli · mcp_server
scripts/         数据准备、E1–E5 实验、权重/数据下载、演示页生成
configs/         YOLO 数据配置
results/         全部实验结果（json/csv）
docs/            design.html 设计文档 · orgalyst_scene.html 全景流程动画 · technical_report.html 技术报告（中文）· technical_report_en.html（English）· PDF 用浏览器打印 A4 即可 · assets/ 两页共用的素材
e5/              Agent 任务集的参考值（数据由 scripts/e5_prepare.sh 从 OrgLine 抽取）
agent/           对话式助手（BioAgent 精简副本：Claude Agent SDK + MCP + 权限门卫 + 网页版）；config.example.yaml 已指向本仓库的 orgalyst MCP
weights/         不进 git，scripts/download_weights.sh 下载
```

## 对话式助手怎么跑

```bash
cd agent && bash install.sh                       # 建 .venv，装 claude-agent-sdk 等
cp config.example.yaml config.yaml                 # 按需改模型；Biomni 工具库默认关闭
mkdir -p ~/.config/bioagent && echo "ANTHROPIC_API_KEY=sk-ant-..." > ~/.config/bioagent/.env
./bioagent.sh --user demo                          # 终端版；输入 /auto auto 后即可一句话驱动整条链路
bash scripts/bioagent-web.sh                       # 网页版（多账号）
```

助手会调用 `mcp__orgalyst__` 前缀的六个工具：`list_models`、`analyze_images`、`count_organoids`、`compare_groups`、`growth_curves`、`run_summary` / `list_runs`。开源模型后端（LiteLLM → vLLM）见 `agent/README.md`。

## 许可与引用

代码 MIT；OrgLine 数据 CC-BY-4.0（不随仓库分发）；权重派生自 Cellpose（BSD-3）与 Ultralytics YOLO11（AGPL-3.0）。请引用 OrgLine 与 Cellpose 的原始论文；本项目：Xiaoyan Li et al., *Orgalyst: a conversational analysis system for organoid bright-field images*, AI4S Open Innovation 2026.
