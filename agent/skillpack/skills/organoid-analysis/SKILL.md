---
name: organoid-analysis
user-invocable: true
description: 类器官 / 器官芯片明场图像分析的标准流程（Orgalyst）。用户给一批明场照片要数数、量大小形态、做质控、比较分组、画生长曲线或出报告时使用；也可用 /organoid-analysis <图片目录> 触发。流程：确认器官与像素尺寸 → 选 count_organoids 或 analyze_images → 核对返回与质控 → 需要时 compare_groups / growth_curves → 按固定格式汇报并给出产物路径。
allowed-tools: [Read, Glob, Bash, AskUserQuestion]
---

# 类器官图像分析（Orgalyst）

## 什么时候用
用户提到类器官、organoid、器官芯片、明场照片、分割、计数、面积、圆度、生长曲线、分组比较，并且手里有一批图片（目录或 glob）。所有数值都由 `mcp__orgalyst__*` 工具算出；**不要自己写分割代码，不要用 Python 重算工具已经给出的统计量。**

## 第 1 步 · 三个前提，缺了再问
1. **器官类型**：`brain / intestine / pdac / colon`（分割）或 `intestine / brain / lung`（检测）。用户没说且从文件名、目录名也看不出来时，用 `generic` 先跑，并在回答里注明“通用模型，精度明显低于专用模型，告诉我器官类型可以重跑”。不要为了这个问题阻塞简单任务。
2. **像素物理尺寸**（µm/px）：用户给了就传 `pixel_size_um`；没给就不传，结果全部以像素为单位，回答里必须说明。**绝对不要估算或编造标定值。**
3. **用户要什么**：只要数量 → 检测路径；要大小、形态、报告 → 分割路径；提到组、处理、对照、时间点、天数 → 分割路径 + 统计。

## 第 2 步 · 选工具
- 只数数：`count_organoids(images, organ)`，几秒出结果；阈值已按器官标定，不要改 `conf`，除非用户明确要求。
- 其他：`analyze_images(images, organ, pixel_size_um, name, qc, meta_csv)`。
  - `name` 用有意义的英文短名（如 `exp3_intestine`），它会出现在 run_dir 里。
  - 用户关心可靠性、图片少于 20 张、或图片质量可疑时加 `qc=True`（耗时约 4 倍）。
  - 有分组 / 时间点 / 个体信息的 CSV（列 `image_id` 加 `group` / `timepoint` / `subject` / `pixel_size_um`）就传 `meta_csv`，后面的统计工具直接能用。
- 分组比较：`compare_groups(run_dir, groups)`，`groups` 是 `{image_id: 组名}` 或 CSV 路径。
- 生长曲线：`growth_curves(run_dir, meta_csv 或 pattern)`；脑类器官公开数据的文件名 `org01_wt2D_d02_LabA` 不传 pattern 也能解析。
- 回看历史：`list_runs()`、`run_summary(run_dir)`。

## 第 3 步 · 拿到返回先核对，再汇报
- 逐图计数里有 0 或明显离群的值 → 打开 `overlays/` 里对应的图看一眼（Read 工具可以看图），判断是空图、失焦还是分割失败，如实写进回答。
- 汇总里的 `n_border_excluded`（贴边排除数）和 `qc` 的低可信数要写进回答。
- 通用模型（generic）或 pdac 的结果要提醒：召回可能只有一半左右。
- 不要把工具返回的数字四舍五入到失真；面积、直径保留到整数或一位小数，圆度、实心度两位小数。

## 第 4 步 · 回答格式（固定）
1. 一句话结论（有几个、多大、有没有差异或变化）。
2. 一张表：逐图数量，以及面积 / 直径 / 圆度的中位数与四分位范围（有 µm 就用 µm，否则标明 px）。
3. 单位与排除说明：像素还是微米；排除了几个贴边实例；质控标出几个不可靠。
4. 有统计时：检验方法、p 值、效应量、结论用一句话说人话（“wt2D 组面积显著大于 TH2-7 组”）。
5. 产物路径：run_dir、`report.html`（告诉用户双击打开）、`tables/features.csv`、`overlays/`；有比较或曲线时加 `compare.html` / `growth.html`。
6. 下一步建议（最多两条）：例如补像素尺寸、给分组文件、人工核对叠加图。

## 不要做的事
- 不要在没有像素尺寸时给出任何微米数字。
- 不要在报告已经生成时再用 Python 重画同样的直方图或重算中位数。
- 不要为了追求准确反复重跑同一批图；一次 analyze 加必要的统计即可。
- 不要把 `manifest.json` 里的哈希、版本念一遍，除非用户问可复现性；问了就给完整路径并说明记录了输入 md5、权重哈希、参数、软件版本。
