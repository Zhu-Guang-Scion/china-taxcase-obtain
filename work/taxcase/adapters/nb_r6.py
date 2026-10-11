# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
宁波市税务局 收割脚本（瑞数，有头 chromium 会话内；jpaas 点击翻页）
=====================================================================
数据源：
  A. 重大税收违法失信主体信息公布栏 /zdsswfsxztxxgbl/（区级页数据全同，抓一份）
     表格：所属税务机关/失信主体名称/识别号/违法性质/详细信息(art 链接)
     翻页：layui a.layui-laypage-next 点击；详情 art 页含完整违法事实
  B. 涉税通知 /xxgk/tzgg/sstz/（658 条，15/页）标题关键词过滤后抓详情
输出：work/taxcase/tmp/sx_nb/nb_*.jsonl + *.html；断点 progress/sx_nb_r6.jsonl（nb_ 前缀 phase）
用法：python nb_r6.py --part shixin|notice|all
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, hashlib, argparse
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 审查修复：tmp 输出统一到 work/taxcase/tmp/ 下（原写到仓库根 tmp/）
TMP = os.path.join(ROOT, "tmp", "sx_nb")
PROGDIR = os.path.join(ROOT, "progress")
PROG = os.path.join(PROGDIR, "sx_nb_r6.jsonl")

SITE = "https://ningbo.chinatax.gov.cn"
DATE_FROM = "2023-01-01"
DATE_RE = re.compile(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})")

JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
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


def pw_open(page, url, tries=3):
    last = ""
    for a in range(tries):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            for _ in range(40):
                time.sleep(1)
                h = page.content()
                last = h
                if btl(h) > 300 and "$_ts=window" not in h[:3000]:
                    return h
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:80]}")
    return last


def fetch_in(page, url, home=None, tries=3):
    for a in range(tries):
        try:
            r = page.evaluate(JS_FETCH, url if url.startswith("http") else SITE + url)
            if r["status"] not in (412, 900) and "$_ts=window" not in r["text"][:3000]:
                return r
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:60]}")
        pw_open(page, home or (SITE + "/index.html"))
        time.sleep(1)
    return {"status": 0, "text": ""}


def polite():
    time.sleep(random.uniform(1.6, 2.8))


