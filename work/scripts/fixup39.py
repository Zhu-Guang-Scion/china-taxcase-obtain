#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""修复 manifest 中 39 件 md 缺失：XML直抽 / parquet标题回退，并回写 manifest。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import html as hl
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(__file__))
from organize_md import (TIAO_HEAD, md_doc, norm_title)

LIB = 'lawlibrary'
W = os.path.join(os.path.dirname(__file__), '..')


def xml_text_md(path):
    """zip(docx) 直抽 word/document.xml 文本（绕过 python-docx content-type 校验）。"""
    try:
        z = zipfile.ZipFile(path)
        names = z.namelist()
        target = 'word/document.xml' if 'word/document.xml' in names else \
                 next((n for n in names if n.endswith('document.xml')), None)
        if not target:
            return ''
        xml = z.read(target).decode('utf-8', errors='replace')
        # 段落切分
        paras = re.split(r'</w:p>', xml)
        out = []
        for p in paras:
            texts = re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)
            t = hl.unescape(''.join(texts)).strip()
            t = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', t)
            if t:
                out.append(t)
        if not out:
            return ''
        lines = []
        for t in out:
            if TIAO_HEAD.match(t):
                lines.append('**' + t + '**')
            elif re.match(r'^第[一二三四五六七八九十百千零\d]+[章节编]', t) and len(t) <= 30:
                lines.append('## ' + t)
            else:
                lines.append(t)
        return '\n\n'.join(lines)
    except Exception:
        return ''


def load_parquet_fallback(titles):
    import pandas as pd
    df = pd.read_parquet(os.path.join(W, '..', 'mirrors', 'law_full.parquet'))
    df['nt'] = df['title'].map(norm_title)
    out = {}
    for t in titles:
        rows = df[df['nt'] == t]
        if len(rows):
            c = rows.iloc[0]['content']
            if c and len(str(c)) > 300:
                out[t] = str(c)
    return out


def main():
    csv_path = os.path.join(LIB, 'manifest.csv')
    rows = list(csv.DictReader(open(csv_path, encoding='utf-8-sig')))
    fail = [r for r in rows if not r['Markdown']]
    print('待修复:', len(fail))

    need_parquet = []
    for r in fail:
        p = os.path.join(LIB, r['原文件'])
        if not os.path.exists(p):
            continue
        if p.endswith('.pdf'):
            need_parquet.append(norm_title(r['标题']))
        elif p.endswith(('.docx', '.doc')) and xml_text_md(p):
            pass
        else:
            need_parquet.append(norm_title(r['标题']))
    pq = load_parquet_fallback(set(need_parquet)) if need_parquet else {}
    print('parquet 命中:', len(pq))

    fixed = still = 0
    for r in fail:
        p = os.path.join(LIB, r['原文件'])
        base = os.path.splitext(os.path.basename(r['原文件']))[0]
        md_dir = os.path.join(LIB, r['库'], r['类别'], 'Markdown')
        os.makedirs(md_dir, exist_ok=True)
        md_path = os.path.join(md_dir, base + '.md')
        body = ''
        src = ''
        if os.path.exists(p):
            if p.endswith('.pdf'):
                body = pq.get(norm_title(r['标题']), '')
                src = '扫描PDF→HF快照回退'
            else:
                body = xml_text_md(p)
                src = 'docx直抽XML'
        if (not body or len(body.strip()) <= 100):
            body = pq.get(norm_title(r['标题']), '')
            src = 'HF快照回退'
        if body and len(body.strip()) > 100:
            if src == 'docx直抽XML':
                pass
            else:
                paras = [x.strip() for x in re.split(r'\n+', body) if x.strip()]
                body = '\n\n'.join(('**' + x + '**') if TIAO_HEAD.match(x) else x for x in paras)
                body += ('\n\n> 注：原文件为扫描版PDF或格式异常docx，正文取自 HuggingFace '
                         'twang2218/chinese-law-and-regulations 2023-09 快照。')
            meta = {'标题': r['标题'], '库': r['库'], '类别': r['类别'],
                    '机关': r['公布机关'], '公布日期': r['公布日期'],
                    '来源': r['来源'], '链接': r['原文链接']}
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_doc(meta, body))
            r['Markdown'] = os.path.relpath(md_path, LIB)
            # 专题目录补 md
            if r['专题']:
                for tp in r['专题'].split('、'):
                    td = os.path.join(LIB, '专题', f"{tp}法规", r['库'], r['类别'])
                    os.makedirs(td, exist_ok=True)
                    tmd = os.path.join(td, base + '.md')
                    if not os.path.exists(tmd):
                        import shutil
                        shutil.copy2(md_path, tmd)
            fixed += 1
        else:
            still += 1
            print('  仍缺:', r['标题'][:40])

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'修复 {fixed}, 仍缺 {still}')


if __name__ == '__main__':
    main()
