# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
北京市税务局 — 税案通报 + 行政处罚公示 抓取 adapter（playwright 有头方案）
==========================================================================
背景：北京站被瑞数(Ruishu)全站防护 —— HTTPS 443 直接黑洞超时，HTTP 80 返回 412
JS 挑战；无头浏览器会被识别。唯一可行路径：**有头 playwright chromium**，
真实执行瑞数 JS 后 DOM 才有内容。

栏目：
  A. 税案通报（c106920，TRS 静态列表 3 页约 45 条）
     http://beijing.chinatax.gov.cn/bjswj/c106920/ztzl_erji.shtml
     分页：ztzl_erji_1.shtml / ztzl_erji_2.shtml（TRS index_N 规律）
  B. 税务行政一般程序处罚结果（行政执法公示平台，servlet JSON）
     页面: http://beijing.chinatax.gov.cn/bjsat/xzzf/xzzf_sj/ybcxcfjg.html
     接口: POST /bjsat/xzzf/SwxzybcxcfjgServlet?page=N&swjg_dm=11100000000
           body: ajmc=&xzxdrdm=&xzxdrmc=&cfjg=  （10条/页）
     响应: {"count":"65-10","swxzybcxcfjgList":[{NSRSBH,CFRQ,CFJG,NSRMC,CFLB,
            AJMC,FDDBRXM,SWXZCFYJ,WFSD,CFJD,XZCFJDSWH,ROWNO}]}
  C. 重大税收违法失信主体公布栏（wwquery.jsp）：仅按名称/识别号查询表单，
     无批量列表接口，ListXxk.do 404 —— 放弃（记录在 sources）。
  D. 行政复议栏目 2020-05 起停更 —— 放弃。

用法：python bj_all.py            # A+B 全跑（断点续抓）
      python bj_all.py --part a
      python bj_all.py --part b
      python bj_all.py --dry-run
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, random, argparse
from datetime import date
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))
SITE = "http://beijing.chinatax.gov.cn"
DELAY = 3.0
DATE_FROM = "2023-01-01"

JOB_A = {
    "job_id": "bj_saat",
    "list_pages": [f"{SITE}/bjswj/c106920/ztzl_erji{sfx}.shtml"
                   for sfx in ["", "_1", "_2"]],
    "out_dir": os.path.join(LAWLIB, "专题", "税务案例", "北京市", "税案通报"),
    "region": "北京市", "source_name": "国家税务总局北京市税务局",
    "category": "税案通报",
}
JOB_B = {
    "job_id": "bj_xzcf",
    "platform_url": f"{SITE}/bjsat/xzzf/xzzf_sj/ybcxcfjg.html",
    "servlet": "/bjsat/xzzf/SwxzybcxcfjgServlet",
    "out_dir": os.path.join(LAWLIB, "专题", "税务案例", "北京市", "行政处罚公示"),
    "region": "北京市", "source_name": "国家税务总局北京市税务局",
    "category": "行政处罚公示",
}

NOISE_PAT = re.compile(
    r"^(发布时间：.*|来源：.*|\[+大\]+|\[+中\]+|\[+小\]+|【打印】.*|【关闭】.*|"
    r"分享到：.*|.*字号.*|访问量：.*|打印本页.*|关闭窗口.*)$")


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def pw_fetch(page, url, tries=3):
    """带瑞数等待的页面获取：轮询 body 出现真实内容。"""
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            for _ in range(25):
                time.sleep(1)
                html = page.content()
                last = html
                if body_text_len(html) > 300 and "$_ts=window" not in html[:3000]:
                    return html
            try:
                page.reload(timeout=50000, wait_until="domcontentloaded")
            except Exception:
                pass
        except Exception as e:
            print(f"  exc {type(e).__name__}: {str(e)[:80]}")
            time.sleep(3)
    return last


def clean_md(md):
    """去噪音行 + 去正文重复（北京页 xwzx/xxgk 双容器导致的重复）。"""
    lines = [ln.rstrip() for ln in md.split("\n")]
    lines = [ln for ln in lines if not NOISE_PAT.match(ln.strip())]
    md2 = "\n".join(lines)
    md2 = re.sub(r"\n{3,}", "\n\n", md2).strip()
    # 重复段去除：若前半段在后半段重复出现，取首次出现截断
    paras = [p.strip() for p in md2.split("\n\n") if len(p.strip()) > 40]
    for i in range(1, len(paras)):
        if paras[i] == paras[0]:
            md2 = "\n\n".join(paras[:i])
            break
    return md2


