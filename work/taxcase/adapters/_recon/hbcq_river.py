# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""湖北/重庆 税务局 — 有头 playwright 会话内抓取（瑞数反爬，四川/北京同款手法）
================================================================================
背景：
  hubei.chinatax.gov.cn    HTTPS(443) 黑洞超时，HTTP(80) 412 瑞数 → 全程走 http://
  chongqing.chinatax.gov.cn HTTPS 202 瑞数 → https:// 会话
唯一可行路径：有头 chromium 过挑战后，会话内 page.evaluate(fetch) 拿数据。

用法：
  python hbcq_river.py --part recon_hb   # 湖北侦察：首页导航+etax+已知栏目探测+网络监听
  python hbcq_river.py --part recon_cq   # 重庆侦察
  python hbcq_river.py --part harvest_hb # 湖北收割（侦察结果定案后补）
  python hbcq_river.py --part harvest_cq # 重庆收割
断点：progress/hb_cq_r6.jsonl ；原始数据 tmp/hb_cq/
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, hashlib, argparse
from datetime import date
from urllib.parse import urljoin, quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

TMP = os.path.join(ROOT, "tmp", "hb_cq"); os.makedirs(TMP, exist_ok=True)
PROGDIR = os.path.join(ROOT, "progress"); os.makedirs(PROGDIR, exist_ok=True)
PROG = os.path.join(PROGDIR, "hb_cq_r6.jsonl")

DATE_FROM = "2023-01-01"
DELAY_RANGE = (1.8, 3.2)

# 湖北 https 黑洞 → http；重庆 https 正常
SITES = {
    "hb": {"home": "http://hubei.chinatax.gov.cn", "name": "国家税务总局湖北省税务局"},
    "cq": {"home": "https://chongqing.chinatax.gov.cn", "name": "国家税务总局重庆市税务局"},
}

JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""
JS_POST = """async (args) => {
  const r = await fetch(args.url, {method:'POST', credentials:'include',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body: args.body});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def pw_open(page, url, tries=3):
    """带瑞数挑战等待的导航：轮询 body 文本长度>300 且头部无 $_ts。"""
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            for _ in range(45):
                time.sleep(1)
                html = page.content()
                last = html
                if body_text_len(html) > 300 and "$_ts=window" not in html[:3000]:
                    return html
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:90]}")
            time.sleep(4)
    return last


def is_challenge(text, status):
    if status in (412, 900, 202):
        return True
    if "$_ts=window" in text[:3000] or "$_ts.layouts" in text[:3000]:
        return True
    if len(text) < 500 and ("flash.js" in text or "content=" in text[:200]):
        return True
    return False


def fetch_in(page, url, body=None, home=None, tries=4):
    """页面上下文内 fetch；被再挑战则回 home 重过。"""
    if home is None:
        home = SITES["hb" if "hubei" in url else "cq"]["home"] + "/"
    for attempt in range(tries):
        try:
            if body is None:
                r = page.evaluate(JS_FETCH, url)
            else:
                r = page.evaluate(JS_POST, {"url": url, "body": body})
            if not is_challenge(r["text"], r["status"]):
                return r
            log(f"  fetch challenged (st={r['status']} len={len(r['text'])}), reload #{attempt}")
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:90]}")
        pw_open(page, home)
        time.sleep(2)
    return {"status": 0, "text": ""}


def polite():
    time.sleep(random.uniform(*DELAY_RANGE))


# ---------------------------------------------------------------- 侦察

NAV_KW = re.compile(r"处罚|失信|违法|稽查|执法|公示|双公示|曝光|税案|典型")

def extract_nav_links(html, base):
    """提取首页/导航页中含关键词的链接。"""
    out = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href=[\'"]([^\'"#]+)[\'"][^>]*>(.*?)</a>', html, re.S):
        href, txt = m.group(1), re.sub(r"<[^>]+>|\s+", "", m.group(2))
        if not txt or len(txt) < 2 or href.startswith(("javascript", "mailto")):
            continue
        if not NAV_KW.search(txt):
            continue
        u = urljoin(base, href)
        if u in seen:
            continue
        seen.add(u)
        out.append({"url": u, "text": txt[:40]})
    return out


def run_recon(prov):
    from playwright.sync_api import sync_playwright
    site = SITES[prov]
    home = site["home"]
    xhr_log = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        page.on("request", lambda req: xhr_log.append(
            {"m": req.method, "u": req.url[:200],
             "r": (req.resource_type or "")})
            if req.resource_type in ("xhr", "fetch") else None)

        log(f"[{prov}] open home {home} (challenge) ...")
        h = pw_open(page, home + "/")
        log(f"[{prov}] home len={len(h)} title={re.search(r'<title>(.*?)</title>', h, re.S).group(1).strip()[:50] if re.search(r'<title>', h) else '?'}")
        open(os.path.join(TMP, f"{prov}_home.html"), "w", encoding="utf-8").write(h)

        nav = extract_nav_links(h, home + "/")
        log(f"[{prov}] nav keyword links: {len(nav)}")
        for n in nav[:40]:
            log(f"   {n['text']}  ->  {n['url'][:110]}")

        # 已知平台/栏目探测（http/https 按省归一）
        etax_host = f"etax.{'hubei' if prov=='hb' else 'chongqing'}.chinatax.gov.cn"
        scheme = "http" if prov == "hb" else "https"
        probes = [
            f"{scheme}://{etax_host}/zfgspt/extranet/xzcf?city=hz_0",
            f"{scheme}://{etax_host}/zfgspt",
            home + "/col/col2720/index.html",     # 四川同号栏目（大概率无效，试）
        ]
        # 从 nav 里挑可疑栏目（处罚/失信优先）逐个 GET
        for n in nav:
            if re.search(r"处罚|失信|执法公示|稽查", n["text"]) and len(probes) < 16:
                u = n["url"]
                if u.startswith("http") and "chinatax.gov.cn" in u:
                    probes.append(u)
        for u in probes:
            try:
                r = fetch_in(page, u, home=home + "/")
            except Exception as e:
                log(f"[probe] {u[:90]} EXC {str(e)[:60]}")
                continue
            t = re.search(r"<title>(.*?)</title>", r["text"], re.S)
            log(f"[probe] st={r['status']} len={len(r['text'])} title={(t.group(1).strip()[:40] if t else '')} url={u[:100]}")
            key = hashlib.md5(u.encode()).hexdigest()[:10]
            if r["status"] == 200 and len(r["text"]) > 2000:
                open(os.path.join(TMP, f"{prov}_probe_{key}.html"), "w", encoding="utf-8").write(r["text"])
            polite()

        json.dump({"nav": nav, "xhr": xhr_log[-200:]},
                  open(os.path.join(TMP, f"{prov}_recon.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        log(f"[{prov}] recon saved; xhr captured={len(xhr_log)}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True,
                    choices=["recon_hb", "recon_cq", "harvest_hb", "harvest_cq"])
    args = ap.parse_args()
    if args.part.startswith("recon_"):
        run_recon(args.part.split("_")[1])
    else:
        raise SystemExit("harvest parts to be added after recon")


if __name__ == "__main__":
    main()
