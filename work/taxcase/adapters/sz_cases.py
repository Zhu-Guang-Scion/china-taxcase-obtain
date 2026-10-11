# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
深圳市税务局 税务案例抓取 adapter
================================
数据源（探索结论，见 sources/guangdong.md）：
  站内搜索走开普云 SaaS：POST https://zs.kaipuyun.cn/search5/search/s
  （siteCode=bm29360001，覆盖深圳市局主站 + 各区局子站 /ftqswj/ /baqswj/ 等）
  搜索拿到绝对 URL + 标题 + 日期后回源 shenzhen.chinatax.gov.cn 抓正文。

  深圳违法案件公告栏（wfajgg，稽查文书送达公告）与重大税收违法失信主体查询
  （mhsofpro wgtg）均已迁入验证码/会话门禁系统，静态 URL 404、token 链接即焚，
  无法合规抓取 —— 详见 sources 文档。

  TRS 静态分页规律（备用）：list.shtml / list_2.shtml / list_3.shtml ...

用法：
  python sz_cases.py --dry-run
  python sz_cases.py
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import argparse
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import quote

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cffi_requests  # noqa: E402

SZ_HOST = "https://shenzhen.chinatax.gov.cn"
SEARCH_API = "https://zs.kaipuyun.cn/search5/search/s"
SITE_CODE = "bm29360001"
JOB_ID = "sz_cases"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT_ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "深圳市")
REGION = "深圳市"
SOURCE_NAME = "国家税务总局深圳市税务局"
DATE_FROM = "2023-01-01"

SEARCH_TERMS = [
    "依法查处", "骗取出口退税", "虚开增值税", "偷税案件",
    "曝光 涉税", "重大税收违法失信", "税务行政处罚决定",
]

TITLE_KW = re.compile(r"查处|曝光|骗取|虚开|偷税|逃税|失信|违法|处罚|税案|以案|案例|复议|移送")
TITLE_EXCLUDE = re.compile(
    r"裁量基准|管理办法|实施细则|条例$|中华人民共和国|政府采购|招标|中标|招聘|"
    r"宣传月|新闻发布会|解读$|意见$|安全运营|运维项目|物业管理")
# wfajgg 送达公告已 404（迁验证码系统），直接排除，避免大量无效请求
URL_EXCLUDE = re.compile(r"/wfajgg/|/mhsofpro/|/zcwj/|/zcjd/")


def classify(title):
    if re.search(r"行政复议", title):
        return "行政复议"
    if re.search(r"重大税收违法|失信主体|失信案件", title):
        return "重大税收违法失信公布"
    if re.search(r"行政处罚(决定|公示)", title):
        return "行政处罚公示"
    return "税案通报"


