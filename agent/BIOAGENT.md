# BJQDP 项目知识（BioAgent 启动时自动注入）

## 项目是什么
启德医药（BJQDP）类器官图像 AI 分析：对 3D 类器官球状团块（悬浮于基质胶，不是 2D 贴壁细胞）做自动分割、计数与形态量化。
根目录 `/media/ubuntu/Fdisk/BJQDP/`，约 14GB。

## 先读哪里
- `organoid_docs/README.md`：项目现状总索引（最后更新 2026-08-13），任何问题先看它。
- `organoid_docs/02_评测报告/`：4 份 HTML 报告，按日期是一条完整叙事线（07-07 MedGemma 稳定性、07-08 零样本横评、07-10 与嘉士腾商业软件对比、07-14 周报含 GPU 评测）。
- `organoid_docs/03_决策记录/20260803_模型选型决策_cyto3.html`：选型定案。
- `organoid_docs/01_技术调研/`：模型家族对比、label-free 活力预测调研。

## 代码
- `organoid_benchmark/`：零样本横评历史代码（cyto3 / Cellpose-SAM / StarDist / OrganoID），已完成使命，保留可追溯。`run_cyto3.py` 可跑；`batch_sam.py`、`run_cellpose.py` 因 cpsam 权重与 cellpose 3.1 不兼容不可跑；StarDist 缺依赖。
- `organoid_finetune/`：cyto3 微调框架，脚本 `scripts/{ingest,split,train,evaluate,predict,report,common}.py`，配置 `config/train.yaml`。**尚无标注数据未开跑**。数据放 `data/raw/<种类>/<阶段>/{images,masks}/`。批量推理用 `scripts/predict.py`（支持物理标定、逐目标 CSV）。
- 专用环境：`/media/ubuntu/Fdisk/BJQDP/envs/cp3/bin/python`（cellpose 3.1.1.1）。

## 原始图像（只读）
- `肺癌/{正常肺, LU-554, LU-638}`
- `高内涵/CRO1001`
- `MSHHOT倒置显微镜/{CRO1001, GCO1002, OCO1002, PCO1001, PCO1002}`
- `尼康TS2倒置显微镜/CRO1001`
- `嘉士腾实验/{input, results, 嘉士腾分析}`、`嘉士腾三方对比图`
样本编号：LU = 肺癌类器官，CRO/GCO/OCO/PCO = 不同来源类器官系（详见文档），P10 等表示传代。

## 现状（2026-08）
- 选定模型 cyto3；Cellpose-SAM 因误标多暂停（非永久排除）；StarDist 计数不稳定已淘汰；MedGemma-4B 路线被证伪。
- 零样本效果已与商业软件同量级，但存在过检。
- **最大瓶颈：没有任何人工标注**。建议先标 20–30 张跑通微调 P0 全链路。
- 批量推理瓶颈在 CPU 读图/预处理，不在 GPU（4090 比 5090、H800 都快）。
- 物理标定未做（直径仍是像素）；活力/健康度未开展。

## 其他
- `pharma/`：另一个项目，XDC 药物设计的贝叶斯优化 demo（README、PROJECT_PLAN、demo_results 齐全）。
- 服务器：Ubuntu 20.04，2x RTX 4090 24GB，Fdisk 是 fuseblk 挂载（文件权限恒为 777）。
- 生成的文件默认写到 `/media/ubuntu/Fdisk/BJQDP/bioagent/workspace/<使用者>/`（system prompt 里会给出具体路径）。

## Orgalyst：类器官/器官芯片明场图像分析工具（工具前缀 mcp__orgalyst__，2026-09-15 起）
- 用途：用户给一批明场类器官图片（目录或 glob），要计数、量大小/形态、比较分组、出报告时，优先用这些工具，不要自己写分割代码。
- `list_models`：看有哪些器官的专用分割模型（brain / intestine / pdac / colon；未知器官用 generic）。
- `analyze_images(images, organ, pixel_size_um, name)`：分割 + 形态测量，返回 run_dir、总体与逐图汇总；产物在 run_dir 下（features.csv 每个类器官一行；report.html 可直接给用户；masks/、overlays/）。像素尺寸未知就不要编，留空则结果以像素为单位并在报告里注明。
- `count_organoids(images, organ)`：只问“有几个”时用它——YOLO 检测计数，不分割，快；organ 取 intestine / brain / lung / generic，决定已标定的置信度阈值（肠 0.50、脑 0.45、肺 0.40、未知 0.45）。回答时说明这是检测计数，肠/肺每图误差约 20%（中位 13%），脑接近 0；要精确到每个类器官的大小形状仍用 analyze_images。
- `compare_groups(run_dir, groups)`：按 {image_id: 组名} 做组间统计（两组 Mann-Whitney，多组 Kruskal，Cliff's delta，Holm 校正），产物 compare.html / tables/compare.csv。
- `run_summary(run_dir)` / `list_runs()`：回看某次或最近的分析。
- 回答用户时引用 run_dir 与报告路径；解释结果时区分"像素单位"与"微米单位"；贴边实例默认已排除，要说明。
