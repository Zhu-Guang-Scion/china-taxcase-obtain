# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""湖北/重庆 离线转 md + 质量门槛判定入库。
源：
  CQ  tmp/hb_cq/cq_sx_details.jsonl (796) / cq_arts_meta.jsonl (62)
  HB  tmp/hb_cq/hb_arts_meta.jsonl (sx 167 + news 50 + xzcf 5) / hb_xzcf_records.json
入库前逐件 quality_prune.decide() 判定，DEL 不写盘。
断点 progress/hb_cq_r6.jsonl（hbcq_md:{path}）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, hashlib
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t
from quality_prune import decide

TMP = os.path.join(ROOT, "tmp", "hb_cq")
LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))
BASE = os.path.join(LAWLIB, "专题", "税务案例")
PROG = os.path.join(ROOT, "progress", "hb_cq_r6.jsonl")
TODAY = date.today().isoformat()


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def done_keys(prefix):
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


def cjk_len(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s or ""))


def write_md(region, cat, title, pub, src, url, body):
    """质量门槛判定后写盘；返回 verdict。"""
    verdict, fl, why = decide(cat, region, body)
    if verdict == "DEL":
        return "DEL", fl, why, None
    outdir = os.path.join(BASE, region, cat)
    os.makedirs(outdir, exist_ok=True)
    fm = ("---\n"
          f'title: "{title.replace(chr(34), "")}"\n'
          f'来源机关: "国家税务总局{"湖北省" if region == "湖北省" else "重庆市"}税务局"\n'
          f'栏目: "{cat}"\n'
          f'地区: "{region}"\n'
          f"发布日期: {pub or TODAY}\n"
          f'原文来源: "{src}"\n'
          f"抓取日期: {TODAY}\n"
          f"原文链接: {url}\n"
          "---\n\n")
    fname = f"{pub or TODAY}_{t.safe_filename(title)}.md"
    fp = os.path.join(outdir, fname)
    if os.path.exists(fp):
        fp = os.path.join(outdir, f"{pub or TODAY}_{t.safe_filename(title)}_{hashlib.md5(url.encode()).hexdigest()[:6]}.md")
    open(fp, "w", encoding="utf-8").write(fm + body + "\n")
    return "KEEP", fl, why, fp


def clean(v):
    if v is None:
        return ""
    s = str(v).strip()
    if s in ("null", "-", "None"):
        return ""
    return re.sub(r"\s+", " ", s)


# ---------------------------------------------------------------- CQ 失信

AJXZ_MAP = {
    "1": "逃避缴纳税款", "2": "逃避追缴欠税", "3": "骗取出口退税",
    "4": "拒不缴纳税款", "5": "虚开增值税专用发票或者虚开用于骗取出口退税、抵扣税款的其他发票",
    "6": "虚开增值税普通发票", "7": "私印、伪造、变造发票等", "8": "其他税收违法",
    "9": "走逃（失联）", "a": "非法提供银行账户、发票、证明", "b": "代理人违法",
}


def ajxz_txt(code):
    parts = [AJXZ_MAP.get(c.strip(), c.strip()) for c in re.split(r"[,，]", code or "") if c.strip()]
    return "；".join(p for p in parts if p)


def md_cq_sx():
    done = done_keys("hbcq_md:cqsx:")
    stats = {"KEEP": 0, "DEL": 0}
    for ln in open(os.path.join(TMP, "cq_sx_details.jsonl"), encoding="utf-8"):
        d = json.loads(ln)
        k = "hbcq_md:cqsx:" + str(d.get("_id"))
        if k in done:
            continue
        name = clean(d.get("nsrmc")) or "失信主体"
        nature = ajxz_txt(clean(d.get("ajxz")))
        title = f"{name}-{nature[:24]}" if nature else name
        rows = [
            ("失信主体名称（纳税人名称）", clean(d.get("nsrmc"))),
            ("统一社会信用代码（纳税人识别号）", clean(d.get("nsrsbh"))),
            ("组织机构代码", clean(d.get("zzjgdm"))),
            ("注册地址", clean(d.get("zcdz"))),
            ("法定代表人", clean(d.get("frxm")) + (f"（{clean(d.get('frxb'))}，{clean(d.get('frzjlx'))}：{clean(d.get('frzjhm'))}）" if clean(d.get("frzjhm")) else "")),
            ("案件性质", nature),
            ("查处机关（区县）", clean(d.get("swjgmc"))),
        ]
        lines = [f"# {title}", "", "## 失信主体信息", "",
                 "| 项目 | 内容 |", "| --- | --- |"]
        for lab, v in rows:
            if v:
                lines.append(f"| {lab} | {v.replace('|', chr(92)+'|')} |")
        wf = clean(d.get("wfxx"))
        if wf:
            lines += ["", "## 违法事实", "", wf]
        lb = clean(d.get("legalBasis"))
        if lb:
            lines += ["", "## 税务处理及处罚", "", lb]
        url = "http://chongqing.chinatax.gov.cn/xxgkxt/pages/qywh/zdwfajcx.html"
        v, fl, why, fp = write_md("重庆市", "重大税收违法失信公布", title, "",
                                  "重庆税务重大税收违法失信主体信息公布栏", url,
                                  "\n".join(lines))
        stats[v] += 1
        mark({"key": k, "phase": "cq_sx_md", "v": v, "why": why,
              "file": os.path.basename(fp) if fp else ""})
    log(f"CQ失信 md: keep={stats['KEEP']} del={stats['DEL']}")


