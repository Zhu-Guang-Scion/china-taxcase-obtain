# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""caseopen 判决书 JSONL → md 入库
输入：tmp/caseopen_all.jsonl（caseopen_harvest.py 产出，每行一案）
输出：lawlibrary/专题/税务案例/裁判文书网/<案由>/*.md
正文：full_text 去 HTML 标签 → 自然分段；front matter 带法院/案号/案由/日期。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import io, sys, os, re, json, html
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxcase_scrape as t

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", "caseopen_all.jsonl")
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例", "裁判文书网"))


def clean_fulltext(raw):
    txt = html.unescape(raw or "")
    txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.I)
    txt = re.sub(r"</(div|p)>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = txt.replace("\u3000", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n\s*\n+", "\n\n", txt)
    return txt.strip()


def main():
    n = dup = 0
    seen = set()
    for line in open(SRC, encoding="utf-8"):
        try:
            c = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = str(c.get("id") or c.get("doc_id") or c.get("case_id", ""))
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        cause = c.get("_cause", "未分类")
        out_dir = os.path.join(ROOT, cause)
        os.makedirs(out_dir, exist_ok=True)
        case_name = (c.get("case_name") or "未命名").strip()
        court = c.get("court") or ""
        case_id = c.get("case_id") or ""
        jd = (c.get("judgment_date") or "")[:10]
        body = clean_fulltext(c.get("full_text") or "")
        if len(body) < 200:
            continue  # 空文书跳过
        fm = ("---\n"
              f"title: \"{t.safe_filename(case_name, 70)}\"\n"
              f"来源机关: \"{court}\"\n"
              f"栏目: \"裁判文书（{cause}）\"\n"
              "地区: \"全国\"\n"
              f"发布日期: {jd}\n"
              f"原文来源: \"caseopen.org（裁判文书网社区镜像）\"\n"
              "抓取日期: 2026-10-10\n"
              f"原文链接: https://caseopen.org/\n"
              f"案号: \"{case_id}\"\n"
              f"审理程序: \"{c.get('procedure') or ''}\"\n"
              f"案件类型: \"{c.get('case_type') or ''}\"\n"
              "---\n\n")
        md = f"# {case_name}\n\n{body}\n"
        fname = t.safe_filename((jd or "nodate") + "_" + case_name) + ".md"
        fpath = os.path.join(out_dir, fname)
        if os.path.exists(fpath):
            continue
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(fm + md)
        n += 1
    print(f"written={n} dup={dup}")


if __name__ == "__main__":
    main()
