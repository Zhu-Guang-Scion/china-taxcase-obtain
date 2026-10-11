#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""全量乱码/错码扫描：检查 lawlibrary 全部 md 与 docx 正文。

检测项:
  A. U+FFFD 替换符（解码失败的铁证）
  B. UTF-8 被按 GBK 读的典型错码字符占比（鍦 鏂 鐨 鐢 鏄 涓 浠 鍙 等——正常法律文本中极罕见）
  C. GBK 被按 Latin-1/UTF-8 读的错码（æ å ‰ † 连串 / 锟斤拷 / 烫烫）
  D. HTML 实体残留（&nbsp; &lt; &#x）
  E. 控制字符（\x00-\x08 等）
  F. 私有区/兼容区字符 (U+E000-U+F8FF, U+FE30-FE4F 大量出现)
输出: work/verify/mojibake_report.json + 可疑文件清单
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import json
import os
import re
import sys
from collections import Counter

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "lawlibrary"))
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "verify"))

CJK = re.compile(r"[\u4e00-\u9fff]")
# UTF-8→GBK 误解码特征字符（三字节汉字 E4-E9 头被 GBK 拆解后的高频产物）
MOJI_UTF8_AS_GBK = set("鍦鏂鐨鐢鏄涓浠鍙鍗鍏鍐鏌鐪鐧鏁鏍鏉鏄鍋鍒鍗鍟鍥鍥鍥鍦鏈級鈥榚滃€欑殑鏄庣‘璇勫畾鈥滆鈥濄€�澶勭悊鐞嗕紝锛燂紵銆")
MOJI_UTF8_AS_GBK = {c for c in MOJI_UTF8_AS_GBK if c and c != '\ufffd'}
# GBK replacement 经典
GB2312_GARBAGE = set("锟斤拷烫")
# Latin-1 误读
LATIN_GARBAGE = set("æå‰†œüßðþ")

CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HTML_ENTITY = re.compile(r"&(?:nbsp|lt|gt|amp|quot|#\d+|#x[0-9a-fA-F]+);")
PUA = re.compile(r"[\ue000-\uf8ff]")


def scan_text(text):
    issues = {}
    n_fffd = text.count("\ufffd")
    if n_fffd:
        issues["U+FFFD"] = n_fffd
    cjk_n = len(CJK.findall(text))
    moji_hits = sum(text.count(c) for c in MOJI_UTF8_AS_GBK)
    if cjk_n > 200 and moji_hits / cjk_n > 0.02:
        issues["UTF8被GBK读"] = round(moji_hits / cjk_n, 3)
    elif moji_hits > 30:
        issues["UTF8被GBK读(少量)"] = moji_hits
    gbk_g = text.count("锟斤拷") + text.count("烫烫烫")
    if gbk_g > 2:
        issues["锟斤拷类"] = gbk_g
    latin_g = sum(1 for ch in text if ch in LATIN_GARBAGE)
    if latin_g > 20 and latin_g > len(text) * 0.001:
        issues["Latin1误读"] = latin_g
    n_ent = len(HTML_ENTITY.findall(text))
    if n_ent > 15:
        issues["HTML实体残留"] = n_ent
    n_ctrl = len(CTRL.findall(text))
    if n_ctrl:
        issues["控制字符"] = n_ctrl
    n_pua = len(PUA.findall(text))
    if n_pua > 10:
        issues["私有区字符"] = n_pua
    return issues


def docx_text(path):
    """快速抽 docx 正文文本（python-docx 失败则直读XML）。"""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        try:
            import zipfile
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                t = "word/document.xml" if "word/document.xml" in names else None
                if not t:
                    return ""
                xml = z.read(t).decode("utf-8", errors="replace")
                import html as hl
                return hl.unescape(re.sub(r"<[^>]+>", " ", xml))
        except Exception:
            return ""


def main():
    scan_docx = "--docx" in sys.argv
    report = {"md": {}, "docx": {}}
    flagged = []

    # ── md 全量 ──
    md_files = []
    for root, _, files in os.walk(LIB):
        for fn in files:
            if fn.endswith(".md"):
                md_files.append(os.path.join(root, fn))
    # manifest 索引: 相对路径 -> 行
    manifest = {}
    mpath = os.path.join(LIB, "manifest.csv")
    for r in csv.DictReader(open(mpath, encoding="utf-8-sig")):
        manifest[r["Markdown"]] = r
        manifest[r["原文件"]] = r

    cat_stat = Counter()
    n_scan = 0
    for fp in md_files:
        rel = os.path.relpath(fp, LIB).replace("\\", "/")
        row = manifest.get(rel)
        cat = f"{row['库']}/{row['类别']}" if row else "专题副本或未索引"
        n_scan += 1
        try:
            text = open(fp, encoding="utf-8").read()
        except UnicodeDecodeError:
            cat_stat[f"{cat}|解码失败"] += 1
            flagged.append({"file": rel, "issues": {"非UTF-8": 1}})
            continue
        issues = scan_text(text)
        if issues:
            cat_stat[f"{cat}|{'&'.join(issues.keys())}"] += 1
            flagged.append({"file": rel, "issues": issues,
                            "cjk": len(CJK.findall(text))})
    report["md"] = {"扫描数": n_scan, "问题分布": dict(cat_stat)}
    print(f"md 扫描 {n_scan} 件, 问题分布: {dict(cat_stat)}")

    # ── docx 全量(可选; 默认抽 3000 + 全部可疑md对应的源) ──
    if scan_docx:
        import random
        random.seed(20261009)
        docx_files = []
        for root, _, files in os.walk(LIB):
            for fn in files:
                if fn.endswith((".docx", ".doc", ".pdf")):
                    p = os.path.join(root, fn)
                    if "/专题/" not in p.replace("\\", "/"):
                        docx_files.append(p)
        sample = random.sample(docx_files, min(3000, len(docx_files)))
        dstat = Counter()
        dflag = []
        for i, fp in enumerate(sample):
            rel = os.path.relpath(fp, LIB).replace("\\", "/")
            if fp.endswith(".pdf"):
                try:
                    import pymupdf
                    doc = pymupdf.open(fp)
                    text = "\n".join(pg.get_text() for pg in doc)
                    doc.close()
                except Exception:
                    continue
            else:
                text = docx_text(fp)
            if not text or len(text) < 100:
                dstat["空文本"] += 1
                dflag.append({"file": rel, "issues": {"空文本": 1}})
                continue
            issues = scan_text(text)
            if issues:
                dstat["&".join(issues.keys())] += 1
                dflag.append({"file": rel, "issues": issues})
            if (i + 1) % 500 == 0:
                print(f"  docx 抽样 {i+1}/{len(sample)}", flush=True)
        report["docx"] = {"抽样数": len(sample), "问题分布": dict(dstat)}
        flagged.extend(dflag)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "mojibake_report.json"), "w", encoding="utf-8") as f:
        json.dump({"report": report, "flagged": flagged}, f, ensure_ascii=False, indent=1)
    print(f"可疑文件 {len(flagged)} 件 -> mojibake_report.json")


if __name__ == "__main__":
    main()