# ---------------------------------------------------------------- 文章类

def html_to_text(html):
    from bs4 import BeautifulSoup
    from markdownify import markdownify as mdfy
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return soup, mdfy(str(soup), heading_style="ATX", bullets_style="-")


NOISE = re.compile(r"^\s*(\[+大\]+|\[+中\]+|\[+小\]+|打印.*|关闭.*|分享.*|字号.*|访问量.*|微信.*|下载.*|-->*|<!--.*|\|)\s*$")


ART_NOISE = re.compile(
    r"发布时间|来源[：:]|字号|打印|下载|分享|微信|二维码|扫一扫|简体|繁体|无障碍|访问量|阅读量|点击量|责任编辑")


def extract_article(html, fb_title, fb_date, url=""):
    """文章 → (title, date, md_body)，复用通用库 extract_detail（多容器回退+噪音清洗）。"""
    d = t.extract_detail(html, url, fb_title, fb_date)
    if not d or not d.get("md") or cjk_len(d.get("md", "")) < 60:
        return fb_title, fb_date, ""
    title = d.get("title") or fb_title
    pub = d.get("date") or fb_date
    md = d["md"]
    # 1) 杀 base64 图片
    md = re.sub(r"!\[[^\]]*\]\(data:image/[^)]+\)", "", md)
    # 2) 逐行噪音过滤
    lines = [ln.rstrip() for ln in md.split("\n")]
    lines = [ln for ln in lines if not ART_NOISE.search(ln)]
    # 3) 去掉开头连续的链接行/空行/箭头行（面包屑）
    while lines and (not lines[0].strip()
                     or re.match(r"^(\[.*\]\([^)]*\)|!\[[^\]]*\]\([^)]*\)|[-–—>›»\s]+)$", lines[0].strip())):
        lines.pop(0)
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return title, pub, body


def hb_sx_extract(html, fb_title, fb_date):
    """湖北失信公布表：2 列 table 配对 + 叙述段拆 违法事实/处理处罚。"""
    title, pub = fb_title, fb_date
    m = re.search(r'发布时间[：:>\s]*(20\d{2}-\d{2}-\d{2})', html)
    if m:
        pub = m.group(1)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    table = None
    for tb in soup.find_all("table"):
        txt = tb.get_text(" ", strip=True)
        if "纳税人名称" in txt and ("违法事实" in txt or "案件性质" in txt):
            table = tb
            break
    if table is None:
        # 回退：纯文本
        _, _, body = (lambda *a: (a[0], a[1], ""))(None, None, None)
        t2, p2, b2 = hb_sx_extract_text(html, title, pub)
        return t2, p2, b2
    fields, narr = [], ""
    for tr in table.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue
        lab = tds[0].get_text(" ", strip=True)
        val = tds[1].get_text(" ", strip=True)
        if not lab:
            continue
        if "主要违法事实" in lab or "税务处理处罚" in lab:
            narr = val
        elif val:
            fields.append((lab, val))
    out = [f"# {title}", "", "## 失信主体信息", "", "| 项目 | 内容 |", "| --- | --- |"]
    for k, v in fields:
        out.append(f"| {k} | {v.replace('|', chr(92) + '|')[:150]} |")
    if narr:
        m2 = re.search(r"(依照|根据《)", narr)
        if m2 and m2.start() > 30:
            facts, penalty = narr[:m2.start()].strip(), narr[m2.start():].strip()
        else:
            facts, penalty = narr, ""
        out += ["", "## 主要违法事实", "", facts]
        if penalty:
            out += ["", "## 税务处理及处罚", "", penalty]
    return title, pub, "\n".join(out)


