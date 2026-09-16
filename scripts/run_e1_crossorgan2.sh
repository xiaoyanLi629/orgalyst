#!/usr/bin/env bash
# E1 跨器官实验（第二版）：联合 all 与留一 loo_intestine/loo_colon 因内存（cgroup 62 GB）OOM，改为每器官最多 500 张训练图重训；
# 所有联合/留一模型用 per_image_gt（尺度先验上限）、sizemodel、refine 三种直径策略评测，因为混合模型的 diam_labels 对单一器官无意义。
cd /root/autodl-fs/AI4S
export CELLPOSE_LOCAL_MODELS_PATH=/root/autodl-tmp/.cellpose/models
ORG="intestine pdac brain colon"
rm -f results/e1_ft_all_test_* results/e1_ft_loo_intestine_test_* results/e1_ft_loo_colon_test_*
echo "=== retrain (max_per_organ 500) $(date)"
.venv/bin/python -u scripts/train_seg_cellpose.py --organs $ORG --name all --epochs 200 --max_per_organ 500 2>&1 | grep -E "^\[|Traceback|Error"
for o in intestine colon; do
  others=$(echo "$ORG" | tr " " "\n" | grep -v "^$o$" | tr "\n" " ")
  .venv/bin/python -u scripts/train_seg_cellpose.py --organs $others --name loo_$o --epochs 200 --max_per_organ 500 2>&1 | grep -E "^\[|Traceback|Error"
done
echo "=== eval all $(date)"
for o in $ORG; do for m in model per_image_gt sizemodel refine; do
  .venv/bin/python -u scripts/eval_seg_zeroshot.py --pretrained weights/cellpose_ft/all/all --organs $o --split test --diam_mode $m --tag all_${o}_${m} 2>&1 | grep -E "\{|Traceback"
done; done
echo "=== eval loo $(date)"
for o in $ORG; do for m in per_image_gt sizemodel refine; do
  .venv/bin/python -u scripts/eval_seg_zeroshot.py --pretrained weights/cellpose_ft/loo_$o/loo_$o --organs $o --split test --diam_mode $m --tag loo_${o}_${m} 2>&1 | grep -E "\{|Traceback"
done; done
echo "=== E1 crossorgan2 DONE $(date)"
