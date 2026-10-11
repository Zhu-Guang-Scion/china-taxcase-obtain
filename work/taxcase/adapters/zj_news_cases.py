# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
浙江税务案例抓取 adapter（大汉 CMS jpage 列表 + art 详情）
----------------------------------------------------------
栏目：
  1) 税务新闻 col13226（省局，含"稽查局依法查处XX案件"官方通报 + 揭秘类深度稿）
  2) 基层动态 col13229（市局动态，混有市局查处通报，按标题关键词过滤）

列表接口（POST，非静态分页页）：
  /module/web/jpage/dataproxy.jsp?startrecord={s}&endrecord={e}&perpage=15
  data: col=1, appid=1, webid=15, path=/, columnid={col}, sourceContentType=1,
        unitid={unitid}, webname=..., permissiontype=0
  返回 XML datastore，record CDATA 内是 <li><span>日期</span><a href title>

详情：/art/{y}/{m}/{d}/art_{col}_{id}.html
  meta ArticleTitle / ContentSource / Maketime 提供干净标题、来源、时间。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # work/taxcase
import taxcase_scrape as t
from curl_cffi import requests as cr
from datetime import date

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "浙江省")
PROXY = "https://zhejiang.chinatax.gov.cn/module/web/jpage/dataproxy.jsp"

# 案件相关标题关键词（官方通报 + 案例解读）
CASE_KW = [
    "依法查处", "偷税", "虚开", "骗取", "骗享", "骗税", "逃避追缴", "抗税",
    "重大税收违法", "失信", "曝光", "典型案例", "追缴", "稽查", "发票违法",
    "违规享受", "隐匿收入", "私户收款", "账外",
]
# 排除词（政策/招录/会议类误命中）
EXCLUDE_KW = ["裁量基准", "审理标准", "工作标准", "招聘", "拟录用", "考试", "会议",
              "征求意见", "解读《", "办法》", "规定》"]


def is_case(title):
    if not any(k in title for k in CASE_KW):
        return False
    if any(k in title for k in EXCLUDE_KW):
        return False
    return True


def fetch_list_pages(columnid, unitid, max_pages, date_from="2023-01-01", delay=2.5):
    """翻 dataproxy.jsp，返回 [(url,title,date)]，日期倒序；连续整页早于阈值即停。"""
    items, per = [], 15
    seen = set()
    stale_pages = 0
    for page in range(1, max_pages + 1):
        s, e = (page - 1) * per + 1, page * per
        url = f"{PROXY}?startrecord={s}&endrecord={e}&perpage={per}"
        data = {"col": "1", "appid": "1", "webid": "15", "path": "/",
                "columnid": str(columnid), "sourceContentType": "1",
                "unitid": str(unitid), "webname": "国家税务总局浙江省税务局",
                "permissiontype": "0"}
        got = None
        for attempt in range(3):
            wait = delay - (time.time() - t._last_ts[0]) + (__import__("random").uniform(0, 1))
            if wait > 0:
                time.sleep(wait)
            try:
                r = cr.post(url, data=data, impersonate="chrome124", timeout=40,
                            headers={"Referer": f"https://zhejiang.chinatax.gov.cn/col/col{columnid}/index.html",
                                     "X-Requested-With": "XMLHttpRequest"})
                t._last_ts[0] = time.time()
                if r.status_code == 200 and "<record>" in r.text:
                    got = r.text
                    break
            except Exception:
                pass
            time.sleep(4 + attempt * 3)
        if got is None:
            print(f"[list] col{columnid} page {page} failed, stop")
            break
        recs = re.findall(r"<!\[CDATA\[(.*?)\]\]>", got, re.S)
        if not recs:
            break
        n_old = 0
        for rec in recs:
            m = re.search(r'href="([^"]+art_\d+_\d+\.html)"[^>]*title="([^"]+)"', rec)
            dm = re.search(r"<span>(\d{4}-\d{2}-\d{2})</span>", rec)
            if not (m and dm):
                continue
            u = m.group(1)
            if u.startswith("/"):
                u = "https://zhejiang.chinatax.gov.cn" + u
            if u in seen:
                continue
            d = dm.group(1)
            if d < date_from:
                n_old += 1
                continue
            seen.add(u)
            items.append((u, m.group(2).strip(), d))
        print(f"[list] col{columnid} p{page}: +{len(recs)} recs, old={n_old}")
        if n_old >= len(recs) - 1:  # 整页基本都旧了
            stale_pages += 1
            if stale_pages >= 2:
                break
        else:
            stale_pages = 0
    return items


