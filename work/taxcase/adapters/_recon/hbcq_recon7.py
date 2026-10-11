# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆：点击进入行政执法信息公示平台，抓落地页+XHR+子栏目。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json

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
    xhr = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        page.on("request", lambda r: xhr.append({"m": r.method, "u": r.url[:220],
                 "pt": (r.post_data or "")[:200]}) if r.resource_type in ("xhr", "fetch") else None)
        page.goto(B + "/cqtax/", timeout=60000, wait_until="domcontentloaded")
        for _ in range(40):
            time.sleep(1)
            if body_text_len(page.content()) > 300:
                break
        # 点击 行政执法信息公示平台
        href = page.evaluate("""() => {
          const a=[...document.querySelectorAll('a')].find(x=>(x.textContent||'').trim().includes('行政执法信息公示平台'));
          if(a){const h=a.getAttribute('href'); a.click(); return h;}
          return null;
        }""")
        time.sleep(8)
        print(f"xzzf click href={href} -> {page.url[:110]}", flush=True)
        h = page.content()
        t = re.search(r"<title>(.*?)</title>", h, re.S)
        print(f"page len={len(h)} title={(t.group(1).strip()[:40] if t else '?')}", flush=True)
        open(os.path.join(TMP, "cq_xzzf.html"), "w", encoding="utf-8").write(h)
        # 平台上的子栏目链接
        links = page.evaluate("""() => [...document.querySelectorAll('a')].map(a=>({
            t:(a.textContent||'').trim().slice(0,26), h:a.getAttribute('href')||''}))
            .filter(x=>x.t&&!x.h.startsWith('javascript'))""")
        seen = set()
        for l in links:
            if re.search(r"处罚|许可|公示|执法|欠税|失信|查询", l["t"]) and (l["t"][:10], l["h"][-30:]) not in seen:
                seen.add((l["t"][:10], l["h"][-30:]))
                print(f"   {l['t']:24s} {l['h'][:100]}", flush=True)
        json.dump(xhr, open(os.path.join(TMP, "cq_xzzf_xhr.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        browser.close()


if __name__ == "__main__":
    main()
