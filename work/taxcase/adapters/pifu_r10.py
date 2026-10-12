# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
R10 · 税务批复/函件/官方答复 —— 信源一：总局政策法规库 fgk.chinatax.gov.cn
====================================================================
机制（2026-10-11 实测，调研见 _research/pifu_sources_r10.md）：
  列表: GET https://www.chinatax.gov.cn/search5/search/s
            ?siteCode=bm29000002&searchWord={词}&type=&pageSize=10&pageNum={n}
            &orderBy=5&column=政策法规
        TRS search5 JSON，searchResultAll.searchTotal[] 每条含
        title / url / govDoc{docNum,docType,docYear} / cwrq(成文日期) /
        label / xxgk_aging(时效性) / shortContent
        服务端每页封顶 10 条（pageSize 传 20 也只回 10），pageNum 从 0 起。
        关键词为全文匹配（噪音大），须按 govDoc.docType 二次过滤函类。
  详情: fgk.chinatax.gov.cn/zcfgk/c100012/{id}/content.html
        正文 <div class="arc_cont"> 内 TextContentDuanLuo 段落（老文档混 <p>）；
        页头 p.arc_date 带 时效性(span.xg)+成文日期。
  答复: 总局官网建议提案办理栏 /chinatax/n810214/c102374/c102387/
        首页仅 22 条直出、无分页（index_1.html 404），历史项走 search5
        检索（searchWord=号建议的答复 total≈84 + 提案答复）再按 URL 前缀
        /c102387/ 过滤；正文容器 <div class="text" id="fontzoom">。

文号规范化（跨源去重主键，shui5_r10.py 复用）：
  norm_docno("国税函〔2009〕779号") → ("国税函","2009","779","国税函|2009|779")
  括号〔[]()（）〕全删、全角数字转半角、机关段小写化无关（保留中文原文，
  两源原文机关字面一致即可对齐；fgk 用〔〕、shui5 用[]，删括号后同键）。

用法:
  python adapters/pifu_r10.py --phase list     # 枚举列表 → 缓存 items
  python adapters/pifu_r10.py --phase detail   # 详情入库（断点续抓）
  python adapters/pifu_r10.py --phase all      # list + detail
  python adapters/pifu_r10.py --phase all --dry  # 只看列表抽样
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import argparse
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import quote as _uquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

REPO = os.environ.get(
    "CHINALAW_ROOT", os.path.normpath(os.path.join(HERE, "..", "..", "..")))
LIB = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "全国", "税务批复与函件")
OUT_DIR = LIB
JOB = "pifu_r10"
SEARCH = "https://www.chinatax.gov.cn/search5/search/s"
COLUMN_FAGUI = "%E6%94%BF%E7%AD%96%E6%B3%95%E8%A7%84"          # column=政策法规
MIN_GAP = 1.6          # brief: delay≥1.5s
_last = [0.0]

# 函类 docType 白名单（fgk 权威字段；公告/令/国函/财税 均排除）
HAN_DOCTYPES = {"国税函", "国税函发", "国税函字", "税总函", "税总办函", "税函"}
# 标题黑名单（形式函，research §3）
TITLE_BLACKLIST = re.compile(r"名单|会议|任免|值班|印章|着装")
# 列表检索词（column=政策法规）
KEYWORDS = ["批复", "国税函", "税总函", "税函"]
# 建议提案答复检索词（无 column 限定，按 URL /c102387/ 过滤）
DAFU_KEYWORDS = ["号建议的答复", "提案答复"]