def extract_article(html, url, fb_title, fb_date):
    """北京 TRS 文章页：只取 #xwzx_content_all 第一个容器。"""
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one("#xwzx_content_all") or soup.select_one(".xwzx_content")
    title, pub, src_org = fb_title, fb_date, ""
    m = re.search(r'<meta\s+name="ArticleTitle"\s+content=[\'"]([^\'"]+)', html)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'发布时间[：:]\s*(2\d{3}-\d{2}-\d{2})', html)
    if m:
        pub = m.group(1)
    m = re.search(r'来源[：:]\s*([^<\s「"\'》]{2,30})', html)
    if m:
        src_org = m.group(1)
    if node is None:
        d = t.extract_detail(html, url, title, pub)
        if d:
            d["md"] = clean_md(d["md"])
            d["title"], d["date"], d["source_org"] = title, pub, src_org or d["source_org"]
        return d
    for tag in node.select("script,style,.shareIcon,.fontsize,.print,iframe,form"):
        tag.decompose()
    md = t.MarkdownConverter(heading_style="ATX", bullets="-").convert_soup(node)
    return {"title": title, "date": pub, "source_org": src_org,
            "md": clean_md(md), "attachments": []}


def write_md(out_dir, prog, url, title, pub, src_org, job, md, attachments=None):
    fname = t.safe_filename((pub or "nodate") + "_" + title) + ".md"
    fpath = os.path.join(out_dir, fname)
    fm = ("---\n"
          f"title: \"{title.replace(chr(34), '')}\"\n"
          f"来源机关: \"{job['source_name']}\"\n"
          f"栏目: \"{job['category']}\"\n"
          f"地区: \"{job['region']}\"\n"
          f"发布日期: {pub or ''}\n"
          f"原文来源: \"{src_org or ''}\"\n"
          f"抓取日期: {date.today().isoformat()}\n"
          f"原文链接: {url}\n")
    if attachments:
        fm += "附件:\n" + "\n".join(f"  - {a}" for a in attachments) + "\n"
    fm += "---\n\n"
    with open(fpath, "w", encoding="utf-8", newline="\n") as f:
        f.write(fm + md + "\n")
    prog.write(json.dumps({"url": url, "ok": True, "file": fname,
                           "title": title, "date": pub}, ensure_ascii=False) + "\n")
    prog.flush()


def parse_case_list(html, page_url):
    soup = BeautifulSoup(html, "lxml")
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "/c106920/2" not in href or not href.endswith(".shtml"):
            continue
        u = urljoin(page_url, href).split("#")[0]
        title = re.sub(r"\s+", " ", (a.get("title") or a.get_text(" ", strip=True) or "")).strip()
        if len(title) < 8 or u in seen:
            continue
        seen.add(u)
        scope = a.parent.get_text(" ", strip=True)[:150] if a.parent else ""
        m = re.search(r"(2\d{3}-\d{2}-\d{2})", scope)
        items.append((u, title, m.group(1) if m else ""))
    return items


def run_part_a(page, dry_run=False):
    os.makedirs(JOB_A["out_dir"], exist_ok=True)
    done, prog_path = t.load_progress(JOB_A["job_id"])
    n_new = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        for lu in JOB_A["list_pages"]:
            html = pw_fetch(page, lu)
            items = parse_case_list(html, lu)
            print(f"[A] {lu} -> {len(items)} items")
            if not items:
                continue
            for url, title, ldate in items:
                if ldate and ldate < DATE_FROM:
                    continue
                if url in done:
                    n_skip += 1
                    continue
                if dry_run:
                    print(f"[dry] {ldate} {title[:50]}")
                    n_new += 1
                    continue
                ah = pw_fetch(page, url)
                d = extract_article(ah, url, title, ldate)
                if not d or len(d["md"]) < 100:
                    prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                           ensure_ascii=False) + "\n")
                    prog.flush()
                    continue
                write_md(JOB_A["out_dir"], prog, url, d["title"], d["date"],
                         d["source_org"], JOB_A, d["md"], d["attachments"])
                n_new += 1
                time.sleep(DELAY + random.uniform(0, 1))
    print(f"[A] DONE new={n_new} skip={n_skip}")


FIELD_LABELS = [
    ("XZCFJDSWH", "决定书文号"), ("AJMC", "案件名称"), ("CFLB", "处罚类别"),
    ("WFSD", "违法事实（处罚事由）"), ("SWXZCFYJ", "处罚依据"), ("CFJD", "处罚决定"),
    ("NSRMC", "行政相对人名称"), ("NSRSBH", "行政相对人代码（纳税人识别号）"),
    ("FDDBRXM", "法定代表人姓名"), ("CFJG", "处罚机关"), ("CFRQ", "处罚日期"),
]


