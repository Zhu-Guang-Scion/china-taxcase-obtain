#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""MinerU OCR 升级：把 HF快照回退md 的 PDF 换成对官方扫描件的真 OCR md。

- 逐件: 临时副本(干净文件名) -> mineru-open-api extract(pipeline, ch) -> 校验 -> 入库
- 校验: OCR中文字数/条数 与 原快照md 相当(0.55~1.8倍, 条数差<=3或比例0.5+) 才替换
- 断点: work/lists/mineru_ocr_progress.json
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time

# 可移植化（审查修复）：mineru CLI 支持环境变量 MINERU_CLI 覆盖，回退 PATH 查找
CLI = os.environ.get("MINERU_CLI", shutil.which("mineru-open-api") or "mineru-open-api")
# Token 从环境变量读取：MINERU_TOKEN（单个）或 MINERU_TOKENS（逗号分隔多个轮换）
TOKENS = [t for t in os.environ.get("MINERU_TOKENS", "").split(",") if t] or \
         [os.environ["MINERU_TOKEN"] for _ in [1] if os.environ.get("MINERU_TOKEN")]
if not TOKENS:
    sys.exit("请设置 MINERU_TOKEN 或 MINERU_TOKENS 环境变量（本仓库不内置密钥）")
ROOT = os.path.join(os.path.dirname(__file__), '..')
PROG = os.path.join(ROOT, 'lists', 'mineru_ocr_progress.json')
TIAO = re.compile(r'第[一二三四五六七八九十百千零\d]+条')
CJK = re.compile(r'[\u4e00-\u9fff]')


def stats(text):
    return len(CJK.findall(text)), len(TIAO.findall(text))


def to_md_body(raw):
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith('#'):
            t = ln.lstrip('# ').strip()
            if t:
                lines.append(('**' + t + '**') if TIAO.match(t) else t)
        elif TIAO.match(ln):
            lines.append('**' + ln + '**')
        else:
            lines.append(ln)
    return '\n\n'.join(lines)


def md_doc(meta, body):
    fm = [f"{k}: {v}" for k, v in
          [('title', meta['标题']), ('库', meta['库']), ('类别', meta['类别']),
           ('公布机关', meta['公布机关']), ('公布日期', meta['公布日期']),
           ('时效性', '现行有效'), ('来源', 'MinerU OCR(pipeline)'), ('原文链接', meta['原文链接'])] if v]
    return '---\n' + '\n'.join(fm) + '\n---\n\n' + body + '\n'


def run_mineru(pdf_path, out_dir, token):
    env = dict(os.environ)
    env['MINERU_TOKEN'] = token
    r = subprocess.run([CLI, 'extract', pdf_path, '-o', out_dir, '-f', 'md',
                        '--model', 'pipeline', '--language', 'ch'],
                       capture_output=True, timeout=1200, env=env)
    md = os.path.join(out_dir, os.path.splitext(os.path.basename(pdf_path))[0] + '.md')
    if os.path.exists(md):
        return open(md, encoding='utf-8').read()
    err = (r.stderr or b'').decode('utf-8', errors='replace')
    raise RuntimeError(err[-200:] or 'no output')


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, '..', 'lawlibrary', 'manifest.csv'), encoding='utf-8-sig')))
    prog = json.load(open(PROG, encoding='utf-8')) if os.path.exists(PROG) else {}

    targets = []
    for r in rows:
        if not r['原文件'].lower().endswith('.pdf') or not r['Markdown']:
            continue
        mp = os.path.join(ROOT, '..', 'lawlibrary', r['Markdown'])
        if os.path.exists(mp) and ('快照' in open(mp, encoding='utf-8').read()[-500:] or
                                   'HuggingFace' in open(mp, encoding='utf-8').read()[-500:]):
            targets.append(r)
    print(f'待升级 {len(targets)}', flush=True)

    upgraded = kept = failed = 0
    ti = 0
    for i, r in enumerate(targets):
        key = r['原文链接']
        if prog.get(key, {}).get('done'):
            continue
        src_pdf = os.path.join(ROOT, '..', 'lawlibrary', r['原文件'])
        old_md = os.path.join(ROOT, '..', 'lawlibrary', r['Markdown'])
        old_text = open(old_md, encoding='utf-8').read()
        old_cjk, old_tiao = stats(old_text)

        tmp_dir = os.path.join(ROOT, 'mineru_tmp', f'u{i}')
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_pdf = os.path.join(tmp_dir, 'doc.pdf')
        shutil.copy2(src_pdf, tmp_pdf)
        ok = False
        raw = ''
        for attempt in range(3):
            try:
                raw = run_mineru(tmp_pdf, tmp_dir, TOKENS[(ti + attempt) % len(TOKENS)])
                if len(raw.strip()) > 100:
                    ok = True
                    ti += attempt
                    break
            except Exception as e:
                print(f'  retry {attempt} {r["标题"][:25]}: {str(e)[:80]}', flush=True)
                time.sleep(5)
        if not ok:
            prog[key] = {'done': False, 'error': 'mineru failed'}
            failed += 1
            _save(prog)
            continue

        body = to_md_body(raw)
        new_cjk, new_tiao = stats(body)
        # 校验: 与快照文本量级相当
        ratio = new_cjk / max(old_cjk, 1)
        tiao_ok = abs(new_tiao - old_tiao) <= 3 or (new_tiao >= old_tiao * 0.5 and new_tiao > 0) or old_tiao == 0
        if 0.55 <= ratio <= 1.8 and tiao_ok:
            meta = {'标题': r['标题'], '库': r['库'], '类别': r['类别'], '公布机关': r['公布机关'],
                    '公布日期': r['公布日期'], '原文链接': r['原文链接']}
            body_full = body + ('\n\n> 注：本文件原为扫描版PDF，正文由 MinerU OCR 识别'
                                '（mineru.net pipeline 模型），以官方原 PDF 为准。')
            with open(old_md, 'w', encoding='utf-8') as f:
                f.write(md_doc(meta, body_full))
            if r['专题']:
                for tp in r['专题'].split('、'):
                    td = os.path.join(ROOT, '..', 'lawlibrary', '专题', f'{tp}法规', r['库'], r['类别'])
                    base = os.path.splitext(os.path.basename(r['原文件']))[0].rstrip('_')
                    tmd = os.path.join(td, base + '.md')
                    if os.path.exists(tmd):
                        shutil.copy2(old_md, tmd)
            r['来源'] = 'MinerU OCR(pipeline)'
            prog[key] = {'done': True, 'ocr_cjk': new_cjk, 'snapshot_cjk': old_cjk}
            upgraded += 1
            print(f'  ✓ [{i+1}] {r["标题"][:32]} | ocr {new_cjk} vs 快照 {old_cjk} 字, 条 {new_tiao}/{old_tiao}', flush=True)
        else:
            prog[key] = {'done': False, 'kept_snapshot': True, 'ratio': round(ratio, 2),
                         'ocr_tiao': new_tiao, 'old_tiao': old_tiao}
            kept += 1
            print(f'  = [{i+1}] 保留快照 {r["标题"][:30]} | 比率{ratio:.2f} 条{new_tiao}/{old_tiao}', flush=True)
        _save(prog)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        time.sleep(1)

    with open(os.path.join(ROOT, '..', 'lawlibrary', 'manifest.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'结束: OCR升级 {upgraded}, 保留快照 {kept}, 失败 {failed}')


def _save(prog):
    with open(PROG, 'w', encoding='utf-8') as f:
        json.dump(prog, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
