#!/bin/bash
# 湖南 xzcf 循环重跑（断点续跑；每轮日志独立文件，无内层管道）
# 审查修复：cd 按脚本自身位置定位 work/taxcase（原为 /e/ 硬编码绝对路径）
cd "$(cd "$(dirname "$0")" && pwd)/.."
TARGET=2681
for i in $(seq 1 12); do
  n=$(wc -l < tmp/hn/xzcf_records.jsonl 2>/dev/null || echo 0)
  echo "[loop $i] records=$n / $TARGET  $(date +%H:%M:%S)"
  if [ "$n" -ge "$TARGET" ]; then echo "target reached"; break; fi
  timeout 900 python -u adapters/hn_xzcf.py > tmp/hn/xzcf_run_$i.log 2>&1
  tail -3 tmp/hn/xzcf_run_$i.log
  n2=$(wc -l < tmp/hn/xzcf_records.jsonl 2>/dev/null || echo 0)
  if [ "$n2" -eq "$n" ] && [ "$i" -gt 1 ]; then
    echo "[loop $i] no progress ($n), cooldown 360s"
    sleep 360
  else
    sleep 15
  fi
done
echo "FINAL: $(wc -l < tmp/hn/xzcf_records.jsonl)"
