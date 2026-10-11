#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""用 lawtext/regulations md（bbbs 命名）转 docx 补齐地方法规缺口。

- 只处理 flk_地方法规.jsonl 中 sxx=3 且尚未 ok 的条目
- md 解析: front matter(id/title/date/status) + 正文
- 输出命名与官方下载一致, 进度记 source=lawtext_md
- 之后可用 mirror_fill/官方下载升级覆盖（upgrade 逻辑见文件尾注释）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from docx import Document

ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
DL_ROOT = os.path.join(ROOT, "downloads", "flk")
MIRRORS = os.path.abspath(os.path.join(ROOT, "..", "mirrors"))
REGS = os.path.join(MIRRORS, "regulations", "content")
SXX_MAP = {3: "有效"}


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name.strip().rstrip(".")[:100] or "unnamed"


FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def parse_md(path):
    text = open(path, encoding="utf-8").read()
    fm = {}
    m = FM_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"^(\w+):\s*(.*)$", line)
            if mm:
                v = mm.group(2).strip().strip("'\"")
                # urls 列表跳过
                if mm.group(1) in ("urls",):
                    continue
                fm[mm.group(1)] = v
        body = text[m.end():]
    else:
        body = text
    # md -> 纯文本段落
    body = re.sub(r"^#!.*$", "", body, flags=re.M)
    body = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", body) if p.strip()]
    return fm, paras


def make_docx(title, paras, meta, fpath):
    doc = Document()
    doc.add_heading(title, level=1)
    m = [f"{k}：{v}" for k, v in
         [("类别", meta.get("cat", "")), ("公布机关", meta.get("zdjgName", "")),
          ("公布日期", meta.get("gbrq", "")), ("来源", "lawtext/regulations镜像")] if v]
    p = doc.add_paragraph(" ｜ ".join(m))
    for run in p.runs:
        run.italic = True
    for t in paras:
        if not t:
            continue
        para = doc.add_paragraph()
        r = para.add_run(t)
        if re.match(r"^第[一二三四五六七八九十百千零\d]+[条章节编]", t):
            r.bold = True
    doc.save(fpath)


def main():
    md_index = {}
    for p in glob.glob(os.path.join(REGS, "**", "*.md"), recursive=True):
        md_index[os.path.splitext(os.path.basename(p))[0]] = p
    print("md 索引:", len(md_index))

    cat = "地方法规"
    items = [json.loads(l) for l in open(os.path.join(LISTS, f"flk_{cat}.jsonl"), encoding="utf-8") if l.strip()]
    prog_path = os.path.join(LISTS, f"flk_dl_progress_{cat}.jsonl")
    done = {}
    if os.path.exists(prog_path):
        for line in open(prog_path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    done[rec["bbbs"]] = rec.get("ok", False)
                except Exception:
                    pass

    out_dir = os.path.join(DL_ROOT, cat)
    os.makedirs(out_dir, exist_ok=True)
    filled = 0
    no_md = 0
    thin = 0
    with open(prog_path, "a", encoding="utf-8") as pf:
        for it in items:
            bbbs = it["bbbs"]
            if done.get(bbbs):
                continue
            src = md_index.get(bbbs)
            if not src:
                no_md += 1
                continue
            fm, paras = parse_md(src)
            cjk = sum(1 for t in paras for ch in t if "\u4e00" <= ch <= "\u9fff")
            if cjk < 200 or len(paras) < 3:
                thin += 1
                continue
            name = sanitize(f"{it.get('flxz') or cat}_{it['title']}_{it.get('gbrq','')}_有效")
            fpath = os.path.join(out_dir, name + ".docx")
            n = 1
            while os.path.exists(fpath) and os.path.getsize(fpath) < 2000 and n < 5:
                fpath = os.path.join(out_dir, f"{name}_{n}.docx")
                n += 1
            if not (os.path.exists(fpath) and os.path.getsize(fpath) > 2000):
                make_docx(it["title"], paras, it, fpath)
            if os.path.getsize(fpath) > 2000:
                pf.write(json.dumps({"bbbs": bbbs, "ok": True,
                                     "file": os.path.basename(fpath),
                                     "source": "lawtext_md", "bytes": os.path.getsize(fpath)},
                                    ensure_ascii=False) + "\n")
                filled += 1
    print(f"[{cat}] md补齐 {filled}, 无md {no_md}, 内容过薄 {thin}, 清单共 {len(items)}")


if __name__ == "__main__":
    main()
