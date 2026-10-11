# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""四川 etax 平台记录 + 失信公布栏行 + TRS 文章 → lawlibrary md（离线转换）。
被 sc_river.py --part md 调用；也可单独 python sc_river_md.py
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # safe_filename

TMP = os.path.join(ROOT, "tmp")
ETAXD = os.path.join(TMP, "sc_etax")
PAGES = os.path.join(TMP, "sc_pages")
LISTS_LOCAL = os.path.join(TMP, "sc_lists")
ATT_DIR_LOCAL = os.path.join(TMP, "sc_atts")
PROGDIR = os.path.join(ROOT, "progress")
PROG = os.path.join(PROGDIR, "sc_cols.jsonl")

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))
OUT_XZCF = os.path.join(LAWLIB, "专题", "税务案例", "四川省", "行政处罚公示")
ETAX_PAGE = "https://etax.sichuan.chinatax.gov.cn/zfgspt/extranet/swxzcfjg"
DATE_FROM = "2023-01-01"
MAX_OUT = 1000

CID_MAP = {
    "20038": ("重大税收违法失信公布", "重大税收违法失信公布"),
    "20038d": ("重大税收违法失信公布", "重大税收违法失信公布"),
    "19241": ("通知公告涉税公告", "通知公告涉税公告"),
    "fuyi": ("行政复议", "行政复议"),
}
NOISE_TITLE = re.compile(r"采购|比选|招标|询价|造价|监理")

FIELD_LABEL = [
    ("XZCFJDSWH", "行政处罚决定书文号"),
    ("AJMC", "案件名称"),
    ("NSRMC", "被处罚对象（纳税人名称）"),
    ("TYSHXYDM", "统一社会信用代码"),
    ("FDDBRXM", "法定代表人"),
    ("CFLB", "处罚类别"),
    ("CFJG", "处罚结果"),
    ("SWJGMC", "处罚机关"),
    ("ZCGCFRQ", "作出处罚日期"),
    ("CFSXQ", "处罚事项发生日期起"),
    ("WCSX", "处罚事项发生日期止"),
    ("XXXCBGRQ", "信息公布日期"),
    ("FBSJ", "发布时间"),
    ("GSSJZ", "公示截止"),
    ("SXZTMC", "公示状态"),
]

SX_FIELDS = [
    ("zdnsrmc", "失信主体名称"),
    ("title", "失信主体名称"),
    ("zdnsrsbh", "统一社会信用代码（纳税人识别号）"),
    ("zdzzjgdm", "组织机构代码"),
    ("zdzcdz", "注册地址"),
    ("zdfddbr", "法定代表人"),
    ("zdcwfzr", "财务负责人"),
    ("zdzjjg", "相关中介机构"),
    ("zdajxz", "案件性质（违法性质）"),
    ("zdgbjg", "公布机关"),
]


def clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s in ("null", "-", "None"):
        return ""
    return re.sub(r"\s+", " ", s)


def done_keys():
    ks = set()
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                ks.add(json.loads(ln).get("key"))
            except Exception:
                pass
    return ks


