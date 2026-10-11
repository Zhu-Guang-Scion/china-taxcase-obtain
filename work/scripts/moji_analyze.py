#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, csv, re
from collections import Counter

d = json.load(open('work/verify/mojibake_report.json', encoding='utf-8'))
flagged = d['flagged']
manifest_md = {}
manifest_orig = {}
for r in csv.DictReader(open('lawlibrary/manifest.csv', encoding='utf-8-sig')):
    manifest_md[r['Markdown'].replace(chr(92), '/')] = r
    manifest_orig[r['原文件'].replace(chr(92), '/')] = r

cat_issue = Counter()
pu_files, fffd_files, ctrl_files, gbk_files = [], [], [], []
for f in flagged:
    r = manifest_md.get(f['file'])
    cat = f"{r['库']}/{r['类别']}" if r else '未索引'
    for issue in f['issues']:
        cat_issue[f'{cat}|{issue}'] += 1
    if '私有区字符' in f['issues']: pu_files.append((f['file'], f['issues']['私有区字符']))
    if 'U+FFFD' in f['issues']: fffd_files.append((f['file'], f['issues']['U+FFFD']))
    if '控制字符' in f['issues']: ctrl_files.append((f['file'], f['issues']['控制字符']))
    if '锟斤拷' in f['issues']: gbk_files.append((f['file'], f['issues']['锟斤拷类']))

print('分类×问题:')
for k, c in sorted(cat_issue.items()):
    print(f'  {c:4} {k}')
print()
print('== 锟斤拷件 ==')
for p, n in gbk_files: print('  ', n, p)
print('== FFFD top10 ==')
for p, n in sorted(fffd_files, key=lambda x: -x[1])[:10]: print('  ', n, p[:70])
print('== 控制字符件 ==')
for p, n in ctrl_files: print('  ', n, p[:70])

if pu_files:
    p0 = sorted(pu_files, key=lambda x: -x[1])[0][0]
    t = open(os.path.join('lawlibrary', p0), encoding='utf-8').read()
    puas = Counter(hex(ord(c)) for c in t if 0xe000 <= ord(c) <= 0xf8ff)
    print()
    print('== PUA 码点分布 ==', p0[:60])
    for cp, n in puas.most_common(8):
        print(f'   {cp}: {n} 次')
    i = next(i for i, c in enumerate(t) if 0xe000 <= ord(c) <= 0xf8ff)
    print('   上下文:', repr(t[max(0, i-30):i+30]))
