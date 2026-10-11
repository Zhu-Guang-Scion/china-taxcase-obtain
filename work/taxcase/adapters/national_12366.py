# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
国家税务总局 12366 纳税服务平台 —— 全库抓取 adapter
====================================================================
机制（2026-10-10 实测）：
  列表: POST https://12366.chinatax.gov.cn/sscx/search
        data: zlflag=2(问题解答) zltype='' keywords='' order=desc sortField=ZLFBRQ
              page pagesize(服务端封顶10)
        返回 {totalRow,pageCount,pageContent:[{ZLCODE,ZLTITLE,ZLNR(截断),ZLFBRQ,...}]}
  详情: POST https://12366.chinatax.gov.cn/sscx/toDetail  data: code=ZLCODE flag={zlflag}
        返回 {bean:{ZLNR(全文HTML), ZLTITLE, ZLGJZ, ZLFBRQ, ZLTYPEMC,...}}
  totalRow 实测（2026-10-10）: zlflag=2 → 5027（问题解答）; 3 → 196（办税流程）;
  5 → 274（表证单书，ZLNR 为 Word 嵌入 HTML，需剥 <style>/mso 噪声）。
  zlflag=1（税收法规）跳过 —— 本项目法规库已全覆盖。

用法:
  python national_12366.py --flag 2 --limit 300   # 原增量模式
  python national_12366.py --flag 2               # 全库（断点续抓）
  python national_12366.py --flag all             # 2+3+5 顺序全量
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import taxcase_scrape as t  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

BASE = "https://12366.chinatax.gov.cn"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
LIB = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "全国")
OUT_DIR = os.path.join(LIB, "12366热点问答")
H = {"Referer": BASE + "/sscx/main", "Origin": BASE,
     "X-Requested-With": "XMLHttpRequest"}
MIN_GAP = 0.8          # 秒，单通道礼貌间隔下限（0.8 + 响应耗时 ≈ ≤1 req/s/通道）
_last = [0.0]

# flag → (job_id, 输出目录, 栏目, 原文来源标签)
FLAGS = {
    "2": ("national_12366", LIB + "/12366热点问答",
          "12366热点问答", "12366纳税服务平台问题解答库"),
    "3": ("national_12366_flow", LIB + "/12366办税流程",
          "12366办税流程", "12366纳税服务平台办税流程库"),
    "5": ("national_12366_form", LIB + "/12366表证单书",
          "12366表证单书", "12366纳税服务平台表证单书库"),
}


def _post(path, data):
    for attempt in range(3):
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        try:
            rr = cr.post(BASE + path, data=data, impersonate="chrome124",
                         timeout=45, headers=dict(H, Referer=BASE + path))
            _last[0] = time.time()
            if rr.status_code == 200:
                return rr
        except Exception:
            pass
        time.sleep(3 + attempt * 2)
    return None


def list_page(flag, page):
    rr = _post("/sscx/search", {"zltype": "", "zlflag": flag, "keywords": "",
                                "order": "desc", "sortField": "ZLFBRQ",
                                "page": str(page), "pagesize": "10"})
    if rr is None:
        return None
    try:
        return rr.json()
    except Exception:
        return None


def fetch_detail(code, flag):
    rr = _post("/sscx/toDetail", {"code": code, "flag": flag})
    if rr is None:
        return None
    try:
        return rr.json().get("bean") or {}
    except Exception:
        return None


def zlnr_to_md(zlnr):
    """ZLNR: HTML 片段（带 <br/> 与实体），转纯文本段落。"""
    s = html.unescape(zlnr or "")
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---- 表证单书（zlflag=5）专用：Word 嵌入 HTML 深度清洗 ----
_NOISE = re.compile(
    r"@font-face|font-family|mso-|ReadOnly|DocumentNotSpecified|"
    r"MicrosoftInternetExplorer|Web0|^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|"
    r"^[A-Za-z ]{0,20}\d+(\.\d+)*$|^\d+(\.\d+)+$|^=|guest|^user$|"
    r"Sheet\d|Print_Area|False|True|Wingdings|Calibri|宋体|黑体|楷体|仿宋|"
    r"方正小标宋|华文中宋|Times New Roman|Arial")


def zlnr_form_md(zlnr):
    s = html.unescape(zlnr or "")
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", "", s)
    s = re.sub(r"(?is)<head[^>]*>.*?</head>", "", s)
    s = re.sub(r"(?is)<!--.*?-->", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|tr|div|h[1-6]|table)>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = re.sub(r"<[^>]+>", "", s)
    lines = []
    for ln in s.split("\n"):
        ln2 = re.sub(r"[ \t\u3000]+", " ", ln).strip()
        if not ln2:
            continue
        if _NOISE.search(ln2):
            continue
        lines.append(ln2)
    out = "\n".join(lines)
    out = re.sub(r"\t+", "\t", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def cn_chars(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s or ""))


def load_done(job_id):
    """合并所有 {job_id}*.jsonl 断点记录（含分片 worker 文件）。"""
    done = set()
    import glob as _g
    paths = sorted(_g.glob(os.path.join(t.PROG_DIR, job_id + "*.jsonl")))
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("ok"):
                        done.add(rec["url"])
                except json.JSONDecodeError:
                    pass
    return done, paths


def norm_title(s):
    return re.sub(r"\s+", " ", (s or "")).strip().replace('"', "")


