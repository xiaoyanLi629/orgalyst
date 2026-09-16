#!/usr/bin/env bash
# E1 按器官微调 cyto3 并评测。用法：bash run_e1_finetune.sh [organ ...]（默认 brain pdac intestine colon）
cd /root/autodl-fs/AI4S
export CELLPOSE_LOCAL_MODELS_PATH=/root/autodl-tmp/.cellpose/models
ORGANS=${@:-brain pdac intestine colon}
for o in $ORGANS; do
  echo "=== train $o $(date)"
  .venv/bin/python -u scripts/train_seg_cellpose.py --organs $o --epochs 200 2>&1 | grep -vE "it/s\]|^\s*$" | grep -E "^\[|Epoch|epoch|loss|Error|Traceback|done" | tail -40
  echo "=== eval $o $(date)"
  .venv/bin/python -u scripts/eval_seg_zeroshot.py --pretrained weights/cellpose_ft/$o/$o --organs $o --split test 2>&1 | grep -vE "it/s\]|^\s*$"
done
echo "=== E1 finetune DONE $(date)"
