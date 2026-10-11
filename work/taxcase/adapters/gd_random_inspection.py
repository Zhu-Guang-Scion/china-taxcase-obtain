# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
广东省 双随机/随机抽查公示 补抓 adapter（扩源 round2）
====================================================
来源：省站 search5 全文检索（gd_cases.iter_search 复用），关键词 随机抽查/双随机。
URL 多在 /gdsw/ssjygkgzdt/（执法公开工作动态）、/gdsw/SSJYGK/、/gdsw/gongzuoqingkuang001/
（行政执法公示平台新闻化页面）——与已知空壳 JSP 不同，这些是 TRS shtml 静态页，可抓。

只取 2023-01-01 后、标题含 抽查 的 公示/结果 类；排除政策文件（管理办法/实施方案/名录库）与
工作计划。按标题中的市名归类到 广东省/<市名>/随机抽查公示/，无市名归 广东省/随机抽查公示/。

用法: python gd_random_inspection.py [--dry]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import argparse
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "adapters"))
import taxcase_scrape as t  # noqa: E402
from gd_cases import iter_search, clean_md, GD_HOST  # noqa: E402

JOB_ID = "gd_random_inspection"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT_ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "广东省")
DATE_FROM = "2023-01-01"
TITLE_EXCLUDE = re.compile(
    r"管理办法|实施方案|名录库|工作计划|跨部门联合|事项清单|国务院办公厅|转发的通知|"
    r"印发《|转发国家税务总局")

CITY_RE = re.compile(r"(广州|韶关|深圳|珠海|汕头|佛山|江门|湛江|茂名|肇庆|惠州|梅州|汕尾|"
                     r"河源|阳江|清远|东莞|中山|潮州|揭阳|云浮)市")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    queue = {}
    for term in ["随机抽查 结果公示", "双随机", "随机抽查事项的公示"]:
        for u, ti, d in iter_search(term):
            ti = re.sub(r"<[^>]+>", "", ti or "").strip()
            if not u.startswith("https://guangdong.chinatax.gov.cn/"):
                continue
            if "随机抽查" not in ti and "双随机" not in ti:
                continue
            if TITLE_EXCLUDE.search(ti):
                continue
            if d and d < DATE_FROM:
                continue
            queue.setdefault(u, (ti, d))
        print(f"[list] {term}: cum {len(queue)}")

    print("[list] total:", len(queue))
    if args.dry:
        for u, (ti, d) in sorted(queue.items(), key=lambda x: x[1][1] or ""):
            print(f"[dry] {d} {ti[:60]}")
        return

    # 与省轮/市轮 progress 去重
    done = set()
    for pj in ("gd_cases.jsonl", "gd_city_cases.jsonl"):
        p = os.path.join(t.PROG_DIR, pj)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if rec.get("url") and rec.get("ok"):
                        done.add(rec["url"].replace("http://", "https://"))
    prog_path = os.path.join(t.PROG_DIR, JOB_ID + ".jsonl")
    n_new = n_fail = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        for u, (ti, d) in sorted(queue.items(), key=lambda x: x[1][1] or ""):
            uhttps = u.replace("http://", "https://")
            if uhttps in done:
                n_skip += 1
                continue
            r = t.polite_get(uhttps, 2.6, referer=GD_HOST + "/")
            d_art = t.extract_detail(r.text, uhttps, ti, d) if r is not None else None
            if not d_art or len(d_art.get("md") or "") < 80:
                prog.write(json.dumps({"url": uhttps, "ok": False, "err": "fetch/parse",
                                       "title": ti}, ensure_ascii=False) + "\n")
                prog.flush()
                n_fail += 1
                continue
            title = d_art["title"] or ti
            pd = d_art["date"] or d
            m = CITY_RE.search(title)
            sub = (m.group(1) + "市") if m else ""
            out_dir = os.path.join(OUT_ROOT, sub, "随机抽查公示") if sub else \
                os.path.join(OUT_ROOT, "随机抽查公示")
            os.makedirs(out_dir, exist_ok=True)
            org = ("国家税务总局" + sub + "税务局") if sub else "国家税务总局广东省税务局"
            fname = t.safe_filename((pd or "nodate") + "_" + title) + ".md"
            fm = ("---\n"
                  f"title: \"{title.replace(chr(34), '')}\"\n"
                  f"来源机关: \"{org}\"\n"
                  "栏目: \"随机抽查公示\"\n"
                  "地区: \"广东省\"\n"
                  f"发布日期: {pd or ''}\n"
                  f"原文来源: \"{d_art.get('source_org') or ''}\"\n"
                  f"抓取日期: {date.today().isoformat()}\n"
                  f"原文链接: {uhttps}\n---\n\n")
            with open(os.path.join(out_dir, fname), "w", encoding="utf-8", newline="\n") as f:
                f.write(fm + clean_md(d_art["md"]) + "\n")
            prog.write(json.dumps({"url": uhttps, "ok": True, "file": fname,
                                   "title": title, "date": pd, "city": sub},
                                  ensure_ascii=False) + "\n")
            prog.flush()
            n_new += 1
    print(f"[run] DONE new={n_new} fail={n_fail} skip={n_skip}")


if __name__ == "__main__":
    main()
