#!/usr/bin/env bash
# 等 E1 按器官微调结束后：(1) 用逐图直径重评四个器官（sizemodel 与 per_image_gt），零样本 cyto3 也补 per_image_gt 上限；(2) 启动 E2 YOLO 检测训练。
cd /root/autodl-fs/AI4S
export CELLPOSE_LOCAL_MODELS_PATH=/root/autodl-tmp/.cellpose/models
while ! grep -q "E1 finetune DONE" logs/e1_finetune.log 2>/dev/null; do sleep 60; done
echo "=== re-eval fine-tuned models with per-image diameters $(date)"
for o in brain pdac intestine colon; do
  for m in sizemodel per_image_gt; do
    .venv/bin/python -u scripts/eval_seg_zeroshot.py --pretrained weights/cellpose_ft/$o/$o --organs $o --split test --diam_mode $m --tag ft_${o}_${m} 2>&1 | grep -E "^(intestine|pdac|brain|colon) \{|saved|Traceback|Error"
  done
done
echo "=== zero-shot cyto3 with per-image GT diameter (oracle) $(date)"
.venv/bin/python -u scripts/eval_seg_zeroshot.py --model cyto3 --split test --diam_mode per_image_gt 2>&1 | grep -E "^(intestine|pdac|brain|colon) \{|saved|Traceback|Error"
echo "=== E2 YOLO11m detection $(date)"
for o in intestine brain lung; do
  echo "--- det $o $(date)"
  .venv/bin/python -u scripts/train_det_yolo.py --organs $o --epochs 100 --imgsz 1024 --batch 8 2>&1 | grep -E "^(intestine|brain|lung) \{|saved|Traceback|Error|epochs completed" | tail -6
done
echo "--- det all $(date)"
.venv/bin/python -u scripts/train_det_yolo.py --organs intestine brain lung --name all --epochs 100 --imgsz 1024 --batch 8 2>&1 | grep -E "^(intestine|brain|lung) \{|saved|Traceback|Error|epochs completed" | tail -8
echo "=== after_ft DONE $(date)"