def extract_detail_zj(html, url, fb_title, fb_date):
    """优先 meta ArticleTitle/ContentSource/Maketime，正文复用 t.extract_detail。"""
    title = fb_title
    m = re.search(r'name="ArticleTitle"\s+content="([^"]+)"', html)
    if m:
        title = m.group(1).strip()
    src_org = ""
    m = re.search(r'name="ContentSource"\s+content="([^"]+)"', html)
    if m:
        src_org = m.group(1).strip()
    pub = fb_date
    m = re.search(r'name=.Maketime.\s+content="(\d{4}-\d{2}-\d{2})', html)
    if m:
        pub = m.group(1)
    d = t.extract_detail(html, url, title, pub)
    if d:
        d["title"] = title
        d["source_org"] = src_org
        d["date"] = pub
    return d


def run(columnid, unitid, category, max_pages, job_id, date_from="2023-01-01",
        dedup_titles=None, dry=False):
    out_dir = os.path.join(ROOT, category)
    os.makedirs(out_dir, exist_ok=True)
    done, prog_path = t.load_progress(job_id)
    items = fetch_list_pages(columnid, unitid, max_pages, date_from)
    cases = [(u, ti, d) for (u, ti, d) in items if is_case(ti)]
    print(f"[{job_id}] list total={len(items)} case-like={len(cases)}")
    n_new = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        for url, title, ldate in cases:
            if url in done:
                n_skip += 1
                continue
            if dedup_titles is not None:
                key = re.sub(r"\s+", "", title)
                if key in dedup_titles:
                    prog.write(json.dumps({"url": url, "ok": True, "dup": title},
                                          ensure_ascii=False) + "\n")
                    continue
            if dry:
                print(f"[dry] {ldate} {title[:46]}")
                n_new += 1
                continue
            r = t.polite_get(url, 2.5, referer="https://zhejiang.chinatax.gov.cn/")
            if r is None:
                prog.write(json.dumps({"url": url, "ok": False, "err": "fetch"},
                                      ensure_ascii=False) + "\n")
                continue
            d = extract_detail_zj(r.text, url, title, ldate)
            if not d or len(d["md"]) < 100:
                prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                continue
            fname = t.safe_filename((d["date"] or "nodate") + "_" + d["title"]) + ".md"
            fpath = os.path.join(out_dir, fname)
            fm = ("---\n"
                  f"title: \"{d['title'].replace(chr(34), '')}\"\n"
                  f"来源机关: \"{d['source_org'] or '国家税务总局浙江省税务局'}\"\n"
                  f"栏目: \"{category}\"\n"
                  f"地区: \"浙江省\"\n"
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
            if dedup_titles is not None:
                dedup_titles.add(re.sub(r"\s+", "", d["title"]))
    print(f"[{job_id}] DONE new={n_new} skip={n_skip}")
    return n_new


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("col", choices=["news", "grassroots"])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--max-pages", type=int, default=None)
    a = ap.parse_args()
    if a.col == "news":
        run(13226, 57907, "税案通报", a.max_pages or 20, "zj_news_cases", dry=a.dry)
    else:
        run(13229, 57907, "税案通报", a.max_pages or 60, "zj_grass_cases", dry=a.dry)
