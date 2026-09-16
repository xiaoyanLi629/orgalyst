#!/usr/bin/env bash
# Cellpose 4（Cellpose-SAM）独立环境：与 3.1 不能共存。torch 从本地 wheelhouse 复用，cellpose 4 从清华镜像装。
# 权重 cpsam 从 cellpose.org 经 Hysteria2 代理用 aria2c 下载到 /root/autodl-tmp/.cellpose/models/（与 3.x 的 cyto3 同目录，文件名不冲突）。
set -uo pipefail
ENV=/root/autodl-tmp/cellpose4-env; WH=/root/autodl-tmp/wheelhouse; UV=/root/miniconda3/bin/uv
export UV_CACHE_DIR=/root/autodl-tmp/.cache/uv TMPDIR=/root/autodl-tmp/.tmp
[ -x $ENV/bin/python ] || /root/miniconda3/bin/python -m venv $ENV
$UV pip install --python $ENV/bin/python --index-url https://pypi.tuna.tsinghua.edu.cn/simple --find-links $WH "torch==2.14.0" "torchvision==0.29.0" "cellpose==4.2.1.1" "numpy<2.3" scikit-image scipy pandas pillow tifffile 2>&1 | tail -2
$ENV/bin/python -c "import cellpose, torch; print(\"cellpose\", cellpose.version, \"torch\", torch.__version__, \"cuda\", torch.cuda.is_available())"
M=/root/autodl-tmp/.cellpose/models; mkdir -p $M
if [ ! -s $M/cpsam ]; then
  bash /root/autodl-fs/bioagent/scripts/proxy_global.sh start "日本大阪-Hysteria2" >/dev/null 2>&1
  cd $M && aria2c -x8 -s8 -k1M -c --file-allocation=none --all-proxy=http://127.0.0.1:17891 --summary-interval=60 --console-log-level=warn -o cpsam "https://www.cellpose.org/models/cpsam" 2>&1 | grep -E "OK|ERR|\[#" | tail -3
  bash /root/autodl-fs/bioagent/scripts/proxy_global.sh stop >/dev/null 2>&1
fi
ls -la $M/cpsam && md5sum $M/cpsam | cut -c1-12 && cp -n $M/cpsam /root/autodl-fs/AI4S/weights/cellpose/cpsam
echo "=== setup_cellpose4 DONE $(date)"
