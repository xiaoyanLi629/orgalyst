#!/usr/bin/env bash
# Cellpose-SAM 微调对照（等零样本评测结束后）：pdac 与 intestine 各 100 epoch，评测 native 与 per_image_gt
cd /root/autodl-fs/AI4S; PY=/root/autodl-tmp/cellpose4-env/bin/python
while ! grep -q "E1 cpsam DONE" logs/e1_cpsam.log 2>/dev/null; do sleep 60; done
for o in pdac intestine; do
  echo "=== train cpsam $o $(date)"
  $PY -u scripts/train_seg_cpsam.py --organs $o --epochs 100 --batch_size 2 --lr 1e-5 2>&1 | grep -E "^\[|Traceback|Error|out of memory" | tail -5
  for d in native per_image_gt; do echo "=== eval cpsam_ft $o $d $(date)"; $PY scripts/eval_seg_cpsam.py --pretrained weights/cpsam_ft/$o/$o --organs $o --diam_mode $d --tag cpsamft_${o}_${d} 2>&1 | grep -E "\{|Traceback|Error"; done
done
echo "=== cpsam ft DONE $(date)"
