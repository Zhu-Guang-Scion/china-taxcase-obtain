# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
四川省税务局 — 有头 playwright 会话内抓取（瑞数反爬，北京同款手法）
=====================================================================
背景：sichuan.chinatax.gov.cn / etax.sichuan.chinatax.gov.cn 全站瑞数($_ts)。
cookie 复放 curl_cffi 一律 412（cookie 与 UA/会话绑定）——唯一可行路径：
有头 chromium 真实过挑战后，在页面上下文内 page.evaluate(fetch) 拿数据。

栏目：
  A. 主站 TRS col 栏目（jpage dataproxy.jsp 数据代理，15条/页）
     - col2720  行政处罚公示
     - col8705  税务行政一般程序处理结果（各市州稽查局，表格型正文）
     - col11932 行政处罚决定和结果
     （col8705/11932 的 /col/colNNNN/index.html 直访 404 —— 在运行时从
       col2720 文章页/变体路径再确认；dataproxy 参数从栏目页 param_{unitid} 提取）
  B. etax 行政执法信息公示平台（Spring JSON）
     POST /zfgspt/extranet/shgs/query_swxz_ybcx_cfjg.spring
     body: nsrmc=&shxydm=&cfjg=&xzcfjdswh=&ajmc=&zccfrqq=&zccfrqz=&type=gs
           &pageSize=N&pageIndex=0    （total≈1367）
  C. 重大税收违法失信案件信息（etax 菜单 data-url 为空，运行时探测）

用法：python sc_river.py --part cols   # 主站列表+详情 HTML 落 tmp/sc_pages/
      python sc_river.py --part md     # 离线 HTML → lawlibrary md
      python sc_river.py --part etax   # etax 平台结构化记录 → tmp/sc_etax/ + md
断点：progress/sc_cols.jsonl（已完成 URL/KEY 清单）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, hashlib, argparse
from datetime import date
from urllib.parse import urljoin, quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

TMP = os.path.join(ROOT, "tmp")
PAGES = os.path.join(TMP, "sc_pages"); os.makedirs(PAGES, exist_ok=True)
LISTS = os.path.join(TMP, "sc_lists"); os.makedirs(LISTS, exist_ok=True)
ETAXD = os.path.join(TMP, "sc_etax"); os.makedirs(ETAXD, exist_ok=True)
PROGDIR = os.path.join(ROOT, "progress"); os.makedirs(PROGDIR, exist_ok=True)
PROG = os.path.join(PROGDIR, "sc_cols.jsonl")

SITE = "https://sichuan.chinatax.gov.cn"
ETAX = "https://etax.sichuan.chinatax.gov.cn"
DATE_FROM = "2023-01-01"
DELAY_RANGE = (1.6, 2.8)
MAX_PER_COL = 1000

# 栏目 → 入库目录名（lawlibrary/专题/税务案例/四川省/ 下）
COLS = [
    {"cid": "2720",  "name": "行政处罚公示",       "out": "行政处罚公示"},
    {"cid": "8705",  "name": "一般程序处理结果",   "out": "行政处罚公示"},
    {"cid": "11932", "name": "行政处罚决定和结果", "out": "行政处罚公示"},
]

# 法定主动公开内容(col463) 下的失信/通知公告栏目（probe13 发现）
XZ_COLS = [
    {"cid": "20038", "name": "重大税收违法案件",   "out": "重大税收违法失信公布",
     "kw": None},
    {"cid": "19241", "name": "通知公告",           "out": "通知公告涉税公告",
     "kw": re.compile(r"复议|送达|处罚|失信|违法|稽查|偷税|虚开|骗税|欠税|检查")},
]
ATT_DIR = os.path.join(TMP, "sc_atts"); os.makedirs(ATT_DIR, exist_ok=True)

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
JS_FETCH_B64 = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return {status: r.status, b64: btoa(bin)};
}"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_done():
    done = set()
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                d = json.loads(ln)
                if d.get("phase") == "art":
                    done.add(d.get("key"))
            except Exception:
                pass
    return done


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def pw_open(page, url, tries=3):
    """带瑞数挑战等待的导航（北京经验：重载会自动完成）。"""
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            for _ in range(30):
                time.sleep(1)
                html = page.content()
                last = html
                if body_text_len(html) > 300 and "$_ts=window" not in html[:3000]:
                    return html
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:80]}")
            time.sleep(3)
    return last


