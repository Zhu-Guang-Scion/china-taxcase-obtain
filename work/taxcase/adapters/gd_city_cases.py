# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
广东省 21 市税务局子站 税务案例抓取 adapter（扩源 round2）
========================================================
机制（见 sources/guangdong.md）：各市频道列表页为 TRS common_list/city_list.shtml，
channelId 藏在列表页内联 JS（channelId = "32hex"），翻页走
  /gdtaxejs/common/search/{channelId}?_pageSize=20&page={n}&_isAgg=true&_isJson=true&_template=index
返回 url 为 ../../gdsw/... 相对路径，基准是站点根。
结果 newest-first，翻到日期 < 2023-01-01 即停。

栏目映射（2026-10-10 实测各市首页）：
  通知公告 {c}_tzgg / 广州 gzsw_tggg；工作动态 {c}_swxw；基层动态 {c}_jcdt；
  基层公告（仅东莞/中山） {c}_jcgg；媒体视点（仅茂名） {c}_mtbd

用法：
  python gd_city_cases.py --dry              # 只列清单
  python gd_city_cases.py --city dg,fs       # 指定市
  python gd_city_cases.py --list-only        # 仅做列表阶段（写 progress 供续跑）
  python gd_city_cases.py --budget 3300      # 详情阶段时间预算（秒）
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
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import taxcase_scrape as t  # noqa: E402

HOST = "https://guangdong.chinatax.gov.cn"
JOB_ID = "gd_city_cases"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT_ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "广东省")
DATE_FROM = "2023-01-01"

# 市配置: key -> (市名, 城市代码, 栏目代码列表)
CITIES = {
    "dg": ("东莞市", "dgsw", ["dgsw_tzgg", "dgsw_swxw", "dgsw_jcdt", "dgsw_jcgg"]),
    "fs": ("佛山市", "fssw", ["fssw_tzgg", "fssw_swxw", "fssw_jcdt"]),
    "hz": ("惠州市", "hzsw", ["hzsw_tzgg", "hzsw_swxw", "hzsw_jcdt"]),
    "zh": ("珠海市", "zhsw", ["zhsw_tzgg", "zhsw_swxw", "zhsw_jcdt"]),
    "gz": ("广州市", "gzsw", ["gzsw_tggg", "gzsw_swxw", "gzsw_gzdt"]),
    "zs": ("中山市", "zssw", ["zssw_tzgg", "zssw_swxw", "zssw_jcdt", "zssw_jcgg"]),
    "jm": ("江门市", "jmsw", ["jmsw_tzgg", "jmsw_swxw", "jmsw_jcdt"]),
    "zj": ("湛江市", "zjsw", ["zjsw_tzgg", "zjsw_swxw", "zjsw_jcdt"]),
    "st": ("汕头市", "stsw", ["stsw_tzgg", "stsw_swxw", "stsw_jcdt"]),
    "zq": ("肇庆市", "zqsw", ["zqsw_tzgg", "zqsw_swxw", "zqsw_jcdt"]),
    "qy": ("清远市", "qysw", ["qysw_tzgg", "qysw_swxw", "qysw_jcdt"]),
    "jy": ("揭阳市", "jysw", ["jysw_tzgg", "jysw_swxw", "jysw_jcdt"]),
    "sg": ("韶关市", "sgsw", ["sgsw_tzgg", "sgsw_swxw", "sgsw_jcdt"]),
    "mm": ("茂名市", "mmsw", ["mmsw_tzgg", "mmsw_swxw", "mmsw_jcdt", "mmsw_mtbd"]),
    "yj": ("阳江市", "yjsw", ["yjsw_tzgg", "yjsw_swxw", "yjsw_jcdt"]),
    "cz": ("潮州市", "czsw", ["czsw_tzgg", "czsw_swxw", "czsw_jcdt"]),
    "hy": ("河源市", "hysw", ["hysw_tzgg", "hysw_swxw", "hysw_jcdt"]),
    "yf": ("云浮市", "yfsw", ["yfsw_tzgg", "yfsw_swxw", "yfsw_jcdt"]),
    "sw": ("汕尾市", "swsw", ["swsw_tzgg", "swsw_swxw", "swsw_jcdt"]),
}

TITLE_KW = re.compile(
    r"处罚|查处|曝光|骗取|虚开|偷税|逃税|失信|违法|税案|以案|案例|复议|欠税|送达|"
    r"强拍|变卖|抵税|稽查|移送|追缴")
TITLE_EXCLUDE = re.compile(
    r"采购|招标|中标|招聘|遴选|公务员|宣传月|新闻发布会|征文|讲座|培训|走访|慰问|"
    r"党建|共建|志愿|停电|系统维护|目录清单|招租|报名|执法资格|考试|拟任命|任职|免职|"
    r"表彰|问卷调查|意见征集|收费|政策解读|解读$|办事指南|操作指引|指引$|服务|"
    r"停电|温馨提示|常识|须知|声明")

COL_NAME = {"tzgg": "通知公告", "tggg": "通知公告", "swxw": "税务新闻",
            "jcdt": "基层动态", "jcgg": "基层公告", "gzdt": "工作动态", "mtbd": "媒体视点"}


