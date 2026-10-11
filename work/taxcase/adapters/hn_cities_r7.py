# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
河南 全省（省站+19市局子站）稽查通报/失信公布 收割（第七轮，安徽模式）
====================================================================
结构（实测 2026-10-11）：
  - 省站+市局子站都在 henan.chinatax.gov.cn 路径前缀下（/zhengzhou/ 等，19 市）
  - 汇联 CMS：静态列表 index_N.html（page1=目录页，pageN=index_{N-1}.html）
  - 全站搜索 API（无验证码，GET）：
    https://wzjh.henan.chinatax.gov.cn/search-api/open/api/external-new
    ?keywords=..&siteId={站点}&searchRange=-1000&sortType=150&pageNumber=N&pageSize=15
    siteId 只搜本站（-1/0 全省无效，须逐站循环）；siteId 表在
    /upload/4500180001/search/js/search1.js 的 search.list（省站 4500180001 + 19 市）
    返回 datas[]：title/pubDate/channelName/selfUrl/content(截断摘要)；
    selfUrl 有 //henan / ://henan / /henan 三种残形，须归一化
  - 详情页：h2.articleTit 标题；span 日期：YYYY-MM-DD；.con-source 来源；
    div#mainText 正文（图片型公告=纯 img，文本型通报=富文本）
策略：逐站 keywords 枚举（依法查处/失信/虚开/偷税/骗取），URL 去重，
      标题关键词过滤 → 抓详情 → 内容门槛（≥120 汉字+案情叙述+案件要素）→ 入库。
用法：python hn_cities_r7.py [--only 省|郑州|..]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

API = "https://wzjh.henan.chinatax.gov.cn/search-api/open/api/external-new"
SITE = "https://henan.chinatax.gov.cn"
DELAY = 1.4
DATE_FROM = "2023-01-01"

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))

SITES = {
    "省局": "4500180001",
    "郑州": "4500150001",
    "郑州航空港": "4500000001",
    "开封": "4751990001",
    "洛阳": "4710000001",
    "平顶山": "4670990001",
    "安阳": "4550000001",
    "鹤壁": "4580300001",
    "新乡": "4536000001",
    "焦作": "4540030001",
    "濮阳": "4570050001",
    "许昌": "4611990001",
    "漯河": "4620010001",
    "三门峡": "4720990001",
    "南阳": "4574090001",
    "商丘": "4760050001",
    "信阳": "4640990001",
    "周口": "4660010001",
    "驻马店": "4630050001",
    "济源": "4550010001",
}
PATH2CITY = {
    "zhengzhoushiyanqu": "郑州航空港", "zhengzhou": "郑州", "kaifeng": "开封", "luoyang": "洛阳",
    "pingdingshan": "平顶山", "anyang": "安阳", "hebi": "鹤壁", "xinxiang": "新乡",
    "jiaozuo": "焦作", "puyang": "濮阳", "xuchang": "许昌", "luohe": "漯河",
    "sanmenxia": "三门峡", "nanyang": "南阳", "shangqiu": "商丘", "xinyang": "信阳",
    "zhoukou": "周口", "zhumadian": "驻马店", "jiyuan": "济源",
}
KEYWORDS = ["依法查处", "失信", "虚开", "偷税", "骗取", "稽查"]

TITLE_KW = re.compile(r"查处|虚开|偷税|骗取|骗税|曝光|稽查|案件|以案释法|警示|追缴|违法|失信")
TITLE_EXCL = re.compile(
    r"送达|催报|催缴|征求意见|招聘|采购|遴选|招标|听证会|意见的公告|采购意向|结果公示|_framework|裁量基准|政府采购|若干问题的解释|管理办法|暂行办法|实施细则|优秀案卷|殊荣|评查|获奖|获评|比选|风险点|风险防控|合规指引|操作指南")
FACT_RE = re.compile(r"经查|经检查|查明|检查发现|经税务机关|依法查处|立案|违法事实|查实|经检|依法作出|予以处罚")
CASE_RE = re.compile(r"偷税|虚开|骗取|骗税|少缴|未缴|追缴|罚款|没收|处罚|移送|滞纳金|留抵|出口退税|黑名单|失信")

PROG = os.path.join(ROOT, "progress", "hn_cities_r7.jsonl")
_seen = {}


def load_prog():
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                j = json.loads(line)
                _seen[j["k"]] = j
            except Exception:
                pass


def mark(k, st, **kw):
    if k in _seen:
        return False
    j = {"k": k, "st": st}
    j.update(kw)
    _seen[k] = j
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(j, ensure_ascii=False) + "\n")
    return True


def norm_url(u):
    u = (u or "").strip()
    m = re.search(r"(henan\.chinatax\.gov\.cn/.+)$", u)
    if not m:
        return u if u.startswith("http") else ""
    return "https://" + m.group(1)


def city_of(url, title, channel):
    m = re.search(rf"henan\.chinatax\.gov\.cn/({'|'.join(PATH2CITY)})/", url)
    if m:
        return PATH2CITY[m.group(1)]
    for c in ["郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳", "许昌",
              "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店", "济源", "航空港"]:
        if c in title:
            return "郑州航空港" if c == "航空港" else c
    return "省局"


