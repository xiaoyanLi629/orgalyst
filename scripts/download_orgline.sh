#!/usr/bin/env bash
# 下载 OrgLine 数据集（Zenodo 16355179），校验 MD5 后解压。
set -u
ROOT=/root/autodl-fs/AI4S
RAW=$ROOT/data/OrgLine/raw
OUT=$ROOT/data/OrgLine
LOG=$ROOT/logs/download_orgline.log
cd "$RAW" || exit 1
bash /root/autodl-fs/bioagent/scripts/proxy_global.sh start "日本大阪-Hysteria2" >> "$LOG" 2>&1
echo "=== start $(date)" >> "$LOG"

declare -A MD5=(
  [OrgDet.zip]=5a3cf0c001c387cf641456f6d0ccb153
  [InstanceSeg.zip]=6ddc154981785f48cf97f682d6c40e3c
)

for f in OrgDet.zip InstanceSeg.zip; do
  url="https://zenodo.org/api/records/16355179/files/$f/content"
  for attempt in 1 2 3 4 5; do
    echo "--- $f attempt $attempt $(date)" >> "$LOG"
    aria2c -x16 -s16 -k1M -c --file-allocation=none --all-proxy=http://127.0.0.1:17891 --retry-wait=10 --max-tries=0 \
      --summary-interval=60 --console-log-level=warn -o "$f" "$url" >> "$LOG" 2>&1
    got=$(md5sum "$f" | cut -d' ' -f1)
    if [ "$got" = "${MD5[$f]}" ]; then
      echo "OK md5 $f $got" >> "$LOG"; echo "$got  $f" >> "$RAW/MD5SUMS"; break
    else
      echo "BAD md5 $f got=$got, retrying" >> "$LOG"; rm -f "$f" "$f.aria2"
    fi
  done
done

for f in OrgDet.zip InstanceSeg.zip; do
  name=${f%.zip}
  if grep -q "$f" "$RAW/MD5SUMS" 2>/dev/null; then
    echo "--- unzip $f $(date)" >> "$LOG"
    mkdir -p "$OUT/$name" && unzip -q -o "$f" -d "$OUT/$name" >> "$LOG" 2>&1 && echo "unzipped $f" >> "$LOG"
  fi
done
echo "=== done $(date)" >> "$LOG"
bash /root/autodl-fs/bioagent/scripts/proxy_global.sh stop >> "$LOG" 2>&1
touch "$ROOT/logs/download_orgline.DONE"
