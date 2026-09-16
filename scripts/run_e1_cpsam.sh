#!/usr/bin/env bash
# Cellpose-SAM 零样本：cpsam（论文版）与 cpsam_v2（4.2 默认）各跑 native 与 per_image_gt
cd /root/autodl-fs/AI4S; PY=/root/autodl-tmp/cellpose4-env/bin/python
for m in cpsam cpsam_v2; do
  while [ -f /root/.cellpose/models/$m.aria2 ] || [ ! -s /root/.cellpose/models/$m ]; do sleep 30; done
  cp -n /root/.cellpose/models/$m weights/cellpose/$m 2>/dev/null
  for d in native per_image_gt; do echo "=== $m $d $(date)"; $PY scripts/eval_seg_cpsam.py --pretrained $m --diam_mode $d 2>&1 | grep -E "^(intestine|pdac|brain|colon) \{|saved|Traceback|Error"; done
done
echo "=== E1 cpsam DONE $(date)"
