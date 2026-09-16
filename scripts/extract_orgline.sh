#!/usr/bin/env bash
# 把 data/OrgLine/raw/*.zip 解压到 data/OrgLine/{OrgDet,InstanceSeg}；可重复运行（会先清空目标目录）。
ROOT=/root/autodl-fs/AI4S
L=$ROOT/logs/extract_orgline.log
cd $ROOT/data/OrgLine || exit 1
for f in OrgDet InstanceSeg; do
  echo "--- $f $(date)" >> $L
  rm -rf $f; mkdir -p $f
  if unzip -q raw/$f.zip -d $f >> $L 2>&1; then echo "OK $f $(find $f -type f | wc -l) files $(date)" >> $L; else echo "FAIL $f" >> $L; fi
done
echo "DONE $(date)" >> $L
