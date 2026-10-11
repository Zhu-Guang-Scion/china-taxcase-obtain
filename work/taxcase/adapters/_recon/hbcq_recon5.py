# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆：验证瑞数 URL token 可复用性 + 进入信息公开区找行政处罚栏目。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq")
HOME = "https://chongqing.chinatax.gov.cn/"


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def wait_ready(page, sec=40):
    for _ in range(sec):
        time.sleep(1)
        h = page.content()
        if body_text_len(h) > 300 and "$_ts=window" not in h[:3000]:
            return h
    return h


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        page.goto(HOME, timeout=60000, wait_until="domcontentloaded")
        wait_ready(page)
        print("home ok", flush=True)

        # 1) 点击"信息公开"链接，拿 token 化后的 URL
        clicked = page.evaluate("""() => {
          const a=[...document.querySelectorAll('a')].find(x=>(x.textContent||'').trim()==='信息公开');
          if(a){a.click(); return a.getAttribute('href');}
          return null;
        }""")
        time.sleep(6)
        print(f"clicked xxgk href={clicked} -> url={page.url[:120]}", flush=True)
        m = re.search(r"Wr2wvrT6=([^&]+)", page.url)
        token = m.group(1) if m else ""
        print(f"TOKEN: {token[:60]}...", flush=True)
        h = page.content()
        open(os.path.join(TMP, "cq_xxgk.html"), "w", encoding="utf-8").write(h)
        # 信息公开页的子栏目
        links = page.evaluate("""() => [...document.querySelectorAll('a')].map(a=>({
            t:(a.textContent||'').trim().slice(0,24), h:a.getAttribute('href')||''}))
            .filter(x=>x.t && x.h && !x.h.startsWith('javascript'))""")
        seen = set()
        for l in links:
            if re.search(r"处罚|公示|执法|失信|稽查|公开", l["t"]) and (l["t"], l["h"]) not in seen:
                seen.add((l["t"], l["h"]))
                print(f"   {l['t']:22s} {l['h'][:90]}", flush=True)

        # 2) token 复用测试：直访文章 URL + token
        if token:
            art = "https://chongqing.chinatax.gov.cn/xwdt/swxw/202610/t20261008_386627.html"
            try:
                page.goto(f"{art}?Wr2wvrT6={token}", timeout=50000, wait_until="domcontentloaded")
                time.sleep(3)
                h = page.content()
                t = re.search(r"<title>(.*?)</title>", h, re.S)
                print(f"[token-art] len={len(h)} title={(t.group(1).strip()[:40] if t else '?')}", flush=True)
            except Exception as e:
                print("[token-art] exc", str(e)[:80], flush=True)
            # 3) token 用于另一栏目列表
            lst = "https://chongqing.chinatax.gov.cn/xwdt/jcdt/"
            try:
                page.goto(f"{lst}?Wr2wvrT6={token}", timeout=50000, wait_until="domcontentloaded")
                time.sleep(3)
                h = page.content()
                t = re.search(r"<title>(.*?)</title>", h, re.S)
                print(f"[token-list] len={len(h)} title={(t.group(1).strip()[:40] if t else '?')}", flush=True)
                if len(h) > 5000:
                    open(os.path.join(TMP, "cq_t_list_token.html"), "w", encoding="utf-8").write(h)
            except Exception as e:
                print("[token-list] exc", str(e)[:80], flush=True)
        browser.close()


if __name__ == "__main__":
    main()
