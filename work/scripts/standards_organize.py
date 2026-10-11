#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""会计准则与执业准则：整理 + md 转换 + manifest。

输入: work/lists/standards_<子集>.jsonl (子代理产出) + work/downloads/standards/<子集>/
输出: lawlibrary/会计准则与执业准则/<子集>/{原文件,Markdown}/ + manifest.csv
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from organize_md import to_md, md_doc  # noqa: E402
from xmlfallback import docx_xml_fallback  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LISTS = os.path.join(ROOT, "lists")
STD = os.path.join(ROOT, "downloads", "standards")
LIB = os.path.abspath(os.path.join(ROOT, "..", "lawlibrary", "会计准则与执业准则"))

CJK = re.compile(r"[\u4e00-\u9fff]")


def norm_meta(r, subset):
    return {
        "标题": r.get("title", ""),
        "库": "会计准则与执业准则",
        "类别": subset,
        "机关": r.get("org", "") or ("中国注册会计师协会" if subset == "执业准则" else "财政部"),
        "公布日期": r.get("date", ""),
        "文号": r.get("doc_no", ""),
        "来源": r.get("source", ""),
        "链接": r.get("url", ""),
    }


def md_doc_std(meta, body):
    fm = [f"{k}: {v}" for k, v in
          [("title", meta["标题"]), ("库", "会计准则与执业准则"), ("类别", meta["类别"]),
           ("发布机关", meta["机关"]), ("文号", meta["文号"]), ("日期", meta["公布日期"]),
           ("时效性", "现行有效"), ("来源", meta["来源"]), ("链接", meta["链接"])] if v]
    return "---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n"


def safe(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip().rstrip(".")
    return name[:100] or "unnamed"


def main():
    rows_out = []
    lists = [p for p in sorted(glob.glob(os.path.join(LISTS, "standards_*.jsonl")))
             if "dl_progress" not in os.path.basename(p)]
    for lp in lists:
        subset = os.path.basename(lp)[len("standards_"):-len(".jsonl")]
        src_dir = os.path.join(STD, subset)
        orig_dir = os.path.join(LIB, subset, "原文件")
        md_dir = os.path.join(LIB, subset, "Markdown")
        os.makedirs(orig_dir, exist_ok=True)
        os.makedirs(md_dir, exist_ok=True)
        recs = {}
        for line in open(lp, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    r = json.loads(line)
                    recs[(r.get("url", ""), r.get("file", ""), r.get("title", ""))] = r
                except Exception:
                    pass
        # 磁盘全索引(含子目录), 供 file 字段解析
        disk_index = {}
        for fp in glob.glob(os.path.join(src_dir, "**", "*.*"), recursive=True):
            disk_index[os.path.basename(fp)] = fp
        n_ok = n_md = 0
        for key, r in recs.items():
            if not r.get("file"):
                rows_out.append({**norm_meta(r, subset), "状态": "未下载", "原文件": "", "Markdown": ""})
                continue
            src = os.path.join(src_dir, r["file"])
            if not os.path.exists(src):
                src = disk_index.get(os.path.basename(r["file"]), src)
            if not os.path.exists(src):
                rows_out.append({**norm_meta(r, subset), "状态": "文件缺失", "原文件": r["file"], "Markdown": ""})
                continue
            meta = norm_meta(r, subset)
            base = safe(f"{r['file']}".rsplit(".", 1)[0])
            ext = "." + r["file"].rsplit(".", 1)[1]
            dst = os.path.join(orig_dir, base + ext)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
            n_ok += 1
            # md
            md_path = os.path.join(md_dir, base + ".md")
            body = ""
            try:
                body = to_md(src)
            except Exception:
                body = ""
            if (not body or len(body.strip()) <= 100) and ext.lower() in (".docx", ".doc"):
                body = docx_xml_fallback(src)
            if body and len(body.strip()) > 100:
                if not os.path.exists(md_path):
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_doc_std(meta, body))
                n_md += 1
                md_rel = os.path.relpath(md_path, os.path.dirname(LIB))
            else:
                md_rel = ""
            rows_out.append({
                **{k: meta[k] for k in ("标题", "类别", "机关", "公布日期", "文号", "来源", "链接")},
                "时效性": "现行有效",
                "状态": "已入库",
                "原文件": os.path.relpath(dst, os.path.dirname(LIB)),
                "Markdown": os.path.relpath(md_path, os.path.dirname(LIB)) if md_rel else "",
            })
        print(f"[{subset}] 清单{len(recs)} 入库{n_ok} md{n_md}")

    os.makedirs(LIB, exist_ok=True)
    fields = ["标题", "类别", "机关", "公布日期", "文号", "时效性", "状态", "来源", "原文件", "Markdown", "链接"]
    with open(os.path.join(LIB, "manifest.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)
    ok = sum(1 for r in rows_out if r.get("状态") == "已入库")
    md = sum(1 for r in rows_out if r.get("Markdown"))
    print(f"总: 条目{len(rows_out)} 入库{ok} md{md} -> {os.path.join(LIB, 'manifest.csv')}")


if __name__ == "__main__":
    main()
