# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆收割（三源）：
  --part xzcf : 8888 行政执法公示平台 处罚结果（验证码 ddddocr 破解）
  --part sx   : 重大税收违法失信主体（/api/qeuryZdaj + /api/queryZdajById，无验证码）
  --part news : /cqtax/ 税务新闻 + 通知公告 关键词文章
断点 progress/hb_cq_r6.jsonl ；原始 tmp/hb_cq/
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, hashlib, argparse, base64

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq"); os.makedirs(TMP, exist_ok=True)
PROG = os.path.join(ROOT, "progress", "hb_cq_r6.jsonl")

DATE_FROM = "2023-01-01"
PLAT = "http://chongqing.chinatax.gov.cn:8888"
B = "https://chongqing.chinatax.gov.cn"

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


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def load_done(prefix):
    s = set()
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                k = json.loads(ln).get("key", "")
                if k.startswith(prefix):
                    s.add(k)
            except Exception:
                pass
    return s


def btl(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", m.group(1) if m else "")))


def pw_open(page, url, tries=3):
    last = ""
    for _ in range(tries):
        try:
            page.goto(url, timeout=70000, wait_until="domcontentloaded")
            for _ in range(40):
                time.sleep(1)
                last = page.content()
                if btl(last) > 250 and "$_ts=window" not in last[:3000]:
                    return last
        except Exception as e:
            log(f"  pw_open exc {str(e)[:80]}")
            time.sleep(3)
    return last


def polite(a=1.7, b=3.0):
    time.sleep(random.uniform(a, b))


# ---------------------------------------------------------------- xzcf（验证码平台）

JS_AJAX_JSON = """async (args) => {
  return await new Promise(resolve => {
    $.ajax({type:'post', url: args.url, data: args.data, timeout: args.to || 25000,
      success: r => resolve(r),
      error: (x, s) => resolve({__err: s, __st: x.status})});
  });
}"""


def get_captcha_ocr(page, ocr):
    r = page.evaluate(JS_FETCH_B64, PLAT + "/verifyCode/getVerifyCode")
    if r["status"] != 200 or not r.get("b64"):
        return None
    raw = base64.b64decode(r["b64"])
    fp = os.path.join(TMP, "_cap.png")
    open(fp, "wb").write(raw)
    code = ocr.classification(raw)
    return code.strip()


def run_xzcf(max_pages=60):
    import ddddocr
    from playwright.sync_api import sync_playwright
    ocr = ddddocr.DdddOcr(show_ad=False)
    out = os.path.join(TMP, "cq_xzcf_records.jsonl")
    seen = set()
    if os.path.exists(out):
        for ln in open(out, encoding="utf-8"):
            try:
                d = json.loads(ln)
                seen.add(d.get("_key") or json.dumps(d, ensure_ascii=False)[:80])
            except Exception:
                pass
    fw = open(out, "a", encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        log("open platform ...")
        pw_open(page, PLAT + "/sjzfgs/xzcf/swxzybcxcfjg")

        def query(pageno, rows=15, code=None, select1=1):
            data = {"twolm": "swxzybcxcfjg", "siteCode": "sj", "rows": str(rows),
                    "page": str(pageno)}
            if code:
                data["checkVerifyCode"] = code
            r = page.evaluate(JS_AJAX_JSON, {"url": "/api/loadNewsInfo", "data": data, "to": 30000})
            return r

        # --- 首次：解验证码 ---
        cur_code = [None]
        def query_with_cap(pageno, rows):
            for attempt in range(10):
                code = cur_code[0] or get_captcha_ocr(page, ocr)
                if not code:
                    log("  captcha fetch fail, retry")
                    time.sleep(2)
                    continue
                r = query(pageno, rows, code)
                if isinstance(r, dict) and r.get("state") == 2222:
                    log(f"  cap wrong ({code!r}), retry #{attempt}")
                    cur_code[0] = None
                    time.sleep(1.2)
                    continue
                # 成功后验证码可能仍有效 → 保留 cur_code 供下页试探
                return r
            return {"__err": "captcha-exhausted"}

        cur_code[0] = None
        r1 = query_with_cap(1, 15)
        log(f"p1 result keys: {str(r1)[:220]}")
        if r1.get("state") == 0:
            total = r1.get("dataTotal") or {}
            log(f"dataTotal={total}")
            rows_all = []
            for k, v in (r1.get("data") or {}).items():
                rows_all.extend(v or [])
                log(f"  data[{k}]: {len(v or [])} rows; sample keys: "
                    f"{sorted((v or [{}])[0].keys())[:12] if v else []}")
            for rec in rows_all:
                k = json.dumps(rec, ensure_ascii=False, sort_keys=True)[:100]
                if k not in seen:
                    seen.add(k)
                    rec["_key"] = k
                    fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fw.flush()
            # 总量
            tot = sum(int(v) for v in total.values()) if total else len(rows_all)
            log(f"total≈{tot}")
            npages = min(max_pages, (tot // 15) + 2)
            for pn in range(2, npages + 1):
                # 先试旧验证码
                r = query(pn, 15, cur_code[0]) if cur_code[0] else None
                if isinstance(r, dict) and r.get("state") == 2222:
                    cur_code[0] = None
                    r = query_with_cap(pn, 15)
                if not isinstance(r, dict) or r.get("state") != 0:
                    log(f"p{pn} fail: {str(r)[:120]}")
                    break
                n_new = 0
                for k, v in (r.get("data") or {}).items():
                    for rec in (v or []):
                        kk = json.dumps(rec, ensure_ascii=False, sort_keys=True)[:100]
                        if kk not in seen:
                            seen.add(kk)
                            rec["_key"] = kk
                            fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            n_new += 1
                fw.flush()
                log(f"p{pn}: +{n_new} (cum={len(seen)})")
                if n_new == 0 and pn > 3:
                    break
                polite()
        fw.close()
        browser.close()
    log(f"xzcf done, records={len(seen)}")


# ---------------------------------------------------------------- sx（失信）

def run_sx(max_records=2000):
    from playwright.sync_api import sync_playwright
    rows_path = os.path.join(TMP, "cq_sx_rows.jsonl")
    det_path = os.path.join(TMP, "cq_sx_details.jsonl")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        log("open zdwfajcx ...")
        pw_open(page, "http://chongqing.chinatax.gov.cn/xxgkxt/pages/qywh/zdwfajcx.html")

        JS_SX = """async (args) => {
          return await new Promise(resolve => {
            $.ajax({type:'post', url: args.url, data: args.data, timeout: 25000,
              success: r => resolve(r),
              error: (x,s) => resolve({__err:s, __st:x.status})});
          });
        }"""

        def q(**kw):
            base = {"sftz": "Y", "pageSize": "200", "pageIndex": "1", "dp": "",
                    "ajxz": "", "nd": "", "nsrmc": "", "nsrsbh": "", "zcdz": "",
                    "zzjgdm": "", "frxm": "", "frzjhm": "", "cwfwrxm": "", "cwfwrsfz": ""}
            base.update({k: str(v) for k, v in kw.items()})
            return page.evaluate(JS_SX, {"url": "/api/qeuryZdaj",
                                         "data": {"jsonstr": json.dumps(base, ensure_ascii=False)}})

        # 枚举案件性质 1-9 a b（必须带条件才出数据）
        seen, total_sum = set(), 0
        fw = open(rows_path, "w", encoding="utf-8")
        for ajxz in list("123456789") + ["a", "b"]:
            pageno = 1
            empty_hit = 0
            while pageno <= 40:
                r = q(ajxz=ajxz, pageIndex=pageno)
                if not (isinstance(r, dict) and r.get("success")):
                    log(f"[ajxz={ajxz}] p{pageno} fail: {str(r)[:100]}")
                    empty_hit += 1
                    if empty_hit >= 2:
                        break
                    continue
                data = r.get("data") or []
                flat = list(data.values())[0] if isinstance(data, dict) else data
                new = 0
                for rec in (flat or []):
                    k = str(rec.get("id") or "") + "|" + str(rec.get("type") or "")
                    if not rec.get("id") or k in seen:
                        continue
                    seen.add(k)
                    fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    new += 1
                if pageno == 1:
                    total_sum += int(r.get("total") or 0)
                    log(f"[ajxz={ajxz}] total={r.get('total')}")
                log(f"[ajxz={ajxz}] p{pageno}: +{new} (cum={len(seen)})")
                if new == 0:
                    break
                if len(seen) >= max_records:
                    break
                pageno += 1
                polite()
            fw.flush()
            if len(seen) >= max_records:
                log("hit max_records")
                break
        fw.close()
        log(f"sx rows={len(seen)} (sum totals={total_sum})")

        # 详情
        ids = []
        for ln in open(rows_path, encoding="utf-8"):
            try:
                d = json.loads(ln)
                ids.append((str(d.get("id")), str(d.get("type") or ""), d))
            except Exception:
                pass
        done_ids = set()
        if os.path.exists(det_path):
            for ln in open(det_path, encoding="utf-8"):
                try:
                    done_ids.add(json.loads(ln).get("id"))
                except Exception:
                    pass
        fd = open(det_path, "a", encoding="utf-8")
        for i, (rid, typ, base) in enumerate(ids):
            if rid in done_ids or rid == "None":
                continue
            r = page.evaluate(JS_SX, {"url": "/api/queryZdajById", "data": {"id": rid}})
            if isinstance(r, dict) and r.get("success"):
                val = r.get("value") or {}
                val["_id"] = rid
                val["_type"] = typ
                val["_listRow"] = {k: base.get(k) for k in ("swjgmc", "mc", "hm", "ajxz")}
                fd.write(json.dumps(val, ensure_ascii=False) + "\n")
            else:
                log(f"  detail fail {rid}: {str(r)[:80]}")
                time.sleep(1.5)
            if (i + 1) % 25 == 0:
                log(f"  details {i+1}/{len(ids)}")
                fd.flush()
            polite(1.5, 2.6)
        fd.close()
        browser.close()
    log("sx done")


# ---------------------------------------------------------------- news（文章）

NEWS_COLS = [
    {"name": "swxw", "url": f"{B}/cqtax/xwdt/swxw/", "label": "税务新闻"},
    {"name": "tzgg", "url": f"{B}/cqtax/xxgk/tzgg/", "label": "通知公告"},
]
KW = re.compile(r"处罚|失信|违法|稽查|偷税|虚开|骗税|欠税|曝光|查处|复议|送达|典型案例|税案")
DATE_RE = re.compile(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})")


def norm_date(s):
    m = DATE_RE.search(s or "")
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def run_news(max_arts=300):
    from playwright.sync_api import sync_playwright
    pages_dir = os.path.join(TMP, "cq_pages"); os.makedirs(pages_dir, exist_ok=True)
    meta_path = os.path.join(TMP, "cq_arts_meta.jsonl")
    done = load_done("cqart:")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN", ignore_https_errors=True)
        page = ctx.new_page()
        all_arts = []
        for col in NEWS_COLS:
            base = col["url"]
            stop_all = False
            for pageno in range(1, 40):
                u = base if pageno == 1 else f"{base}index_{pageno-1}.html"
                html = pw_open(page, u)
                if len(html) < 4000:
                    log(f"[{col['name']}] p{pageno} unavailable, stop")
                    break
                arts = re.findall(
                    r'<a[^>]+href=[\'"](\./\d{6}/t\d{8}_\d+\.html|/cqtax/[^\'"]*t\d{8}_\d+\.html)[\'"][^>]*>([^<]{4,80})</a>',
                    html)
                items = []
                seen = set()
                for href, title in arts:
                    au = href if href.startswith("http") else base + href[2:]
                    if au in seen:
                        continue
                    seen.add(au)
                    items.append((au, re.sub(r"\s+", " ", title).strip()))
                # 日期：从链接路径取 tYYYYMMDD
                dated = []
                for au, ti in items:
                    m = re.search(r"t(\d{8})_\d+\.html", au)
                    d = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}" if m else ""
                    dated.append((au, ti, d))
                if not dated:
                    log(f"[{col['name']}] p{pageno} no items")
                    break
                for au, ti, d in dated:
                    if d and d < DATE_FROM:
                        stop_all = True
                kw = [(au, ti, d) for au, ti, d in dated if KW.search(ti)]
                all_arts.extend(kw)
                log(f"[{col['name']}] p{pageno}: {len(dated)} arts, kw={len(kw)}, cum={len(all_arts)}")
                if stop_all:
                    log(f"[{col['name']}] reached < {DATE_FROM}")
                    break
                polite()
        # 去重
        uniq, seen = [], set()
        for a in all_arts:
            if a[0] not in seen:
                seen.add(a[0])
                uniq.append(a)
        todo = [a for a in uniq if f"cqart:{a[0]}" not in done][:max_arts]
        log(f"kw arts={len(uniq)}, todo={len(todo)}")
        fm = open(meta_path, "a", encoding="utf-8")
        n_ok = 0
        for i, (au, ti, d) in enumerate(todo):
            html = pw_open(page, au, tries=2)
            if len(html) > 3000:
                key = hashlib.md5(au.encode()).hexdigest()[:12]
                fp = os.path.join(pages_dir, f"{key}.html")
                open(fp, "w", encoding="utf-8").write(html)
                fm.write(json.dumps({"url": au, "title": ti, "date": d, "file": fp,
                                     "col": "news"}, ensure_ascii=False) + "\n")
                mark({"key": f"cqart:{au}", "phase": "cq_art", "st": 200})
                n_ok += 1
            else:
                mark({"key": f"cqart:{au}", "phase": "cq_art_fail", "len": len(html)})
            if (i + 1) % 15 == 0:
                log(f"  arts {i+1}/{len(todo)} ok={n_ok}")
                fm.flush()
            polite()
        fm.close()
        log(f"news done ok={n_ok}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["xzcf", "sx", "news"])
    ap.add_argument("--max-arts", type=int, default=300)
    ap.add_argument("--max-pages", type=int, default=60)
    args = ap.parse_args()
    if args.part == "xzcf":
        run_xzcf(args.max_pages)
    elif args.part == "sx":
        run_sx()
    else:
        run_news(args.max_arts)


if __name__ == "__main__":
    main()