def is_challenge(text, status):
    if status in (412, 900):
        return True
    if "$_ts=window" in text[:3000] or "$_ts.layouts" in text[:3000]:
        return True
    if len(text) < 500 and ("flash.js" in text or "1.1.1.3" in text):
        return True
    return False


def fetch_in(page, url, body=None, home=SITE + "/col/col2720/index.html", tries=4):
    """页面上下文内 fetch；若被再次挑战则回主页重过。"""
    for attempt in range(tries):
        try:
            if body is None:
                r = page.evaluate(JS_FETCH, url)
            else:
                r = page.evaluate(JS_POST, {"url": url, "body": body})
            if not is_challenge(r["text"], r["status"]):
                return r
            log(f"  fetch challenged (st={r['status']} len={len(r['text'])}), reload home #{attempt}")
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:80]}")
        pw_open(page, home)
        time.sleep(2)
    return {"status": 0, "text": ""}


def polite():
    time.sleep(random.uniform(*DELAY_RANGE))


DATE_RE = re.compile(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})")


def norm_date(s):
    m = DATE_RE.search(s or "")
    if not m:
        return ""
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    return f"{y}-{mo:02d}-{d:02d}"


# ---------------------------------------------------------------- cols 部分

def parse_dataproxy(txt):
    """解析 dataproxy.jsp 返回的 recordset → [(url,title,date)]，及 totalrecord。"""
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
        d = dm.group(1) if dm else norm_date(seg)
        items.append((url, title.strip(), d))
    return total, items


def extract_jpage_params(col_html, cid):
    """从栏目页提取 jpage 参数（优先 param_{unitid} JS 对象）。"""
    out = None
    m = re.search(r"var param_(\d+)\s*=\s*\{(.*?)\};", col_html, re.S)
    if m:
        uid, body = m.group(1), m.group(2)
        kv = dict(re.findall(r"(\w+)\s*:\s*['\"]?([^,'\"]*)['\"]?", body))
        out = {
            "unitid": uid, "columnid": kv.get("columnid", cid),
            "webid": kv.get("webid", "1"), "path": kv.get("path", SITE + "/"),
            "webname": kv.get("webname", "国家税务总局四川省税务局"),
            "permissiontype": kv.get("permissiontype", "0"),
        }
    if out is None:
        um = re.search(r"unitid=\s*'?(\d+)'?", col_html)
        out = {"unitid": um.group(1) if um else "", "columnid": cid, "webid": "1",
               "path": SITE + "/", "webname": "国家税务总局四川省税务局",
               "permissiontype": "0"}
    pm = re.search(r"perPage\s*:\s*(\d+)", col_html)
    out["perpage"] = int(pm.group(1)) if pm else 15
    ng = re.search(r"dataproxy\.jsp\?[^'\"<]+", col_html)
    out["nextgroup_url"] = ng.group(0) if ng else ""
    return out


