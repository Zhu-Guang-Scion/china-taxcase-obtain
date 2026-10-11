#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""乱码修复：按问题类型修复 docx(两处副本) + 重建 md + 同步专题。

- 控制字符 / PUA(U+E000-F8FF) / 锟斤拷残留: docx 内逐 run 清洗后重建 md
- U+FFFD: 优先用规章库 API 正文整体重建 docx；API 不可用则清洗 FFFD(按语境替换顿号/分号难以可靠推断, 直接剔除并留注)
- .doc/.pdf 源: 只修 md 文本本身
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB = os.path.abspath(os.path.join(ROOT, "..", "lawlibrary"))
WORK_GOV = os.path.join(ROOT, "downloads", "gov")
WORK_FLK = os.path.join(ROOT, "downloads", "flk")

PUA_RE = re.compile(r"[\ue000-\uf8ff]")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CJK = re.compile(r"[\u4e00-\u9fff]")


def clean_text(t):
    t = PUA_RE.sub("", t)
    t = CTRL_RE.sub("", t)
    t = t.replace("\ufffd", "")
    t = t.replace("锟斤拷", "").replace("锟斤", "").replace("斤拷", "")
    return t


def fix_docx_runs(path):
    """逐 run 清洗 docx，返回是否修改。"""
    from docx import Document
    doc = Document(path)
    changed = False
    for p in doc.paragraphs:
        for r in p.runs:
            if r.text and (PUA_RE.search(r.text) or CTRL_RE.search(r.text)
                           or "\ufffd" in r.text or "锟" in r.text):
                r.text = clean_text(r.text)
                changed = True
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        if r.text and (PUA_RE.search(r.text) or CTRL_RE.search(r.text)
                                       or "\ufffd" in r.text or "锟" in r.text):
                            r.text = clean_text(r.text)
                            changed = True
    if changed:
        doc.save(path)
    return changed


def rebuild_md_from_docx(manifest_row, lib_docx_path, md_path):
    from organize_md import to_md, md_doc
    body = to_md(lib_docx_path)
    meta = {'标题': manifest_row['标题'], '库': manifest_row['库'], '类别': manifest_row['类别'],
            '机关': manifest_row['公布机关'], '公布日期': manifest_row['公布日期'],
            '来源': manifest_row['来源'], '链接': manifest_row['原文链接']}
    body = clean_text(body)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_doc(meta, body))
    return len(body)


def main():
    d = json.load(open(os.path.join(ROOT, 'verify', 'mojibake_report.json'), encoding='utf-8'))
    flagged = d['flagged']
    manifest = []
    rows = list(csv.DictReader(open(os.path.join(LIB, 'manifest.csv'), encoding='utf-8-sig')))
    md_map = {}
    for r in rows:
        md_map[r['Markdown'].replace(chr(92), '/')] = r

    seen = set()
    fixed_docx = fixed_md_only = api_rebuilt = failed = 0
    for f in flagged:
        rel = f['file']
        if rel in seen:
            continue
        seen.add(rel)
        # 专题副本: 主库修好后统一同步, 此处跳过
        if rel.startswith('专题/'):
            continue
        row = md_map.get(rel)
        if not row:
            # 试试按文件名在对应类别 Markdown 目录定位(命名差异)
            continue
        lib_md = os.path.join(LIB, rel)
        lib_orig = os.path.join(LIB, row['原文件'])
        ext = os.path.splitext(lib_orig)[1].lower()
        issues = f['issues']

        # 规章库 + FFFD/锟斤拷 -> API 正文重建
        if row['库'] == '国家规章库' and ('U+FFFD' in issues or '锟斤拷' in issues):
            try:
                import gov_download as gd
                item = None
                for line in open(os.path.join(ROOT, 'lists', f"gov_{row['类别']}.jsonl"), encoding='utf-8'):
                    it = json.loads(line)
                    if it['url'] == row['原文链接']:
                        item = it
                        break
                if item:
                    c = gd.fetch_content_via_api(item)
                    if c and len(c) > 400:
                        import html as hl
                        text = hl.unescape(re.sub(r'<[^>]+>', '', c))
                        paras = [clean_text(p.strip()) for p in re.split(r'\n|　　', text) if p.strip()]
                        cjk = sum(1 for p in paras for ch in p if '\u4e00' <= ch <= '\u9fff')
                        if cjk > 300:
                            # 重建 work 副本与 lawlibrary 原文件
                            base = os.path.splitext(os.path.basename(row['原文件']))[0]
                            work_dir = os.path.join(WORK_GOV, row['类别'])
                            work_fp = os.path.join(work_dir, base + '.docx')
                            gd.make_docx(item['title'], [('p', p) for p in paras], item, work_fp)
                            if os.path.exists(lib_orig):
                                import shutil
                                shutil.copy2(work_fp, lib_orig)
                            n = rebuild_md_from_docx(row, lib_orig, lib_md)
                            with open(os.path.join(ROOT, 'lists', f"gov_dl_progress_{row['类别']}.jsonl"), 'a', encoding='utf-8') as pf:
                                pf.write(json.dumps({'url': item['url'], 'ok': True,
                                                     'file': os.path.basename(work_fp),
                                                     'source': 'api_content', 'repaired': 'mojibake'},
                                                    ensure_ascii=False) + '\n')
                            api_rebuilt += 1
                            continue
            except Exception as e:
                print('  API重建失败', rel[:50], e)

        # 通用: 清洗 docx 两处副本 + 重建 md
        if ext == '.docx':
            changed_any = False
            for fp in (lib_orig,):
                if os.path.exists(fp):
                    if fix_docx_runs(fp):
                        changed_any = True
            # work 源副本
            base = os.path.basename(row['原文件'])
            for wd in (WORK_GOV, WORK_FLK):
                wfp = os.path.join(wd, row['类别'], base)
                if os.path.exists(wfp) and fix_docx_runs(wfp):
                    pass
            if changed_any or os.path.exists(lib_orig):
                try:
                    n = rebuild_md_from_docx(row, lib_orig, lib_md)
                    if n > 50:
                        fixed_docx += 1
                        continue
                except Exception as e:
                    print('  md重建失败', rel[:50], e)
        # .doc/.pdf 源: 只清 md
        try:
            t = open(lib_md, encoding='utf-8').read()
            t2 = clean_text(t)
            if t2 != t:
                open(lib_md, 'w', encoding='utf-8').write(t2)
                fixed_md_only += 1
                continue
        except Exception:
            pass
        failed += 1

    # 同步专题副本(重新从主库md复制)
    import shutil
    synced = 0
    for f in flagged:
        rel = f['file']
        if not rel.startswith('专题/'):
            continue
        parts = rel.split('/')
        if len(parts) < 6:
            continue
        main_rel = '/'.join([parts[2], parts[3], 'Markdown', parts[-1]])
        main_fp = os.path.join(LIB, main_rel)
        if os.path.exists(main_fp):
            shutil.copy2(main_fp, os.path.join(LIB, rel))
            synced += 1

    print(f'修复: docx清洗+md重建 {fixed_docx}, API重建 {api_rebuilt}, 仅md清洗 {fixed_md_only}, 失败 {failed}, 专题同步 {synced}')


if __name__ == '__main__':
    main()
