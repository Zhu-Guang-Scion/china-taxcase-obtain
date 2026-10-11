# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""青岛/湖南 有头 chromium 侦察：过墙后摸清栏目与数据接口。
用法: python qd_hn_recon.py --site qd|hn
产出: tmp/qd/recon.json / tmp/hn/recon.json + 各页面 html 样本
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, argparse
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp")
os.makedirs(os.path.join(TMP, "qd"), exist_ok=True)
os.makedirs(os.path.join(TMP, "hn"), exist_ok=True)

SITES = {
    "qd": {"base": "https://qingdao.chinatax.gov.cn", "home": "https://qingdao.chinatax.gov.cn/",
           "out": os.path.join(TMP, "qd")},
    "hn": {"base": "https://hunan.chinatax.gov.cn", "home": "https://hunan.chinatax.gov.cn/",
           "out": os.path.join(TMP, "hn")},
}

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
    if "$_ts=window" in text[:3000]:
        return True
    if len(text) < 700 and ("MMB1_" in text or "ZYbKRgIknL7izCT" in text):
        return True
    return False


def fetch_in(page, url, home, tries=4):
    for attempt in range(tries):
        try:
            r = page.evaluate(JS_FETCH, url)
            if not is_challenged(r["text"], r["status"]):
                return r
            log(f"  challenged st={r['status']} len={len(r['text'])}, re-pass #{attempt}")
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:80]}")
        pw_open(page, home)
        time.sleep(2)
    return {"status": 0, "text": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=["qd", "hn"])
    args = ap.parse_args()
    cfg = SITES[args.site]
    from playwright.sync_api import sync_playwright
    rep = {"site": args.site, "ts": time.strftime("%F %T"), "probes": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log(f"open home {cfg['home']} (challenge) ...")
        h = pw_open(page, cfg["home"])
        log(f"home ready? len={len(h)} textlen={body_text_len(h)}")
        open(os.path.join(cfg["out"], "home.html"), "w", encoding="utf-8").write(h)
        title = re.search(r"<title>(.*?)</title>", h, re.S)
        rep["home_title"] = title.group(1).strip() if title else ""
        rep["home_len"] = len(h)
        # cookies
        rep["cookies"] = [{"name": c["name"], "len": len(c["value"])} for c in ctx.cookies()]

        # 主页中的相关链接（处罚/失信/稽查/公示）
        links = []
        for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.S):
            u, t = m.group(1), re.sub(r"<[^>]+>|\s", "", m.group(2))
            if re.search(r"处罚|失信|稽查|公示|执法|公告|公开|通报", t) and len(t) > 1:
                links.append({"url": urljoin(cfg["base"] + "/", u), "text": t[:40]})
        rep["home_links"] = links[:80]
        log(f"home links kept: {len(links)}")

        # 平台/接口路径探测
        paths = []
        if args.site == "qd":
            paths = [
                "/zfgspt/extranet/xzcf",
                "/qdswj/",  # 猜 TRS 栏目根
                "/ssfw/",
                "/module/search/index.html",
                "/searchfront/plugin/interface/search/search.do",
                "/jsearchfront/plugin/interface/search/search.do",
            ]
        else:
            paths = [
                "/zfgspt/extranet/xzcf",
                "/hnswj/",
                "/col/col12717/index.html",
                "/module/jsearch/front/search.do",
                "/jsearchfront/plugin/interface/search/search.do",
            ]
        for pth in paths:
            u = cfg["base"] + pth
            r = fetch_in(page, u, cfg["home"])
            t = r["text"]
            ti = re.search(r"<title>(.*?)</title>", t, re.S)
            rec = {"url": u, "st": r["status"], "len": len(t),
                   "title": ti.group(1).strip()[:60] if ti else "",
                   "head": t[:200].replace("\n", " ")}
            rep["probes"].append(rec)
            log(f"probe {pth} -> st={r['status']} len={len(t)} title={rec['title']}")
            if len(t) > 3000:
                fn = "probe_" + re.sub(r"\W", "_", pth)[-50:] + ".html"
                open(os.path.join(cfg["out"], fn), "w", encoding="utf-8").write(t)

        # 全站搜索接口探测（TRS jsearch：网站 id 从页面挖）
        mids = set(re.findall(r'websiteid["\']?\s*[:=]\s*["\']?(\d{12,18})', h))
        rep["websiteids"] = list(mids)
        log(f"websiteid candidates: {mids}")

        json.dump(rep, open(os.path.join(cfg["out"], "recon.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)
        browser.close()
    log("recon done -> " + os.path.join(cfg["out"], "recon.json"))


if __name__ == "__main__":
    main()
