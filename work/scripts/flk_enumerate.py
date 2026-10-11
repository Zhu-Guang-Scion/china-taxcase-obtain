#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""枚举 flk.npc.gov.cn 全部现行有效(sxx=3)法规清单，按大类保存 JSONL。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import random
import sys
import time

import requests

BASE = "https://flk.npc.gov.cn"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "lists")
os.makedirs(OUT_DIR, exist_ok=True)

# 大类 -> 叶子编码（索引中法规实际挂载的编码）
CATEGORIES = {
    "宪法": [100],
    "法律": [110, 120, 130, 140, 150, 155, 160, 170, 180, 190, 195, 200],
    "行政法规": [210, 215],
    "监察法规": [220],
    "地方法规": [230, 260, 270, 290, 295, 300, 305, 310],
    "司法解释": [320, 330, 340, 350],
}


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://flk.npc.gov.cn/",
        "Origin": "https://flk.npc.gov.cn",
        "Accept": "application/json, text/plain, */*",
    })
    refresh_cookie(s)
    return s


def refresh_cookie(s):
    for i in range(5):
        try:
            r = s.get(BASE + "/", timeout=20)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2 + 2 * i)
    return False


def search_page(s, codes, page, size=500, retries=6):
    payload = {
        "searchRange": 1, "searchContent": "", "searchType": 2,
        "sxrq": [], "gbrq": [], "gbrqYear": [],
        "flfgCodeId": codes, "zdjgCodeId": [], "sxx": [3],
        "xgzlSearch": False,
        "orderByParam": {"order": "-1", "sort": ""},
        "pageNum": page, "pageSize": size,
    }
    for i in range(retries):
        try:
            r = s.post(BASE + "/law-search/search/list", json=payload, timeout=30)
            if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
                j = r.json()
                if j.get("code", 200) == 200:
                    return j
            # WAF 挑战或异常：刷新 cookie 后重试
            refresh_cookie(s)
        except Exception:
            refresh_cookie(s)
        time.sleep(2 + 2 * i + random.random())
    raise RuntimeError(f"search_page failed: codes={codes} page={page}")


def main():
    s = make_session()
    summary = {}
    all_bbbs = set()
    for cat, codes in CATEGORIES.items():
        out_path = os.path.join(OUT_DIR, f"flk_{cat}.jsonl")
        rows_out = []
        page = 1
        total = None
        while True:
            j = search_page(s, codes, page)
            total = j.get("total", 0)
            rows = j.get("rows", [])
            for row in rows:
                bbbs = row.get("bbbs", "")
                if not bbbs or bbbs in all_bbbs:
                    continue
                all_bbbs.add(bbbs)
                rows_out.append({
                    "bbbs": bbbs,
                    "title": row.get("title", ""),
                    "flxz": row.get("flxz", ""),
                    "flfgCodeId": row.get("flfgCodeId"),
                    "gbrq": row.get("gbrq") or "",
                    "sxrq": row.get("sxrq") or "",
                    "zdjgName": row.get("zdjgName", ""),
                    "zdjgCodeId": row.get("zdjgCodeId"),
                    "sxx": row.get("sxx"),
                    "cat": cat,
                })
            print(f"[{cat}] page {page}: +{len(rows)} (累计 {len(rows_out)}/{total})", flush=True)
            if not rows or len(rows_out) >= total:
                break
            page += 1
            time.sleep(0.6 + random.random() * 0.4)
        with open(out_path, "w", encoding="utf-8") as f:
            for r in rows_out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        summary[cat] = {"total_reported": total, "rows_saved": len(rows_out)}
        print(f"[{cat}] 完成: {len(rows_out)}/{total} -> {out_path}", flush=True)

    with open(os.path.join(OUT_DIR, "flk_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("SUMMARY:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
