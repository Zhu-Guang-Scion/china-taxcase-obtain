# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆：捕获 xzzf 平台 target=_blank 弹窗真实 URL。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq")
B = "https://chongqing.chinatax.gov.cn"


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        page.goto(B + "/cqtax/", timeout=60000, wait_until="domcontentloaded")
        for _ in range(40):
            time.sleep(1)
            if body_text_len(page.content()) > 300:
                break
        time.sleep(3)
        # 找 xzzf 链接并点击（带 popup 捕获）
        try:
            with ctx.expect_page(timeout=25000) as pop:
                page.evaluate("""() => {
                  const a=[...document.querySelectorAll('a')].find(x=>(a=>a)((x.getAttribute('href')||'').includes('xzzf')));
                  const b=[...document.querySelectorAll('a')].find(x=>(x.textContent||'').includes('行政执法信息公示'));
                  (b||a).click();
                }""")
            np = pop.value
            np.wait_for_load_state("domcontentloaded", timeout=40000)
            time.sleep(6)
            h = np.content()
            t = re.search(r"<title>(.*?)</title>", h, re.S)
            print(f"POPUP url={np.url[:130]}", flush=True)
            print(f"len={len(h)} title={(t.group(1).strip()[:44] if t else '?')}", flush=True)
            open(os.path.join(TMP, "cq_xzzf_real.html"), "w", encoding="utf-8").write(h)
        except Exception as e:
            print("popup exc:", str(e)[:120], flush=True)
            print("page.url:", page.url[:120], flush=True)
            open(os.path.join(TMP, "cq_xzzf_nav.html"), "w", encoding="utf-8").write(page.content())
        browser.close()


if __name__ == "__main__":
    main()