def hb_sx_extract_text(html, title, pub):
    soup, _ = html_to_text(html)
    txt = soup.get_text("\n", strip=True)
    i = txt.find("纳税人名称")
    j = txt.find("网站地图")
    seg = txt[i:j if j > 0 else None]
    return title, pub, "\n".join([f"# {title}", "", "## 失信公布表", "", seg])


def col_of(url, region):
    if region == "重庆市":
        return "税案通报" if "/xwdt/" in url else "通知公告涉税案例"
    return "税案通报" if "/xwdt/" in url else "通知公告涉税案例"


def md_articles(meta_file, region, prefix, use_hb_sx=False):
    done = done_keys(f"hbcq_md:{prefix}:")
    stats = {"KEEP": 0, "DEL": 0}
    for ln in open(meta_file, encoding="utf-8"):
        a = json.loads(ln)
        key = f"hbcq_md:{prefix}:{os.path.basename(a['file'])}"
        if key in done or not os.path.exists(a["file"]):
            continue
        html = open(a["file"], encoding="utf-8", errors="replace").read()
        if use_hb_sx and a.get("col") == "sx":
            title, pub, body = hb_sx_extract(html, a.get("title", ""), a.get("date", ""))
            cat = "重大税收违法失信公布"
        else:
            title, pub, body = extract_article(html, a.get("title", ""), a.get("date", ""),
                                               a["url"])
            cat = col_of(a["url"], region)
            if a.get("col") == "xzcf":
                cat = "行政处罚公示"
        if not body or cjk_len(body) < 60:
            mark({"key": key, "phase": "art_md_empty", "col": a.get("col")})
            continue
        v, fl, why, fp = write_md(region, cat, title, pub, "", a["url"], body)
        stats[v] += 1
        if v == "DEL":
            mark({"key": key, "phase": "art_md_del", "why": why, "fl": fl})
        else:
            mark({"key": key, "phase": "art_md", "file": os.path.basename(fp) if fp else ""})
    log(f"{region} articles: keep={stats['KEEP']} del={stats['DEL']}")


# ---------------------------------------------------------------- HB gspt 处罚记录

FIELD_LABEL = [
    ("XZCFJDSWH", "行政处罚决定书文号"), ("AJMC", "案件名称"), ("CFLB", "处罚类别"),
    ("CFSY", "处罚事由"), ("CFYJ", "处罚依据"), ("NSRMC", "行政相对人名称"),
    ("TYSHXYDM", "统一社会信用代码"), ("ZJHM", "证件号码"), ("FDDBRXM", "法定代表人姓名"),
    ("CFJG", "处罚结果"), ("CFSWJG", "处罚机关"), ("GSSJ", "公示时间"),
    ("CFSXQ", "处罚生效期"), ("FKJE", "罚款金额（万元）"), ("XZXDRLB", "行政相对人类别"),
]


def md_hb_xzcf():
    p = os.path.join(TMP, "hb_xzcf_records.json")
    if not os.path.exists(p):
        log("no hb_xzcf_records.json")
        return
    recs = json.load(open(p, encoding="utf-8"))
    stats = {"KEEP": 0, "DEL": 0}
    for r in recs:
        title = clean(r.get("AJMC")) or clean(r.get("NSRMC")) or "税务行政处罚"
        rows = [(lab, clean(r.get(k))) for k, lab in FIELD_LABEL if clean(r.get(k))]
        lines = [f"# {title}", "", "## 处罚信息", "", "| 项目 | 内容 |", "| --- | --- |"]
        for lab, v in rows:
            lines.append(f"| {lab} | {v.replace('|', chr(92)+'|')} |")
        v2, fl, why, fp = write_md(
            "湖北省", "行政处罚公示", title, clean(r.get("GSSJ")),
            "湖北税务执法信息公示平台",
            "http://hubei.chinatax.gov.cn" + clean(r.get("articleurl")),
            "\n".join(lines))
        stats[v2] += 1
        log(f"  hb xzcf {title[:20]}: {v2} ({why})")
    log(f"HB处罚: keep={stats['KEEP']} del={stats['DEL']}")


def main():
    md_cq_sx()
    md_articles(os.path.join(TMP, "cq_arts_meta.jsonl"), "重庆市", "cqart")
    md_articles(os.path.join(TMP, "hb_arts_meta.jsonl"), "湖北省", "hbart", use_hb_sx=True)
    md_hb_xzcf()


if __name__ == "__main__":
    main()
