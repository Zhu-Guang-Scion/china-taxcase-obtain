# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""caseopen.org 裁判文书全量收割（playwright 有头导航法）
原理：主页过 Anubis+CF → 逐个导航 /api/search?...&export=true（limit 强制2000含全文）
     → 稳定提取 innerText 至 JSON 可解析 → 存 tmp/caseopen_all.jsonl（逐案）
目标案由（总量已实测）：
  税务行政管理 4723 / 逃税罪 2634 / 虚开发票罪 5226 / 抗税罪 12 —— 全量
  骗取出口退税罪 year:[2020 TO 2026] 12143 / 虚开增值税专用发票罪 year:[2020 TO 2026] 11802 —— 近年子集
去重：doc_id/url 为键。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import io, sys, time, json, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdout.reconfigure(line_buffering=True)
from playwright.sync_api import sync_playwright
from urllib.parse import quote

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", "caseopen_all.jsonl")
DONE_MARK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", "caseopen_progress.json")

TARGETS = [
    ("税务行政管理", 'cause:"税务行政管理"', [0, 2000, 4000]),
    ("逃税罪", 'cause:"逃税罪"', [0, 2000]),
    ("虚开发票罪", 'cause:"虚开发票罪"', [0, 2000, 4000]),
    ("抗税罪", 'cause:"抗税罪"', [0]),
    ("骗取出口退税罪", 'cause:"骗取出口退税罪" AND year:[2020 TO 2026]',
     list(range(0, 14000, 2000))),
    ("虚开增值税专用发票罪", 'cause:"虚开增值税专用发票罪" AND year:[2020 TO 2026]',
     list(range(0, 12000, 2000))),
]


def click_turnstile(pg):
    """CF Turnstile 复选框点击：在挑战 iframe 内找 checkbox 元素点击；退而求其次按视觉坐标。"""
    try:
        for f in pg.frames:
            if "challenge" in f.url or "turnstile" in f.url or "cloudflare" in f.url:
                try:
                    box = f.locator("input[type=checkbox]")
                    if box.count():
                        box.first.click(timeout=3000)
                        return True
                except Exception:
                    pass
        # 坐标兜底：复选框通常在页面中部左侧（截图实测 ~205,312，视口1280x900）
        pg.mouse.click(205, 312)
        return True
    except Exception:
        return False


def grab(pg, max_wait=300):
    t0 = time.time()
    clicked = 0
    while time.time() - t0 < max_wait:
        try:
            title = pg.title()
            if ("请稍候" in title or "Just" in title) and time.time() - t0 > 12:
                # 挑战页：先等自动过，12s 后尝试点 Turnstile（最多3次）
                if clicked < 3:
                    click_turnstile(pg)
                    clicked += 1
                    time.sleep(4)
                    continue
            t = pg.evaluate("() => document.body.innerText")
            if not t or len(t) < 200:
                time.sleep(4)
                continue
            try:
                return json.loads(t)
            except json.JSONDecodeError:
                time.sleep(3)
        except Exception:
            time.sleep(4)  # challenge redirect / context destroyed
    return None


def main():
    seen = set()
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            try:
                seen.add(json.loads(line)["id"])
            except Exception:
                pass
    done_pages = set()
    if os.path.exists(DONE_MARK):
        done_pages = set(json.load(open(DONE_MARK, encoding="utf-8")))
    print(f"resume: {len(seen)} cases, {len(done_pages)} pages done", flush=True)
    fout = open(OUT, "a", encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        pg.goto("https://caseopen.org/", timeout=60000, wait_until="domcontentloaded")
        time.sleep(8)
        print("home:", pg.title(), flush=True)
        for cause, query, offsets in TARGETS:
            for off in offsets:
                pkey = f"{cause}@{off}"
                if pkey in done_pages:
                    continue
                url = ("https://caseopen.org/api/search?search=" + quote(query) +
                       "&search_type=keyword&offset=" + str(off) + "&export=true")
                try:
                    pg.goto(url, timeout=300000, wait_until="domcontentloaded")
                except Exception as e:
                    print(f"[{pkey}] goto err {str(e)[:60]}", flush=True)
                    continue
                j = grab(pg)
                if not j or "cases" not in j:
                    print(f"[{pkey}] GRAB FAIL", flush=True)
                    continue
                n_new = 0
                for c in j["cases"]:
                    key = str(c.get("id") or c.get("doc_id") or
                              (c.get("case_id", "") + c.get("case_name", "")))
                    if key in seen:
                        continue
                    seen.add(key)
                    c["_cause"] = cause
                    fout.write(json.dumps(c, ensure_ascii=False) + "\n")
                    n_new += 1
                fout.flush()
                done_pages.add(pkey)
                json.dump(sorted(done_pages), open(DONE_MARK, "w", encoding="utf-8"))
                meta = j.get("search_meta", {})
                print(f"[{pkey}] got={len(j['cases'])} new={n_new} total={meta.get('total')} cum={len(seen)}", flush=True)
        ctx.close()
        b.close()
    print("ALL DONE cum=", len(seen), flush=True)


if __name__ == "__main__":
    main()
