# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
天津市税务局 — 税案通报类新闻抓取 adapter
=========================================
栏目：税务新闻(lmdm=020001, 50页) + 通知公告(lmdm=010003, 58页)
特点：
  - 列表分页为 POST /u_zlmViewMx.action  (form: lmdm, fjdm, page, d)
  - 文章标题/日期在 <meta name="ArticleTitle"> / <meta name="PubDate">
  - 无瑞数，curl_cffi 直接可抓
策略：列表全翻 → 标题含案例关键词才抓详情（宁精勿滥）
用法：python tj_news.py            # 两个栏目都跑（断点续抓）
      python tj_news.py --dry-run
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, argparse
from datetime import date
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402

SITE = "https://tianjin.chinatax.gov.cn"
LIST_URL = SITE + "/u_zlmViewMx.action"
DELAY = 2.5

# 案例关键词（标题级过滤）
CASE_KW = re.compile(
    r"稽查|查处|曝光|偷税|骗[取税]|虚开|违法|失信|复议|处罚|骗税|抗税|追缴|黑名单|典型案例|税案")

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))
JOBS = [
    {
        "job_id": "tj_swxw",
        "lmdm": "020001",
        "fjdm": "11200000000",
        "max_pages": 50,
        "out_dir": os.path.join(LAWLIB, "专题", "税务案例", "天津市", "税案通报"),
        "region": "天津市",
        "source_name": "国家税务总局天津市税务局",
        "category": "税案通报",
    },
    {
        "job_id": "tj_tzgg",
        "lmdm": "010003",
        "fjdm": "11200000000",
        "max_pages": 58,
        "out_dir": os.path.join(LAWLIB, "专题", "税务案例", "天津市", "通知公告涉税案例"),
        "region": "天津市",
        "source_name": "国家税务总局天津市税务局",
        "category": "通知公告涉税案例",
    },
]


def fetch_list_page(lmdm, fjdm, page, delay=DELAY):
    """POST 翻页取列表 HTML（curl_cffi，天津无瑞数）。"""
    from curl_cffi import requests as cr
    time.sleep(delay + random.uniform(0, 0.8))
    r = cr.post(LIST_URL, data={"lmdm": lmdm, "fjdm": fjdm, "page": str(page), "d": ""},
                impersonate="chrome124", timeout=40,
                headers={"Referer": f"{LIST_URL}?fjdm={fjdm}&lmdm={lmdm}",
                         "Origin": SITE, "Accept-Language": "zh-CN,zh;q=0.9"})
    if r.status_code == 200:
        return r.text
    return None


def parse_items(html):
    """列表页 → [(url,title,date)]。链接相对路径 + 同行日期。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not re.search(r"\d{14,}\.shtml$", href):
            continue
        u = urljoin(SITE + "/", href)
        title = re.sub(r"\s+", " ", (a.get("title") or a.get_text(" ", strip=True) or "")).strip()
        # title 属性带 "[机关名]标题" 前缀，去括号头
        title = re.sub(r"^\[[^\]]{2,40}\]", "", title).strip() or title
        if len(title) < 8:
            continue
        date_s = ""
        scope_node = a.find_parent("tr") or a.parent
        scope = scope_node.get_text(" ", strip=True)[:200] if scope_node else ""
        m = re.search(r"(2\d{3}[-/.]\d{1,2}[-/.]\d{1,2})", scope)
        if m:
            date_s = m.group(1).replace(".", "-")
            # 规范化 2026-7-4 -> 2026-07-04
            p = date_s.split("-")
            if len(p) == 3:
                date_s = f"{p[0]}-{int(p[1]):02d}-{int(p[2]):02d}"
        if u in seen:
            continue
        seen.add(u)
        items.append((u, title, date_s))
    return items


def extract_detail_tj(html, url, fb_title, fb_date):
    """天津文章页：meta ArticleTitle/PubDate + 正文容器回退。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    title = fb_title
    m = re.search(r'<meta\s+name="ArticleTitle"\s+content=[\'"]([^\'"]+)', html)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    pub = fb_date
    m = re.search(r'<meta\s+name="PubDate"\s+content=[\'"](2\d{3}-\d{2}-\d{2})', html)
    if m:
        pub = m.group(1)
    d = t.extract_detail(html, url, title, pub)
    if d:
        d["title"], d["date"] = title, pub
    return d


def run(job, dry_run=False):
    os.makedirs(job["out_dir"], exist_ok=True)
    done, prog_path = t.load_progress(job["job_id"])
    n_new = n_skip = n_seen_kw = n_old = 0
    date_from = "2023-01-01"
    print(f"[{job['job_id']}] start, done={len(done)}")
    with open(prog_path, "a", encoding="utf-8") as prog:
        for page in range(1, job["max_pages"] + 1):
            html = fetch_list_page(job["lmdm"], job["fjdm"], page)
            if html is None:
                print(f"[{job['job_id']}] page {page} fetch fail, stop")
                break
            items = parse_items(html)
            if not items:
                print(f"[{job['job_id']}] page {page} empty, stop")
                break
            stop_old = False
            for url, title, ldate in items:
                if ldate and ldate < date_from:
                    n_old += 1
                    if n_old >= 30:
                        stop_old = True
                    continue
                if not CASE_KW.search(title):
                    continue
                n_seen_kw += 1
                if url in done:
                    n_skip += 1
                    continue
                if dry_run:
                    print(f"[dry] {ldate} {title[:50]}")
                    n_new += 1
                    continue
                r = t.polite_get(url, DELAY, referer=SITE + "/")
                if r is None:
                    prog.write(json.dumps({"url": url, "ok": False, "err": "fetch"},
                                           ensure_ascii=False) + "\n")
                    continue
                d = extract_detail_tj(r.text, url, title, ldate)
                if not d or len(d["md"]) < 100:
                    prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                           ensure_ascii=False) + "\n")
                    prog.flush()
                    continue
                if d["date"] and d["date"] < date_from:
                    # 详情页日期早于阈值：不落盘，计旧跳过
                    n_old += 1
                    prog.write(json.dumps({"url": url, "ok": False, "err": "pre-2023"},
                                           ensure_ascii=False) + "\n")
                    prog.flush()
                    continue
                fname = t.safe_filename((d["date"] or "nodate") + "_" + d["title"]) + ".md"
                fpath = os.path.join(job["out_dir"], fname)
                fm = ("---\n"
                      f"title: \"{d['title'].replace(chr(34), '')}\"\n"
                      f"来源机关: \"{job['source_name']}\"\n"
                      f"栏目: \"{job['category']}\"\n"
                      f"地区: \"{job['region']}\"\n"
                      f"发布日期: {d['date'] or ''}\n"
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
                n_new += 1
                if n_new % 10 == 0:
                    print(f"[{job['job_id']}] page={page} new={n_new} kw_hits={n_seen_kw}")
            if stop_old:
                print(f"[{job['job_id']}] reached pre-2023 zone at page {page}, stop")
                break
    print(f"[{job['job_id']}] DONE new={n_new} skip={n_skip} kw_hits={n_seen_kw} old={n_old}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--job", help="only run this job_id")
    args = ap.parse_args()
    for job in JOBS:
        if args.job and job["job_id"] != args.job:
            continue
        run(job, args.dry_run)


if __name__ == "__main__":
    main()
