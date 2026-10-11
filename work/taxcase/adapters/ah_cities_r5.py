# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
安徽 16 市局频道 · 稽查查处/税案通报 收割（第五轮）
====================================================
结构（实测 2026-10-10）：
  - 16 市频道都在主站 http://anhui.chinatax.gov.cn（非子域名）：
    合肥 col9471 / 淮北 9472 / 亳州 9473 / 宿州 9474 / 蚌埠 9475 / 阜阳 9476 /
    淮南 9477 / 滁州 9478 / 六安 9479 / 马鞍山 9480 / 芜湖 9481 / 宣城 9482 /
    铜陵 9483 / 池州 9484 / 安庆 9485 / 黄山 9486
  - 每市频道下 4 个子栏目：工作动态 / 媒体税讯 / 通知公告 / 基层动态（col id 逐市+9）
  - 大汉 CMS jpage 翻页：POST /module/web/jpage/dataproxy.jsp
    ?startrecord={s}&endrecord={e}&perpage=15
    form: col=1&appid=1&webid=39&path=/&columnid={cid}&sourceContentType=1
          &unitid={uid}&webname=国家税务总局安徽省税务局&permissiontype=0
    （unitid 从栏目页 columnid=X&unitid=Y 提取；webid=39 是安徽）
  - 列表项：<li ...><span>YYYY-MM-DD</span><a href="/art/..." title="标题">
策略：工作动态+基层动态 全翻（日期<2023-01-01 整页早停），通知公告限 20 页；
      标题关键词过滤 + 内容案情门槛（≥120 汉字且含"经查/查处+偷税/虚开/罚款"类叙述）。
用法：python ah_cities_r5.py          # 断点续抓
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

SITE = "http://anhui.chinatax.gov.cn"
DATAPROXY = SITE + "/module/web/jpage/dataproxy.jsp"
DELAY = 1.6
DATE_FROM = "2023-01-01"

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))

# 16 市：频道 col + 子栏目 col（实测首页导航）
CITIES = {
    "合肥":   {"工作动态": 9492, "通知公告": 9489, "基层动态": 21865},
    "淮北":   {"工作动态": 9500, "通知公告": 9502, "基层动态": 15071},
    "亳州":   {"工作动态": 9509, "通知公告": 9511, "基层动态": 15072},
    "宿州":   {"工作动态": 9518, "通知公告": 9520, "基层动态": 15073},
    "蚌埠":   {"工作动态": 9527, "通知公告": 9529, "基层动态": 15074},
    "阜阳":   {"工作动态": 9536, "通知公告": 9538, "基层动态": 15075},
    "淮南":   {"工作动态": 9545, "通知公告": 9547, "基层动态": 21868},
    "滁州":   {"工作动态": 9554, "通知公告": 9556, "基层动态": 15076},
    "六安":   {"工作动态": 9563, "通知公告": 9565, "基层动态": 15077},
    "马鞍山": {"工作动态": 9572, "通知公告": 9574, "基层动态": 21866},
    "芜湖":   {"工作动态": 9581, "通知公告": 9583, "基层动态": 17052},
    "宣城":   {"工作动态": 9590, "通知公告": 9592, "基层动态": 21864},
    "铜陵":   {"工作动态": 9599, "通知公告": 9601, "基层动态": 15078},
    "池州":   {"工作动态": 9608, "通知公告": 9610, "基层动态": 15079},
    "安庆":   {"工作动态": 9617, "通知公告": 9619, "基层动态": 21867},
    "黄山":   {"工作动态": 9626, "通知公告": 9628, "基层动态": 15080},
}

TITLE_KW = re.compile(r"查处|虚开|偷税|骗取|骗税|曝光|稽查|案件|以案释法|警示|追缴|违法")
TITLE_EXCL = re.compile(
    r"送达|催报|催缴|听证|告知书|征求意见|欠税|招聘|采购|遴选|招标|公示名单|批前|听证会|双随机|意见的公告|结果公示")
FACT_RE = re.compile(r"经查|经检查|查明|检查发现|经税务机关|依法查处|立案|违法事实|查实|经检")
CASE_RE = re.compile(r"偷税|虚开|骗取|骗税|少缴|未缴|追缴|罚款|没收|处罚|移送|滞纳金|骗取留抵|骗取出口退税|黑名单")

PROG = os.path.join(ROOT, "progress", "ah_tj_round5.jsonl")
_seen = {}


def load_prog():
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                j = json.loads(line)
                _seen[j["k"]] = j["st"]
            except Exception:
                pass


def mark(k, st, **kw):
    if k in _seen:
        return False
    _seen[k] = st
    j = {"k": k, "st": st}
    j.update(kw)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(j, ensure_ascii=False) + "\n")
    return True


ITEM_RE = re.compile(
    r'<span>([\d-]{8,10})</span>\s*<a[^>]*?href="([^"]+)"[^>]*?title="([^"]*)"', re.S)


def parse_items(text):
    out = []
    for m in ITEM_RE.finditer(text):
        ds, href, title = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = SITE + href
        if "anhui.chinatax.gov.cn" not in href or "/art/" not in href:
            continue
        out.append((href.split("#")[0], re.sub(r"\s+", " ", title), ds.replace(".", "-")))
    return out


