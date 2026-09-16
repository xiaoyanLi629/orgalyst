#!/usr/bin/env bash
# 在本地盘重建 Orgalyst 的 Python 环境。换实例后只需重跑本脚本。
# 用法：bash /root/autodl-fs/AI4S/scripts/setup_env.sh
# 步骤：miniconda 的 Python 3.10 建 venv → wheelhouse_install.sh（uv 解析 → aria2c 多线程拉 wheel → 离线安装 → CUDA 自检）
# 为什么不直接 pip install：AutoDL 实例单连接只有 0.2–1 MB/s，aria2c 16 连接到清华镜像可达 10 MiB/s；
#                          torch 2.14 + CUDA 13 库约 3.5 GB。系统盘只剩几 GB，所以 venv、wheel、临时目录都放本地盘 autodl-tmp。
set -euo pipefail
ROOT=/root/autodl-fs/AI4S
ENV=/root/autodl-tmp/orgalyst-env
PY=${PY:-/root/miniconda3/bin/python}
LOG=$ROOT/logs/setup_env.log
mkdir -p "$(dirname "$ENV")" "$ROOT/logs"
echo "=== setup_env $(date) python=$PY env=$ENV" | tee -a "$LOG"
[ -x "$ENV/bin/python" ] || "$PY" -m venv "$ENV"
command -v /root/miniconda3/bin/uv >/dev/null || /root/miniconda3/bin/pip install -q -i https://pypi.tuna.tsinghua.edu.cn/simple uv
ln -sfn "$ENV" "$ROOT/.venv"
bash "$ROOT/scripts/wheelhouse_install.sh" 2>&1 | tee -a "$LOG"
echo "=== setup_env DONE $(date)" | tee -a "$LOG"
