# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
最高人民法院 www.court.gov.cn 涉税案例抓取 adapter
====================================================
入口：
  - 站内搜索 GET /search.html?content=<kw>&page=<n>（每页~10条，可翻页）
  - 典型案例发布专栏 /zixun/gengduo/104.html（分页 104_N.html，共22页，TRS）
  - 公报 gongbao.court.gov.cn（http 可访问，https 挂；期刊目录为 POST /Home/PeriodicalsDic，
    参数 year/number → JSON，条目 md5_id 拼 /Details/{md5}.html）
探索结论：
  - court 站内 2022-2026 公报各期均无涉税案例条目（标题扫描，仅《增值税法》法条）。
  - 2025-11-24 最高法发布"依法惩治危害税收征管犯罪典型案例"（8件）：
    /zixun/xiangqing/482251.html（全文在发布稿内）
  - 2024-03-18 两高涉税典型案例仅在国新办发布会发布，两高官网无独立文章（已核实，未抓）。
文章页：TRS，正文容器命中通用回退链；标题去 " - 中华人民共和国最高人民法院" 后缀。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, sys, json
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import taxcase_scrape as t

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "最高人民法院")

TARGETS = [
    ("https://www.court.gov.cn/zixun/xiangqing/482251.html",
     "依法惩治危害税收征管犯罪典型案例", "依法惩治危害税收征管犯罪典型案例"),
    ("https://www.court.gov.cn/zixun/xiangqing/482341.html",
     "依法惩治危害税收征管犯罪典型案例", "典型案例解读"),
]

FOOTER_MARKS = ["责任编辑：", "Copyrights©", "京ICP备"]


def clean(md):
    for mark in FOOTER_MARKS:
        i = md.find(mark)
        if i != -1:
            md = md[:i]
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def main():
    prog_path = os.path.join(t.PROG_DIR, "court_cases.jsonl")
    done = set()
    if os.path.exists(prog_path):
        for line in open(prog_path, encoding="utf-8"):
            try:
                rec = json.loads(line)
                if rec.get("ok"):
                    done.add(rec["url"])
            except json.JSONDecodeError:
                pass
    prog = open(prog_path, "a", encoding="utf-8")
    n = 0
    for url, theme, category in TARGETS:
        if url in done:
            continue
        r = t.polite_get(url, delay=2.5, referer="https://www.court.gov.cn/")
        if r is None:
            prog.write(json.dumps({"url": url, "ok": False, "err": "fetch"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            continue
        d = t.extract_detail(r.text, url, "", "")
        if not d or len(d["md"]) < 100:
            prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            continue
        d["title"] = re.sub(r"\s*-\s*中华人民共和国最高人民法院\s*$", "", d["title"]).strip()
        d["md"] = clean(d["md"])
        out_dir = os.path.join(ROOT, theme)
        os.makedirs(out_dir, exist_ok=True)
        fname = t.safe_filename((d["date"] or "nodate") + "_" + d["title"]) + ".md"
        fpath = os.path.join(out_dir, fname)
        fm = ("---\n"
              f"title: \"{d['title'].replace(chr(34), '')}\"\n"
              f"来源机关: \"最高人民法院\"\n"
              f"栏目: \"{category}\"\n"
              f"地区: \"全国\"\n"
              f"发布日期: {d['date']}\n"
              f"原文来源: \"{d['source_org']}\"\n"
              f"抓取日期: {date.today().isoformat()}\n"
              f"原文链接: {url}\n"
              "---\n\n")
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(fm + d["md"] + "\n")
        prog.write(json.dumps({"url": url, "ok": True, "file": fname,
                               "title": d["title"], "date": d["date"]},
                              ensure_ascii=False) + "\n")
        prog.flush()
        n += 1
        print(f"[ok] {d['date']} {d['title'][:50]}")
    print(f"COURT DONE new={n}")


if __name__ == "__main__":
    main()
