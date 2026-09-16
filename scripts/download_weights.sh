#!/usr/bin/env bash
# 下载 Orgalyst 的模型权重到 weights/：按器官微调的 Cellpose 权重（brain/intestine/pdac/colon，各 26 MB）、
# 三器官联合 YOLO11m 检测权重（40 MB），以及 Cellpose 官方的 cyto3 基础权重与尺寸估计器（从 cellpose.org）。
# 用法：bash scripts/download_weights.sh [--mirror]   （国内加 --mirror 走 hf-mirror.com）
set -e
cd "$(dirname "$0")/.."
HF=https://huggingface.co; [ "${1:-}" = "--mirror" ] && HF=https://hf-mirror.com
REPO=XiaoyanLi/orgalyst-weights
dl() { # url dest
  mkdir -p "$(dirname "$2")"; [ -s "$2" ] && { echo "exists $2"; return; }
  if command -v aria2c >/dev/null; then aria2c -x8 -s8 -q -o "$(basename "$2")" -d "$(dirname "$2")" "$1"; else curl -L --retry 3 -o "$2" "$1"; fi; echo "ok $2"; }
for o in brain intestine pdac colon all; do
  dl "$HF/$REPO/resolve/main/cellpose_ft/$o/$o" "weights/cellpose_ft/$o/$o"
  dl "$HF/$REPO/resolve/main/cellpose_ft/$o/train_log.json" "weights/cellpose_ft/$o/train_log.json"
done
dl "$HF/$REPO/resolve/main/yolo/yolo11m_all_best.pt" "weights/yolo/all/weights/best.pt"
# Cellpose 官方 cyto3（通用兜底 + 尺寸估计器），放到 CELLPOSE_LOCAL_MODELS_PATH（默认 weights/cellpose）
CP=${CELLPOSE_LOCAL_MODELS_PATH:-$PWD/weights/cellpose}
dl https://www.cellpose.org/models/cyto3 "$CP/cyto3"
dl https://www.cellpose.org/models/size_cyto3.npy "$CP/size_cyto3.npy"
echo "weights ready under weights/ (set CELLPOSE_LOCAL_MODELS_PATH=$CP)"