# ---------------- 文号规范化（去重主键） ----------------
_FW = {ord(f): ord(h) for f, h in zip("０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                                      "0123456789abcdefghijklmnopqrstuvwxyz")}


def norm_docno(docnum):
    """国税函〔2009〕779号 → ("国税函","2009","779","国税函|2009|779")；失败返回 None。"""
    if not docnum:
        return None
    s = str(docnum).translate(_FW).strip()
    s = re.sub(r"[\s〔〕\[\]()（）<>《》]", "", s)
    m = re.match(r"^(.*?)(19|20)(\d{2})[.]?(\d{1,5})号?$", s)
    if not m:
        return None
    org = m.group(1)
    year = m.group(2) + m.group(3)
    no = m.group(4)
    if not org:                       # 无机关前缀的裸文号，不可作跨源键
        return None
    return org, year, no, f"{org}|{year}|{no}"


DOCNO_RE = re.compile(
    r"([\u4e00-\u9fff]{2,10})(?:〔|\[|（|\()\s*((?:19|20)\d{2})\s*(?:〕|\]|）|\))\s*(\d{1,5})\s*号")


def docno_from_title(title):
    """shui5 标题抽文号：'国税函[2009]779号 关于…' → norm 元组；失败 None。"""
    m = DOCNO_RE.search(title or "")
    if not m:
        return None
    org, yr, no = m.group(1), m.group(2), m.group(3)
    return org, yr, no, f"{org}|{yr}|{no}"


def title_key(title, dt=""):
    """无文号类的复合键（建议提案答复等）：title_norm + 日期。"""
    s = re.sub(r"\s+", "", title or "")
    return "T|" + s[:60] + "|" + (dt or "")[:10]


def strip_tags_keep_lines(seg):
    seg = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", seg)
    seg = re.sub(r"(?i)</(p|div|tr|h[1-6]|li|table)>", "\n", seg)
    seg = re.sub(r"(?i)<br\s*/?>", "\n", seg)
    seg = re.sub(r"(?i)</t[dh]>", "\t", seg)
    seg = re.sub(r"<[^>]+>", "", seg)
    import html as _h
    seg = _h.unescape(seg)
    lines = [re.sub(r"[ \t\u3000]+", " ", ln).strip() for ln in seg.split("\n")]
    return "\n\n".join([ln for ln in lines if ln])


def cn_chars(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s or ""))


# ---------------- 断点 ----------------

def load_prog():
    """返回 (done_urls, keys)——keys 为已 ok 入库的文号键集合（跨源去重用）。"""
    path = os.path.join(t.PROG_DIR, JOB + ".jsonl")
    done, keys, dups = set(), set(), set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("url"):
                    done.add(rec["url"])
                if rec.get("ok") and rec.get("docno_key"):
                    keys.add(rec["docno_key"])
                if rec.get("dup_of"):
                    dups.add(rec["docno_key"])
    return done, keys, dups


# ---------------- HTTP ----------------

def _get(url):
    for attempt in range(3):
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            rr = cr.get(url, impersonate="chrome124", timeout=45,
                        headers={"Referer": "https://www.chinatax.gov.cn/"})
            _last[0] = time.time()
            if rr.status_code == 200:
                return rr
        except Exception:
            pass
        time.sleep(3 + attempt * 2)
    return None


def search_page(word, page, column=True):
    url = (f"{SEARCH}?siteCode=bm29000002&searchWord="
           + _uquote(word)
           + f"&type=&pageSize=10&pageNum={page}&orderBy=5"
           + (f"&column={COLUMN_FAGUI}" if column else ""))
    rr = _get(url)
    if rr is None:
        return None
    try:
        return rr.json().get("searchResultAll") or {}
    except Exception:
        return None


# ---------------- 列表枚举 ----------------

def clean_title(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def enum_lists(items_path):
    items, seen = [], set()
    stats = {}
    for kw in KEYWORDS:
        sra = search_page(kw, 0)
        if not sra:
            print(f"[list] {kw} page0 FAILED")
            continue
        total = sra.get("total") or 0
        n_kw = 0
        pages = (total + 9) // 10
        for pg in range(pages):
            sra2 = sra if pg == 0 else search_page(kw, pg)
            if not sra2:
                print(f"[list] {kw} page {pg} failed, skip")
                time.sleep(1)
                continue
            for r in sra2.get("searchTotal") or []:
                url = r.get("url") or ""
                title = clean_title(r.get("title"))
                gd = r.get("govDoc") or {}
                dtype, dnum = gd.get("docType") or "", gd.get("docNum") or ""
                if "/zcfgk/" not in url:
                    continue
                if dtype not in HAN_DOCTYPES:
                    continue                            # 噪音：公告/令/国函/财税/国税发…
                if TITLE_BLACKLIST.search(title):
                    continue
                if url in seen:
                    continue
                seen.add(url)
                items.append({
                    "url": url, "title": title, "docnum": dnum,
                    "doctype": dtype,
                    "cwrq": (r.get("cwrq") or "")[:10],
                    "pubdate": (r.get("pubDate") or "")[:10],
                    "aging": r.get("xxgk_aging") or "",
                    "label": r.get("label") or "",
                    "src": "fgk", "kind": "函件"})
                n_kw += 1
            if pg % 10 == 0:
                print(f"[list] {kw} {pg}/{pages} cum={len(items)}")
            time.sleep(0.3)
        stats[kw] = {"total": total, "kept": n_kw}
        print(f"[list] {kw}: total={total} kept(函类)={n_kw}")
    # 建议提案答复（无文号 → title 键）
    for kw in DAFU_KEYWORDS:
        sra = search_page(kw, 0, column=False)
        if not sra:
            print(f"[list] {kw} FAILED")
            continue
        total = sra.get("total") or 0
        n_kw = 0
        for pg in range((total + 9) // 10):
            sra2 = sra if pg == 0 else search_page(kw, pg, column=False)
            if not sra2:
                continue
            for r in sra2.get("searchTotal") or []:
                url = r.get("url") or ""
                if "/c102387/" not in url:
                    continue
                title = clean_title(r.get("title"))
                if url in seen:
                    continue
                seen.add(url)
                items.append({
                    "url": url, "title": title, "docnum": "",
                    "doctype": "建议提案答复",
                    "cwrq": "", "pubdate": (r.get("pubDate") or "")[:10],
                    "aging": "", "label": "",
                    "src": "fgk", "kind": "答复"})
                n_kw += 1
            time.sleep(0.3)
        stats[kw] = {"total": total, "kept": n_kw}
        print(f"[list] {kw}: total={total} kept(/c102387/)={n_kw}")
    # 文号级去重（同文 fgk 双 url 极少，但 docNum 权威键先压一遍）
    by_key, dedup_loss = {}, 0
    for it in items:
        nt = norm_docno(it["docnum"]) if it["docnum"] else None
        key = nt[3] if nt else title_key(it["title"], it.get("pubdate"))
        it["docno_key"] = key
        if key in by_key:
            dedup_loss += 1
            continue
        by_key[key] = it
    final = list(by_key.values())
    json.dump({"stats": stats, "dedup_loss": dedup_loss, "items": final},
              open(items_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[list] fgk items unique={len(final)} (docno dedup -{dedup_loss})")
    return final


# ---------------- 详情 ----------------

def parse_fgk_detail(html_text):
    m = re.search(r'<div class="arc_cont">(.*?)<div class="bot-btns-box">', html_text, re.S)
    if not m:
        m = re.search(r'<div class="arc_cont">(.*?)</div>\s*<!--', html_text, re.S)
    if not m:
        return ""
    return strip_tags_keep_lines(m.group(1)).strip()


def parse_dafu_detail(html_text):
    m = re.search(r'<div class="text"[^>]*id="fontzoom">(.*?)</div>\s*<div', html_text, re.S)
    if not m:
        m = re.search(r'<div class="text"[^>]*id="fontzoom">(.*)</div>', html_text, re.S)
    if not m:
        return ""
    return strip_tags_keep_lines(m.group(1)).strip()


def run_detail(items):
    done, keys, _dups = load_prog()
    os.makedirs(OUT_DIR, exist_ok=True)
    prog_path = os.path.join(t.PROG_DIR, JOB + ".jsonl")
    n_new = n_dup = n_skip = n_fail = 0
    pending = [it for it in items if it["url"] not in done]
    print(f"[run] fgk already done={len(items) - len(pending)}, to fetch={len(pending)}")
    with open(prog_path, "a", encoding="utf-8") as prog:
        for idx, it in enumerate(pending, 1):
            key = it.get("docno_key") or title_key(it["title"], it.get("pubdate"))
            if key in keys:
                prog.write(json.dumps({"url": it["url"], "ok": False, "dup_of": key,
                                       "docno_key": key, "src": "fgk"},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_dup += 1
                continue
            rr = _get(it["url"])
            body = ""
            if rr is not None:
                body = (parse_dafu_detail(rr.text) if "/c102387/" in it["url"]
                        else parse_fgk_detail(rr.text))
            if cn_chars(body) < 100:
                # 重试一次（正文抽空可能是容器差异）
                rr = _get(it["url"])
                if rr is not None:
                    body = (parse_dafu_detail(rr.text) if "/c102387/" in it["url"]
                            else parse_fgk_detail(rr.text))
            if cn_chars(body) < 100:
                prog.write(json.dumps({"url": it["url"], "ok": False,
                                       "err": "low-content",
                                       "docno_key": key, "src": "fgk",
                                       "title": it["title"]},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_skip += 1
                continue
            title = re.sub(r"\s+", " ", it["title"]).strip()
            dt = it.get("cwrq") or it.get("pubdate") or ""
            fname = t.safe_filename(f"{dt}_{it['docnum']}{title}") + ".md"
            fm = ("---\n"
                  f"title: \"{title}\"\n"
                  "来源机关: \"国家税务总局\"\n"
                  "栏目: \"税务批复与函件\"\n"
                  "地区: \"全国\"\n"
                  f"文号: \"{it['docnum'] or '无'}\"\n"
                  f"发布日期: {dt}\n"
                  f"时效性: \"{it.get('aging') or ''}\"\n"
                  f"文件类型: \"{it.get('kind')}\"\n"
                  "原文来源: \"国家税务总局政策法规库\"\n"
                  f"抓取日期: {date.today().isoformat()}\n"
                  f"原文链接: {it['url']}\n---\n\n")
            with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(fm + body + "\n")
            prog.write(json.dumps({"url": it["url"], "ok": True, "file": fname,
                                   "docno_key": key, "src": "fgk",
                                   "title": title, "date": dt},
                                  ensure_ascii=False) + "\n")
            prog.flush()
            keys.add(key)
            n_new += 1
            if n_new % 50 == 0:
                print(f"[run] fgk {idx}/{len(pending)} new={n_new} dup={n_dup} "
                      f"skip={n_skip} fail={n_fail}")
    print(f"[run] fgk DONE: new={n_new} dup={n_dup} skip(低内容)={n_skip} fail={n_fail}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all", choices=["list", "detail", "all"])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    items_path = os.path.join(t.PROG_DIR, JOB + ".fgk_items.json")
    os.makedirs(OUT_DIR, exist_ok=True)
    if args.phase in ("list", "all"):
        items = enum_lists(items_path)
    else:
        items = json.load(open(items_path, encoding="utf-8"))["items"]
    if args.limit:
        items = items[:args.limit]
    if args.dry:
        for it in items[:20]:
            print("[dry]", it["doctype"], it["docnum"], it["title"][:40])
        print("total:", len(items))
        return
    if args.phase in ("detail", "all"):
        run_detail(items)


if __name__ == "__main__":
    main()
