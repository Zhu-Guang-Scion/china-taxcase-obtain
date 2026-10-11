# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
财政部 会计信息质量检查公告/财会监督检查公告 抓取 adapter
============================================================
入口：监督评价局 jdjc.mof.gov.cn「工作通知及公告」栏目 /jianchagonggao/
  - TRS createPageHTML(11, 0, 'index', 'htm') → index_0.htm..index_10.htm（每页10条）
  - 详情 URL 形如 /jianchagonggao/YYYYMM/tYYYYMMDD_NNNNNNN.htm（**必须带月份目录**，
    列表页 href 是相对 ./YYYYMM/...，漏掉目录会落到"页面不存在"软404页）
范围：全部历年编号公告（第十号~第四十六号 会计信息质量检查公告、第四十七~五十二号
  财会监督检查公告=更名延续）+ "财政部发布XXXX年会计信息质量检查公告"新闻稿
  （内含编号公告全文，补齐缺失的35-40号）+ 德勤/普华永道/中兴财光华行政处罚决定。
  编号35-40号部分未在栏目中单列，由年度新闻稿覆盖。
输出目录：lawlibrary/专题/税务案例/财政部/会计信息质量检查公告/
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
ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例",
                            "财政部", "会计信息质量检查公告")
SEL_JSON = os.path.join(os.path.dirname(HERE), "tmp", "mof_sel.json")

FOOTER_MARKS = ["Copyright", "京ICP备", "网站地图", "主办单位：财政部办公厅", "热门检索"]


def clean(md):
    for mark in FOOTER_MARKS:
        i = md.find(mark)
        if i != -1:
            md = md[:i]
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def main():
    sel = json.load(open(SEL_JSON, encoding="utf-8"))
    # 剔除与涉税/会计信息质量无关项
    sel = {u: x for u, x in sel.items() if "中瑞" not in x}
    prog_path = os.path.join(t.PROG_DIR, "mof_checks.jsonl")
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
    os.makedirs(ROOT, exist_ok=True)
    n = 0
    for url in sorted(sel):
        title = sel[url]
        if url in done:
            continue
        m = re.search(r"/t(\d{8})_\d+\.htm$", url)
        url_date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else ""
        r = t.polite_get(url, delay=2.5, referer="http://jdjc.mof.gov.cn/jianchagonggao/")
        if r is None or "页面不存在" in r.text:
            prog.write(json.dumps({"url": url, "ok": False, "err": "fetch_or_dead"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            print("[dead]", url); continue
        d = t.extract_detail(r.text, url, title, url_date)
        if not d or len(d["md"]) < 100:
            prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            continue
        if not d["title"] or len(d["title"]) < 6:
            d["title"] = title
        d["title"] = re.sub(r"\s*[-_]\s*中华人民共和国财政部监督.*$", "", d["title"]).strip()
        d["md"] = clean(d["md"])
        if not d["date"]:
            d["date"] = url_date
        category = "会计信息质量检查公告"
        if "财会监督检查公告" in d["title"]:
            category = "财会监督检查公告"
        elif "行政处罚" in d["title"] or "答记者问" in d["title"]:
            category = "行政处罚决定"
        fname = t.safe_filename((d["date"] or "nodate") + "_" + d["title"]) + ".md"
        fpath = os.path.join(ROOT, fname)
        fm = ("---\n"
              f"title: \"{d['title'].replace(chr(34), '')}\"\n"
              f"来源机关: \"财政部\"\n"
              f"栏目: \"{category}\"\n"
              f"地区: \"全国\"\n"
              f"发布日期: {d['date']}\n"
              f"原文来源: \"{d['source_org']}\"\n"
              f"抓取日期: {date.today().isoformat()}\n"
              f"原文链接: {url}\n")
        if d["attachments"]:
            fm += "附件:\n" + "\n".join(f"  - {a}" for a in d["attachments"]) + "\n"
        fm += "---\n\n"
        with open(fpath, "w", encoding="utf-8", newline="\n") as f:
            f.write(fm + d["md"] + "\n")
        prog.write(json.dumps({"url": url, "ok": True, "file": fname,
                               "title": d["title"], "date": d["date"]},
                              ensure_ascii=False) + "\n")
        prog.flush()
        n += 1
        print(f"[ok] {d['date']} {d['title'][:45]}")
    print(f"MOF DONE new={n}")


if __name__ == "__main__":
    main()
