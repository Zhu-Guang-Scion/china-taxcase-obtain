# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
福建 9 市局子站（+平潭）· 处罚/处理决定书送达 · 重大税收违法失信 · 税案通报 收割（R7）
================================================================================
结构（实测 2026-10-11）：
  - 市局子站在主站路径下（非子域名）：fzsswj/zzsswj/qzsswj/smsswj/ptsswj/npsswj/
    lysswj/ndsswj/pingtanswj（首页底部"市局频道"），无墙（curl_cffi 直连 200）
  - 厦门为计划单列市独立站 xiamen.chinatax.gov.cn：
      * https 全路径软 404 回首页（robots.txt 也回首页 104384B）；
        ** http:// 直连正常**（内容页/栏目页都要走 http）
      * sbf.xiamen.chinatax.gov.cn:1080 处罚/失信平台已确认空库（记录数:0）
      * 栏目静态翻页：pages/index.html, index2.html, index3.html…（无后缀数字 1）
  - 主站系 TRS WCM + avalon 前端，列表翻页走 was5：
      GET https://fujian.chinatax.gov.cn/was5/web/search
          ?channelid=203958&templet=advsch.jsp&sortfield=-docreltime
          &classsql= siteid={sid}&searchword={sw}&prepage=50&page={n}
      searchword 支持 DOCTITLE=关键字（标题子串精准）；OR/AND 组合与日期过滤
      均报错（不可用），日期靠客户端过滤（sortfield=-docreltime 时间倒序）
      响应：{"count":"N","pagenum":"M","docs":[{title,title2,url,time,docid,content,…}]}
      （非严格 JSON：内嵌单引号串，按字段正则解析）
  - 各子站 siteid：福州48 漳州49 泉州50 三明51 莆田52 南平53 龙岩54 宁德55 平潭56
  - 决定书送达公告（县局通知公告/税务公告/其他公告等栏目）**正文内嵌决定书全文**
    （违法事实及证据 / 处罚决定 两节俱全）——富全文直收
策略（每子站 4 组检索）：
  Q1 DOCTITLE=处罚决定书   → 栏目「行政处罚决定」（全时段）
  Q2 DOCTITLE=处理决定书   → 栏目「行政处罚决定」（与 Q1 按 URL 去重）
  Q3 DOCTITLE=重大税收违法 → 栏目「重大税收违法失信公布」
  Q4 DOCTITLE=虚开|偷税|查处|曝光|骗取|骗税|税案 → 栏目「税案通报」（2023-01-01 起）
质量门槛：正文 cjk≥200 + 案情叙述 + 处罚要素，再过 quality_prune.decide()，DEL 不入库。
量控：每市 ≤300、全省 ≤2,000。
用法：python fj_cities_r7.py [--city 福州] [--site xm]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402
from quality_prune import decide  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

FJ = "https://fujian.chinatax.gov.cn"
WAS5 = FJ + "/was5/web/search"
DELAY = 1.4
PROG = os.path.join(ROOT, "progress", "fj_cities_r7.jsonl")
LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))
CITY_CAP = 300
GLOBAL_CAP = 2000

SITES = {48: "福州", 49: "漳州", 50: "泉州", 51: "三明", 52: "莆田",
         53: "南平", 54: "龙岩", 55: "宁德", 56: "平潭"}
ORG = {"平潭": "国家税务总局平潭综合实验区税务局"}

NEWS_KWS = ["虚开", "偷税", "查处", "曝光", "骗取", "骗税", "税案", "追缴"]

TITLE_EXCL_NEWS = re.compile(
    r"送达|催报|催缴|听证|告知书|征求意见|招聘|采购|遴选|招标|名单|批前|双随机|"
    r"意见的公告|结果公示|裁量基准|宣传月|征期|申报提醒|服务|走访|调研|座谈会")

# 案情叙述（决定书/失信类）
FACT_RE = re.compile(r"违法事实|经查明|经查|检查发现|经检查|经我局|存在违法|查实|经核实")
# 处罚/处理要素
CASE_RE = re.compile(r"罚款|追缴|滞纳金|处罚决定|处理决定|不予处罚|失信主体|没收|移送")

_seen = {}
_city_done = {}   # city -> done count
_global_done = 0


def load_prog():
    global _global_done
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            _seen[j["k"]] = j.get("st", "")
            if j.get("st") == "done":
                c = j.get("city", "?")
                _city_done[c] = _city_done.get(c, 0) + 1
                _global_done += 1


def mark(k, st, **kw):
    if k in _seen and _seen[k] not in ("",):
        return False
    _seen[k] = st
    j = {"k": k, "st": st}
    j.update(kw)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(j, ensure_ascii=False) + "\n")
    return True


