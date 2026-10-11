# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""湖北收割（三源）：
  --part sx   : 失信公布文章（/hbsw/xxgk/zdssxxcx/index{N}.html，167 件 → 详情页）
  --part xzcf : 省局 gspt 处罚平台 datajson 记录（内嵌 JS，直接解析）
  --part news : /hbsw/xwdt/swxw/ + /hbsw/xxgk/tzgg/ 关键词文章
全站 http（https 黑洞）；列表/文章直访均过（瑞数 cookie 会话内有效）。
断点 progress/hb_cq_r6.jsonl ；原始 tmp/hb_cq/hb_pages|*.json
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, hashlib, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq"); os.makedirs(TMP, exist_ok=True)
PAGES = os.path.join(TMP, "hb_pages"); os.makedirs(PAGES, exist_ok=True)
PROG = os.path.join(ROOT, "progress", "hb_cq_r6.jsonl")

DATE_FROM = "2023-01-01"
B = "http://hubei.chinatax.gov.cn"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def load_done(prefix):
    s = set()
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                k = json.loads(ln).get("key", "")
                if k.startswith(prefix):
                    s.add(k)
            except Exception:
                pass
    return s


def btl(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", m.group(1) if m else "")))


def pw_open(page, url, tries=3):
    last = ""
    for _ in range(tries):
        try:
            page.goto(url, timeout=70000, wait_until="domcontentloaded")
            for _ in range(30):
                time.sleep(1)
                last = page.content()
                if btl(last) > 200 and "$_ts=window" not in last[:3000]:
                    return last
        except Exception as e:
            log(f"  pw_open exc {str(e)[:80]}")
            time.sleep(3)
    return last


def polite(a=1.7, b=3.0):
    time.sleep(random.uniform(a, b))


def parse_list_links(html, base):
    """列表页 → [(url, title, date)]；兼容 title 属性与锚文本。"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"\d{4,8}\.htm(l)?$", href):
            continue
        title = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
        if len(title) < 6:
            continue
        u = href if href.startswith("http") else base + href.lstrip("./") if not href.startswith("/") else B + href
        u = re.sub(r"^https://", "http://", u)
        if u in seen:
            continue
        seen.add(u)
        # 日期：邻近文本
        seg = a.parent.get_text(" ", strip=True) if a.parent else ""
        m = re.search(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})", seg)
        d = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
        out.append((u, title[:80], d))
    return out


def run_sx():
    from playwright.sync_api import sync_playwright
    done = load_done("hbart:")
    meta_path = os.path.join(TMP, "hb_arts_meta.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        base = B + "/hbsw/xxgk/zdssxxcx/"
        all_arts = []
        for pn in range(0, 13):
            u = f"{base}index.html" if pn == 0 else f"{base}index{pn}.html"
            html = pw_open(page, u)
            if len(html) < 4000:
                log(f"p{pn} unavailable")
                break
            items = parse_list_links(html, base)
            new = [x for x in items if x not in all_arts]
            all_arts.extend(new)
            log(f"p{pn}: {len(items)} arts (cum={len(all_arts)})")
            if not items:
                break
            polite()
        # 去重
        seen, uniq = set(), []
        for a in all_arts:
            if a[0] in seen:
                continue
            seen.add(a[0])
            uniq.append(a)
        todo = [a for a in uniq if f"hbart:{a[0]}" not in done]
        log(f"sx articles={len(uniq)} todo={len(todo)}")
        fm = open(meta_path, "a", encoding="utf-8")
        n_ok = 0
        for i, (au, ti, d) in enumerate(todo):
            html = pw_open(page, au, tries=2)
            if len(html) > 3000:
                key = hashlib.md5(au.encode()).hexdigest()[:12]
                fp = os.path.join(PAGES, f"{key}.html")
                open(fp, "w", encoding="utf-8").write(html)
                fm.write(json.dumps({"url": au, "title": ti, "date": d, "file": fp,
                                     "col": "sx"}, ensure_ascii=False) + "\n")
                mark({"key": f"hbart:{au}", "phase": "hb_sx_art", "st": 200})
                n_ok += 1
            else:
                mark({"key": f"hbart:{au}", "phase": "hb_sx_art_fail", "len": len(html)})
            if (i + 1) % 15 == 0:
                log(f"  arts {i+1}/{len(todo)} ok={n_ok}")
                fm.flush()
            polite()
        fm.close()
        log(f"sx done ok={n_ok}")
        browser.close()


def run_xzcf():
    """gspt 处罚平台：页面内嵌 datajson，直接解析保存。"""
    from playwright.sync_api import sync_playwright
    out = os.path.join(TMP, "hb_xzcf_records.json")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        for u in [B + "/gspt/xzcf/swxzybcx/index.html"]:
            html = pw_open(page, u)
            # 在页面内执行：直接读 datajson 数组
            recs = page.evaluate("""() => (typeof datajson !== 'undefined') ? datajson : null""")
            log(f"{u} records={len(recs) if recs else 0}")
            if recs:
                json.dump(recs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                log(f"saved {out}")
        browser.close()


KW = re.compile(r"处罚|失信|违法|稽查|偷税|虚开|骗税|欠税|曝光|查处|复议|送达|典型案例|税案|检察")

NEWS_COLS = [
    {"base": B + "/hbsw/xwdt/swxw/", "name": "swxw"},
    {"base": B + "/hbsw/xxgk/tzgg/", "name": "tzgg"},
]


def run_news(max_arts=400):
    from playwright.sync_api import sync_playwright
    done = load_done("hbart:")
    meta_path = os.path.join(TMP, "hb_arts_meta.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        all_arts = []
        for col in NEWS_COLS:
            base = col["base"]
            stop_all = False
            for pn in range(0, 60):
                u = f"{base}index.html" if pn == 0 else f"{base}index{pn}.html"
                html = pw_open(page, u, tries=2)
                if len(html) < 4000:
                    log(f"[{col['name']}] p{pn} unavailable")
                    break
                items = parse_list_links(html, base)
                if not items:
                    log(f"[{col['name']}] p{pn} no items")
                    break
                for au, ti, d in items:
                    if d and d < DATE_FROM:
                        stop_all = True
                kw = [(au, ti, d) for au, ti, d in items if KW.search(ti)]
                all_arts.extend(kw)
                log(f"[{col['name']}] p{pn}: {len(items)} kw={len(kw)} cum={len(all_arts)}")
                if stop_all:
                    log(f"[{col['name']}] < {DATE_FROM}")
                    break
                polite()
        seen, uniq = set(), []
        for a in all_arts:
            if a[0] not in seen:
                seen.add(a[0])
                uniq.append(a)
        todo = [a for a in uniq if f"hbart:{a[0]}" not in done][:max_arts]
        log(f"news kw arts={len(uniq)} todo={len(todo)}")
        fm = open(meta_path, "a", encoding="utf-8")
        n_ok = 0
        for i, (au, ti, d) in enumerate(todo):
            html = pw_open(page, au, tries=2)
            if len(html) > 3000:
                key = hashlib.md5(au.encode()).hexdigest()[:12]
                fp = os.path.join(PAGES, f"{key}.html")
                open(fp, "w", encoding="utf-8").write(html)
                fm.write(json.dumps({"url": au, "title": ti, "date": d, "file": fp,
                                     "col": "news"}, ensure_ascii=False) + "\n")
                mark({"key": f"hbart:{au}", "phase": "hb_news_art", "st": 200})
                n_ok += 1
            else:
                mark({"key": f"hbart:{au}", "phase": "hb_news_art_fail", "len": len(html)})
            if (i + 1) % 15 == 0:
                log(f"  arts {i+1}/{len(todo)} ok={n_ok}")
                fm.flush()
            polite()
        fm.close()
        log(f"news done ok={n_ok}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["sx", "xzcf", "news"])
    ap.add_argument("--max-arts", type=int, default=400)
    args = ap.parse_args()
    if args.part == "sx":
        run_sx()
    elif args.part == "xzcf":
        run_xzcf()
    else:
        run_news(args.max_arts)


if __name__ == "__main__":
    main()
