# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆/湖北 二轮侦察：真实导航到关键页面（etax 平台 / 失信查询 / 稽查动态列表），
抓页面 HTML + 监听 XHR，落盘 tmp/hb_cq/。用法：
  python hbcq_recon2.py --prov cq
  python hbcq_recon2.py --prov hb
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, argparse, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq"); os.makedirs(TMP, exist_ok=True)

TARGETS = {
    "cq": [
        ("etax_xzcf", "https://etax.chongqing.chinatax.gov.cn/zfgspt/extranet/xzcf"),
        ("zdwfajcx", "http://chongqing.chinatax.gov.cn/xxgkxt/pages/qywh/zdwfajcx.html"),
        ("jcdt_list", "https://chongqing.chinatax.gov.cn/xwdt/jcdt/"),
        ("tzgg_list", "https://chongqing.chinatax.gov.cn/xxgk/tzgg/"),
    ],
    "hb": [
        ("hb_home", "http://hubei.chinatax.gov.cn/"),
        ("etax_hb", "http://etax.hubei.chinatax.gov.cn/zfgspt/extranet/xzcf"),
        ("hb_xzcf", "http://hubei.chinatax.gov.cn/col/col2720/index.html"),
    ],
}


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prov", required=True, choices=["cq", "hb"])
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    xhr_all = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        cur = {"k": ""}
        def on_req(req):
            if req.resource_type in ("xhr", "fetch"):
                xhr_all.setdefault(cur["k"], []).append(
                    {"m": req.method, "u": req.url[:220],
                     "post": (req.post_data or "")[:300] if req.method == "POST" else ""})
        page.on("request", on_req)

        for name, url in TARGETS[args.prov]:
            cur["k"] = name
            xhr_all[name] = []
            log(f"[{name}] goto {url}")
            html = ""
            try:
                page.goto(url, timeout=70000, wait_until="domcontentloaded")
                for _ in range(45):
                    time.sleep(1)
                    html = page.content()
                    if body_text_len(html) > 300 and "$_ts=window" not in html[:3000]:
                        break
            except Exception as e:
                log(f"[{name}] exc {type(e).__name__}: {str(e)[:100]}")
                continue
            time.sleep(4)  # 让页面自身 XHR 打完
            t = re.search(r"<title>(.*?)</title>", html, re.S)
            log(f"[{name}] len={len(html)} title={(t.group(1).strip()[:44] if t else '?')} "
                f"textlen={body_text_len(html)} xhr={len(xhr_all[name])}")
            fp = os.path.join(TMP, f"{args.prov}_{name}.html")
            open(fp, "w", encoding="utf-8").write(html)
            log(f"[{name}] saved {fp}")
        json.dump(xhr_all, open(os.path.join(TMP, f"{args.prov}_xhr2.json"), "w",
                                encoding="utf-8"), ensure_ascii=False, indent=1)
        log("done")
        browser.close()


if __name__ == "__main__":
    main()
