# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""青岛 recon 第2步：xxgk2019 栏目树 + WAS5 搜索接口摸底（会话内 fetch）"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time
from urllib.parse import urljoin, quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "tmp", "qd")

SITE = "https://qingdao.chinatax.gov.cn"
HOME = SITE + "/"

JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def pw_open(page, url, tries=4):
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            for _ in range(40):
                time.sleep(1)
                html = page.content()
                last = html
                if body_text_len(html) > 300 and "$_ts=window" not in html[:3000]:
                    return html
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:90]}")
            time.sleep(3)
    return last


def is_challenged(text, status):
    if status in (412, 900):
        return True
    if len(text) < 3000 and ("$_ts" in text or "MMB1_" in text):
        return True
    return False


def fetch_in(page, url, home=HOME, tries=4):
    for attempt in range(tries):
        try:
            r = page.evaluate(JS_FETCH, url)
            if not is_challenged(r["text"], r["status"]):
                return r
            log(f"  challenged st={r['status']}, re-pass #{attempt}")
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:80]}")
        pw_open(page, home)
        time.sleep(2)
    return {"status": 0, "text": ""}


def links_of(html, base):
    out = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html, re.S):
        u, t = m.group(1), re.sub(r"<[^>]+>|\s", "", m.group(2))
        if u.startswith("javascript") or not t:
            continue
        out.append((urljoin(base + "/", u), t[:50]))
    return out


def main():
    from playwright.sync_api import sync_playwright
    rep = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        pw_open(page, HOME)

        # 1) 信息公开栏目树
        r = fetch_in(page, SITE + "/xxgk2019/")
        h = r["text"]
        open(os.path.join(OUT, "xxgk.html"), "w", encoding="utf-8").write(h)
        log(f"xxgk2019 st={r['status']} len={len(h)}")
        lk = [(u, t) for u, t in links_of(h, SITE + "/xxgk2019/")
              if re.search(r"处罚|失信|稽查|执法|公告|通报|公开|复议", t)]
        rep["xxgk_links"] = [{"url": u, "text": t} for u, t in lk]
        for u, t in lk:
            print("  ", u[:90], "|", t)

        # 2) WAS5 搜索接口：行政处罚决定书（看结构与翻页参数）
        for kw in ["行政处罚决定书", "重大税收违法", "税务行政处罚"]:
            u = (f"{SITE}/search/was5/web/search?channelid=296952"
                 f"&searchword={quote(kw)}")
            r = fetch_in(page, u)
            t = r["text"]
            log(f"was5 '{kw}' st={r['status']} len={len(t)}")
            fn = "was5_" + kw + ".html"
            open(os.path.join(OUT, fn), "w", encoding="utf-8").write(t)
            # 数结果条数与翻页特征
            hits = re.findall(r'href=["\']([^"\']+\.s?html)["\'][^>]*>([^<]{8,80})<', t)
            tot = re.search(r"(?:共|搜索到|找到)[^0-9]{0,6}(\d+)[^0-9]{0,4}(?:条|篇|项)", t)
            pages = re.findall(r'(?:page|pageno|pageNo|CurPage|curpage)[="\'/]+(\d+)', t)
            rep[f"was5_{kw}"] = {"len": len(t), "hits": len(hits),
                                 "total": tot.group(1) if tot else "",
                                 "pageparams": sorted(set(pages))[:10],
                                 "sample": [h[1][:40] for h in hits[:6]]}
            log(f"  hits={len(hits)} total={tot.group(1) if tot else '?'} pages={sorted(set(pages))[:8]}")
            for h2 in hits[:5]:
                print("    ", h2[0][:80], "|", h2[1][:40])
            time.sleep(2)

        json.dump(rep, open(os.path.join(OUT, "recon2.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()
    log("done")


if __name__ == "__main__":
    main()
