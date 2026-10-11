#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""枚举中注协现行执业准则体系各子栏目（含分页），输出 JSONL 清单。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import re
import sys
import time
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))
import gov_download as gd

BASE = "https://www.cicpa.org.cn/ztzl1/Professional_standards/xxzztx/zyzz/"
SECTIONS = {
    "sjzz": "审计准则",
    "syzz": "审阅准则",
    "qtjzywzz": "其他鉴证业务准则",
    "xgfwzz": "相关服务准则",
    "yyzn": "应用指南",
    "wtjd": "问题解答",
}
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
OUT = os.path.join(REPO, "work", "lists", "cicpa_enum_raw.jsonl")

ITEM_RE = re.compile(
    r'<li><img[^>]*/><a\s+href="([^"]+)"[^>]*title="([^"]*)"', re.S)


def fetch(s, url, tries=4):
    for i in range(tries):
        try:
            r = s.get(url, timeout=40)
            if r.status_code == 200:
                return r.content.decode("utf-8", errors="replace")
            raise RuntimeError(f"http {r.status_code}")
        except Exception as e:
            print(f"  retry {i+1} {url}: {e}", flush=True)
            time.sleep(1.5 * (i + 1))
    return None


def main():
    s = gd.make_session()
    records = []
    for key, name in SECTIONS.items():
        sec_url = BASE + key + "/"
        print(f"== {name} ({sec_url})", flush=True)
        html = fetch(s, sec_url)
        if not html:
            print(f"  !! 首页获取失败: {sec_url}")
            continue
        pages = [(sec_url, html)]
        m = re.search(r"var countPage = (\d+)", html)
        count = int(m.group(1)) if m else 1
        print(f"  countPage={count}")
        for p in range(1, count):
            purl = f"{BASE}{key}/index_{p}.html"
            ph = fetch(s, purl)
            if ph:
                pages.append((purl, ph))
            time.sleep(0.6)
        for purl, ph in pages:
            for href, title in ITEM_RE.findall(ph):
                title = title.replace("&amp;", "&").replace("&quot;", '"').strip()
                if not title or href.startswith("#"):
                    continue
                absu = urljoin(purl, href)
                records.append({
                    "section": name, "section_key": key,
                    "title": title, "url": absu,
                    "list_page": purl,
                })
        time.sleep(0.6)
    # dedupe by url
    seen = {}
    for r in records:
        seen.setdefault(r["url"], r)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in seen.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"total unique: {len(seen)}")
    # stats per section
    from collections import Counter
    c = Counter(r["section"] for r in seen.values())
    for k, v in c.items():
        print(k, v)


if __name__ == "__main__":
    main()
