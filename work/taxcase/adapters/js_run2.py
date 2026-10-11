# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""补充抓取（第二轮）：用扩充后的过滤规则（稽查局泛化送达公告 + 区县聚合栏）重扫。
- 复用同一 progress job_id（js_city_<city>），已抓 URL 跳过且不计入配额
- 栏目目录计数达到 1000 件即硬停（简报量控）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os
import sys

AD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AD)
sys.path.insert(0, os.path.dirname(AD))

import js_run  # noqa: E402
from js_hanweb import HanwebCol, build_md, quit_word  # noqa: E402

ROOT = js_run.ROOT
HARD_CAP = 1000


def dir_count(cat):
    d = os.path.join(ROOT, cat)
    return len(os.listdir(d)) if os.path.isdir(d) else 0


def run_city(city, col_id, new_cap=45):
    job = f"js_city_{city}"
    done = js_run.load_done(job)
    hc = HanwebCol(col_id)
    n_new = n_old = n_new_hits = 0
    stats = {"pdf": 0, "docx": 0, "doc": 0, "scanned_img": 0, "binary": 0, "fail": 0}
    stop = False
    for url, title, ds in hc.iter(max_pages=50):
        if stop:
            break
        if ds and ds < "2023-01-01":
            n_old += 1
            if n_old >= 15:
                break
            continue
        cat = None
        if js_run.KW_FUYI.search(title):
            cat = "行政复议公告送达"
        elif js_run.KW_CF.search(title) or (js_run.KW_JC.search(title) and js_run.KW_SD.search(title)):
            cat = "处罚决定书送达公告"
        else:
            continue
        if dir_count(cat) >= HARD_CAP:
            print(f"[sup:{city}] {cat} hit HARD_CAP, stop all")
            return True
        if url in done:
            continue
        fm = build_md(url, title, ds, js_run.SRC, "江苏省", cat)
        if not fm:
            js_run.log(job, {"url": url, "ok": False, "err": "parse"})
            continue
        for a in fm["attachments"]:
            stats[a["kind"]] = stats.get(a["kind"], 0) + 1
        fn = js_run.write_one(fm, os.path.join(ROOT, cat), cat)
        js_run.log(job, {"url": url, "ok": True, "file": fn, "title": fm["title"],
                         "date": fm["date"], "cat": cat})
        n_new += 1
        n_new_hits += 1
        if n_new_hits >= new_cap:
            stop = True
        if n_new % 10 == 1:
            print(f"[sup:{city}] new={n_new} {fm['date']} {fm['title'][:36]}", flush=True)
    quit_word()
    print(f"[sup:{city}] DONE new={n_new} stats={stats}", flush=True)
    return False


def main():
    for city, cid in js_run.CITY_COLS.items():
        if run_city(city, cid):
            break
    # 省局通知公告补充
    run_city("省局", 8274, new_cap=40)


if __name__ == "__main__":
    main()
