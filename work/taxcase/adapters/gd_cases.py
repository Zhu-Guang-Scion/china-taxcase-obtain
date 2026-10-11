# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
广东省税务局 税务案例抓取 adapter
================================
数据源（探索结论，见 sources/guangdong.md）：
  A. 以案释法专栏（法治公平与税同行专题）—— TRS channel，走 gdtaxejs JSON 分页接口
     栏目页: https://guangdong.chinatax.gov.cn/gdsw/fzgpystx_yasf/list.shtml
     接口:   /gdtaxejs/common/search/{channelId}?_pageSize=20&page={n}&_isAgg=true&_isJson=true&_template=index
  B. 站内搜索接口（TRS search5，覆盖省站+市县子站）——关键词枚举散落的税案新闻
     POST https://guangdong.chinatax.gov.cn/search5/search/s

省局 JSP 应用（zdsswfaj 失信公布 / sgs_new 双公示 / zfgspt 处罚列表）实测全部返回
"共0条"，为废弃空壳，无法抓取 —— 详见 sources 文档。

用法：
  python gd_cases.py --dry-run   # 只列清单
  python gd_cases.py             # 正式抓取
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
from urllib.parse import quote, urljoin

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cffi_requests  # noqa: E402

# ---------------- 配置 ----------------
GD_HOST = "https://guangdong.chinatax.gov.cn"
SITE_CODE = "bm29190001"
JOB_ID = "gd_cases"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT_ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "广东省")
REGION = "广东省"
SOURCE_NAME = "国家税务总局广东省税务局"
DATE_FROM = "2023-01-01"

# A. 以案释法 channel（2026-04 上线，全量抓）
YASF_CHANNEL_ID = "d46d7c83a9454be597ad514b7d90a499"
YASF_LIST_URL = GD_HOST + "/gdsw/fzgpystx_yasf/list.shtml"

# B. 搜索关键词（宁精勿滥：强案件标记词）
SEARCH_TERMS = [
    "依法查处", "骗取出口退税", "虚开增值税", "偷税案件",
    "曝光 涉税", "重大税收违法失信", "税务行政处罚决定",
]

# 标题过滤：命中才要（搜索是全文匹配，必须再用标题收紧）
TITLE_KW = re.compile(r"查处|曝光|骗取|虚开|偷税|逃税|失信|违法|处罚|税案|以案|案例|复议|移送")
# 排除：政策法规/采购/人事/宣传类噪音标题
TITLE_EXCLUDE = re.compile(
    r"裁量基准|管理办法|实施细则|条例$|中华人民共和国|政府采购|招标|中标|招聘|公示公告$|"
    r"宣传月|新闻发布会|解读$|意见$|公告$")
# 排除 URL（非案例页面）
URL_EXCLUDE = re.compile(r"/(zcwj|zjfg|zcjd|wzjd)/")  # 政策文件/法规/解读频道


def classify(title):
    """按标题归类到栏目与子目录。"""
    if re.search(r"行政复议", title):
        return "行政复议"
    if re.search(r"失信", title) and re.search(r"重大税收违法|失信主体|失信案件", title):
        return "重大税收违法失信公布"
    if re.search(r"行政处罚(决定|公示)", title):
        return "行政处罚公示"
    return "税案通报"


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def clean_title(s):
    s = strip_tags(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# ---------------- 数据源A：以案释法 JSON 分页 ----------------

def iter_yasf():
    """以案释法专栏全量（URL 是 ../../gdsw/... 相对路径，基于接口 URL 解析）。"""
    base = (f"{GD_HOST}/gdtaxejs/common/search/{YASF_CHANNEL_ID}"
            f"?_pageSize=20&page={{n}}&_isAgg=true&_isJson=true&_template=index"
            f"&_rangeTimeGte=&_channelName=")
    page = 1
    while page <= 10:
        url = base.format(n=page)
        r = t.polite_get(url, 3.0, referer=YASF_LIST_URL)
        if r is None:
            print("[yasf] fetch fail page", page)
            return
        try:
            data = json.loads(r.text)["data"]
        except Exception:
            print("[yasf] json fail page", page)
            return
        results = data.get("results") or []
        if not results:
            return
        for it in results:
            raw = (it.get("url") or "").strip()
            # 接口返回 ../../gdsw/... 相对路径，基准是站点根（同站点前端用法）
            if raw.startswith("../../"):
                u = GD_HOST + "/" + raw[6:]
            elif raw.startswith("/"):
                u = GD_HOST + raw
            else:
                u = urljoin(GD_HOST + "/", raw)
            title = clean_title(it.get("title", ""))
            d = (it.get("publishedTimeStr") or "")[:10]
            if u and title:
                yield u, title, d
        if page * 20 >= int(data.get("total") or 0):
            return
        page += 1


# ---------------- 数据源B：站内搜索枚举 ----------------

def iter_search(term):
    """search5 接口按关键词翻页，yield (url,title,date)。"""
    url = GD_HOST + "/search5/search/s"
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
        ok = False
        for attempt in range(3):
            time.sleep(2.6 + (attempt if attempt else 0) * 2)  # 手动限速
            try:
                rr = cffi_requests.post(url, data=data, impersonate="chrome124",
                                        timeout=45,
                                        headers={"Referer": GD_HOST + "/search5/html/searchResult.html"})
                if rr.status_code == 200:
                    j = rr.json()
                    ok = True
                    break
            except Exception:
                time.sleep(4)
        if not ok:
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


# ---------------- 落盘 ----------------

NOISE = re.compile(
    r"^(浏览次数|字号|打印本页|分享至|【打印】|【关闭】|.*扫描分享.*)$")


def clean_md(md):
    lines = []
    for ln in md.splitlines():
        s = ln.strip()
        if NOISE.match(s):
            continue
        if re.match(r"^\[?(大|中|小)\]?$", s):
            continue
        lines.append(ln)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


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
    ap.add_argument("--skip-yasf", action="store_true")
    ap.add_argument("--skip-search", action="store_true")
    args = ap.parse_args()

    # 1) 汇总清单
    queue = {}  # url -> (title, date, origin)
    if not args.skip_yasf:
        for u, ti, d in iter_yasf():
            queue.setdefault(u, (ti, d, "以案释法"))
        print("[list] yasf items:", len(queue))

    if not args.skip_search:
        for term in SEARCH_TERMS:
            n0 = len(queue)
            for u, ti, d in iter_search(term):
                if not u.startswith(GD_HOST):
                    continue
                if URL_EXCLUDE.search(u):
                    continue
                if not TITLE_KW.search(ti):
                    continue
                if TITLE_EXCLUDE.search(ti):
                    continue
                queue.setdefault(u, (ti, d, "search:" + term))
            print(f"[list] term={term!r} +{len(queue)-n0} (cum {len(queue)})")

    # 2) 日期过滤
    final = {u: v for u, v in queue.items() if not (v[1] and v[1] < DATE_FROM)}
    print("[list] total unique:", len(queue), "after date filter:", len(final))

    if args.dry_run:
        for u, (ti, d, org) in sorted(final.items(), key=lambda x: x[1][1] or "", reverse=True)[:60]:
            print(f"[dry] {d} [{classify(ti)}] ({org}) {ti[:46]}")
        print("[dry] would fetch:", len(final))
        return

    done, prog_path = load_done()
    n_new = n_fail = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        for u, (ti, d, org) in final.items():
            if u in done:
                n_skip += 1
                continue
            r = t.polite_get(u, 2.6, referer=GD_HOST + "/")
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
