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

# 1. 锟斤拷件
print('== 锟斤拷件 ==')
for f in flagged:
    if '锟斤拷' in str(f['issues']):
        print('  ', f['file'], f['issues'])
        fp = os.path.join('lawlibrary', f['file'])
        t = open(fp, encoding='utf-8').read()
        i = t.find('锟')
        print('    上下文:', t[max(0,i-60):i+60].replace('\n', ' '))

# 2. 厦门FFFD: 查源HTML的原始字节
print()
print('== 厦门 FFFD 源头 ==')
md_fp = 'lawlibrary/国家规章库/地方政府规章/Markdown/厦门市城市生活垃圾管理办法_2004-12-14.md'
t = open(md_fp, encoding='utf-8').read()
i = t.find('\ufffd')
print('  md上下文:', repr(t[max(0,i-40):i+40]))
# 找对应html
for p in os.listdir('work/downloads/gov/地方政府规章'):
    if '厦门市城市生活垃圾管理办法' in p and p.endswith('.html'):
        html_fp = os.path.join('work/downloads/gov/地方政府规章', p)
        raw = open(html_fp, 'rb').read()
        # 找 请求的charset
        m = re.search(rb'charset=["\']?([\w-]+)', raw[:2000], re.I)
        print('  HTML声明的charset:', m.group(1) if m else '无')
        # 尝试 gb18030 解码找 FFFD
        for enc in ('utf-8', 'gb18030', 'gbk'):
            try:
                tt = raw.decode(enc)
                print(f'  {enc}解码: FFFD数={tt.count(chr(0xFFFD))}, 锟数={tt.count("锟")}')
            except Exception as e:
                print(f'  {enc}解码失败: {str(e)[:50]}')
        break

# 3. PUA: 地方法规件的来源与其docx
print()
print('== 地方法规 PUA 样本 ==')
pu_files = [f for f in flagged if '私有区字符' in f['issues'] and '/地方法规/' in f['file']]
print('  PUA地方法规件数:', len(pu_files))
# 取3件看docx原文与md对照
manifest = {}
for r in csv.DictReader(open('lawlibrary/manifest.csv', encoding='utf-8-sig')):
    manifest[r['Markdown'].replace(chr(92), '/')] = r
    manifest[r['原文件'].replace(chr(92), '/')] = r
pua_counter = Counter()
ctx_samples = []
for f in pu_files[:20]:
    md_fp = os.path.join('lawlibrary', f['file'])
    t = open(md_fp, encoding='utf-8').read()
    for m in re.finditer(r'[\ue000-\uf8ff]', t):
        cp = m.start()
        pua_counter[hex(ord(t[cp]))] += 1
        if len(ctx_samples) < 12:
            ctx_samples.append((hex(ord(t[cp])), t[max(0,cp-12):cp+13].replace('\n',' ')))
print('  PUA码点汇总:', dict(pua_counter.most_common(10)))
for cp, c in ctx_samples[:10]:
    print(f'    {cp}: …{c}…')
# 一件的来源
r0 = manifest.get(pu_files[0]['file'])
print('  样例件来源:', r0['来源'] if r0 else '?', '|', pu_files[0]['file'][-50:])