def mark_line(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def rec_date(rec):
    for f in ("FBSJ", "ZCGCFRQ", "XXXCBGRQ"):
        v = clean(rec.get(f))
        m = re.match(r"(20\d{2})-(\d{2})-(\d{2})", v)
        if m:
            return v[:10]
    return ""


def front_matter(title, cat, pub, src, url):
    return (
        "---\n"
        f'title: "{title.replace(chr(34), "")}"\n'
        '来源机关: "国家税务总局四川省税务局"\n'
        f'栏目: "{cat}"\n'
        '地区: "四川省"\n'
        f"发布日期: {pub or date.today().isoformat()}\n"
        f'原文来源: "{src}"\n'
        f"抓取日期: {date.today().isoformat()}\n"
        f"原文链接: {url}\n"
        "---\n\n"
    )


# ------------------------------------------------------------- etax 处罚记录

def rec_to_md(rec):
    title = clean(rec.get("AJMC")) or clean(rec.get("NSRMC")) or "税务行政处罚"
    d = rec_date(rec)
    rows = [(lab, clean(rec.get(k))) for k, lab in FIELD_LABEL]
    rows = [(k, v) for k, v in rows if v]
    lines = [f"# {title}", "", "## 处罚信息", "", "| 项目 | 内容 |", "| --- | --- |"]
    for k, v in rows:
        v = v.replace("|", "\\|")
        lines.append(f"| {k} | {v} |")
    cfsy = clean(rec.get("CFSY"))
    cfyj = clean(rec.get("CFYJ"))
    if cfsy:
        lines += ["", "## 违法事实", "", cfsy]
    if cfyj:
        lines += ["", "## 处罚依据", "", cfyj]
    return front_matter(title, "行政处罚公示", d, "四川税务行政执法信息公示平台",
                        ETAX_PAGE) + "\n".join(lines) + "\n"


def run_md_etax():
    rec_path = os.path.join(ETAXD, "records.jsonl")
    if not os.path.exists(rec_path):
        print("no records.jsonl")
        return
    recs, order = {}, []
    for ln in open(rec_path, encoding="utf-8"):
        try:
            r = json.loads(ln)
        except Exception:
            continue
        k = r.get("KEY") or (clean(r.get("XZCFJDSWH")) + "|" + clean(r.get("NSRMC")))
        if k not in recs:
            recs[k] = r
            order.append(k)
    dated = sorted(((rec_date(recs[k]), k) for k in order if rec_date(recs[k]) >= DATE_FROM),
                   reverse=True)
    capped = False
    if len(dated) > MAX_OUT:
        dated = dated[:MAX_OUT]
        capped = True
    done = {k for k in done_keys() if k.startswith("etax:")}
    n_new = 0
    for d, k in dated:
        if f"etax:{k}" in done:
            continue
        md = rec_to_md(recs[k])
        title = clean(recs[k].get("AJMC")) or clean(recs[k].get("NSRMC"))
        fname = f"{d}_{t.safe_filename(title)}.md"
        fp = os.path.join(OUT_XZCF, fname)
        if os.path.exists(fp):
            fp = os.path.join(OUT_XZCF, f"{d}_{t.safe_filename(title)}_{k[:6]}.md")
        open(fp, "w", encoding="utf-8").write(md)
        mark_line({"key": f"etax:{k}", "phase": "etax_md",
                   "file": os.path.basename(fp), "ts": time.strftime("%m-%d %H:%M")})
        n_new += 1
    undated = sum(1 for k in order if not rec_date(recs[k]))
    print(f"etax unique={len(order)} in-window={len(dated)}(capped={capped}) "
          f"undated={undated} new_md={n_new}")


# ------------------------------------------------------------- 失信公布栏行

def strip_tags(v, block_nl=False):
    v = clean(v)
    if block_nl:
        v = re.sub(r"</p\s*>|<br\s*/?>|</tr>", "\n", v, flags=re.I)
    v = re.sub(r"<[^>]+>", "", v)
    v = re.sub(r"[ \t]+", " ", v)
    v = re.sub(r"\n{3,}", "\n\n", v)
    return v.strip()


def run_md_shixin():
    sx_path = os.path.join(ETAXD, "shixin_rows.jsonl")
    if not os.path.exists(sx_path):
        print("no shixin_rows.jsonl (skip)")
        return
    outdir = os.path.join(LAWLIB, "专题", "税务案例", "四川省", "重大税收违法失信公布")
    os.makedirs(outdir, exist_ok=True)
    done = {k for k in done_keys() if k.startswith("sx:")}
    rows = []
    for ln in open(sx_path, encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except Exception:
            pass

    def dt(r):
        try:
            return datetime.fromtimestamp(int(r.get("deploytime", 0)) / 1000).strftime("%Y-%m-%d")
        except Exception:
            return ""

    rows = sorted(((dt(r), r) for r in rows if dt(r) >= DATE_FROM),
                  key=lambda x: x[0], reverse=True)
    if len(rows) > MAX_OUT:
        rows = rows[:MAX_OUT]
    n_new = 0
    for d, r in rows:
        k = "sx:" + (r.get("url") or "")[-40:]
        if k in done:
            continue
        name = clean(r.get("title")) or clean(r.get("zdnsrmc")) or "失信主体"
        nature = clean(r.get("zdajxz"))[:30]
        title = f"{name}-{nature}" if nature else name
        seen_lab, table_rows = set(), []
        for f, lab in SX_FIELDS:
            if lab in seen_lab:
                continue
            v = strip_tags(r.get(f)).replace("|", "\\|")
            if not v:
                continue
            seen_lab.add(lab)
            table_rows.append((lab, v))
        lines = [f"# {title}", "", "## 失信主体信息", "", "| 项目 | 内容 |", "| --- | --- |"]
        for lab, v in table_rows:
            lines.append(f"| {lab} | {v} |")
        lines.append(f"| 信息公布日期 | {d} |")
        facts = strip_tags(r.get("zdzywfss"), block_nl=True)
        if facts:
            lines += ["", "## 主要违法事实", "", facts]
        pen = strip_tags(r.get("zdswclcf"))
        if pen:
            lines += ["", "## 税务处理及处罚", "", pen]
        url = (r.get("url") or "").replace("http://sichuan.", "https://sichuan.")
        md = front_matter(title, "重大税收违法失信公布", d,
                          "四川税务重大税收违法失信主体信息公布栏", url)
        fname = f"{d}_{t.safe_filename(title)}.md"
        fp = os.path.join(outdir, fname)
        if os.path.exists(fp):
            fp = os.path.join(outdir, f"{d}_{t.safe_filename(title)}_{k[-8:]}.md")
        open(fp, "w", encoding="utf-8").write(md + "\n".join(lines) + "\n")
        mark_line({"key": k, "phase": "sx_md", "file": os.path.basename(fp),
                   "ts": time.strftime("%m-%d %H:%M")})
        n_new += 1
    print(f"shixin in-window={len(rows)} new_md={n_new} -> {outdir}")


# ------------------------------------------------------------- TRS 文章页

def art_extract(html, fb_title, fb_date):
    """四川 TRS 文章：meta 标题/日期 + ZJEG_RSS 内容标记切片。"""
    from bs4 import BeautifulSoup
    from markdownify import markdownify as mdfy
    title, pub = fb_title, fb_date
    m = re.search(r'<meta\s+name="ArticleTitle"\s+content=[\'"]([^\'"]+)', html)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r'<meta\s+name="PubDate"\s+content=[\'"](20\d{2}-\d{2}-\d{2})', html)
    if m:
        pub = m.group(1)
    seg = ""
    m = re.search(r"ZJEG_RSS\.content\.begin(.*?)ZJEG_RSS\.content\.end", html, re.S)
    if m:
        seg = m.group(1)
    else:
        soup = BeautifulSoup(html, "lxml")
        node = soup.select_one(".info-cont") or soup.select_one("#zoom")
        seg = str(node) if node else ""
    seg = re.sub(r"<meta[^>]*>", "", seg)
    body = mdfy(seg, heading_style="ATX", bullets_style="-")
    lines = [ln.rstrip() for ln in body.split("\n")]
    lines = [ln for ln in lines if not re.match(
        r"^\s*(\[+大\]+|\[+中\]+|\[+小\]+|打印.*|关闭.*|分享.*|字号.*|访问量.*|-->*|<!--.*)\s*$", ln)]
    return title, pub, re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def att_text(art):
    import hashlib
    out = []
    for au in (art.get("atts") or [])[:6]:
        an = os.path.basename(au.split("?")[0])[:60] or "att"
        ak = hashlib.md5(au.encode()).hexdigest()[:12] + "_" + an
        fp = os.path.join(ATT_DIR_LOCAL, ak)
        if not os.path.exists(fp) or not an.lower().endswith(".pdf"):
            continue
        try:
            import pymupdf
            doc = pymupdf.open(fp)
            txt = "\n".join(pg.get_text() for pg in doc)
            doc.close()
            if len(txt.strip()) > 200:
                out.append((an, txt.strip()))
        except Exception:
            continue
    return out


def run_md_arts():
    meta_path = os.path.join(LISTS_LOCAL, "arts_meta.jsonl")
    if not os.path.exists(meta_path):
        print("no arts_meta.jsonl (skip arts)")
        return
    done = {k for k in done_keys() if k.startswith("art:")}
    stats = {}
    for ln in open(meta_path, encoding="utf-8"):
        try:
            a = json.loads(ln)
        except Exception:
            continue
        if f"art:{a['key']}" in done or not os.path.exists(a.get("file", "")):
            continue
        if a.get("title") and NOISE_TITLE.search(a["title"]):
            mark_line({"key": f"art:{a['key']}", "phase": "art_md_noise", "cid": a["cid"],
                       "ts": time.strftime("%m-%d %H:%M")})
            stats.setdefault(a["cid"], [0, 0, 0])
            stats[a["cid"]][2] += 1
            continue
        html = open(a["file"], encoding="utf-8", errors="replace").read()
        title, pub, body = art_extract(html, a.get("title", ""), a.get("date", ""))
        if not body or len(body) < 40:
            mark_line({"key": f"art:{a['key']}", "phase": "art_md_empty", "cid": a["cid"],
                       "ts": time.strftime("%m-%d %H:%M")})
            stats.setdefault(a["cid"], [0, 0, 0])
            stats[a["cid"]][1] += 1
            continue
        outdir_name, cat = CID_MAP.get(a["cid"], ("行政处罚公示", "行政处罚公示"))
        outdir = os.path.join(LAWLIB, "专题", "税务案例", "四川省", outdir_name)
        os.makedirs(outdir, exist_ok=True)
        atts_txt = att_text(a)
        if atts_txt:
            body += "\n\n" + "\n\n".join(
                f"## 附件原文（{an}）\n\n{tx}" for an, tx in atts_txt)
        md = front_matter(title, cat, pub, "", a["url"])
        fname = f"{pub}_{t.safe_filename(title)}.md" if pub else f"{t.safe_filename(title)}.md"
        fp = os.path.join(outdir, fname)
        if os.path.exists(fp):
            fp = os.path.join(outdir, f"{pub}_{t.safe_filename(title)}_{a['key'][:6]}.md")
        open(fp, "w", encoding="utf-8").write(md + body + "\n")
        mark_line({"key": f"art:{a['key']}", "phase": "art_md", "cid": a["cid"],
                   "file": os.path.basename(fp), "ts": time.strftime("%m-%d %H:%M")})
        stats.setdefault(a["cid"], [0, 0, 0])
        stats[a["cid"]][0] += 1
    for cid, (ok, empty, noise) in stats.items():
        print(f"cid{cid}: md={ok} empty={empty} noise={noise}")


def run_md():
    run_md_shixin()
    run_md_arts()
    run_md_etax()


if __name__ == "__main__":
    run_md()
