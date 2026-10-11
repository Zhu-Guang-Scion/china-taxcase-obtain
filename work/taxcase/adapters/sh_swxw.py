# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
上海税务 —— 税案通报（税务新闻过滤）抓取器
==========================================
数据源1：税务新闻 /xwdt/swxw/（TRS 静态列表，39页，index_1.html…）
        过滤标题含 稽查/查处/偷税/逃税/骗取/虚开/曝光/违法/失信/欠税/拒不 等
        → 稽查案例曝光通报（最高价值）
数据源2：信息公开-通知公告 /xxgk/tzgg/ 过滤 稽查随机抽查 工作安排/结果公示
        → 稽查公布
用法：
  python sh_swxw.py --sample    # 各抓第1页小样
  python sh_swxw.py             # 正式
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402

BASE = "https://shanghai.chinatax.gov.cn"
DATE_FROM = "2023-01-01"

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))

SOURCES = [
    {
        "name": "swxw",
        "list": BASE + "/xwdt/swxw/",
        "out": os.path.join(REPO, "lawlibrary", "专题", "税务案例", "上海市", "税案通报"),
        "category": "税案通报",
        "prog": os.path.join(ROOT, "progress", "sh_swxw.jsonl"),
        "kw": re.compile(r"稽查|查处|偷税|逃税|骗取|骗税|虚开|曝光|违法|失信|欠税|拒不|追缴|处罚"),
        "max_pages": 45,
    },
    {
        "name": "tzgg",
        "list": BASE + "/xxgk/tzgg/",
        "out": os.path.join(REPO, "lawlibrary", "专题", "税务案例", "上海市", "稽查公布"),
        "category": "稽查公布",
        "prog": os.path.join(ROOT, "progress", "sh_tzgg.jsonl"),
        "kw": re.compile(r"稽查|抽查|随机抽查|违法|失信"),
        "max_pages": 8,
    },
]


def parse_items(html, page_url):
    """上海 TRS 列表: <a class="info" href="./202609/t481644.html" title>… <span class=time>日期"""
    from urllib.parse import urljoin
    items, seen = [], set()
    host = re.sub(r"^https?://", "", page_url).split("/")[0]
    for m in re.finditer(
            r'<a[^>]+href="([^"]+)"[^>]*title="([^"]{6,120})"[^>]*>(?:(?!</li>).)*?'
            r'class="time[^"]*"[^>]*>\s*(\d{4}-\d{2}-\d{2})', html, re.S):
        href, title, ds = m.groups()
        if not re.search(r"t\d{5,}\.html$", href):
            continue
        url = urljoin(page_url, href)
        url = re.sub(r"/\./", "/", url)
        if host not in url:
            continue
        if url in seen:
            continue
        seen.add(url)
        items.append((url, re.sub(r"\s+", " ", title), ds))
    return items


def pagecount(html):
    m = re.search(r"pagecount\s*=\s*(\d+)", html)
    return int(m.group(1)) if m else 1


def load_done(path):
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
    return done


def run(sample=False):
    for src in SOURCES:
        os.makedirs(src["out"], exist_ok=True)
        done = load_done(src["prog"])
        r0 = t.polite_get(src["list"], delay=2.5)
        if r0 is None:
            print(f"[{src['name']}] first page fail"); continue
        pc = pagecount(r0.text)
        pages = 1 if sample else min(pc, src["max_pages"])
        print(f"[{src['name']}] pagecount={pc} will crawl {pages}")
        n_new = n_hit = 0
        with open(src["prog"], "a", encoding="utf-8") as prog:
            for pg in range(pages):
                url = src["list"] if pg == 0 else src["list"] + f"index_{pg}.html"
                r = t.polite_get(url, delay=2.5)
                if r is None:
                    print(f"[{src['name']}] page {pg} fail"); break
                items = parse_items(r.text, url)
                if not items:
                    print(f"[{src['name']}] page {pg} empty, stop"); break
                for u, ti, ds in items:
                    if ds and ds < DATE_FROM:
                        continue
                    if not src["kw"].search(ti):
                        continue
                    n_hit += 1
                    if u in done:
                        continue
                    rr = t.polite_get(u, delay=2.5)
                    if rr is None:
                        continue
                    d = t.extract_detail(rr.text, u, ti, ds)
                    if not d or len(d["md"]) < 120:
                        continue
                    fname = t.safe_filename((d["date"] or ds or "nodate") + "_" + d["title"]) + ".md"
                    fm = ("---\n"
                          f"title: \"{d['title'].replace(chr(34), '')}\"\n"
                          "来源机关: \"国家税务总局上海市税务局\"\n"
                          f"栏目: \"{src['category']}\"\n"
                          "地区: \"上海市\"\n"
                          f"发布日期: {d['date'] or ds or ''}\n"
                          f"原文来源: \"{d['source_org']}\"\n"
                          f"抓取日期: {date.today().isoformat()}\n"
                          f"原文链接: {u}\n")
                    if d["attachments"]:
                        fm += "附件:\n" + "\n".join(f"  - {a}" for a in d["attachments"]) + "\n"
                    fm += "---\n\n"
                    with open(os.path.join(src["out"], fname), "w",
                              encoding="utf-8", newline="\n") as f:
                        f.write(fm + d["md"] + "\n")
                    prog.write(json.dumps({"url": u, "ok": True, "file": fname,
                                           "title": d["title"], "date": d["date"] or ds},
                                          ensure_ascii=False) + "\n")
                    prog.flush()
                    n_new += 1
        print(f"[{src['name']}] DONE hits={n_hit} new={n_new}")


if __name__ == "__main__":
    run(sample="--sample" in sys.argv)
