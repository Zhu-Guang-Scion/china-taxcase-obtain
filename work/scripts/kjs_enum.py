#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""枚举财政部会计司 kjs.mof.gov.cn 栏目列表页，产出 jsonl 索引。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import gov_download as gd

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "lists", "kjs_zhengcefabu.jsonl")

LINK_RE = re.compile(
    r'<a[^>]+href="(\./\d{6}/t\d+_\d+\.htm)"[^>]+title="([^"]{4,200})"', re.S)


def fetch_page(s, url, retries=3):
    for i in range(retries):
        try:
            r = s.get(url, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"http {r.status_code}")
            enc = r.apparent_encoding or "utf-8"
            return r.content.decode(enc, errors="replace")
        except Exception as e:
            print(f"  retry {i+1} {url}: {e}", flush=True)
            time.sleep(1 + i)
    return ""


def main():
    s = gd.make_session()
    base = "http://kjs.mof.gov.cn/zhengcefabu/"
    items = {}
    # page 0 = index.htm, then index_1..index_36
    urls = [base] + [f"{base}index_{i}.htm" for i in range(1, 37)]
    for idx, u in enumerate(urls):
        html = fetch_page(s, u)
        found = 0
        # date usually near link in the <span>/<li>
        for m in LINK_RE.finditer(html):
            href, title = m.group(1), m.group(2).strip()
            # look for date around the match
            ctx = html[max(0, m.start()-400):m.end()+400]
            dm = re.search(r"(20\d{2})[-/年\.](\d{1,2})[-/月\.](\d{1,2})", ctx)
            date = ""
            if dm:
                date = f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
            url_full = "http://kjs.mof.gov.cn/zhengcefabu/" + href[2:]
            if url_full not in items:
                items[url_full] = {"url": url_full, "title": title, "date": date}
                found += 1
        print(f"page {idx}: +{found} (total {len(items)})", flush=True)
        time.sleep(0.6)
    with open(OUT, "w", encoding="utf-8") as f:
        for it in items.values():
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"saved {len(items)} -> {OUT}")


if __name__ == "__main__":
    main()
