# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
陕西省税务局 收割脚本（瑞数，有头 chromium 会话内抓取）
=================================================================
数据源：
  A. 执法公示平台 zfgs.shaanxi.chinatax.gov.cn:88 行政处罚
     iframe /shaanxiswgscx/sxsw/xzcfPage.do?nCataid=6067
     数据 GET /shaanxiswgscx/sxsw/xzcf.do  (csrfToken header + 数字验证码首查，
     翻页 isCheckVerifyCode=false 免码；验证码截图→人工识别→captcha_answer.txt)
  B. 主站 重大税收违法失信主体 col15616（167 篇文章，URL 已枚举）
     列表接口 /module/search/index.jsp?field_1672=<year>&...
  C. 主站通知公告 col5383 关键词（稽查|处罚|失信|偷税|虚开|骗税|送达|复议|违法）
     dataproxy 翻页
输出：work/taxcase/tmp/sx_nb/*.html + xzcf_records.jsonl；断点 progress/sx_nb_r6.jsonl
用法：python sx_nb.py --part xzcf|shixin|notice|all
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, hashlib, argparse
from datetime import date
from urllib.parse import urljoin, quote
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                     # work/taxcase
# 审查修复：tmp 输出统一到 work/taxcase/tmp/ 下（原写到仓库根 tmp/）
TMP = os.path.join(ROOT, "tmp", "sx_nb")
os.makedirs(TMP, exist_ok=True)
PROGDIR = os.path.join(ROOT, "progress")
os.makedirs(PROGDIR, exist_ok=True)
PROG = os.path.join(PROGDIR, "sx_nb_r6.jsonl")

ZFGS = "http://zfgs.shaanxi.chinatax.gov.cn:88"
SITE = "https://shaanxi.chinatax.gov.cn"
IFRAME_URL = ZFGS + "/shaanxiswgscx/sxsw/xzcfPage.do?nCataid=6067"
DATE_FROM = "2023-01-01"
CAP_PNG = os.path.join(TMP, "captcha.png")
CAP_BIG = os.path.join(TMP, "captcha_big.png")
ANS_FILE = os.path.join(TMP, "captcha_answer.txt")

SEARCH_TMPL = ("/module/search/index.jsp?field_2166=&field_1656=&field_1652="
               "&field_1663=&field_1653=&field_2390=&field_2391=&field_2410="
               "&field_1670=&field_1672={year}&field_1651="
               "&strSelectID=style_2166,1656,1663,1652,1653,2390,2213,2391,1651,"
               "1672,2410,1670&i_columnid=style_3"
               "&field=field_2166:1:0,field_2213:1:0,field_1656:1:0,field_2391:1:0,"
               "field_2410:12:0,field_1651:12:0,field_1652:1:0,field_2390:1:0,"
               "field_1672:12:0,field_1670:12:0,field_1653:1:0,field_1663:1:0")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def load_done(phase):
    done = set()
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                d = json.loads(ln)
                if d.get("phase") == phase and d.get("ok"):
                    done.add(d.get("key"))
            except Exception:
                pass
    return done


def btl(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", m.group(1) if m else "")))


def pw_open(page, url, tries=3, wait=35):
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            for _ in range(wait):
                time.sleep(1)
                html = page.content()
                last = html
                if btl(html) > 200 and "$_ts=window" not in html[:3000]:
                    return html
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:80]}")
            time.sleep(3)
    return last


JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""


def fetch_in(page, url, home=None, tries=3):
    for attempt in range(tries):
        try:
            r = page.evaluate(JS_FETCH, url if url.startswith("http") else SITE + url)
            if r["status"] not in (412, 900) and "$_ts=window" not in r["text"][:3000]:
                return r
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:70]}")
        pw_open(page, home or (SITE + "/index.html"))
        time.sleep(1)
    return {"status": 0, "text": ""}


def polite():
    time.sleep(random.uniform(1.6, 2.8))


JS_XZCF = """async (args) => {
  return await new Promise(resolve => {
    $.ajax({
      url: '/shaanxiswgscx/sxsw/xzcf.do',
      method: 'GET',
      headers: {csrfToken: args.token},
      data: {ajmc:'', xzxdrmc:'', xzxdrdm:'', cfjg:'',
             nCataId: args.cataid, currentPage: args.page,
             isCheckVerifyCode: args.check, verifycode: args.vc},
      datatype: 'json', async: true,
      success: d => resolve({ok: true, raw: JSON.stringify(d)}),
      error: (x, s) => resolve({ok: false, status: x.status,
                                txt: (x.responseText||'').slice(0,300)})
    });
  });
}"""


def js_ok(page):
    """页面是否还活着（jQuery 可用 + csrfToken 存在）。"""
    try:
        return page.evaluate("() => !!(window.jQuery && document.getElementById('csrfToken'))")
    except Exception:
        return False


def ocr_captcha_vote(png_path):
    """多预处理变体投票，高置信才返回；否则 None。"""
    try:
        import ddddocr, warnings, io
        warnings.filterwarnings("ignore")
        from PIL import Image as PImage, ImageFilter
        ocr = ddddocr.DdddOcr()
        img = PImage.open(png_path)
        variants = {
            "raw": img,
            "gray": img.convert("L"),
            "bw130": img.convert("L").point(lambda p: 255 if p > 130 else 0),
            "med": img.convert("L").filter(ImageFilter.MedianFilter(3)),
        }
        reads = []
        for v in variants.values():
            buf = io.BytesIO()
            v.save(buf, format="PNG")
            reads.append(ocr.classification(buf.getvalue()).strip())
        from collections import Counter
        top, cnt = Counter(reads).most_common(1)[0]
        if cnt >= 3 and re.fullmatch(r"\d{4}", top):
            return top
        return None
    except Exception:
        return None


def submit_xzcf(page, token, vc, page_no=1, retries=2):
    """提交查询；412 时稍等重试（同码）。返回 raw 文本或 None(网络失败)。"""
    for t in range(retries + 1):
        try:
            r = page.evaluate(JS_XZCF, {"token": token, "cataid": "6067",
                                        "page": page_no, "check": page_no == 1,
                                        "vc": vc if page_no == 1 else ""})
        except Exception as e:
            log(f"  evaluate exc: {str(e)[:70]}")
            return None
        if r.get("ok"):
            return r.get("raw") or ""
        log(f"  ajax fail st={r.get('status')} retry {t}")
        time.sleep(6 + 4 * t)
    return None


def pass_captcha(page, token, max_tries=20):
    """单页载入→settle→图片刷新取新码（不重载页面）→投票OCR→提交。
    验证码错：仅刷新图片；连续网络失败：整页重载。"""
    reload_needed = True
    for attempt in range(max_tries):
        if os.path.exists(ANS_FILE):
            os.remove(ANS_FILE)
        if reload_needed:
            pw_open(page, IFRAME_URL, tries=1, wait=25)
            time.sleep(6)
            reload_needed = False
        try:
            token = page.evaluate("() => document.getElementById('csrfToken').value")
            page.evaluate("() => { document.getElementById('verifyImg').src = "
                          "'cfVerifycode.do?random=' + Math.random(); }")
            time.sleep(2)
            page.query_selector("#verifyImg").screenshot(path=CAP_PNG)
        except Exception as e:
            log(f"  screenshot exc: {str(e)[:60]}")
            reload_needed = True
            continue
        img = Image.open(CAP_PNG).convert("L")
        img.resize((img.width * 4, img.height * 4), Image.LANCZOS).save(CAP_BIG)
        vc = ocr_captcha_vote(CAP_PNG)
        log(f"CAPTCHA attempt={attempt} vote={vc!r}")
        if not vc:
            time.sleep(2)   # 低置信，不浪费提交，仅换码
            continue
        raw = submit_xzcf(page, token, vc, 1)
        if raw is None:
            reload_needed = True
            continue
        if '"success":true' in raw:
            open(os.path.join(TMP, "xzcf_p1.json"), "w", encoding="utf-8").write(raw)
            log(f"  captcha passed (vc={vc}), p1 saved")
            return True, token
        if "验证码" in raw:
            log("  wrong captcha (vote), next image")
            time.sleep(3)
            continue
        log(f"  other resp: {raw[:110]}")
    return False, token


def parse_xzcf_raw(raw):
    """响应 {"params":{"data":"[...]", ...}, "success":true}，data 是 JSON 字符串。"""
    d = json.loads(raw)
    params = d.get("params") or {}
    data = params.get("data")
    if isinstance(data, str):
        data = json.loads(data)
    return d, params, data


def run_xzcf(max_records=2000):
    from playwright.sync_api import sync_playwright
    rec_path = os.path.join(TMP, "xzcf_records.jsonl")
    done_pages = load_done("xzcf_page")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open iframe page (challenge)...")
        pw_open(page, IFRAME_URL)
        token = page.evaluate("() => document.getElementById('csrfToken').value")

        ok, token = pass_captcha(page, token)
        if not ok:
            log("XZCF ABORT: captcha not passed")
            browser.close()
            return

        fw = open(rec_path, "a", encoding="utf-8")
        total = None
        pg = 1
        n_rec = 0
        while pg <= 200:
            if pg == 1:
                raw = open(os.path.join(TMP, "xzcf_p1.json"), encoding="utf-8").read()
            else:
                if pg in done_pages:
                    pg += 1
                    continue
                time.sleep(random.uniform(1.8, 3.0))
                if not js_ok(page):
                    pw_open(page, IFRAME_URL, tries=1, wait=20)
                    time.sleep(5)
                    token = page.evaluate(
                        "() => document.getElementById('csrfToken').value")
                raw = submit_xzcf(page, token, "", pg, retries=2)
                if raw is None:
                    log(f"  p{pg} unreachable (412x3), stop")
                    break
                if '"success":true' not in raw:
                    log(f"  p{pg} resp: {raw[:110]} → 需重新过码")
                    ok, token = pass_captcha(page, token)
                    if not ok:
                        log("  re-captcha failed, stop")
                        break
                    continue
            try:
                d, params, data = parse_xzcf_raw(raw)
            except Exception as e:
                log(f"  p{pg} parse fail: {e}")
                break
            if total is None:
                total = params.get("totalSize") or params.get("total") or d.get("total")
                log(f"  total={total} params_keys={list(params.keys())[:10]}")
            if not data:
                log(f"  p{pg} empty")
                mark({"phase": "xzcf_page", "key": pg, "ok": True})
                break
            for rec in data:
                fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_rec += 1
            mark({"phase": "xzcf_page", "key": pg, "ok": True, "n": len(data)})
            log(f"  p{pg}: +{len(data)} cum={n_rec} (total={total})")
            if total and n_rec >= int(total):
                break
            if n_rec >= max_records:
                log("  hit max_records")
                break
            pg += 1
        fw.close()
        log(f"XZCF done: {n_rec} records -> {rec_path}")
        browser.close()


# ------------------------------------------------------------- 失信主体

def run_shixin():
    """col15616 四年 167 篇文章全抓（URL 枚举自 tmp/sx_nb/sx_shixin_urls.json）。"""
    from playwright.sync_api import sync_playwright
    urls_path = os.path.join(TMP, "sx_shixin_urls.json")
    if not os.path.exists(urls_path):
        log("urls json missing, enumerate first")
        return
    yearmap = json.load(open(urls_path, encoding="utf-8"))
    arts = []
    for y, rows in yearmap.items():
        for r in rows:
            arts.append(r)
    done = load_done("sx_art")
    todo = [a for a in arts if a["url"] not in done]
    log(f"shixin todo {len(todo)} / {len(arts)}")
    meta_path = os.path.join(TMP, "shixin_meta.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open main site (challenge)...")
        pw_open(page, SITE + "/col/col15616/index.html")
        n_ok = 0
        with open(meta_path, "a", encoding="utf-8") as mf:
            for i, a in enumerate(todo):
                key = hashlib.md5(a["url"].encode()).hexdigest()[:12]
                r = fetch_in(page, a["url"], home=SITE + "/col/col15616/index.html")
                if r["status"] == 200 and len(r["text"]) > 800:
                    fp = os.path.join(TMP, f"sxart_{key}.html")
                    open(fp, "w", encoding="utf-8").write(r["text"])
                    mf.write(json.dumps({**a, "key": key, "file": fp},
                                        ensure_ascii=False) + "\n")
                    mark({"phase": "sx_art", "key": a["url"], "ok": True})
                    n_ok += 1
                else:
                    mark({"phase": "sx_art", "key": a["url"], "ok": False,
                          "st": r["status"]})
                    log(f"  FAIL {a['url'][:70]} st={r['status']}")
                if (i + 1) % 20 == 0:
                    log(f"  {i+1}/{len(todo)} ok={n_ok}")
                polite()
        log(f"shixin done: ok={n_ok} fail={len(todo)-n_ok}")
        browser.close()


# ------------------------------------------------------------- 通知公告

def extract_jpage_params(col_html, cid):
    out = None
    m = re.search(r"var param_(\d+)\s*=\s*\{(.*?)\};", col_html, re.S)
    if m:
        uid, body = m.group(1), m.group(2)
        kv = dict(re.findall(r"(\w+)\s*:\s*['\"]?([^,'\"]*)['\"]?", body))
        out = {"unitid": uid, "columnid": kv.get("columnid", cid),
               "webid": kv.get("webid", "1"), "path": kv.get("path", SITE + "/"),
               "webname": kv.get("webname", "国家税务总局陕西省税务局"),
               "permissiontype": kv.get("permissiontype", "0")}
    if out is None:
        um = re.search(r"unitid=\s*'?(\d+)'?", col_html)
        out = {"unitid": um.group(1) if um else "", "columnid": cid, "webid": "1",
               "path": SITE + "/", "webname": "国家税务总局陕西省税务局",
               "permissiontype": "0"}
    pm = re.search(r"perPage\s*:\s*(\d+)", col_html)
    out["perpage"] = int(pm.group(1)) if pm else 15
    return out


def parse_dataproxy(txt):
    total = 0
    m = re.search(r"totalrecord=['\"]?(\d+)", txt)
    if m:
        total = int(m.group(1))
    items = []
    for rm in re.finditer(r"<record>(.*?)</record>", txt, re.S):
        seg = rm.group(1)
        a = re.search(r"href=['\"]?([^'\"\s>]+)", seg)
        if not a:
            continue
        url = a.group(1)
        tm = re.search(r"title=['\"]([^'\"]+)", seg)
        if tm:
            title = tm.group(1)
        else:
            am = re.search(r">([^<>]{5,120})</a>", seg)
            title = am.group(1).strip() if am else ""
        dm = re.search(r"(20\d{2}-\d{2}-\d{2})", seg)
        items.append((url, title.strip(), dm.group(1) if dm else ""))
    return total, items


def run_notice():
    """col5383 通知公告（关键词过滤）+ 详情抓取。"""
    from playwright.sync_api import sync_playwright
    kwp = re.compile(r"复议|送达|处罚|失信|违法|稽查|偷税|虚开|骗税|欠税|检查")
    done = load_done("notice_art")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open main site...")
        pw_open(page, SITE + "/index.html")
        col_url = SITE + "/col/col5383/index.html"
        r = fetch_in(page, col_url)
        hcol = r["text"]
        if r["status"] != 200 or len(hcol) < 2000:
            log(f"col5383 unavailable st={r['status']}")
            browser.close()
            return
        params = extract_jpage_params(hcol, "5383")
        log(f"col5383 params: {params}")
        base_q = (f"col=1&appid=1&webid={params['webid']}"
                  f"&path={quote(params['path'], safe='')}"
                  f"&columnid={params['columnid']}&sourceContentType=1"
                  f"&unitid={params['unitid']}"
                  f"&webname={quote(quote(params['webname'], safe=''), safe='')}"
                  f"&permissiontype={params['permissiontype']}")
        dp_url = SITE + "/module/web/jpage/dataproxy.jsp?" + base_q
        # 试探 perpage
        per = params.get("perpage", 15)
        for pp in (20, 15, 10):
            r = fetch_in(page, dp_url, body=None) if False else None
            break
        collected, seen = [], set()
        pageno = 1
        while pageno <= 60:
            body = f"startrecord={(pageno-1)*per+1}&endrecord={pageno*per}&perpage={per}"
            # dataproxy 需要 POST
            r2 = page.evaluate("""async (args) => {
              const r = await fetch(args.url, {method:'POST', credentials:'include',
                  headers:{'Content-Type':'application/x-www-form-urlencoded'},
                  body: args.body});
              const buf = await r.arrayBuffer();
              let text = new TextDecoder('utf-8').decode(buf);
              if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
              return {status: r.status, text: text};
            }""", {"url": dp_url, "body": body})
            tot, items = parse_dataproxy(r2["text"])
            new, stop_old = 0, False
            for u, title, d in items:
                au = urljoin(col_url + "/", u)
                if au in seen:
                    continue
                seen.add(au)
                new += 1
                if kwp.search(title or ""):
                    collected.append({"url": au, "title": title, "date": d})
                if d and d < DATE_FROM:
                    stop_old = True
            if new == 0 and pageno > 1:
                break
            log(f"col5383 p{pageno}: +{new} kw_kept={len(collected)}")
            if stop_old:
                break
            polite()
            pageno += 1
        # 详情
        todo = [a for a in collected if a["url"] not in done]
        log(f"notice todo: {len(todo)}")
        meta_path = os.path.join(TMP, "notice_meta.jsonl")
        n_ok = 0
        with open(meta_path, "a", encoding="utf-8") as mf:
            for i, a in enumerate(todo):
                key = hashlib.md5(a["url"].encode()).hexdigest()[:12]
                r = fetch_in(page, a["url"], home=col_url)
                if r["status"] == 200 and len(r["text"]) > 500:
                    fp = os.path.join(TMP, f"sxnt_{key}.html")
                    open(fp, "w", encoding="utf-8").write(r["text"])
                    mf.write(json.dumps({**a, "key": key, "file": fp},
                                        ensure_ascii=False) + "\n")
                    mark({"phase": "notice_art", "key": a["url"], "ok": True})
                    n_ok += 1
                else:
                    mark({"phase": "notice_art", "key": a["url"], "ok": False})
                if (i + 1) % 10 == 0:
                    log(f"  notice {i+1}/{len(todo)} ok={n_ok}")
                polite()
        log(f"notice done: ok={n_ok}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["xzcf", "shixin", "notice", "all"])
    ap.add_argument("--max-records", type=int, default=2000)
    args = ap.parse_args()
    if args.part in ("xzcf", "all"):
        run_xzcf(args.max_records)
    if args.part in ("shixin", "all"):
        run_shixin()
    if args.part in ("notice", "all"):
        run_notice()


if __name__ == "__main__":
    main()
