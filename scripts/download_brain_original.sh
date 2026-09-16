#!/usr/bin/env bash
# 脑类器官原始数据集（Schröter 2024，Zenodo 10301912，0.97 GB）：含每图人工测量尺寸的 CSV，用于 E3 一致性验证。走 Hysteria2 代理 + aria2c。
set -u
D=/root/autodl-fs/AI4S/data/brain_original; L=/root/autodl-fs/AI4S/logs/download_brain_original.log
bash /root/autodl-fs/bioagent/scripts/proxy_global.sh start "日本大阪-Hysteria2" >> $L 2>&1
cd $D && aria2c -x16 -s16 -k1M -c --file-allocation=none --all-proxy=http://127.0.0.1:17891 --summary-interval=60 --console-log-level=warn -o data.zip "https://zenodo.org/api/records/10301912/files/data.zip/content" >> $L 2>&1
bash /root/autodl-fs/bioagent/scripts/proxy_global.sh stop >> $L 2>&1
unzip -l data.zip | grep -iE "\.csv$" >> $L 2>&1
unzip -o -j data.zip "*.csv" -d $D >> $L 2>&1
echo "=== brain_original DONE $(date)" >> $L