def was5_page(sid, sw, page, prepage=50):
    from urllib.parse import quote
    u = (f"{WAS5}?channelid=203958&templet=advsch.jsp&sortfield=-docreltime"
         f"&classsql=" + quote(f" siteid={sid}")
         + "&searchword=" + quote(sw) + f"&prepage={prepage}&page={page}")
    for attempt in range(3):
        time.sleep(DELAY + random.uniform(0, 0.8))
        try:
            r = cr.get(u, impersonate="chrome124", timeout=60,
                       headers={"X-Requested-With": "XMLHttpRequest",
                                "Referer": FJ + "/"})
            if r.status_code == 200 and '"docs"' in r.text:
                return r.text
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def parse_was5(text):
    """非严格 JSON → [(url, title, date, channelname)]
    文档块以 {"title" 分隔；字段间含 \r\n，不能做整体连续匹配。"""
    out, seen = [], set()
    chunks = re.split(r'\{\s*?"title"', text)
    for chunk in chunks[1:]:
        m2 = re.search(r'"title2":"(.*?)"\s*,\s*"?url"?\s*:\s*"(.*?)"', chunk, re.S)
        if not m2:
            continue
        title = re.sub(r"</?font[^>]*>", "", m2.group(1)).strip()
        url = m2.group(2).strip()
        dt = re.search(r'"time":"([\d-]{8,10})"', chunk)
        ch = re.search(r'"channelname":"([^"]*)"', chunk)
        if url in seen:
            continue
        seen.add(url)
        out.append((url, title, (dt.group(1) if dt else "").replace(".", "-"),
                    (ch.group(1) if ch else "")))
    return out


def fetch_detail(url, list_title, list_date):
    r = t.polite_get(url, DELAY, referer=FJ + "/")
    if r is None:
        return None
    d = t.extract_detail(r.text, url, list_title, list_date)
    if not d or len(d["md"]) < 60:
        return None
    md = re.sub(r"!\[\]\([^)]*icons/[a-z]+\.png\)", "", d["md"])
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    d["md"] = md
    return d


def gate(md):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", md))
    if cjk < 200:
        return False, f"short({cjk})"
    if not FACT_RE.search(md):
        return False, "no-fact"
    if not CASE_RE.search(md):
        return False, "no-case"
    return True, ""


def write_md(city, column, url, title, date, d):
    out_dir = os.path.join(LAWLIB, "专题", "税务案例", "福建省", city, column)
    os.makedirs(out_dir, exist_ok=True)
    fn = f"{date}_{t.safe_filename(title)}.md"
    p = os.path.join(out_dir, fn)
    if os.path.exists(p):
        return "exists"
    org = ORG.get(city, f"国家税务总局{city}市税务局")
    fm = ("---\n"
          f'title: "{title}"\n'
          f'来源机关: "{org}"\n'
          f'栏目: "{column}"\n'
          '地区: "福建省"\n'
          f"发布日期: {date}\n"
          '原文来源: "国家税务总局福建省税务局网站"\n'
          "抓取日期: 2026-10-11\n"
          f"原文链接: {url}\n"
          "---\n\n")
    body = d["md"]
    if d.get("attachments"):
        body += "\n\n附件:\n" + "\n".join(f"  - {a}" for a in d["attachments"]) + "\n"
    with open(p, "w", encoding="utf-8") as f:
        f.write(fm + body + "\n")
    return "done"


def cap_ok(city):
    return (_city_done.get(city, 0) < CITY_CAP and _global_done < GLOBAL_CAP)


def process_item(city, column, url, title, ds, need_news_filter=False):
    """详情抓取 + 双门槛 + 入库。返回状态串。"""
    global _global_done
    if not cap_ok(city):
        return "cap"
    if need_news_filter and TITLE_EXCL_NEWS.search(title):
        return "skip-excl"
    d = fetch_detail(url, title, ds)
    if d is None:
        return "fetch-fail"
    ok, why = gate(d["md"])
    if not ok:
        return "rejected:" + why
    verdict, fl, _why = decide(column, "福建省", d["md"])
    if verdict == "DEL":
        return "prune-del"
    title = title if len(title) >= 8 else d["title"].strip()
    title = re.sub(r"^国家税务总局福建省税务局\s*\S*\s*", "", title)
    title = title.strip() or "untitled"
    date = d["date"] or ds or ""
    st = write_md(city, column, url, title, date, d)
    if st == "done":
        _city_done[city] = _city_done.get(city, 0) + 1
        _global_done += 1
    return st


def run_query(city, sid, sw, column, max_items, need_news_filter=False,
              date_from=None):
    """walk was5 pages for one searchword; return stats"""
    stats = {"pages": 0, "items": 0, "done": 0, "old": 0}
    page = 1
    while page <= 40 and stats["done"] < max_items and cap_ok(city):
        txt = was5_page(sid, sw, page)
        if txt is None:
            print(f"  [{city}|{sw}] page {page} FAILED, stop", flush=True)
            break
        items = parse_was5(txt)
        stats["pages"] += 1
        if not items:
            break
        for url, title, ds, ch in items:
            stats["items"] += 1
            if url in _seen:
                continue
            if date_from and ds and ds < date_from:
                stats["old"] += 1
                mark(url, "old", city=city, col=column, q=sw, title=title, date=ds)
                continue
            st = process_item(city, column, url, title, ds,
                              need_news_filter=need_news_filter)
            mark(url, st, city=city, col=column, q=sw, title=title, date=ds)
            if st == "done":
                stats["done"] += 1
                print(f"    + [{city}] {ds} {title[:46]}", flush=True)
            elif st == "cap":
                return stats
        page += 1
    return stats