def run_flag(flag, limit=0, dry=False, pages=None, worker=""):
    job_id, out_dir, column, src_label = FLAGS[flag]
    print(f"##### zlflag={flag} → {job_id}{worker}  dir={out_dir}")

    # 1) 列表翻页（pages="a:b" 时只翻该区间，供并行 worker 分片）
    p_lo, p_hi = (1, None)
    if pages:
        a, b = pages.split(":")
        p_lo = int(a) if a else 1
        p_hi = int(b) if b else None
    first = list_page(flag, p_lo)
    if not first:
        print("[list] first page FAILED, abort this flag")
        return
    total = first.get("totalRow") or 0
    all_pages = first.get("pageCount") or 1
    p_hi = p_hi or all_pages
    items = []
    seen = set()
    failed_pages = []

    def absorb(j):
        n = 0
        for r in j.get("pageContent") or []:
            code = r.get("ZLCODE")
            if code and code not in seen:
                seen.add(code)
                items.append({"code": code,
                              "title": norm_title(r.get("ZLTITLE")),
                              "date": (r.get("ZLFBRQ") or "").replace("/", "-")[:10]})
                n += 1
        return n

    absorb(first)
    for page in range(p_lo + 1, p_hi + 1):
        j = list_page(flag, page)
        if j is None:
            failed_pages.append(page)
            continue
        absorb(j)
        if page % 20 == 0:
            print(f"[list] page {page}/{p_hi} cum {len(items)}")
    # 失败列表页重试一轮
    if failed_pages:
        print(f"[list] retry {len(failed_pages)} failed pages")
        for page in list(failed_pages):
            j = list_page(flag, page)
            if j is not None:
                absorb(j)
                failed_pages.remove(page)
    print(f"[list] pages {p_lo}-{p_hi} unique items={len(items)} "
          f"(totalRow={total}, pageCount={all_pages}) failed_pages={len(failed_pages)}")
    if limit:
        items = items[:limit]

    if dry:
        for it in items[:20]:
            print("[dry]", it["date"], it["title"][:50])
        return

    # 2) 详情入库（断点续抓；worker 分片写独立 jsonl，load 时合并）
    done, _paths = load_done(job_id)
    prog_path = os.path.join(t.PROG_DIR, job_id + (worker or "") + ".jsonl")
    os.makedirs(out_dir, exist_ok=True)
    n_new = n_fail = n_skip = n_done0 = 0
    pending = []
    for it in items:
        key = BASE + "/sscx/detail?code=" + str(it["code"])
        if key in done:
            n_done0 += 1
            continue
        pending.append((it, key))
    print(f"[run] already done={n_done0}, to fetch={len(pending)}")

    with open(prog_path, "a", encoding="utf-8") as prog:
        for idx, (it, key) in enumerate(pending, 1):
            bean = fetch_detail(it["code"], flag)
            if flag == "5":
                body = zlnr_form_md(bean.get("ZLNR")) if bean else ""
                rich = cn_chars(body) >= 100   # 纯下载页/噪声页阈值
            else:
                body = zlnr_to_md(bean.get("ZLNR")) if bean else ""
                rich = len(body) >= 30
            title = norm_title(bean.get("ZLTITLE")) or it["title"]
            pd = ((bean.get("ZLFBRQ") or it["date"]) or "").replace("/", "-")[:10]
            if not rich:
                # 失败再试一次；仍失败则记 jsonl（重跑可续）
                bean = fetch_detail(it["code"], flag)
                body = (zlnr_form_md(bean.get("ZLNR")) if flag == "5"
                        else zlnr_to_md(bean.get("ZLNR"))) if bean else ""
                ok = cn_chars(body) >= 100 if flag == "5" else len(body) >= 30
                if not ok:
                    prog.write(json.dumps(
                        {"url": key, "ok": False, "err": "low-content",
                         "title": title}, ensure_ascii=False) + "\n")
                    prog.flush()
                    if flag == "5":
                        n_skip += 1
                    else:
                        n_fail += 1
                    continue
            md = body
            kw = (bean.get("ZLGJZ") or "").strip()
            if kw:
                md = f"关键词：{kw}\n\n{md}"
            fname = t.safe_filename((pd or "nodate") + "_" + title) + ".md"
            fm = ("---\n"
                  f"title: \"{title}\"\n"
                  "来源机关: \"国家税务总局12366纳税服务平台\"\n"
                  f"栏目: \"{column}\"\n"
                  "地区: \"全国\"\n"
                  f"发布日期: {pd or ''}\n"
                  f"原文来源: \"{src_label}\"\n"
                  f"抓取日期: {date.today().isoformat()}\n"
                  f"原文链接: {key}\n---\n\n")
            with open(os.path.join(out_dir, fname), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(fm + md + "\n")
            prog.write(json.dumps({"url": key, "ok": True, "file": fname,
                                   "title": title, "date": pd},
                                  ensure_ascii=False) + "\n")
            prog.flush()
            n_new += 1
            if n_new % 50 == 0:
                print(f"[run] {job_id} new={n_new} fail={n_fail} skip={n_skip} "
                      f"({idx}/{len(pending)})")
    print(f"[run] DONE {job_id}: new={n_new} fail={n_fail} skip={n_skip} "
          f"(already={n_done0})")
    return {"job": job_id, "total": total, "unique": len(items),
            "new": n_new, "fail": n_fail, "skip": n_skip, "already": n_done0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flag", default="2",
                    help="2|3|5|all（all=2+3+5 顺序全量）")
    ap.add_argument("--limit", type=int, default=0, help="0=全库")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--pages", default=None, help="列表页区间 a:b（并行分片用）")
    ap.add_argument("--worker", default="", help="分片后缀，如 .w1")
    args = ap.parse_args()
    flags = ["2", "3", "5"] if args.flag == "all" else [args.flag]
    t0 = time.time()
    for fl in flags:
        run_flag(fl, limit=args.limit, dry=args.dry,
                 pages=args.pages, worker=args.worker)
    print(f"[all] elapsed {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
