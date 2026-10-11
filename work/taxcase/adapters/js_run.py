# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""江苏税务正式抓取驱动。

Job A: col24019 税案通报（全量，2025-02 起）
Job B: 14 市局通知公告 + 省局通知公告 col8274，标题分类：
   - 含「复议」            → 行政复议公告送达/
   - 含「处罚|处理决定」    → 处罚决定书送达公告/
   - 其余跳过
   每市扫到 date<2023-01-01（容错 15 条）或命中数达 per_city_cap。
附件：PDF/docx 提取全文追加进 md；扫描件/旧doc 跳过并计数。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import re
import sys
from datetime import date as _date

AD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AD)
sys.path.insert(0, os.path.dirname(AD))
import taxcase_scrape as t  # noqa: E402
from js_hanweb import HanwebCol, build_md, quit_word  # noqa: E402

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "江苏省")
SRC = "国家税务总局江苏省税务局"
KW_FUYI = re.compile(r"复议")
KW_CF = re.compile(r"行政处罚|处罚决定|处理决定")
KW_JC = re.compile(r"稽查")
KW_SD = re.compile(r"送达公告|公告送达|文书送达")

CITY_COLS = {
    "南京": 9161, "无锡": 9193, "徐州": 9223, "常州": 9280, "苏州": 9363,
    "南通": 9432, "连云港": 9508, "淮安": 9566, "盐城": 9530, "扬州": 9479,
    "镇江": 9426, "泰州": 9386, "宿迁": 9335, "苏州工业园区": 9287,
    "南京区县": 8433, "无锡区县": 8507,
}


def write_one(fm, out_dir, category):
    os.makedirs(out_dir, exist_ok=True)
    fname = t.safe_filename((fm["date"] or "nodate") + "_" + fm["title"]) + ".md"
    fpath = os.path.join(out_dir, fname)
    if os.path.exists(fpath):
        return fname
    front = ("---\n"
             f"title: \"{fm['title'].replace(chr(34), '')}\"\n"
             f"来源机关: \"{fm.get('source_org') or SRC}\"\n"
             f"栏目: \"{category}\"\n"
             f"地区: \"江苏省\"\n"
             f"发布日期: {fm['date'] or ''}\n"
             f"原文来源: \"{fm.get('source_org') or ''}\"\n"
             f"抓取日期: {_date.today().isoformat()}\n"
             f"原文链接: {fm['url']}\n")
    att = fm.get("attachments") or []
    if att:
        front += "附件:\n" + "\n".join(
            f"  - {a['url']} ({a['kind']})" for a in att) + "\n"
    front += "---\n\n"
    with open(fpath, "w", encoding="utf-8", newline="\n") as f:
        f.write(front + fm["md"] + "\n")
    return fname


def log(job_id, rec):
    path = os.path.join(os.path.dirname(AD), "progress", job_id + ".jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_done(job_id):
    done, _ = t.load_progress(job_id)
    return done


def run_job_a():
    job = "js_shuiantongbao"
    out = os.path.join(ROOT, "税案通报")
    done = load_done(job)
    hc = HanwebCol(24019)
    n_new = n_skip = 0
    stats = {"scanned": 0, "pdf": 0, "docx": 0, "doc": 0,
             "scanned_img": 0, "skip_binary": 0, "fail": 0}
    for url, title, ds in hc.iter(max_pages=10):
        stats["scanned"] += 1
        if url in done:
            n_skip += 1
            continue
        fm = build_md(url, title, ds, SRC, "江苏省", "税案通报")
        if not fm:
            log(job, {"url": url, "ok": False, "err": "parse"})
            continue
        for a in fm["attachments"]:
            stats[a["kind"]] = stats.get(a["kind"], 0) + 1
        fn = write_one(fm, out, "税案通报")
        log(job, {"url": url, "ok": True, "file": fn, "title": fm["title"],
                  "date": fm["date"]})
        n_new += 1
        print(f"[A] {n_new}/{hc.total} {fm['date']} {fm['title'][:36]}")
    quit_word()
    print(f"[A] DONE new={n_new} skip={n_skip} stats={stats}")


GLOBAL_CAP = {"行政复议公告送达": [0, 950], "处罚决定书送达公告": [0, 950]}


def run_job_b(city, col_id, per_city_cap=65):
    job = f"js_city_{city}"
    done = load_done(job)
    hc = HanwebCol(col_id)
    n_new = n_skip = n_old = hits = 0
    stop = False
    stats = {"scanned": 0, "pdf": 0, "docx": 0, "doc": 0,
             "scanned_img": 0, "skip_binary": 0, "fail": 0}
    for url, title, ds in hc.iter(max_pages=50):
        if stop:
            break
        stats["scanned"] += 1
        if ds and ds < "2023-01-01":
            n_old += 1
            if n_old >= 15:
                stop = True
            continue
        cat = None
        if KW_FUYI.search(title):
            cat = "行政复议公告送达"
        elif KW_CF.search(title):
            cat = "处罚决定书送达公告"
        elif KW_JC.search(title) and KW_SD.search(title):
            cat = "处罚决定书送达公告"  # 稽查局文书/送达公告（多为处理+处罚决定书）
        else:
            continue
        if GLOBAL_CAP[cat][0] >= GLOBAL_CAP[cat][1]:
            continue  # 栏目全局达上限，只记录不再抓
        hits += 1
        if hits > per_city_cap:
            stop = True
            break
        if url in done:
            n_skip += 1
            continue
        fm = build_md(url, title, ds, SRC, "江苏省", cat)
        if not fm:
            log(job, {"url": url, "ok": False, "err": "parse"})
            continue
        for a in fm["attachments"]:
            stats[a["kind"]] = stats.get(a["kind"], 0) + 1
        fn = write_one(fm, os.path.join(ROOT, cat), cat)
        log(job, {"url": url, "ok": True, "file": fn, "title": fm["title"],
                  "date": fm["date"], "cat": cat})
        GLOBAL_CAP[cat][0] += 1
        n_new += 1
        if n_new % 10 == 1:
            print(f"[B:{city}] new={n_new} hits={hits} {fm['date']} {fm['title'][:36]}")
    quit_word()
    print(f"[B:{city}] DONE new={n_new} skip={n_skip} hits={hits} stats={stats}")


def run_job_c():
    run_job_b("省局", 8274, per_city_cap=40)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("a", "all"):
        run_job_a()
    if which in ("b", "all"):
        for city, cid in CITY_COLS.items():
            run_job_b(city, cid)
    if which in ("c", "all"):
        run_job_c()
