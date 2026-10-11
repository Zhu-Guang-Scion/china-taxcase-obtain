# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
最高人民检察院 www.spp.gov.cn 涉税案例抓取 adapter
====================================================
入口：
  - 典型案例专栏 /spp/zgjdxal/index.shtml（TRS createPageHTML 分页 index_N.shtml）
  - 网上发布厅 /spp/wsfbt/index.shtml（同构分页）
  - 指导性案例 /spp/jczdal/index.shtml（按批发布，整批一个页面）
发现方式：全量枚举列表 → 标题/正文含税关键词过滤（见 TARGETS，人工核定）。
文章页结构：TRS，正文容器命中通用回退链；标题需去 "_中华人民共和国最高人民检察院" 后缀，
页脚版权/备案行需裁剪。
已知坑：
  - 不存在的旧文（如第二十二批 t20201208_488360）服务器 302 到首页而非 404，
    表现为返回 67KB 首页 —— 以 title 判别。
  - 站内搜索 /guestweb/s?siteCode=N000005434&searchWord= 实测不按关键词过滤，无用。
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
ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "最高人民检察院")

# (url, 主题目录, 栏目)  —— 人工核定的涉税目标
TARGETS = [
    # 依法惩治涉税犯罪典型案例
    ("https://www.spp.gov.cn/xwfbh/wsfbt/202408/t20240823_663858.shtml",
     "依法惩治涉税犯罪典型案例", "依法惩治骗取出口退税犯罪典型案例"),
    ("https://www.spp.gov.cn/spp/xwfbh/wsfbh/202206/t20220617_560088.shtml",
     "依法惩治涉税犯罪典型案例", "六部门打击骗取留抵退税案件公布"),
    # 涉税检察公益诉讼
    ("https://www.spp.gov.cn/xwfbh/wsfbt/202607/t20260723_732545.shtml",
     "涉税检察公益诉讼", "成品油涉税专项监督"),
    ("https://www.spp.gov.cn/xwfbh/wsfbt/201703/t20170323_186100.shtml",
     "涉税检察公益诉讼", "行政公益诉讼"),
    ("https://www.spp.gov.cn/xwfbh/wsfbt/201701/t20170124_179527.shtml",
     "涉税检察公益诉讼", "行政公益诉讼"),
    ("https://www.spp.gov.cn/xwfbh/wsfbt/201701/t20170123_179471.shtml",
     "涉税检察公益诉讼", "行政公益诉讼"),
    # 指导性案例（整批，含检例第183号 成品油税收监管）
    ("https://www.spp.gov.cn/spp/jczdal/202308/t20230803_623811.shtml",
     "指导性案例", "指导性案例"),
]

FOOTER_MARKS = [
    "Copyrights©", "未经本网书面授权", "为了获得更好的使用",
    "备案序号：京ICP备", "最高人民检察院 （100726）",
]


def clean(md):
    # 按页脚标记整段裁剪
    for mark in FOOTER_MARKS:
        i = md.find(mark)
        if i != -1:
            md = md[:i]
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md


def main():
    prog_path = os.path.join(t.PROG_DIR, "spp_cases.jsonl")
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
        m = re.search(r"/t(\d{8})_\d+\.shtml", url)
        url_date = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else ""
        r = t.polite_get(url, delay=2.5, referer="https://www.spp.gov.cn/")
        if r is None:
            prog.write(json.dumps({"url": url, "ok": False, "err": "fetch"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            continue
        # 死链 302 到首页的判别
        tm = re.search(r"<title>([^<]*)</title>", r.text)
        if tm and tm.group(1).strip() == "中华人民共和国最高人民检察院":
            prog.write(json.dumps({"url": url, "ok": False, "err": "redirect_home"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            print("[dead->home]", url); continue
        d = t.extract_detail(r.text, url, "", url_date)
        if not d or len(d["md"]) < 100:
            prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                  ensure_ascii=False) + "\n"); prog.flush()
            continue
        d["title"] = re.sub(r"_中华人民共和国最高人民检察院\s*$", "", d["title"]).strip()
        d["md"] = clean(d["md"])
        if not d["date"]:
            d["date"] = url_date
        out_dir = os.path.join(ROOT, theme)
        os.makedirs(out_dir, exist_ok=True)
        fname = t.safe_filename((d["date"] or "nodate") + "_" + d["title"]) + ".md"
        fpath = os.path.join(out_dir, fname)
        fm = ("---\n"
              f"title: \"{d['title'].replace(chr(34), '')}\"\n"
              f"来源机关: \"最高人民检察院\"\n"
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
        print(f"[ok] {d['date']} {d['title'][:45]} -> {theme}/{fname[:40]}")
    print(f"SPP DONE new={n}")


if __name__ == "__main__":
    main()
