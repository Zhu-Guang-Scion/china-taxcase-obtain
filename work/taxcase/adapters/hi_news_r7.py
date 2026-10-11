# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
海南 税务新闻频道 · 稽查查处通报收割（第七轮）
=============================================
结构（实测 2026-10-11）：
  - JEECms：列表 https://hainan.chinatax.gov.cn/ssxc_1_2/ 静态分页 index_N.html
    （每页 ~14 条，无日期显示——日期从详情 meta PubDate 取）
  - 详情：meta ArticleTitle/PubDate/ContentSource；正文 div#fontzoom
  - 主站无失信公布栏（信息公开>行政执法>行政处罚 = /upgrading.html 升级空壳）；
    税收执法信息栏（searchMlInfo.jspx id=47）仅 17 条程序性稽查局送达公告；
    站内搜索 search.jspx 的 q 参数失效——数据真实所在是税务新闻频道
策略：标题关键词过滤（排除总局通稿镜像——已在"国家税务总局/税案通报"库内），
      内容门槛同安徽模式（≥120 汉字+案情叙述+案件要素）。
用法：python hi_news_r7.py [--pages N]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

SITE = "https://hainan.chinatax.gov.cn"
BASE = "/ssxc_1_2"
DELAY = 1.6
DATE_FROM = "2023-01-01"
MAX_PAGES = 120

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))

TITLE_KW = re.compile(r"查处|虚开|偷税|骗取|骗税|稽查|追缴|曝光|违法|失信|揭秘|还原")
# 总局通稿镜像（库内"国家税务总局/税案通报"已收，避免重复）
MIRROR_RE = re.compile(r"^(税务部门|新华社|人民日报|央视|专家解释|依法查处网红)")
EXCL_RE = re.compile(r"征求意见|裁量基准|征求意见稿|采购|招聘|监控|监控查处")
FACT_RE = re.compile(r"经查|经检查|查明|检查发现|经税务机关|依法查处|立案|违法事实|查实|依法作出|予以处罚|依法对")
CASE_RE = re.compile(r"偷税|虚开|骗取|骗税|少缴|未缴|追缴|罚款|没收|处罚|移送|滞纳金|留抵|出口退税|失信")

PROG = os.path.join(ROOT, "progress", "hi_news_r7.jsonl")
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
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(j, ensure_ascii=False) + "\n")
    _seen[k] = j
    return True


def fetch_list(page):
    u = f"{SITE}{BASE}/" if page == 1 else f"{SITE}{BASE}/index_{page}.html"
    for attempt in range(3):
        time.sleep(DELAY + random.uniform(0, 0.8))
        try:
            r = cr.get(u, impersonate="chrome124", timeout=150,
                       headers={"Accept-Language": "zh-CN,zh;q=0.9", "Referer": SITE + "/"})
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


ITEM_RE = re.compile(r'<a[^>]+href="(/ssxc_1_2/\d+\.html)"[^>]*(?:title="([^"]*)")?[^>]*>\s*([^<]{5,100})\s*<')


def parse_items(txt):
    out = []
    for m in ITEM_RE.finditer(txt):
        href, t1, t2 = m.groups()
        title = re.sub(r"\s+", "", (t1 or t2 or "").strip())
        if title:
            out.append((SITE + href, title))
    # 去重保序
    seen = set()
    res = []
    for u, ti in out:
        if u in seen:
            continue
        seen.add(u)
        res.append((u, ti))
    return res


def html2md(seg):
    seg = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", seg)
    seg = re.sub(r"<br\s*/?>", "\n", seg, flags=re.I)
    seg = re.sub(r"</p>", "\n\n", seg, flags=re.I)
    seg = re.sub(r"<img[^>]*src=\"([^\"]+)\"[^>]*>", lambda m: f"![图]({m.group(1)})", seg)
    seg = re.sub(r"<[^>]+>", "", seg)
    seg = seg.replace("&nbsp;", " ").replace("&amp;", "&").replace("&ldquo;", "“").replace("&rdquo;", "”").replace("&mdash;", "—")
    seg = re.sub(r"[ \t]+", " ", seg)
    seg = re.sub(r"\n{3,}", "\n\n", seg)
    return seg.strip()


