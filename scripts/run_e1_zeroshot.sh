#!/usr/bin/env bash
# E1 零样本基线：cyto3 自动直径 vs cyto3 用训练集真值中位直径
cd /root/autodl-fs/AI4S
export CELLPOSE_LOCAL_MODELS_PATH=/root/autodl-tmp/.cellpose/models
.venv/bin/python scripts/eval_seg_zeroshot.py --model cyto3 --split test 2>&1 | grep -vE "it/s\]|^\s*$"
.venv/bin/python scripts/eval_seg_zeroshot.py --model cyto3 --split test --diameter_from_gt 2>&1 | grep -vE "it/s\]|^\s*$"
echo "=== E1 zeroshot DONE"