def api_search(kw, site_id, page):
    params = {"keywords": kw, "siteId": site_id, "allKeyword": "", "anyKeyword": "",
              "noKeyword": "", "searchRange": -1000, "sortType": 150,
              "beginTime": "", "endTime": "", "pageNumber": page, "pageSize": 15,
              "fileType": 0, "docType": 0, "pageNum": page}
    for attempt in range(3):
        time.sleep(DELAY + random.uniform(0, 0.8))
        try:
            r = cr.get(API, params=params, impersonate="chrome124", timeout=150,
                       headers={"Referer": SITE + "/", "Origin": SITE,
                                "Accept-Language": "zh-CN,zh;q=0.9"})
            if r.status_code == 200:
                return r.json().get("data", {})
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def search_site(site_name, site_id):
    """单站多关键词枚举 → 候选条目 dict"""
    found = {}
    for kw in KEYWORDS:
        page = 1
        while page <= 15:
            d = api_search(kw, site_id, page)
            if d is None:
                break
            datas = d.get("datas", [])
            if not datas:
                break
            for it in datas:
                url = norm_url(it.get("selfUrl", ""))
                if not url or "/20" not in url:
                    continue
                title = re.sub(r"<[^>]+>|\s+", "", it.get("title", ""))
                date = (it.get("pubDate") or "")[:10]
                if url in found:
                    continue
                found[url] = {"url": url, "title": title, "date": date,
                              "channel": it.get("channelName", ""), "site": site_name,
                              "summary_cjk": len(re.findall(r"[\u4e00-\u9fff]", it.get("content", "")))}
            total = int(d.get("totalRow") or 0)
            if page * 15 >= total:
                break
            page += 1
        time.sleep(0.5)
    return found


def html2md(seg):
    seg = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", seg)
    seg = re.sub(r"<br\s*/?>", "\n", seg, flags=re.I)
    seg = re.sub(r"</p>", "\n\n", seg, flags=re.I)
    seg = re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*>", lambda m: f"![图]({m.group(1)})", seg)
    seg = re.sub(r"<[^>]+>", "", seg)
    seg = seg.replace("&nbsp;", " ").replace("&amp;", "&").replace("&ldquo;", "“").replace("&rdquo;", "”")
    seg = re.sub(r"[ \t]+", " ", seg)
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    return seg.strip()


def fetch_detail_write(item):
    url = item["url"]
    r = t.polite_get(url, DELAY, referer=SITE + "/")
    if r is None:
        return "fetch-fail"
    txt = r.text
    m = re.search(r'<h2 class="articleTit">([\s\S]{2,300}?)</h2>', txt)
    title = html2md(m.group(1)) if m else item["title"]
    md5 = re.search(r"日期：(\d{4}-\d{2}-\d{2})", txt)
    date = md5.group(1) if md5 else item["date"]
    srcm = re.search(r'class="con-source">来源：([^<]{2,40})<', txt)
    source_org = srcm.group(1).strip() if srcm else ""
    mb = re.search(r'<div id="mainText">([\s\S]*?)<div class="xiangguanBox">', txt)
    if not mb:
        mb = re.search(r'<div id="mainText">([\s\S]*?)</div>\s*</div>', txt)
    if not mb:
        return "no-body"
    body = html2md(mb.group(1))
    # 图片绝对化
    body = re.sub(r"!\[图\]\((/[^)]+)\)", lambda m2: f"![图]({SITE}{m2.group(1)})", body)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    if cjk < 120:
        return f"short({cjk})"
    if not FACT_RE.search(body):
        return "no-fact-narrative"
    if not CASE_RE.search(body):
        return "no-case-elements"
    city = city_of(url, title, item["channel"])
    org_default = "国家税务总局河南省税务局" if city == "省局" else f"国家税务总局{city}市税务局"
    out_dir = os.path.join(LAWLIB, "专题", "税务案例", "河南省", city, "税案通报")
    os.makedirs(out_dir, exist_ok=True)
    fn = f"{date}_{t.safe_filename(title)}.md"
    p = os.path.join(out_dir, fn)
    if os.path.exists(p):
        return "exists"
    fm = ("---\n"
          f'title: "{title}"\n'
          f'来源机关: "{source_org or org_default}"\n'
          '栏目: "税案通报"\n'
          '地区: "河南省"\n'
          f"发布日期: {date}\n"
          f'原文来源: "{source_org or "国家税务总局河南省税务局网站"}"\n'
          "抓取日期: 2026-10-11\n"
          f"原文链接: {url}\n"
          "---\n\n")
    with open(p, "w", encoding="utf-8") as f:
        f.write(fm + body + "\n")
    return "done"


def run(site_name, site_id):
    found = search_site(site_name, site_id)
    stats = {"found": len(found), "kw_pass": 0, "done": 0, "rejected": 0}
    print(f"[{site_name}] search found {len(found)} unique urls", flush=True)
    for url, it in sorted(found.items(), key=lambda x: x[1]["date"], reverse=True):
        if url in _seen:
            continue
        if it["date"] and it["date"] < DATE_FROM:
            mark(url, "old", site=site_name, title=it["title"], date=it["date"])
            continue
        if not TITLE_KW.search(it["title"]) or TITLE_EXCL.search(it["title"]):
            mark(url, "skip-kw", site=site_name, title=it["title"], date=it["date"])
            continue
        stats["kw_pass"] += 1
        st = fetch_detail_write(it)
        mark(url, st, site=site_name, title=it["title"], date=it["date"])
        if st == "done":
            stats["done"] += 1
            print(f"    + {it['date']} {it['title'][:46]}", flush=True)
        elif st.startswith(("short", "no-")):
            stats["rejected"] += 1
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑某站（省局/郑州/...）")
    args = ap.parse_args()
    load_prog()
    grand = {"done": 0}
    for name, sid in SITES.items():
        if args.only and name != args.only:
            continue
        s = run(name, sid)
        grand["done"] += s["done"]
        print(f"== {name}: found={s['found']} kw_pass={s['kw_pass']} done={s['done']} rej={s['rejected']}", flush=True)
    print("TOTAL done:", grand["done"], "progress:", len(_seen))


if __name__ == "__main__":
    main()