def run_city(city, sid):
    print(f"===== {city} (siteid={sid}) done={_city_done.get(city,0)} =====", flush=True)
    s1 = run_query(city, sid, "DOCTITLE=处罚决定书", "行政处罚决定", CITY_CAP)
    print(f"  Q1 处罚决定书: {s1}", flush=True)
    s2 = run_query(city, sid, "DOCTITLE=处理决定书", "行政处罚决定", CITY_CAP)
    print(f"  Q2 处理决定书: {s2}", flush=True)
    s3 = run_query(city, sid, "DOCTITLE=重大税收违法", "重大税收违法失信公布", CITY_CAP)
    print(f"  Q3 重大税收违法: {s3}", flush=True)
    nd = CITY_CAP - _city_done.get(city, 0)
    if nd > 0:
        for kw in NEWS_KWS:
            if nd <= 0 or not cap_ok(city):
                break
            s4 = run_query(city, sid, f"DOCTITLE={kw}", "税案通报", nd,
                           need_news_filter=True, date_from="2023-01-01")
            nd = CITY_CAP - _city_done.get(city, 0)
            if s4["done"]:
                print(f"  Q4 {kw}: {s4}", flush=True)
    print(f"== {city} TOTAL done={_city_done.get(city,0)}", flush=True)


# ---------------------------------------------------------------- 厦门 ----
XM = "http://xiamen.chinatax.gov.cn"
XM_COLS = [
    ("通知公告", "/xmswcms/bsfw/bsfw-sstz/pages/index{n}.html", 52),
    ("税务要闻", "/xmswcms/ssxc/swyw-gzdt/pages/index{n}.html", 120),
    ("外媒体头", "/xmswcms/ssxc/ssxc-wxtt/pages/index{n}.html", 60),
]
XM_TITLE_KW = re.compile(r"失信|虚开|偷税|骗取|骗税|曝光|稽查|税案|查处|追缴|处罚决定|处理决定|违法")
XM_ITEM_RE = re.compile(
    r'href="(/xmswcms/content/S\d+\.html)"[^>]*title="([^"]{4,80})"')
XM_DATE_RE = re.compile(r'>(\d{2}-\d{2})<|\[(\d{4}-\d{2}-\d{2})\]|(\d{4}-\d{2}-\d{2})')


def xm_page(colpath, n):
    suffix = "" if n == 1 else str(n)
    u = XM + colpath.replace("{n}", suffix)
    for attempt in range(3):
        time.sleep(DELAY + random.uniform(0, 0.8))
        try:
            r = cr.get(u, impersonate="chrome124", timeout=60, referer=XM + "/")
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def run_xiamen():
    city = "厦门"
    print(f"===== 厦门（独立站 http 直连）done={_city_done.get(city,0)} =====", flush=True)
    stats = {"items": 0, "done": 0}
    for colname, colpath, maxpg in XM_COLS:
        for n in range(1, min(maxpg, 60) + 1):
            if not cap_ok(city):
                return stats
            txt = xm_page(colpath, n)
            if txt is None:
                break
            items = XM_ITEM_RE.findall(txt)
            if not items:
                break
            got = 0
            for href, title in items:
                stats["items"] += 1
                url = XM + href
                if url in _seen:
                    continue
                if not XM_TITLE_KW.search(title) or TITLE_EXCL_NEWS.search(title):
                    mark(url, "skip-kw", city=city, col=colname, title=title)
                    continue
                column = "重大税收违法失信公布" if ("失信" in title or "重大税收违法" in title) else "税案通报"
                st = process_item(city, column, url, title, "")
                mark(url, st, city=city, col=colname, title=title)
                if st == "done":
                    stats["done"] += 1
                    got += 1
                    print(f"    + [厦门] {title[:46]}", flush=True)
                elif st == "cap":
                    return stats
            if got == 0 and n > 8:   # 连续多页无产出且翻深了就停
                pass
    print(f"== 厦门 TOTAL done={_city_done.get(city,0)}", flush=True)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", help="只跑某市（福州/漳州/…/平潭/厦门）")
    args = ap.parse_args()
    load_prog()
    print(f"resume: seen={len(_seen)} city_done={_city_done} global={_global_done}", flush=True)
    if args.city == "厦门":
        run_xiamen()
    elif args.city:
        for sid, c in SITES.items():
            if c == args.city:
                run_city(c, sid)
    else:
        for sid, c in SITES.items():
            run_city(c, sid)
        run_xiamen()
    print("TOTAL global done:", _global_done, "progress records:", len(_seen), flush=True)


if __name__ == "__main__":
    main()