def classify(title):
    if re.search(r"行政复议", title):
        return "行政复议"
    if re.search(r"失信", title):
        return "重大税收违法失信公布"
    if re.search(r"行政处罚|处罚决定", title):
        return "行政处罚公示"
    if re.search(r"送达", title):
        return "文书送达公告"
    if re.search(r"欠税", title):
        return "欠税公告"
    if re.search(r"强拍|变卖|抵税|拍卖", title):
        return "执法公告"
    return "税案通报"


def clean_title(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def get_channel_id(col_code):
    """从列表页内联 JS 提取 channelId。"""
    for suffix in ("city_list.shtml", "common_list.shtml", "list.shtml", "index.shtml"):
        list_url = f"{HOST}/gdsw/{col_code}/{suffix}"
        r = t.polite_get(list_url, 2.5)
        if r is None:
            continue
        m = re.search(r'channelId\s*=\s*"([0-9a-f]{32})"', r.text)
        if m:
            return m.group(1), list_url
    return None, ""


# ---------- 附件正文提取（送达公告正文常在 docx/doc 附件里） ----------

def extract_attachment_md(url):
    """下载附件并抽取文本：docx→python-docx；pdf→pymupdf；doc（老格式）→None。"""
    low = url.lower()
    if not low.endswith((".docx", ".doc", ".pdf")):
        return None
    r = t.polite_get(url, 2.6)
    if r is None:
        return None
    try:
        if low.endswith(".docx"):
            import io
            import docx as pydocx
            d = pydocx.Document(io.BytesIO(r.content))
            parts = []
            for p in d.paragraphs:
                if p.text.strip():
                    parts.append(p.text.strip())
            for tb in d.tables:
                for row in tb.rows:
                    cells = [c.get_text("\n", strip=True).replace("\n", " ") for c in row.cells]
                    parts.append("| " + " | ".join(cells) + " |")
            txt = "\n\n".join(parts)
            return txt if len(txt) > 50 else None
        if low.endswith(".pdf"):
            import pymupdf
            with pymupdf.open(stream=r.content, filetype="pdf") as doc:
                txt = "\n".join(pg.get_text() for pg in doc)
            txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
            return txt if len(txt) > 50 else None
    except Exception:
        return None
    return None  # .doc 老二进制格式，本环境无解析器


def iter_channel(col_code, cid, list_url, max_pages=30):
    """JSON 接口翻页，yield (url,title,date)；newest-first，过旧即停。"""
    page = 1
    while page <= max_pages:
        api = (f"{HOST}/gdtaxejs/common/search/{cid}?_pageSize=20&page={page}"
               f"&_isAgg=true&_isJson=true&_template=index&_rangeTimeGte=&_channelName=")
        r = t.polite_get(api, 2.5, referer=list_url)
        if r is None:
            print(f"  [{col_code}] api fail p{page}")
            return
        try:
            data = json.loads(r.text)["data"]
        except Exception:
            print(f"  [{col_code}] json fail p{page}")
            return
        results = data.get("results") or []
        if not results:
            return
        stale = 0
        for it in results:
            raw = (it.get("url") or "").strip()
            if raw.startswith("../../"):
                u = HOST + "/" + raw[6:]
            elif raw.startswith("/"):
                u = HOST + raw
            else:
                u = urljoin(HOST + "/", raw)
            title = clean_title(it.get("title", ""))
            d = (it.get("publishedTimeStr") or "")[:10]
            if not (u.startswith("https://guangdong.chinatax.gov.cn/") and u.endswith((".shtml", ".html"))):
                continue  # 外链（拍卖平台等）跳过
            if d and d < DATE_FROM:
                stale += 1
                continue
            if u and title:
                yield u, title, d
        if stale >= len(results) - 1:  # 本页几乎全过期
            return
        if page * 20 >= int(data.get("total") or 0):
            return
        page += 1


NOISE = re.compile(
    r"^(浏览次数|字号|打印本页|分享至|【打印】|【关闭】|.*扫描分享.*)$")


def clean_md(md):
    lines = [ln for ln in md.splitlines()
             if not NOISE.match(ln.strip()) and not re.match(r"^\[?(大|中|小)\]?$", ln.strip())]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_progress():
    path = os.path.join(t.PROG_DIR, JOB_ID + ".jsonl")
    done, listed = set(), {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("url") and rec.get("ok"):
                    done.add(rec["url"])
                if rec.get("phase") == "list":
                    listed[rec.get("col")] = rec
    # 省局轮已抓过的 URL 一并视为完成（跨 progress 去重）
    prev = os.path.join(t.PROG_DIR, "gd_cases.jsonl")
    if os.path.exists(prev):
        with open(prev, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("url") and rec.get("ok"):
                    done.add(rec["url"])
    return done, listed, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--city", default="")
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--budget", type=int, default=3000, help="详情阶段秒数")
    args = ap.parse_args()

    order = args.city.split(",") if args.city else list(CITIES.keys())
    done, listed, prog_path = load_progress()

    # ---------- 阶段1：列表 ----------
    queue = {}
    for ck in order:
        if ck not in CITIES:
            continue
        cname, code, cols = CITIES[ck]
        for col in cols:
            col_short = col.split("_", 1)[1]
            cid, list_url = None, None
            if col in listed:
                cid = listed[col].get("cid")
                list_url = listed[col].get("list_url")
            if not cid:
                cid, list_url = get_channel_id(col)
                if not cid:
                    print(f"[{cname}] {col}: no channelId, skip")
                    continue
            n0 = len(queue)
            for u, ti, d in iter_channel(col, cid, list_url):
                if not TITLE_KW.search(ti) or TITLE_EXCLUDE.search(ti):
                    continue
                queue.setdefault(u, (ti, d, cname))
            print(f"[{cname}] {COL_NAME.get(col_short, col)}: +{len(queue)-n0} (cum {len(queue)})")
            with open(prog_path, "a", encoding="utf-8") as pf:
                pf.write(json.dumps({"phase": "list", "col": col, "cid": cid,
                                     "list_url": list_url}, ensure_ascii=False) + "\n")

    print("[list] total candidates:", len(queue),
          "| already done:", sum(1 for u in queue if u in done))

    if args.dry:
        for u, (ti, d, cn) in sorted(queue.items(), key=lambda x: x[1][1] or "", reverse=True)[:50]:
            print(f"[dry] {d} [{cn}/{classify(ti)}] {ti[:48]}")
        return
    if args.list_only:
        return

    # ---------- 阶段2：详情 ----------
    t0 = time.time()
    n_new = n_fail = n_skip = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        for u, (ti, d, cname) in sorted(queue.items(), key=lambda x: x[1][1] or "", reverse=True):
            if time.time() - t0 > args.budget:
                print("[run] budget reached, stop")
                break
            if u in done:
                n_skip += 1
                continue
            r = t.polite_get(u, 2.6, referer=HOST + "/")
            d_art = t.extract_detail(r.text, u, ti, d) if r is not None else None
            md_body = (d_art or {}).get("md") or ""
            atts = (d_art or {}).get("attachments") or []
            if not atts and r is not None and len(md_body) < 100:
                # extract_detail 失败时从页面直取附件链接
                atts = [urljoin(u, m) for m in
                        re.findall(r'href="([^"]+\.(?:pdf|docx?|xlsx?))"', r.text, re.I)]
            # 正文太短且带附件 → 附件抽正文（送达公告正文在 docx/pdf 里）
            if len(md_body) < 100 and atts:
                att_md = []
                for a in atts[:3]:
                    ext_txt = extract_attachment_md(a)
                    if ext_txt:
                        att_md.append(ext_txt)
                    else:
                        att_md.append(f"（附件 {a.rsplit('/', 1)[-1]} 为二进制格式或无文本层，未提取）")
                if any(len(x) > 50 for x in att_md):
                    head = md_body.strip() or ti
                    md_body = head + "\n\n" + "\n\n".join(att_md)
                    if d_art is None:
                        d_art = {"title": ti, "date": d, "source_org": "",
                                 "md": md_body, "attachments": atts}
                    else:
                        d_art["md"] = md_body
            if not d_art or len(d_art.get("md") or "") < 100:
                prog.write(json.dumps({"url": u, "ok": False, "err": "fetch/parse",
                                       "title": ti}, ensure_ascii=False) + "\n")
                prog.flush()
                n_fail += 1
                continue
            title = d_art["title"] or ti
            pd = d_art["date"] or d
            cat = classify(title)
            out_dir = os.path.join(OUT_ROOT, cname, cat)
            os.makedirs(out_dir, exist_ok=True)
            fname = t.safe_filename((pd or "nodate") + "_" + title) + ".md"
            fm = ("---\n"
                  f"title: \"{title.replace(chr(34), '')}\"\n"
                  f"来源机关: \"国家税务总局{cname}税务局\"\n"
                  f"栏目: \"{cat}\"\n"
                  f"地区: \"广东省\"\n"
                  f"发布日期: {pd or ''}\n"
                  f"原文来源: \"\"\n"
                  f"抓取日期: {date.today().isoformat()}\n"
                  f"原文链接: {u}\n")
            atts = d_art.get("attachments") or []
            if atts:
                fm += "附件:\n" + "\n".join(f"  - {a}" for a in atts) + "\n"
            fm += "---\n\n"
            with open(os.path.join(out_dir, fname), "w", encoding="utf-8", newline="\n") as f:
                f.write(fm + clean_md(d_art["md"]) + "\n")
            prog.write(json.dumps({"url": u, "ok": True, "file": fname, "cat": cat,
                                   "city": cname, "title": title, "date": pd},
                                  ensure_ascii=False) + "\n")
            prog.flush()
            n_new += 1
            if n_new % 20 == 0:
                print(f"[run] new={n_new} fail={n_fail} skip={n_skip} "
                      f"elapsed={int(time.time()-t0)}s")
    print(f"[run] DONE new={n_new} fail={n_fail} skip={n_skip} "
          f"elapsed={int(time.time()-t0)}s")


if __name__ == "__main__":
    main()