def fetch_detail_write(url, list_title):
    r = t.polite_get(url, DELAY, referer=SITE + BASE + "/")
    if r is None:
        return "fetch-fail", None
    txt = r.text
    mt = re.search(r'<meta name="ArticleTitle" content="([^"]*)"', txt)
    title = (mt.group(1).strip() if mt else list_title) or list_title
    md_ = re.search(r'<meta name="PubDate" content="(\d{4}-\d{2}-\d{2})"', txt)
    date = md_.group(1) if md_ else ""
    ms = re.search(r'<meta name="ContentSource" content="([^"]*)"', txt)
    source_org = ms.group(1).strip() if ms else ""
    mb = re.search(r'<div[^>]*id="fontzoom"[^>]*>([\s\S]*?)</div>\s*(?:<div|<!--)', txt)
    if not mb:
        mb = re.search(r'<div[^>]*class="[^"]*zx-xxxqy-nr[^"]*"[^>]*>([\s\S]{200,}?)</div>\s*<div', txt)
    if not mb:
        return "no-body", date
    body = html2md(mb.group(1))
    body = re.sub(r"!\[图\]\((/[^))]+)\)", lambda m2: f"![图]({SITE}{m2.group(1)})", body)
    # 镜像判别（后置）：来源与标题均无海南痕迹 → 总局/他省通稿，库内已有，跳过
    if not ("海南" in source_org or "海南" in title or "稽查局" in title
            or "海口" in title or "三亚" in title or "儋州" in title or "洋浦" in title):
        return "mirror-src", date
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    if cjk < 120:
        return f"short({cjk})", date
    if not FACT_RE.search(body) or not CASE_RE.search(body):
        return "no-fact", date
    out_dir = os.path.join(LAWLIB, "专题", "税务案例", "海南省", "税案通报")
    os.makedirs(out_dir, exist_ok=True)
    fn = f"{date}_{t.safe_filename(title)}.md"
    p = os.path.join(out_dir, fn)
    if os.path.exists(p):
        return "exists", date
    fm = ("---\n"
          f'title: "{title}"\n'
          f'来源机关: "{source_org or "国家税务总局海南省税务局"}"\n'
          '栏目: "税案通报"\n'
          '地区: "海南省"\n'
          f"发布日期: {date}\n"
          f'原文来源: "{source_org or "国家税务总局海南省税务局网站"}"\n'
          "抓取日期: 2026-10-11\n"
          f"原文链接: {url}\n"
          "---\n\n")
    with open(p, "w", encoding="utf-8") as f:
        f.write(fm + body + "\n")
    return "done", date


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0)
    args = ap.parse_args()
    load_prog()
    stats = {"pages": 0, "items": 0, "kw_pass": 0, "done": 0, "rej": 0}
    page = 1
    while page <= MAX_PAGES:
        if args.pages and page > args.pages:
            break
        txt = fetch_list(page)
        if txt is None:
            print(f"page {page} FAILED", flush=True)
            break
        items = parse_items(txt)
        stats["pages"] += 1
        if not items:
            print(f"page {page} empty -> stop", flush=True)
            break
        for url, title in items:
            stats["items"] += 1
            if url in _seen:
                continue
            if not TITLE_KW.search(title) or EXCL_RE.search(title):
                mark(url, "skip-kw", title=title)
                continue
            if MIRROR_RE.match(title) and ("海南" not in title and "稽查局" not in title):
                mark(url, "mirror", title=title)
                continue
            stats["kw_pass"] += 1
            st, date = fetch_detail_write(url, title)
            mark(url, st, title=title, date=date)
            if st == "done":
                stats["done"] += 1
                print(f"    + {date} {title[:46]}", flush=True)
            elif st.startswith(("short", "no-")):
                stats["rej"] += 1
            if date and date < DATE_FROM:
                mark(url + "#old", "old-flag", title=title)
        print(f"== page {page}: done={stats['done']} rej={stats['rej']}", flush=True)
        page += 1
    print("FINAL:", stats, "progress:", len(_seen))


if __name__ == "__main__":
    main()
