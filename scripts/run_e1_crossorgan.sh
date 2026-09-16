#!/usr/bin/env bash
# E1 补充实验：等 E2 检测训练结束后跑 (1) 四器官联合分割模型 all；(2) 留一器官 loo_<organ>；各自在四个器官 test 上评测（模型直径 + refine）。
cd /root/autodl-fs/AI4S
export CELLPOSE_LOCAL_MODELS_PATH=/root/autodl-tmp/.cellpose/models
while ! grep -q "E2 det DONE" logs/e2_det.log 2>/dev/null; do sleep 120; done
echo "=== cross-organ start $(date)"
.venv/bin/python -u scripts/train_seg_cellpose.py --organs intestine pdac brain colon --name all --epochs 200 2>&1 | grep -E "^\[|Traceback|Error"
for o in intestine pdac brain colon; do
  .venv/bin/python -u scripts/eval_seg_zeroshot.py --pretrained weights/cellpose_ft/all/all --organs $o --split test --diam_mode model --tag all_${o}_model 2>&1 | grep -E "\{|Traceback"
done
for o in intestine pdac brain colon; do
  others=$(echo "intestine pdac brain colon" | tr " " "\n" | grep -v "^$o$" | tr "\n" " ")
  echo "=== loo_$o (train on: $others) $(date)"
  .venv/bin/python -u scripts/train_seg_cellpose.py --organs $others --name loo_$o --epochs 200 2>&1 | grep -E "^\[|Traceback|Error"
  .venv/bin/python -u scripts/eval_seg_zeroshot.py --pretrained weights/cellpose_ft/loo_$o/loo_$o --organs $o --split test --diam_mode model --tag loo_${o}_model 2>&1 | grep -E "\{|Traceback"
done
echo "=== E1 crossorgan DONE $(date)"
