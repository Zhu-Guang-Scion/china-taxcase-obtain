#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""规章库下载修复：扫描内容过薄的 docx，重提取(剥离style/script)或下载附件。

判定薄内容: docx 全文 < 500 中文字符 且 第X条 数 < 2
修复动作:
  1) 用已存 HTML 重新提取（新提取器剥离 style/script，可修 CSS 误匹配）
  2) 若仍薄：找页面附件链接(pdf/doc/docx/wps)，下载为 <名>_附件.<ext>，docx 保留为元数据存根并注明
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import glob
import json
import os
import random
import re
import sys
import time
from urllib.parse import urljoin

import requests

sys.path.insert(0, os.path.dirname(__file__))
import gov_download as gd

ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
GOV_DL = os.path.join(ROOT, "downloads", "gov")
TIAO_RE = re.compile(r"第[一二三四五六七八九十百千零\d]+条")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
ATT_RE = re.compile(r'href="([^"]+\.(?:pdf|docx?|wps)(?:\?[^"]*)?)"', re.I)


def docx_text_info(path):
    try:
        from docx import Document
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
        return len(CJK_RE.findall(text)), len(TIAO_RE.findall(text))
    except Exception:
        return 0, 0


def main():
    s = gd.make_session()
    repaired, att_saved, still_thin = 0, 0, []
    for cat in ["部门规章", "地方政府规章"]:
        d = os.path.join(GOV_DL, cat)
        files = sorted(glob.glob(os.path.join(d, "*.docx")))
        thin = []
        for fp in files:
            cjk, tiao = docx_text_info(fp)
            if cjk < 500 and tiao < 2:
                thin.append(fp)
        print(f"[{cat}] 薄文件 {len(thin)}/{len(files)}")
        prog_path = os.path.join(LISTS, f"gov_dl_progress_{cat}.jsonl")
        for fp in thin:
            base = os.path.splitext(os.path.basename(fp))[0]
            html_path = os.path.join(d, base + ".html")
            if not os.path.exists(html_path):
                still_thin.append(fp)
                continue
            html = open(html_path, encoding="utf-8").read()
            body = gd.extract_body(html) or gd.extract_body_generic(html)
            blocks = gd.body_to_blocks(body) if body else []
            cjk2 = sum(len(CJK_RE.findall(t)) for _, t in blocks)
            tiao2 = len(TIAO_RE.findall("".join(t for _, t in blocks)))
            if cjk2 >= 400 or tiao2 >= 2:
                # 重生成 docx
                title = base.split("_", 1)[1] if "_" in base else base
                meta = {"cat": cat, "org": "", "date": "", "doc_num": "", "url": ""}
                gd.make_docx(title, blocks, meta, fp)
                repaired += 1
                continue
            # 找附件
            atts = ATT_RE.findall(gd._STYLE_SCRIPT_RE.sub("", html))
            # 附件链接常在正文 div 内或紧邻
            saved_any = False
            for i, href in enumerate(atts[:6]):
                url = urljoin("https://www.gov.cn/", href)
                try:
                    r = s.get(url, timeout=60)
                    if r.status_code == 200 and len(r.content) > 3000:
                        ext = os.path.splitext(url.split("?")[0])[1][:5] or ".pdf"
                        apath = os.path.join(d, f"{base}_附件{i+1}{ext}")
                        with open(apath, "wb") as f:
                            f.write(r.content)
                        saved_any = True
                        att_saved += 1
                except Exception:
                    pass
                time.sleep(0.3 + random.random() * 0.4)
            if saved_any:
                with open(prog_path, "a", encoding="utf-8") as pf:
                    pf.write(json.dumps({"url": f"repair:{base}", "ok": True,
                                         "file": base + ".docx", "repaired": "attachment"},
                                        ensure_ascii=False) + "\n")
                repaired += 1
            else:
                still_thin.append(fp)
    print(f"修复重生成: {repaired}, 附件下载: {att_saved}, 仍薄: {len(still_thin)}")
    with open(os.path.join(ROOT, "verify", "thin_remaining.json"), "w", encoding="utf-8") as f:
        json.dump([os.path.basename(p) for p in still_thin], f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
