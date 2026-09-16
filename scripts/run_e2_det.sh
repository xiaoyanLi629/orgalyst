#!/usr/bin/env bash
# E2 YOLO11m 检测：intestine / brain / lung 各 100 轮 + 三器官联合 all。
cd /root/autodl-fs/AI4S
# ultralytics 开训前的 AMP 自检会加载 yolo11n.pt（默认从 GitHub 下载，本机不通）→ 放到当前目录与其 weights_dir
cp -n weights/yolo/yolo11n.pt ./yolo11n.pt; cp -n weights/yolo/yolo26n.pt weights/yolo26n.pt; mkdir -p ~/.config/Ultralytics/weights && cp -n weights/yolo/yolo11n.pt ~/.config/Ultralytics/weights/; cp -n weights/yolo/Arial.Unicode.ttf ~/.config/Ultralytics/
export YOLO_OFFLINE=1
for o in intestine brain lung; do
  echo "--- det $o $(date)"
  .venv/bin/python -u scripts/train_det_yolo.py --organs $o --epochs 100 --imgsz 1024 --batch 8 2>&1 | grep -E "^(intestine|brain|lung) \{|saved|Traceback|Error|epochs completed" | tail -6
done
echo "--- det all $(date)"
.venv/bin/python -u scripts/train_det_yolo.py --organs intestine brain lung --name all --epochs 100 --imgsz 1024 --batch 8 2>&1 | grep -E "^(intestine|brain|lung) \{|saved|Traceback|Error|epochs completed" | tail -8
echo "=== E2 det DONE $(date)"
