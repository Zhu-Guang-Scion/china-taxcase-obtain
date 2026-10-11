# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
上海税务 —— 文书送达公告（催报催缴等执法文书公告送达）抓取器
============================================================
数据源：站内 was5 检索（TRS）按时间倒序翻页
  GET /was5/web/search?channelid=198173&searchword=文书送达公告
      &orderby=-docreltime&perpage=10&page=N
  结果条目: <a href="/xx/t123.html">标题</a> + var docreltime='YYYY.MM.DD'
  （上海16区税务局的纳税申报催报公告/欠税催缴公告/限期缴纳税款通知书送达公告，
    正文含被送达人名单与文书全文）
用法：
  python sh_wsgg.py --sample   # 第1页小样
  python sh_wsgg.py            # 正式（倒序翻到 2023-01-01 之前停，上限60页）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys
from datetime import date
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402

BASE = "https://shanghai.chinatax.gov.cn"
SEARCH = BASE + "/was5/web/search?channelid=198173&searchword=" + quote("文书送达公告") \
         + "&orderby=-docreltime&perpage=10"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT_DIR = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "上海市", "文书送达公告")
PROG = os.path.join(ROOT, "progress", "sh_wsgg.jsonl")
DATE_FROM = "2023-01-01"
MAX_PAGES = 100
TITLE_KW = re.compile(r"催缴公告|催报公告|送达公告|限期申报|限期缴纳|责令")


def parse_search(html):
    """一条结果 = list_title 链接 + 同 li 内的 docreltime"""
    items = []
    for m in re.finditer(
            r'<p class="list_title"><a[^>]+href="([^"]+)"[^>]*>([^<]{6,120})</a></p>'
            r'(?:(?!</li>).)*?docreltime\s*=\s*\'(\d{4})\.(\d{2})\.(\d{2})\'',
            html, re.S):
        u, ti, y, mo, dd = m.groups()
        if "chinatax.gov.cn" in u or u.startswith("/"):
            url = u if u.startswith("http") else BASE + u
            items.append((url, re.sub(r"\s+", " ", ti), f"{y}-{mo}-{dd}"))
    return items


def load_done():
    done = set()
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("ok"):
                        done.add(rec["url"])
                except json.JSONDecodeError:
                    pass
    return done


def run(sample=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    done = load_done()
    n_new = n_old = 0
    with open(PROG, "a", encoding="utf-8") as prog:
        for pg in range(1, (1 if sample else MAX_PAGES) + 1):
            url = SEARCH + f"&page={pg}"
            r = t.polite_get(url, delay=2.5)
            if r is None:
                print(f"[sh_wsgg] page {pg} fail, stop"); break
            items = parse_search(r.text)
            if not items:
                print(f"[sh_wsgg] page {pg} empty, stop"); break
            page_old = 0
            for u, ti, ds in items:
                if ds < DATE_FROM:
                    page_old += 1
                    continue
                if not TITLE_KW.search(ti):
                    continue
                if u in done:
                    continue
                rr = t.polite_get(u, delay=2.5)
                if rr is None:
                    continue
                d = t.extract_detail(rr.text, u, ti, ds)
                if not d or len(d["md"]) < 150:
                    continue
                fname = t.safe_filename((d["date"] or ds) + "_" + d["title"]) + ".md"
                fm = ("---\n"
                      f"title: \"{d['title'].replace(chr(34), '')}\"\n"
                      "来源机关: \"国家税务总局上海市税务局\"\n"
                      "栏目: \"文书送达公告\"\n"
                      "地区: \"上海市\"\n"
                      f"发布日期: {d['date'] or ds}\n"
                      f"原文来源: \"{d['source_org']}\"\n"
                      f"抓取日期: {date.today().isoformat()}\n"
                      f"原文链接: {u}\n")
                if d["attachments"]:
                    fm += "附件:\n" + "\n".join(f"  - {a}" for a in d["attachments"]) + "\n"
                fm += "---\n\n"
                with open(os.path.join(OUT_DIR, fname), "w",
                          encoding="utf-8", newline="\n") as f:
                    f.write(fm + d["md"] + "\n")
                prog.write(json.dumps({"url": u, "ok": True, "file": fname,
                                       "title": d["title"], "date": d["date"] or ds},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_new += 1
            n_old += page_old
            print(f"[sh_wsgg] page {pg}: {len(items)} items, old={page_old}, new_total={n_new}")
            if page_old == len(items):  # 整页都早于阈值 → 到旧区
                break
    print(f"[sh_wsgg] DONE new={n_new} old={n_old}")


if __name__ == "__main__":
    run(sample="--sample" in sys.argv)
