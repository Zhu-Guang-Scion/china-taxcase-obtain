# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆：测列表/文章直访行为 + 行政处罚平台入口探测。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq")


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def main():
    from playwright.sync_api import sync_playwright
    tests = [
        ("art_direct", "https://chongqing.chinatax.gov.cn/xwdt/swxw/202610/t20261008_386627.html"),
        ("list_idx", "https://chongqing.chinatax.gov.cn/xwdt/jcdt/index.html"),
        ("list_http", "http://chongqing.chinatax.gov.cn/xwdt/jcdt/"),
        ("etax_root", "https://etax.chongqing.chinatax.gov.cn/"),
        ("xxgk_xzcf", "http://chongqing.chinatax.gov.cn/xxgkxt/pages/qywh/xzcfxxcx.html"),
        ("xxgk_root", "http://chongqing.chinatax.gov.cn/xxgkxt/"),
    ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        for name, url in tests:
            try:
                page.goto(url, timeout=55000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"[{name}] goto exc {str(e)[:90]}", flush=True)
                continue
            time.sleep(3)
            h = page.content()
            t = re.search(r"<title>(.*?)</title>", h, re.S)
            print(f"[{name}] len={len(h)} textlen={body_text_len(h)} title={(t.group(1).strip()[:40] if t else '?')} final_url={page.url[:100]}", flush=True)
            if len(h) > 5000:
                open(os.path.join(TMP, f"cq_t_{name}.html"), "w", encoding="utf-8").write(h)
        browser.close()


if __name__ == "__main__":
    main()