def norm_date(s):
    m = DATE_RE.search(s or "")
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def parse_table_rows(h):
    """失信表 → [{org,name,code,vtype,url}]"""
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        href = re.search(r'href=[\'"]([^\'"]*zdsswfsxztxxgbl/art/[^\'"]+)[\'"]', r)
        if not href:
            continue
        cells = [re.sub(r"<[^>]+>|\s+", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if len(cells) < 4:
            continue
        out.append({"org": cells[0][:40], "name": cells[1][:60],
                    "code": cells[2][:24], "vtype": cells[3][:60],
                    "url": urljoin(SITE + "/", href.group(1))})
    return out


def goto_get(page, url, tries=2):
    """宁波瑞数五代：每个 URL 都要 m4oH8x2I 令牌，裸 fetch 412 —— 必须 goto。"""
    h = ""
    for a in range(tries):
        try:
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            for _ in range(18):
                time.sleep(1)
                h = page.content()
                if btl(h) > 200 and "$_ts=window" not in h[:3000]:
                    break
        except Exception as e:
            log(f"  goto exc {type(e).__name__}: {str(e)[:60]}")
            time.sleep(2)
        if len(h) > 1500:
            break
    return h


def run_shixin():
    from playwright.sync_api import sync_playwright
    rows_path = os.path.join(TMP, "nb_shixin_rows.jsonl")
    done_det = load_done("nb_sx_det")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()

        # 翻页收割（点 下一页 直到底）；已有 rows 文件则跳过枚举
        all_rows, seen = [], set()
        if os.path.exists(rows_path):
            for ln in open(rows_path, encoding="utf-8"):
                try:
                    r = json.loads(ln)
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        all_rows.append(r)
                except Exception:
                    pass
            log(f"rows loaded from file: {len(all_rows)}")
        if not all_rows:
            log("open 失信栏 yzq (challenge)...")
            pw_open(page, SITE + "/zdsswfsxztxxgbl/dq/yzq/index.html")
            time.sleep(5)
            h = page.content()
            cm = re.search(r"querydata=\"\{[^}]*'count':'(\d+)'", h)
            total = int(cm.group(1)) if cm else None
            log(f"total count attr={total}")
            page_no = 1
            stale = 0
            while page_no <= 200:
                rows = parse_table_rows(page.content())
                new = 0
                for r in rows:
                    if r["url"] not in seen:
                        seen.add(r["url"])
                        all_rows.append(r)
                        new += 1
                log(f"p{page_no}: rows={len(rows)} new={new} cum={len(all_rows)}")
                if total and len(all_rows) >= total:
                    break
                # 点下一页
                try:
                    nxt = page.query_selector("a.layui-laypage-next")
                    if not nxt or "layui-disabled" in (nxt.get_attribute("class") or ""):
                        log("next disabled, end")
                        break
                    nxt.click()
                    time.sleep(random.uniform(2.8, 4.0))
                    page_no += 1
                    stale = 0 if new else stale + 1
                    if stale >= 3:
                        log("3 pages no new, stop")
                        break
                except Exception as e:
                    log(f"next click exc: {str(e)[:70]}")
                    break
            with open(rows_path, "w", encoding="utf-8") as f:
                for r in all_rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            log(f"rows saved: {len(all_rows)} -> {rows_path}")

        # 详情抓取（goto 方式——fetch 全 412）
        meta_path = os.path.join(TMP, "nb_shixin_meta.jsonl")
        todo = [r for r in all_rows if r["url"] not in done_det]
        log(f"details todo: {len(todo)}")
        n_ok = 0
        with open(meta_path, "a", encoding="utf-8") as mf:
            for i, r in enumerate(todo):
                key = hashlib.md5(r["url"].encode()).hexdigest()[:12]
                rr = goto_get(page, r["url"])
                if len(rr) > 1500:
                    fp = os.path.join(TMP, f"nbsx_{key}.html")
                    open(fp, "w", encoding="utf-8").write(rr)
                    mf.write(json.dumps({**r, "key": key, "file": fp},
                                        ensure_ascii=False) + "\n")
                    mark({"phase": "nb_sx_det", "key": r["url"], "ok": True})
                    n_ok += 1
                else:
                    mark({"phase": "nb_sx_det", "key": r["url"], "ok": False,
                          "st": 0})
                if (i + 1) % 20 == 0:
                    log(f"  det {i+1}/{len(todo)} ok={n_ok}")
                polite()
        log(f"shixin done: det ok={n_ok} fail={len(todo)-n_ok}")
        browser.close()


def parse_list_arts(h):
    """sstz 列表 → [(url,title,date)]"""
    out = []
    seen = set()
    for m in re.finditer(
            r'<a[^>]+href=[\'"]([^\'"#]*art_[^\'"]+)[\'"][^>]*>(.*?)</a>', h, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>|\s+", "", inner).strip()
        if not title or href in seen:
            continue
        seen.add(href)
        out.append((urljoin(SITE + "/", href), title[:90]))
    # 日期：li 内 <span class="fr">2026-09-28</span>
    dates = re.findall(r'class="fr"[^>]*>\s*(20\d{2}-\d{2}-\d{2})', h)
    return out, dates


def run_notice():
    from playwright.sync_api import sync_playwright
    kwp = re.compile(r"处罚|失信|违法|稽查|偷税|虚开|骗税|欠税|检查|催告|强制")
    done_det = load_done("nb_nt_det")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open sstz (challenge)...")
        pw_open(page, SITE + "/xxgk/tzgg/sstz/index.html")
        time.sleep(5)

        arts, seen = [], set()
        stop_all = False
        page_no = 1
        while page_no <= 60 and not stop_all:
            h = page.content()
            items, dates = parse_list_arts(h)
            # 按出现顺序配对日期（li 结构：a + span.fr）
            lis = re.findall(r"<li[^>]*>(.*?)</li>", h, re.S)
            pairs = []
            for li in lis:
                am = re.search(r'href=[\'"]([^\'"#]*art_[^\'"]+)[\'"]', li)
                if not am:
                    continue
                tm = re.search(r'>\s*([^<>]{6,100})</a>', li)
                dm = re.search(r"(20\d{2}-\d{2}-\d{2})", li)
                u = urljoin(SITE + "/", am.group(1))
                t = re.sub(r"\s+", "", tm.group(1)) if tm else ""
                d = dm.group(1) if dm else ""
                pairs.append((u, t, d))
            new = 0
            oldest = None
            for u, t, d in pairs:
                if u in seen:
                    continue
                seen.add(u)
                new += 1
                if d:
                    oldest = d if oldest is None else min(oldest, d)
                if kwp.search(t or ""):
                    arts.append({"url": u, "title": t, "date": d})
            log(f"sstz p{page_no}: +{new} kw_kept={len(arts)} oldest={oldest}")
            if oldest and oldest < DATE_FROM:
                stop_all = True
                break
            try:
                nxt = page.query_selector("a.layui-laypage-next")
                if not nxt or "layui-disabled" in (nxt.get_attribute("class") or ""):
                    break
                nxt.click()
                time.sleep(random.uniform(2.5, 3.8))
                page_no += 1
            except Exception as e:
                log(f"next exc: {str(e)[:70]}")
                break
        rows_path = os.path.join(TMP, "nb_notice_rows.jsonl")
        with open(rows_path, "w", encoding="utf-8") as f:
            for a in arts:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
        log(f"notice rows saved: {len(arts)}")

        todo = [a for a in arts if a["url"] not in done_det]
        log(f"notice details todo: {len(todo)}")
        meta_path = os.path.join(TMP, "nb_notice_meta.jsonl")
        n_ok = 0
        with open(meta_path, "a", encoding="utf-8") as mf:
            for i, a in enumerate(todo):
                key = hashlib.md5(a["url"].encode()).hexdigest()[:12]
                rr = goto_get(page, a["url"])
                if len(rr) > 1200:
                    fp = os.path.join(TMP, f"nbnt_{key}.html")
                    open(fp, "w", encoding="utf-8").write(rr)
                    mf.write(json.dumps({**a, "key": key, "file": fp},
                                        ensure_ascii=False) + "\n")
                    mark({"phase": "nb_nt_det", "key": a["url"], "ok": True})
                    n_ok += 1
                else:
                    mark({"phase": "nb_nt_det", "key": a["url"], "ok": False})
                if (i + 1) % 10 == 0:
                    log(f"  nt {i+1}/{len(todo)} ok={n_ok}")
                polite()
        log(f"notice done: ok={n_ok}")
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["shixin", "notice", "all"])
    args = ap.parse_args()
    if args.part in ("shixin", "all"):
        run_shixin()
    if args.part in ("notice", "all"):
        run_notice()


if __name__ == "__main__":
    main()
