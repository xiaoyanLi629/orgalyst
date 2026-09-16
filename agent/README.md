# agent/ — Orgalyst 的对话式助手（BioAgent 精简副本）

这是一个基于 **Claude Agent SDK** 的终端 / 网页助理，把 `../orgalyst/mcp_server.py` 以 MCP 服务器的形式接给大模型，实验人员用自然语言驱动整条类器官图像分析链路。所有数值计算都在 orgalyst 工具包里完成，助手只负责理解需求、选工具、传参数和解释结果。

## 安装与启动

```bash
cd agent
bash install.sh                                   # 创建 .venv，安装 claude-agent-sdk、fastapi 等；会提示缺什么
cp config.example.yaml config.yaml                 # mcp_servers 里的 orgalyst 已指向 ../orgalyst/mcp_server.py
mkdir -p ~/.config/bioagent && printf 'ANTHROPIC_API_KEY=sk-ant-...\n' > ~/.config/bioagent/.env && chmod 600 ~/.config/bioagent/.env
./bioagent.sh --check                              # 检查 API 连通与 MCP 配置
./bioagent.sh --user demo                          # 终端版；进入后输入 /auto auto，工具调用就不再逐条确认
bash scripts/bioagent-web.sh                       # 网页版（多账号、管理员用量面板），首次运行按提示建账号
```

orgalyst MCP 服务器用的是 `config.yaml` 里 `mcp_servers[0].command` 指定的 Python，默认写的是 `python`，请改成装了 orgalyst 依赖的解释器（例如仓库根目录的 `.venv/bin/python`），并把 `CELLPOSE_LOCAL_MODELS_PATH` 指到 `../weights/cellpose`。

## 助手能调用的 Orgalyst 工具

| 工具 | 作用 |
|---|---|
| `list_models` | 有哪些器官的分割权重、检测权重与各自默认的直径策略 / 置信度阈值 |
| `analyze_images(images, organ, pixel_size_um, name, qc, meta_csv)` | 分割 + 形态测量 + 报告；返回 run_dir 与汇总 |
| `count_organoids(images, organ, conf)` | 只数数（YOLO 检测，阈值已按器官标定） |
| `compare_groups(run_dir, groups)` | 组间统计（Mann-Whitney / Kruskal、Cliff's delta、Holm） |
| `growth_curves(run_dir, meta_csv \| pattern)` | 按个体 × 时间点连成生长曲线 |
| `run_summary(run_dir)` / `list_runs()` | 回看某次或最近的分析 |

`BIOAGENT.md` 是助手的项目说明（系统提示的一部分），其中“Orgalyst”一节告诉它什么时候用哪个工具、回答时要说明像素单位与贴边排除等约定。

## 代理与网络

`bioagent/proxy.py` 支持通过一个本地 mihomo 实例只把 Anthropic 等域名走代理（`config.yaml` 的 `proxy:` 段）。能直连 API 的环境把 `proxy.enabled` 设为 `false` 即可，不需要任何节点配置。

## 开源模型后端

Claude Agent SDK 可以通过 `ANTHROPIC_BASE_URL` 指向一个兼容 Anthropic Messages API 的网关（例如 LiteLLM 前置 vLLM）。把网关地址写进 `~/.config/bioagent/.env`（`ANTHROPIC_BASE_URL=http://127.0.0.1:4000`），`config.yaml` 的 `model:` 改成网关里的模型名即可；E5 任务集脚本 `../scripts/run_agent_tasks.py --tag <name>` 可以对不同后端各跑一遍作对比。

## 权限模型

`bioagent/permissions.py` 是所有工具调用的门卫：原始数据目录（`readonly_dirs`）只读，其他账号的目录与密钥目录一律禁止；每个对话可选 `ask / edits / auto / readonly` 四档确认方式。`tests/` 里有对应的单元测试（`.venv/bin/pytest -q`）。

## Biomni 工具库（可选）

原版 BioAgent 还接入了 Biomni 的生物信息学工具库（数据库查询、文献、分子生物学等，需要约 20 GB 数据湖）。本仓库默认关闭（`biomni.enabled: false`），Orgalyst 的演示不依赖它；需要时按 `install_biomni.sh` 的说明安装后打开。
