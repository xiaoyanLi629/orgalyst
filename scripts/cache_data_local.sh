#!/usr/bin/env bash
# 把 data/processed 复制到本地盘做训练缓存（网络盘小文件读取慢）。完成后写 .complete 标记，脚本据此自动改读本地。
# 实例重建后重跑即可；用完可 rm -rf /root/autodl-tmp/AI4S_data。
set -uo pipefail
SRC=/root/autodl-fs/AI4S/data/processed; DST=/root/autodl-tmp/AI4S_data/processed
mkdir -p "$DST"; rm -f "$DST/.complete"
rsync -a --info=progress2 "$SRC/" "$DST/" && touch "$DST/.complete" && echo "cache complete: $(du -sh $DST | cut -f1)"