def col_meta(colid):
    """栏目页 → (unitid, total, 首页内嵌条目)"""
    r = t.polite_get(f"{SITE}/col/col{colid}/index.html", DELAY, referer=SITE + "/")
    if r is None:
        return "", 0, []
    mu = re.search(r"columnid=(\d+)&unitid=(\d+)", r.text)
    uid = mu.group(2) if mu else ""
    mt = re.findall(r"totalRecord[\":\s]+(\d+)", r.text)
    total = max(int(x) for x in mt) if mt else 0
    return uid, total, parse_items(r.text)


def dataproxy_page(colid, uid, page, perpage=15):
    start = (page - 1) * perpage + 1
    end = page * perpage
    u = f"{DATAPROXY}?startrecord={start}&endrecord={end}&perpage={perpage}"
    data = {"col": "1", "appid": "1", "webid": "39", "path": "/",
            "columnid": str(colid), "sourceContentType": "1",
            "unitid": uid or "", "webname": "国家税务总局安徽省税务局",
            "permissiontype": "0"}
    for attempt in range(3):
        time.sleep(DELAY + random.uniform(0, 0.9))
        try:
            r = cr.post(u, data=data, impersonate="chrome124", timeout=40,
                        headers={"Referer": f"{SITE}/col/col{colid}/index.html",
                                 "X-Requested-With": "XMLHttpRequest"})
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def gate(md):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", md))
    if cjk < 120:
        return False, f"short({cjk})"
    if not FACT_RE.search(md):
        return False, "no-fact-narrative"
    if not CASE_RE.search(md):
        return False, "no-case-elements"
    return True, ""


def fetch_detail_write(city, url, list_title, list_date):
    """抓详情 → 过门槛 → 写 md。返回状态。"""
    r = t.polite_get(url, DELAY, referer=SITE + "/")
    if r is None:
        return "fetch-fail"
    d = t.extract_detail(r.text, url, list_title, list_date)
    if not d or len(d["md"]) < 60:
        return "parse-fail"
    md = d["md"]
    md = re.sub(r"!\[\]\([^)]*icons/[a-z]+\.png\)", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    ok, why = gate(md)
    if not ok:
        return "rejected:" + why
    title = list_title if list_title and len(list_title) >= 8 else d["title"].strip()
    title = re.sub(r"^国家税务总局安徽省税务局\s*\S*\s*", "", title)
    date = d["date"] or list_date or ""
    out_dir = os.path.join(LAWLIB, "专题", "税务案例", "安徽省", city, "税案通报")
    os.makedirs(out_dir, exist_ok=True)
    fn = f"{date}_{t.safe_filename(title)}.md"
    p = os.path.join(out_dir, fn)
    if os.path.exists(p):
        return "exists"
    fm = ("---\n"
          f'title: "{title}"\n'
          f'来源机关: "国家税务总局{city}市税务局"\n'
          '栏目: "税案通报"\n'
          '地区: "安徽省"\n'
          f"发布日期: {date}\n"
          f'原文来源: "{d.get("source_org") or "国家税务总局安徽省税务局网站"}"\n'
          f"抓取日期: 2026-10-10\n"
          f"原文链接: {url}\n"
          "---\n\n")
    with open(p, "w", encoding="utf-8") as f:
        f.write(fm + md + "\n")
    return "done"


def run_city(city, cols, only=None):
    stats = {"pages": 0, "items": 0, "kw_pass": 0, "done": 0}
    for colname, colid in cols.items():
        if only and colname != only:
            continue
        max_pages = {"工作动态": 40, "基层动态": 40, "通知公告": 20}[colname]
        uid, total, first_items = col_meta(colid)
        print(f"[{city}|{colname}] col{colid} unitid={uid} total={total}", flush=True)
        if uid and total > 15:
            pages = min(max_pages, (total + 14) // 15)
            all_items = None
        else:
            pages = 1
            all_items = first_items
        for page in range(1, pages + 1):
            if all_items is not None and page == 1:
                items = all_items
            else:
                txt = dataproxy_page(colid, uid, page)
                if txt is None:
                    print(f"  page {page} FAILED, stop col", flush=True)
                    break
                items = parse_items(txt)
            stats["pages"] += 1
            if not items:
                break
            old_cnt = 0
            for url, title, ds in items:
                stats["items"] += 1
                if url in _seen:
                    continue
                if ds and ds < DATE_FROM:
                    old_cnt += 1
                    mark(url, "old", city=city, col=colname, title=title, date=ds)
                    continue
                if not TITLE_KW.search(title) or TITLE_EXCL.search(title):
                    mark(url, "skip-kw", city=city, col=colname, title=title, date=ds)
                    continue
                stats["kw_pass"] += 1
                st = fetch_detail_write(city, url, title, ds)
                mark(url, st, city=city, col=colname, title=title, date=ds)
                if st == "done":
                    stats["done"] += 1
                    print(f"    + {ds} {title[:45]}", flush=True)
            if old_cnt == len(items) and len(items) >= 10:
                break  # 整页早于起点 → 停
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", help="只跑某市")
    args = ap.parse_args()
    load_prog()
    grand = {"done": 0}
    for city, cols in CITIES.items():
        if args.city and city != args.city:
            continue
        s = run_city(city, cols)
        grand["done"] += s["done"]
        print(f"== {city}: pages={s['pages']} items={s['items']} kw_pass={s['kw_pass']} done={s['done']}", flush=True)
    print("TOTAL done:", grand["done"], "progress records:", len(_seen))


if __name__ == "__main__":
    main()