def rec_to_md(rec):
    lines = []
    wh = rec.get("XZCFJDSWH", "").strip()
    am = rec.get("AJMC", "").strip()
    lines.append(f"# {am}" + (f"（{wh}）" if wh else ""))
    lines.append("")
    for key, label in FIELD_LABELS:
        v = str(rec.get(key, "") or "").strip()
        if not v or v == "-":
            continue
        lines.append(f"**{label}**：{v}")
        lines.append("")
    lines.append("> 本记录整理自国家税务总局北京市税务局行政执法信息公示平台"
                 "「税务行政一般程序处罚结果」栏目。")
    return "\n".join(lines).strip()


def run_part_b(page, dry_run=False):
    os.makedirs(JOB_B["out_dir"], exist_ok=True)
    done, prog_path = t.load_progress(JOB_B["job_id"])
    n_new = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        html = pw_fetch(page, JOB_B["platform_url"])
        if body_text_len(html) < 300:
            print("[B] platform page blocked, abort")
            return
        pg = 1
        empty_streak = 0
        while pg <= 40:
            time.sleep(DELAY + random.uniform(0, 0.8))
            try:
                res = page.evaluate(
                    """async (args) => {
                        const r = await fetch(args.url + '?page=' + args.pg + '&swjg_dm=11100000000', {
                            method:'POST', credentials:'include',
                            headers:{'Content-Type':'application/x-www-form-urlencoded',
                                     'X-Requested-With':'XMLHttpRequest'},
                            body:'ajmc=&xzxdrdm=&xzxdrmc=&cfjg='});
                        return await r.text();
                    }""", {"url": JOB_B["servlet"], "pg": pg})
                d = json.loads(res)
            except Exception as e:
                print(f"[B] page {pg} fetch exc: {e}")
                break
            recs = d.get("swxzybcxcfjgList", []) or []
            if not recs:
                empty_streak += 1
                if empty_streak >= 2:
                    print(f"[B] page {pg} empty, stop (count={d.get('count')})")
                    break
                pg += 1
                continue
            empty_streak = 0
            print(f"[B] page {pg}: {len(recs)} recs (count={d.get('count')})")
            stop_old = False
            for rec in recs:
                cfrq = str(rec.get("CFRQ", ""))[:10]
                if cfrq and cfrq < DATE_FROM:
                    stop_old = True
                    continue
                wh = str(rec.get("XZCFJDSWH", "")).strip()
                am = str(rec.get("AJMC", "")).strip()
                title = (wh + "｜" + am) if wh else am
                url = (f"{JOB_B['platform_url']}#page={pg}")
                if not title:
                    continue
                key = wh or (am + cfrq)
                if key in done:
                    n_skip += 1
                    continue
                if dry_run:
                    print(f"[dry] {cfrq} {title[:50]}")
                    n_new += 1
                    continue
                md = rec_to_md(rec)
                prog_key = key
                fname = t.safe_filename((cfrq or "nodate") + "_" + title) + ".md"
                fpath = os.path.join(JOB_B["out_dir"], fname)
                with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                    f.write("---\n"
                            f"title: \"{title.replace(chr(34), '')}\"\n"
                            f"来源机关: \"{JOB_B['source_name']}\"\n"
                            f"栏目: \"{JOB_B['category']}\"\n"
                            f"地区: \"{JOB_B['region']}\"\n"
                            f"发布日期: {cfrq}\n"
                            f"原文来源: \"\"\n"
                            f"抓取日期: {date.today().isoformat()}\n"
                            f"原文链接: {JOB_B['platform_url']}\n"
                            "---\n\n" + md + "\n")
                prog.write(json.dumps({"url": prog_key, "ok": True, "file": fname,
                                       "title": title, "date": cfrq},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_new += 1
            if stop_old:
                print("[B] reached pre-2023, stop")
                break
            total = re.match(r"(\d+)-", str(d.get("count", "")))
            if total and pg * 10 >= int(total.group(1)):
                break
            pg += 1
    print(f"[B] DONE new={n_new} skip={n_skip}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["a", "b"], default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled",
            "--window-position=2000,2000"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        if args.part in (None, "a"):
            run_part_a(page, args.dry_run)
        if args.part in (None, "b"):
            run_part_b(page, args.dry_run)
        browser.close()


if __name__ == "__main__":
    main()