def run_cols(max_arts=None):
    from playwright.sync_api import sync_playwright
    done = load_done()
    arts_meta_path = os.path.join(LISTS, "arts_meta.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        home = SITE + "/col/col2720/index.html"
        log("open home (challenge) ...")
        h = pw_open(page, home)
        log(f"home ready len={len(h)}")

        all_arts = []
        for col in COLS:
            cid = col["cid"]
            col_url = f"{SITE}/col/col{cid}/index.html"
            r = fetch_in(page, col_url)
            hcol = r["text"]
            ok = (r["status"] == 200 and len(hcol) > 2000
                  and "404" not in (hcol[:400] + hcol[-400:])
                  and "Not Found" not in hcol[:400])
            log(f"[col{cid}] st={r['status']} len={len(hcol)} ok={ok}")
            if not ok:
                # 变体尝试
                for var in [f"{SITE}/col{cid}/index.html", f"{SITE}/col/col{cid}/"]:
                    r = fetch_in(page, var)
                    hcol = r["text"]
                    if r["status"] == 200 and len(hcol) > 2000 and "Not Found" not in hcol[:400]:
                        col_url, ok = var, True
                        log(f"[col{cid}] variant hit: {var}")
                        break
            if not ok:
                log(f"[col{cid}] SKIP (list page unavailable)")
                continue
            params = extract_jpage_params(hcol, cid)
            log(f"[col{cid}] jpage params: {params}")
            tr = re.search(r"totalRecord:\s*(\d+)", hcol)
            log(f"[col{cid}] page totalRecord={tr.group(1) if tr else '?'}")

            # dataproxy 翻页（构造 + nextgroup 两种 URL 形态轮流试）
            base_q = (f"col=1&appid=1&webid={params['webid']}"
                      f"&path={quote(params['path'], safe='')}"
                      f"&columnid={params['columnid']}&sourceContentType=1"
                      f"&unitid={params['unitid']}"
                      f"&webname={quote(quote(params['webname'], safe=''), safe='')}"
                      f"&permissiontype={params['permissiontype']}")
            dp_urls = [f"{SITE}/module/web/jpage/dataproxy.jsp?{base_q}"]
            if params.get("nextgroup_url"):
                ng = params["nextgroup_url"]
                if ng.startswith("/"):
                    ng = SITE + ng
                dp_urls.append(ng)

            per = params.get("perpage", 15)
            collected, seen, total = [], set(), 0
            dp_working = None
            for pageno in range(1, 80):
                start = (pageno - 1) * per + 1
                end = pageno * per
                body = f"startrecord={start}&endrecord={end}&perpage={per}"
                got = None
                for du in ([dp_working] if dp_working else dp_urls):
                    r = fetch_in(page, du, body=body, home=col_url)
                    tot, items = parse_dataproxy(r["text"])
                    if items or tot:
                        if dp_working is None:
                            dp_working = du
                            log(f"[col{cid}] dataproxy URL works: {du[:90]}...")
                        got = (tot, items)
                        break
                if not got:
                    log(f"[col{cid}] page {pageno}: no data, stop")
                    break
                tot, items = got
                if tot:
                    total = tot
                new = 0
                stop_old = False
                for u, title, d in items:
                    au = urljoin(col_url + "/", u)
                    if au in seen:
                        continue
                    seen.add(au)
                    new += 1
                    collected.append({"url": au, "title": title, "date": d, "cid": cid})
                    if d and d < DATE_FROM:
                        stop_old = True
                log(f"[col{cid}] p{pageno}: +{new} (total_rec={total}, got={len(collected)})")
                if stop_old:
                    log(f"[col{cid}] reached < {DATE_FROM}, stop paging")
                    break
                if total and len(collected) >= total:
                    break
                if len(collected) >= MAX_PER_COL:
                    log(f"[col{cid}] hit MAX_PER_COL")
                    break
                if new == 0 and pageno > 1:
                    break
                polite()
            # 落盘列表
            lst = os.path.join(LISTS, f"col{cid}.json")
            json.dump({"col": col, "params": params, "total": total,
                       "items": collected}, open(lst, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            log(f"[col{cid}] saved list: {len(collected)} items -> {lst}")
            all_arts.extend(collected)

        # ---- 详情抓取 ----
        json.dump(all_arts, open(os.path.join(LISTS, "all_arts.json"), "w",
                                 encoding="utf-8"), ensure_ascii=False, indent=1)
        todo = [a for a in all_arts if a["url"] not in done]
        if max_arts:
            todo = todo[:max_arts]
        log(f"details todo: {len(todo)} / {len(all_arts)}")
        n_ok = 0
        for i, a in enumerate(todo):
            key = hashlib.md5(a["url"].encode()).hexdigest()[:12]
            r = fetch_in(page, a["url"], home=SITE + "/")
            txt = r["text"]
            if r["status"] == 200 and len(txt) > 500:
                fp = os.path.join(PAGES, f"{key}.html")
                open(fp, "w", encoding="utf-8").write(txt)
                a2 = dict(a); a2["key"] = key; a2["file"] = fp
                with open(arts_meta_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(a2, ensure_ascii=False) + "\n")
                mark({"key": a["url"], "phase": "art", "st": r["status"],
                      "cid": a["cid"], "ts": time.strftime("%H:%M:%S")})
                n_ok += 1
            else:
                mark({"key": a["url"], "phase": "art_fail", "st": r["status"],
                      "cid": a["cid"], "len": len(txt), "ts": time.strftime("%H:%M:%S")})
                log(f"  FAIL {a['url']} st={r['status']} len={len(txt)}")
            if (i + 1) % 10 == 0:
                log(f"  details {i+1}/{len(todo)} ok={n_ok}")
            polite()
        log(f"details done: ok={n_ok} fail={len(todo)-n_ok}")
        browser.close()


# ---------------------------------------------------------------- etax 部分

ETAX_Q = ETAX + "/zfgspt/extranet/shgs/query_swxz_ybcx_cfjg.spring"


def parse_json_loose(s):
    """arrayBuffer+TextDecoder 已得干净文本；万一仍乱码（charset 头错误遗留）再还原。"""
    try:
        return json.loads(s)
    except Exception:
        pass
    for enc in ("gbk", "gb18030"):
        try:
            return json.loads(s.encode(enc).decode("utf-8"))
        except Exception:
            continue
    raise ValueError(f"json parse fail: {s[:80]!r}")


def run_etax(max_records=1000):
    from playwright.sync_api import sync_playwright
    rec_path = os.path.join(ETAXD, "records.jsonl")
    done_keys = set()
    if os.path.exists(rec_path):
        for ln in open(rec_path, encoding="utf-8"):
            try:
                done_keys.add(json.loads(ln)["KEY"])
            except Exception:
                pass
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open etax xzcf (challenge) ...")
        pw_open(page, ETAX + "/zfgspt/extranet/xzcf?city=ybs_3")
        log("etax ready")

        # 探 pageSize 上限
        ps_cap = 50
        for ps in (200, 100, 50):
            r = fetch_in(page, ETAX_Q, body=(
                "nsrmc=&shxydm=&cfjg=&xzcfjdswh=&ajmc=&zccfrqq=&zccfrqz="
                f"&type=gs&pageSize={ps}&pageIndex=0"), home=ETAX + "/zfgspt/extranet/xzcf?city=ybs_3")
            try:
                d = parse_json_loose(r["text"])
                n = len(d.get("data", []))
                log(f"[etax] pageSize={ps} → n={n} total={d.get('total')}")
                if n == ps:
                    ps_cap = ps
                    break
                if n:
                    ps_cap = ps
                    break
            except Exception as e:
                log(f"[etax] pageSize={ps} parse fail {e}")
        log(f"[etax] using pageSize={ps_cap}")

        fw = open(rec_path, "a", encoding="utf-8")
        got, pagei, empty_hits = 0, 0, 0
        total = None
        orgs = {}
        while pagei < 40:
            r = fetch_in(page, ETAX_Q, body=(
                "nsrmc=&shxydm=&cfjg=&xzcfjdswh=&ajmc=&zccfrqq=&zccfrqz="
                f"&type=gs&pageSize={ps_cap}&pageIndex={pagei}"), home=ETAX + "/zfgspt/extranet/xzcf?city=ybs_3")
            try:
                d = parse_json_loose(r["text"])
            except Exception:
                log(f"[etax] p{pagei} parse fail st={r['status']} len={len(r['text'])}")
                empty_hits += 1
                if empty_hits >= 3:
                    break
                continue
            data = d.get("data", [])
            total = d.get("total", total)
            if not data:
                log(f"[etax] p{pagei} empty, stop")
                break
            for rec in data:
                k = rec.get("KEY") or rec.get("XZCFJDSWH", "")
                if k in done_keys:
                    continue
                fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                done_keys.add(k)
                got += 1
                org = (rec.get("SWJGMC") or "")[:12]
                orgs[org] = orgs.get(org, 0) + 1
            log(f"[etax] p{pagei}: +{len(data)} (cum new={got}, total={total})")
            if got >= max_records:
                log("[etax] hit max_records")
                break
            if total and got >= int(total):
                break
            pagei += 1
            polite()
        fw.close()
        log(f"[etax] orgs sample: {sorted(orgs.items(), key=lambda x: -x[1])[:8]}")

        # ---- 失信入口探测 ----
        probes = []
        for u in [ETAX + "/zfgspt", ETAX + "/zfgspt/extranet/zdsswf",
                  ETAX + "/zfgspt/extranet/zdsswfsxajggl",
                  ETAX + "/zfgspt/extranet/qtsx?city=ybs_3"]:
            r = fetch_in(page, u, home=ETAX + "/zfgspt/extranet/xzcf?city=ybs_3")
            t = re.search(r"<title>(.*?)</title>", r["text"], re.S)
            menus = re.findall(r'title="([^"]{2,20})"[^>]*data-url="([^"]*)"', r["text"])
            probes.append({"url": u, "st": r["status"], "len": len(r["text"]),
                           "title": t.group(1).strip()[:40] if t else "",
                           "menus": menus[:12]})
            log(f"[probe] {u} st={r['status']} len={len(r['text'])} menus={menus[:8]}")
        for ep in ["query_swxz_zdsswf.spring", "query_zdsswf.spring",
                   "query_swxz_sfaj.spring", "query_swxz_sswfaj.spring"]:
            r = fetch_in(page, ETAX + "/zfgspt/extranet/shgs/" + ep,
                         body="type=gs&pageSize=5&pageIndex=0",
                         home=ETAX + "/zfgspt/extranet/xzcf?city=ybs_3")
            log(f"[probe ep] {ep} st={r['status']} len={len(r['text'])} {r['text'][:80]!r}")
            probes.append({"ep": ep, "st": r["status"], "len": len(r["text"]),
                           "head": r["text"][:120]})
        json.dump(probes, open(os.path.join(ETAXD, "shixin_probes.json"), "w",
                               encoding="utf-8"), ensure_ascii=False, indent=1)
        browser.close()


def run_xz():
    """col20038 重大税收违法案件（全量近三年）+ col19241 通知公告（关键词过滤）。"""
    from playwright.sync_api import sync_playwright
    done = load_done()
    arts_meta_path = os.path.join(LISTS, "arts_meta.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open home (challenge) ...")
        pw_open(page, SITE + "/index.html")
        log("home ready")

        all_arts = []
        for col in XZ_COLS:
            cid = col["cid"]
            col_url = f"{SITE}/col/col{cid}/index.html"
            r = fetch_in(page, col_url)
            hcol = r["text"]
            if r["status"] != 200 or len(hcol) < 2000:
                log(f"[col{cid}] unavailable st={r['status']} len={len(hcol)}")
                continue
            params = extract_jpage_params(hcol, cid)
            base_q = (f"col=1&appid=1&webid={params['webid']}"
                      f"&path={quote(params['path'], safe='')}"
                      f"&columnid={params['columnid']}&sourceContentType=1"
                      f"&unitid={params['unitid']}"
                      f"&webname={quote(quote(params['webname'], safe=''), safe='')}"
                      f"&permissiontype={params['permissiontype']}")
            dp_url = f"{SITE}/module/web/jpage/dataproxy.jsp?{base_q}"
            per = params.get("perpage", 15)
            collected, seen, total = [], set(), 0
            for pageno in range(1, 120):
                start = (pageno - 1) * per + 1
                r = fetch_in(page, dp_url, body=f"startrecord={start}&endrecord={pageno * per}&perpage={per}",
                             home=col_url)
                tot, items = parse_dataproxy(r["text"])
                if tot:
                    total = tot
                new, stop_old = 0, False
                for u, title, d in items:
                    au = urljoin(col_url + "/", u)
                    if au in seen:
                        continue
                    seen.add(au)
                    new += 1
                    keep = True
                    if col.get("kw"):
                        keep = bool(col["kw"].search(title or ""))
                    collected.append({"url": au, "title": title, "date": d, "cid": cid,
                                      "kw_hit": keep})
                    if d and d < DATE_FROM:
                        stop_old = True
                if new == 0 and pageno > 1:
                    log(f"[col{cid}] p{pageno}: no new, stop")
                    break
                log(f"[col{cid}] p{pageno}: +{new} (cum={len(collected)}, total={total})")
                if stop_old:
                    log(f"[col{cid}] reached < {DATE_FROM}")
                    break
                if total and len(collected) >= total:
                    break
                polite()
            keep_arts = [a for a in collected if a["kw_hit"]]
            log(f"[col{cid}] enumerated={len(collected)} kw_kept={len(keep_arts)}")
            json.dump({"col": {k: v for k, v in col.items() if k != "kw"},
                       "params": params, "total": total, "items": collected},
                      open(os.path.join(LISTS, f"col{cid}.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            all_arts.extend(keep_arts)

        todo = [a for a in all_arts if a["url"] not in done]
        log(f"details todo: {len(todo)} / {len(all_arts)}")
        n_ok = 0
        for i, a in enumerate(todo):
            key = hashlib.md5(a["url"].encode()).hexdigest()[:12]
            r = fetch_in(page, a["url"], home=SITE + "/index.html")
            txt = r["text"]
            if r["status"] == 200 and len(txt) > 500:
                fp = os.path.join(PAGES, f"{key}.html")
                open(fp, "w", encoding="utf-8").write(txt)
                a2 = dict(a); a2["key"] = key; a2["file"] = fp
                # 附件下载（PDF/doc，复议决定书多为附件）——二进制 base64 通道
                atts = []
                for am in re.finditer(r'href=[\'"]([^\'"]+?\.(?:pdf|docx?|xlsx?))[\'"]', txt, re.I):
                    au2 = urljoin(a["url"], am.group(1))
                    atts.append(au2)
                a2["atts"] = atts
                with open(arts_meta_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(a2, ensure_ascii=False) + "\n")
                for au2 in atts[:6]:
                    an = os.path.basename(au2.split("?")[0])[:60] or "att"
                    ak = hashlib.md5(au2.encode()).hexdigest()[:12] + "_" + an
                    afp = os.path.join(ATT_DIR, ak)
                    if os.path.exists(afp):
                        continue
                    try:
                        r2 = page.evaluate(JS_FETCH_B64, au2)
                        if r2["status"] == 200 and r2.get("b64"):
                            import base64
                            raw = base64.b64decode(r2["b64"])
                            open(afp, "wb").write(raw)
                            log(f"    att ok {an} {len(raw)}B")
                    except Exception as e:
                        log(f"    att fail {an}: {str(e)[:60]}")
                    polite()
                mark({"key": a["url"], "phase": "art", "st": r["status"], "cid": a["cid"],
                      "ts": time.strftime("%H:%M:%S")})
                n_ok += 1
            else:
                mark({"key": a["url"], "phase": "art_fail", "st": r["status"], "cid": a["cid"],
                      "len": len(txt), "ts": time.strftime("%H:%M:%S")})
                log(f"  FAIL {a['url']} st={r['status']}")
            if (i + 1) % 10 == 0:
                log(f"  details {i+1}/{len(todo)} ok={n_ok}")
            polite()
        log(f"details done: ok={n_ok} fail={len(todo)-n_ok}")
        browser.close()


JS_POST_JSON = """async (args) => {
  const r = await fetch(args.url, {method:'POST', credentials:'include',
      headers:{'Content-Type':'application/json',
               'X-Requested-With':'XMLHttpRequest',
               'Accept':'application/json, text/javascript, */*; q=0.01'},
      body: args.body});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""

SX_FETCH_FIELDS = ("title,url,column,module,deploytime,zdnsrmc,zdnsrsbh,zdzzjgdm,"
                   "zdzcdz,zdfddbr,zdcwfzr,zdgbjg,zdajxz,zdwfqjfr,zdsjfzr,zdzjjg,"
                   "zdzywfss,zdswclcf")
SEARCH_DO = SITE + "/jsearchfront/plugin/interface/search/search.do"


JS_JQ_SEARCH = """async (args) => {
  return await new Promise(resolve => {
    $.ajax({
      url: "/jsearchfront/plugin/interface/search/search.do",
      type: "post", timeout: 15000, dataType: "json",
      contentType: "application/json",
      data: JSON.stringify({
        groupFields: null, q: args.q,
        groupTargets: {websiteid: "510000000000000"},
        signs: "JCMS",
        fetch_fields: args.fields,
        filterQuery: args.filterQuery,
        p: args.p, pg: args.pg
      }),
      success: r => resolve({ok: true, total: r.total || 0,
                             rows: r.dataResults || []}),
      error: (x, s2) => resolve({ok: false, status: x.status, total: 0, rows: []})
    });
  });
}"""


def search_do(page, column=None, q="", p=1, pg=15, fields=None):
    """必须走页面自身 jQuery $.ajax（裸 fetch 一律 415）。"""
    fq = f"+(column:{column})" if column else "*"
    r = page.evaluate(JS_JQ_SEARCH, {"q": q, "fields": fields or SX_FETCH_FIELDS,
                                     "filterQuery": fq, "p": p, "pg": pg})
    if not r.get("ok"):
        log(f"  search_do jq fail p{p} st={r.get('status')}")
        return 0, []
    return r["total"], r["rows"]


def run_sx():
    """一回合搞定：col19241 通知公告关键词 + col20038 失信(jsearch) + 复议全站搜索。"""
    from playwright.sync_api import sync_playwright
    done = load_done()
    arts_meta_path = os.path.join(LISTS, "arts_meta.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open home (challenge) ...")
        pw_open(page, SITE + "/index.html")
        log("home ready")

        all_arts = []

        # ---- A) col20038 失信公布栏（jsearch search.do，页面 jQuery）----
        for pg_try in (100, 50, 15):
            total, rows = search_do(page, column="20038", p=1, pg=pg_try)
            if len(rows) >= min(pg_try, total or pg_try):
                pgsize = pg_try
                break
        else:
            pgsize = 15
        log(f"[shixin] pgsize={pgsize}")
        log(f"[shixin] p1 total={total} rows={len(rows)}")
        if rows:
            k0 = rows[0]
            log(f"[shixin] row keys: {sorted(k0.keys())}")
            log(f"[shixin] sample: {json.dumps(k0, ensure_ascii=False)[:400]}")
        sx_path = os.path.join(ETAXD, "shixin_rows.jsonl")
        fw = open(sx_path, "w", encoding="utf-8")
        seen = set()
        for r in rows:
            u = r.get("url") or ""
            if u and u not in seen:
                seen.add(u); fw.write(json.dumps(r, ensure_ascii=False) + "\n")
        fw.close()
        pageno = 2
        while total and len(seen) < min(total, 1000) and pageno <= 80:
            time.sleep(random.uniform(1.6, 2.6))
            t2, rows2 = search_do(page, column="20038", p=pageno, pg=pgsize)
            newn = 0
            fa = open(sx_path, "a", encoding="utf-8")
            for r in rows2:
                u = r.get("url") or ""
                if u and u not in seen:
                    seen.add(u); fa.write(json.dumps(r, ensure_ascii=False) + "\n")
                    newn += 1
            fa.close()
            log(f"[shixin] p{pageno}: +{newn} (cum={len(seen)}/{total})")
            if newn == 0:
                break
            pageno += 1
        log(f"[shixin] rows saved: {len(seen)} -> {sx_path}")
        # 失信详情页（若行字段缺主要违法事实则抓详情）
        need_detail = []
        for u in seen:
            need_detail.append({"url": u, "title": "", "date": "", "cid": "20038d"})
        if rows and clean_str(rows[0].get("zdzywfss")):
            log("[shixin] rows carry zdzywfss -> skip detail pages")
        else:
            all_arts.extend(need_detail[:400])

        # ---- B) col19241 通知公告（dataproxy + 关键词）----
        kwp = re.compile(r"复议|送达|处罚|失信|违法|稽查|偷税|虚开|骗税|欠税")
        for cid, per in [("19241", 20)]:
            col_url = f"{SITE}/col/col{cid}/index.html"
            r = fetch_in(page, col_url)
            hcol = r["text"]
            if r["status"] != 200 or len(hcol) < 2000:
                log(f"[col{cid}] unavailable")
                continue
            params = extract_jpage_params(hcol, cid)
            base_q = (f"col=1&appid=1&webid={params['webid']}"
                      f"&path={quote(params['path'], safe='')}"
                      f"&columnid={params['columnid']}&sourceContentType=1"
                      f"&unitid={params['unitid']}"
                      f"&webname={quote(quote(params['webname'], safe=''), safe='')}"
                      f"&permissiontype={params['permissiontype']}")
            dp_url = f"{SITE}/module/web/jpage/dataproxy.jsp?{base_q}"
            collected, seenc, stop_all = [], set(), False
            for pageno in range(1, 60):
                r = fetch_in(page, dp_url, body=f"startrecord={(pageno-1)*per+1}&endrecord={pageno*per}&perpage={per}",
                             home=col_url)
                tot, items = parse_dataproxy(r["text"])
                new, stop_old = 0, False
                for u, title, d in items:
                    au = urljoin(col_url + "/", u).replace("http://sichuan.", "https://sichuan.")
                    if au in seenc:
                        continue
                    seenc.add(au); new += 1
                    if kwp.search(title or ""):
                        collected.append({"url": au, "title": title, "date": d, "cid": cid})
                    if d and d < DATE_FROM:
                        stop_old = True
                if new == 0 and pageno > 1:
                    break
                log(f"[col{cid}] p{pageno}: +{new} (kw_kept={len(collected)})")
                if stop_old:
                    break
                polite()
            all_arts.extend(collected)

        # ---- C) 全站搜索：行政复议决定书 ----
        for q in ["行政复议决定书"]:
            total, rows = search_do(page, column=None, q=q, p=1, pg=15)
            log(f"[qsearch {q}] total={total}")
            seenc = set()
            pageno = 1
            while total and pageno <= 20:
                if pageno > 1:
                    time.sleep(random.uniform(1.6, 2.6))
                    total, rows = search_do(page, column=None, q=q, p=pageno, pg=15)
                newn = 0
                for r in rows:
                    u = (r.get("url") or "").replace("http://sichuan.", "https://sichuan.")
                    t = (r.get("title") or "")
                    if not u or u in seenc:
                        continue
                    seenc.add(u)
                    if "sichuan.chinatax.gov.cn" not in u:
                        continue
                    if not re.search(r"复议", t or ""):
                        continue
                    dm = ""
                    m = re.search(r"(20\d{2}-\d{2}-\d{2})", str(r.get("deploytime") or ""))
                    if m:
                        dm = m.group(1)
                    else:
                        m = re.search(r"(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})", str(r.get("deploytime") or ""))
                        dm = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
                    all_arts.append({"url": u, "title": t, "date": dm, "cid": "fuyi"})
                    newn += 1
                log(f"[qsearch {q}] p{pageno}: +{newn} (kept={len([a for a in all_arts if a['cid']=='fuyi'])})")
                if newn == 0:
                    break
                if len(seenc) >= total:
                    break
                pageno += 1

        # ---- 详情抓取（含附件）----
        todo = [a for a in all_arts if a["url"].replace("http://sichuan.", "https://sichuan.") not in done and a["url"] not in done]
        log(f"details todo: {len(todo)} / {len(all_arts)}")
        n_ok = 0
        for i, a in enumerate(todo):
            a["url"] = a["url"].replace("http://sichuan.", "https://sichuan.")
            key = hashlib.md5(a["url"].encode()).hexdigest()[:12]
            try:
                r = fetch_in(page, a["url"], home=SITE + "/index.html")
            except Exception as e:
                log(f"  exc {a['url'][:60]}: {str(e)[:50]}")
                continue
            txt = r["text"]
            if r["status"] == 200 and len(txt) > 500:
                fp = os.path.join(PAGES, f"{key}.html")
                open(fp, "w", encoding="utf-8").write(txt)
                a2 = dict(a); a2["key"] = key; a2["file"] = fp
                atts = []
                for am in re.finditer(r'href=[\'"]([^\'"]+?\.(?:pdf|docx?|xlsx?))[\'"]', txt, re.I):
                    atts.append(urljoin(a["url"], am.group(1)))
                a2["atts"] = atts
                with open(arts_meta_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(a2, ensure_ascii=False) + "\n")
                for au2 in atts[:6]:
                    an = os.path.basename(au2.split("?")[0])[:60] or "att"
                    ak = hashlib.md5(au2.encode()).hexdigest()[:12] + "_" + an
                    afp = os.path.join(ATT_DIR, ak)
                    if os.path.exists(afp):
                        continue
                    try:
                        import base64
                        r2 = page.evaluate(JS_FETCH_B64, au2)
                        if r2["status"] == 200 and r2.get("b64"):
                            raw = base64.b64decode(r2["b64"])
                            open(afp, "wb").write(raw)
                    except Exception:
                        pass
                    polite()
                mark({"key": a["url"], "phase": "art", "st": r["status"], "cid": a["cid"],
                      "ts": time.strftime("%H:%M:%S")})
                n_ok += 1
            else:
                mark({"key": a["url"], "phase": "art_fail", "st": r["status"], "cid": a["cid"],
                      "ts": time.strftime("%H:%M:%S")})
            if (i + 1) % 10 == 0:
                log(f"  details {i+1}/{len(todo)} ok={n_ok}")
            polite()
        log(f"details done: ok={n_ok} fail={len(todo)-n_ok}")
        browser.close()


def clean_str(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["cols", "xz", "sx", "md", "etax"])
    ap.add_argument("--max-arts", type=int, default=None)
    ap.add_argument("--max-records", type=int, default=1000)
    args = ap.parse_args()
    if args.part == "cols":
        run_cols(args.max_arts)
    elif args.part == "xz":
        run_xz()
    elif args.part == "sx":
        run_sx()
    elif args.part == "etax":
        run_etax(args.max_records)
    elif args.part == "md":
        from sc_river_md import run_md
        run_md()


if __name__ == "__main__":
    main()