def clean_title(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def iter_search(term):
    page_num = 0
    total = None
    while True:
        if total is not None and page_num * 15 >= min(total, 1500):
            return
        data = {
            "siteCode": SITE_CODE, "searchWord": quote(term), "column": "",
            "wordPlace": "0", "orderBy": "1", "pageSize": "15",
            "pageNum": str(page_num), "checkHandle": "1", "conditionsPattern": "1",
        }
        j = None
        for attempt in range(3):
            time.sleep(2.6 + (attempt if attempt else 0) * 2)
            try:
                rr = cffi_requests.post(SEARCH_API, data=data, impersonate="chrome124",
                                        timeout=45,
                                        headers={"Origin": "https://shenzhen.chinatax.gov.cn",
                                                 "Referer": "https://shenzhen.chinatax.gov.cn/"})
                if rr.status_code == 200:
                    j = rr.json()
                    break
            except Exception:
                continue
        if j is None:
            print("[search] fail:", term, "page", page_num)
            return
        sra = j.get("searchResultAll", {})
        docs = sra.get("searchTotal") or []
        total = int(sra.get("total") or 0)
        if not docs:
            return
        for d in docs:
            u = (d.get("url") or "").strip()
            title = clean_title(d.get("title"))
            pd = str(d.get("pubDate") or "")[:10]
            if u and title:
                yield u, title, pd
        page_num += 1


NOISE = re.compile(r"^(浏览次数|字号|打印本页|分享至|【打印】|【关闭】)$")


def clean_md(md):
    lines = [ln for ln in md.splitlines() if not NOISE.match(ln.strip())]
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def load_done():
    path = os.path.join(t.PROG_DIR, JOB_ID + ".jsonl")
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("ok"):
                        done.add(rec["url"])
                except json.JSONDecodeError:
                    pass
    return done, path


def save_article(prog, url, title, pd, cat, md, attachments):
    out_dir = os.path.join(OUT_ROOT, cat)
    os.makedirs(out_dir, exist_ok=True)
    fname = t.safe_filename((pd or "nodate") + "_" + title) + ".md"
    fpath = os.path.join(out_dir, fname)
    fm = ("---\n"
          f"title: \"{title.replace(chr(34), '')}\"\n"
          f"来源机关: \"{SOURCE_NAME}\"\n"
          f"栏目: \"{cat}\"\n"
          f"地区: \"{REGION}\"\n"
          f"发布日期: {pd or ''}\n"
          f"原文来源: \"\"\n"
          f"抓取日期: {date.today().isoformat()}\n"
          f"原文链接: {url}\n")
    if attachments:
        fm += "附件:\n" + "\n".join(f"  - {a}" for a in attachments) + "\n"
    fm += "---\n\n"
    with open(fpath, "w", encoding="utf-8", newline="\n") as f:
        f.write(fm + md + "\n")
    prog.write(json.dumps({"url": url, "ok": True, "file": fname, "cat": cat,
                           "title": title, "date": pd}, ensure_ascii=False) + "\n")
    prog.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    queue = {}
    for term in SEARCH_TERMS:
        n0 = len(queue)
        for u, ti, d in iter_search(term):
            if not u.startswith(SZ_HOST):
                continue
            if URL_EXCLUDE.search(u):
                continue
            if not TITLE_KW.search(ti):
                continue
            if TITLE_EXCLUDE.search(ti):
                continue
            queue.setdefault(u, (ti, d, term))
        print(f"[list] term={term!r} +{len(queue)-n0} (cum {len(queue)})")

    final = {u: v for u, v in queue.items() if not (v[1] and v[1] < DATE_FROM)}
    print("[list] total unique:", len(queue), "after date filter:", len(final))

    if args.dry_run:
        for u, (ti, d, org) in sorted(final.items(), key=lambda x: x[1][1] or "", reverse=True)[:60]:
            print(f"[dry] {d} [{classify(ti)}] ({org}) {ti[:46]}")
            print("      ", u[:120])
        print("[dry] would fetch:", len(final))
        return

    done, prog_path = load_done()
    n_new = n_fail = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        for u, (ti, d, org) in final.items():
            if u in done:
                n_skip += 1
                continue
            r = t.polite_get(u, 2.6, referer=SZ_HOST + "/")
            d_art = None
            if r is not None:
                d_art = t.extract_detail(r.text, u, ti, d)
            if not d_art or len(d_art.get("md") or "") < 100:
                prog.write(json.dumps({"url": u, "ok": False, "err": "fetch/parse",
                                       "title": ti}, ensure_ascii=False) + "\n")
                prog.flush()
                n_fail += 1
                continue
            title = d_art["title"] or ti
            pd = d_art["date"] or d
            md = clean_md(d_art["md"])
            cat = classify(title)
            save_article(prog, u, title, pd, cat, md, d_art.get("attachments") or [])
            n_new += 1
            if n_new % 20 == 0:
                print(f"[run] new={n_new} fail={n_fail} skip={n_skip}")
    print(f"[run] DONE new={n_new} fail={n_fail} skip={n_skip}")


if __name__ == "__main__":
    main()
