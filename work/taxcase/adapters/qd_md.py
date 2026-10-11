# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""青岛/湖南 r6 → md 入库（质量门槛强制）
  qd_xzcf  tmp/qd/xzcf_records.jsonl → 青岛市/行政处罚公示
  qd_sswf  tmp/qd/sswf_list.jsonl(+details) → 青岛市/重大税收违法失信公布
  hn_sx    tmp/hn/hardcase_records.jsonl → 湖南省/重大税收违法失信公布
  hn_xzcf  tmp/hn/xzcf_records.jsonl → 湖南省/行政处罚公示
用法: python qd_hn_md.py --kind qd_xzcf|qd_sswf|hn_sx|hn_xzcf|all
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, argparse, hashlib
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402
from taxcase_scrape import safe_filename  # noqa: E402

LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例"))
TODAY = date.today().isoformat()
DATE_FROM = "2023-01-01"
TMP = os.path.join(ROOT, "tmp")


def nz(v):
    return "" if v is None else str(v).strip()


def ms2date(v):
    try:
        return datetime.fromtimestamp(int(v) / 1000).strftime("%Y-%m-%d")
    except Exception:
        return ""


def cjk_date(v):
    m = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", nz(v))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def write_md(path, fm, body):
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body)


def make_fm(title, org, column, region, pub, src, url, extra=""):
    return ("---\n"
            f"title: \"{title.replace(chr(34), '')}\"\n"
            f"来源机关: \"{org}\"\n"
            f"栏目: \"{column}\"\n"
            f"地区: \"{region}\"\n"
            f"发布日期: {pub or 'nodate'}\n"
            f"原文来源: \"{src}\"\n"
            f"抓取日期: {TODAY}\n"
            f"原文链接: {url}\n" + extra + "---\n\n")


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def conv_generic(records, out_dir, column, region, org, src, base_url,
                 title_f, rows_f, sections_f, date_f, key_f, url_f,
                 date_from=DATE_FROM, extra_fm_f=None):
    os.makedirs(out_dir, exist_ok=True)
    stats = {"keep": 0, "del": 0, "exists": 0, "old": 0}
    reasons = {}
    seen = set()
    for t in records:
        key = key_f(t)
        if not key or key in seen:
            continue
        seen.add(key)
        pub = date_f(t)
        title = title_f(t)
        lines = ["# " + title, ""]
        for k, v in rows_f(t):
            if v:
                lines.append(f"- **{k}**：{v}")
        for h, v in sections_f(t):
            lines += ["", f"## {h}", "", v or "（未公示）"]
        body = "\n".join(lines) + "\n"
        verdict, fl, why = decide(column, region, body)
        if verdict != "KEEP":
            stats["del"] += 1
            reasons[why] = reasons.get(why, 0) + 1
            continue
        if date_from and pub and pub < date_from:
            stats["old"] += 1
            continue
        fn = f"{pub or 'nodate'}_{safe_filename(title)[:80]}.md"
        path = os.path.join(out_dir, fn)
        if os.path.exists(path):
            stats["exists"] += 1
            continue
        extra = extra_fm_f(t) if extra_fm_f else ""
        fm = make_fm(title, org, column, region, pub, src, url_f(t), extra)
        write_md(path, fm, body)
        stats["keep"] += 1
    print(f"[{column}]", stats, "del:", reasons)
    return stats


# ---------------------------------------------------------------- 青岛处罚
QD_PLATFORM = ("https://etax.qingdao.chinatax.gov.cn:6883/newdzswj/sszfgsptReportList.do"
               "?type=gotoList&tyid=803079ca9d454d268f464306f73e0601&swjgdm=13702000000")


def qd_xzcf():
    recs = load_jsonl(os.path.join(TMP, "qd", "xzcf_records.jsonl"))
    # 按 文号+日期 去重（平台滚动窗口有重复）
    def rows_f(t):
        f = t.get("fields", {})
        return [
            ("行政处罚决定书文号", nz(f.get("行政处罚决定书文号")) or nz(t.get("wh"))),
            ("案件名称", nz(f.get("案件名称")) or nz(t.get("ajmc"))),
            ("纳税人名称", nz(f.get("纳税人名称"))),
            ("统一社会信用代码", nz(f.get("纳税人统一社会信用代码"))),
            ("行政相对人名称", nz(f.get("行政相对人名称"))),
            ("处罚类别", nz(f.get("处罚类别"))),
            ("法定代表人", nz(f.get("法定代表人姓名"))),
            ("处罚机关", nz(f.get("处罚税务机关名称")) or nz(t.get("jiguan"))),
            ("处罚日期", nz(t.get("date"))),
        ]

    def sections_f(t):
        f = t.get("fields", {})
        return [("违法事实", nz(f.get("处罚事由"))),
                ("处罚依据", nz(f.get("执法依据"))),
                ("处罚结果", nz(f.get("处罚结果")))]

    def extra_f(t):
        return (f"决定书文号: \"{nz(t.get('wh')).replace(chr(34), '')}\"\n"
                f"记录KEY: {hashlib.md5((nz(t.get('wh')) + nz(t.get('date'))).encode()).hexdigest().upper()}\n")

    return conv_generic(
        recs, os.path.join(LIB, "青岛市", "行政处罚公示"), "行政处罚公示", "青岛市",
        "国家税务总局青岛市税务局", "青岛市税务局税收执法公示平台", QD_PLATFORM,
        title_f=lambda t: nz(t.get("fields", {}).get("案件名称"))
            or nz(t.get("ajmc")) or (nz(t.get("wh")) + "税务行政处罚"),
        rows_f=rows_f, sections_f=sections_f,
        date_f=lambda t: nz(t.get("date")),
        key_f=lambda t: nz(t.get("wh")) + "|" + nz(t.get("date")),
        url_f=lambda t: QD_PLATFORM, extra_fm_f=extra_f)


# ---------------------------------------------------------------- 青岛失信
SSWF_LABELS = ["纳税人名称", "纳税人识别号", "组织机构代码", "注册地址",
               "法定代表人或负责人姓名、性别及身份证号码(或其他证件号码)",
               "违法期间法人代表或者负责人姓名、性别及身份证号码(或其他证件号码)",
               "负有直接责任的财务人员姓名、性别及身份证号码(或其他证件号码)",
               "实际负责人姓名、性别及身份证号码(或其他证件号码)",
               "负有直接责任的中介机构信息", "案件性质", "主要违法事实",
               "相关法律依据及税务处理处罚情况"]


def parse_sswf_detail(h):
    """青岛失信详情页 → {label: value} + 发布日期（正文标签-值内联结构）"""
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", body)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    dm = re.search(r"发布时间[：:]\s*(20\d{2}-\d{2}-\d{2})", txt)
    date = dm.group(1) if dm else ""
    out = {}
    # 找第一个 "纳税人名称" 起、到 "附件" 止的段
    i0 = txt.find("纳税人名称")
    if i0 == -1:
        return out, date, ""
    i1 = txt.find("附件", i0)
    seg = txt[i0:i1 if i1 > -1 else i0 + 6000]
    pos = []
    for lab in SSWF_LABELS:
        j = seg.find(lab)
        if j > -1:
            pos.append((j, lab))
    pos.sort()
    for k, (j, lab) in enumerate(pos):
        end = pos[k + 1][0] if k + 1 < len(pos) else len(seg)
        val = seg[j + len(lab):end].strip(" ;；,，")
        out[lab] = val
    fact = out.get("主要违法事实", "")
    return out, date, fact


def qd_sswf():
    meta = load_jsonl(os.path.join(TMP, "qd", "sswf_list.jsonl"))
    recs = []
    for m in meta:
        if not m.get("file") or not os.path.exists(m["file"]):
            continue
        h = open(m["file"], encoding="utf-8").read()
        f, d, fact = parse_sswf_detail(h)
        recs.append({"url": m["url"], "f": f, "fact": fact, "date": d})

    def rows_f(t):
        f = t["f"]
        keys = ["纳税人名称", "纳税人识别号", "组织机构代码", "注册地址",
                "案件性质"]
        rows = [(k, nz(f.get(k))) for k in keys]
        for k in list(f):
            if ("法定代表人" in k or "财务人员" in k or "实际负责人" in k
                    or "中介机构" in k) and nz(f.get(k)):
                rows.append((k[:14], nz(f[k])))
        return [r for r in rows if r[1]]

    return conv_generic(
        recs, os.path.join(LIB, "青岛市", "重大税收违法失信公布"), "重大税收违法失信公布",
        "青岛市", "国家税务总局青岛市税务局", "青岛市税务局重大税收违法失信主体信息公布栏",
        "https://qingdao.chinatax.gov.cn/resourcedata/sswf2019/",
        title_f=lambda t: nz(t["f"].get("纳税人名称")) + "（重大税收违法失信主体）",
        rows_f=rows_f,
        sections_f=lambda t: [
            ("主要违法事实", nz(t.get("fact"))),
            ("相关法律依据及税务处理处罚情况",
             nz(t["f"].get("相关法律依据及税务处理处罚情况")))],
        date_f=lambda t: nz(t.get("date")),
        key_f=lambda t: t["url"],
        url_f=lambda t: t["url"])


# ---------------------------------------------------------------- 湖南失信
HN_SX_URL = "https://hunan.chinatax.gov.cn/hardcase/20190408002097"


def hn_sx():
    recs = load_jsonl(os.path.join(TMP, "hn", "hardcase_records.jsonl"))
    def rows_f(t):
        return [
            ("纳税人名称", nz(t.get("taxpayerName"))),
            ("纳税人识别号", nz(t.get("taxpayerNumber"))),
            ("注册地址", nz(t.get("place"))),
            ("案件性质", nz((t.get("hardCaseType") or {}).get("typeName"))),
            ("公示机关/地区", nz(t.get("siteName"))),
        ]
    return conv_generic(
        recs, os.path.join(LIB, "湖南省", "重大税收违法失信公布"), "重大税收违法失信公布",
        "湖南省", "国家税务总局湖南省税务局", "湖南省税务局重大税收违法失信主体信息公布栏",
        HN_SX_URL,
        title_f=lambda t: nz(t.get("taxpayerName")) + "（重大税收违法失信主体）",
        rows_f=rows_f,
        sections_f=lambda t: [
            ("主要违法事实及相关处理处罚", nz(t.get("content")))],
        date_f=lambda t: ms2date(t.get("showTime") or t.get("addTime")),
        key_f=lambda t: nz(t.get("id")),
        url_f=lambda t: HN_SX_URL)


# ---------------------------------------------------------------- 湖南处罚
HN_XZCF_URL = "https://hunan.chinatax.gov.cn/xzzfpenalty/20200325400599"


def hn_xzcf():
    recs = load_jsonl(os.path.join(TMP, "hn", "xzcf_records.jsonl"))
    def rows_f(t):
        return [
            ("行政处罚决定书文号", nz(t.get("jdswh"))),
            ("案件名称", nz(t.get("ajmc"))),
            ("处罚类别", nz(t.get("cflb"))),
            ("行政相对人名称", nz(t.get("xzxdrmc"))),
            ("行政相对人代码", nz(t.get("xzxdrdm"))),
            ("法定代表人", nz(t.get("fddbrxm"))),
            ("处罚机关", nz(t.get("cfjiguan"))),
            ("处罚日期", cjk_date(t.get("cfsxq"))),
        ]
    def date_f(t):
        v = t.get("cfsxq")
        if isinstance(v, (int, float)):
            return ms2date(v)
        return cjk_date(v)
    return conv_generic(
        recs, os.path.join(LIB, "湖南省", "行政处罚公示"), "行政处罚公示", "湖南省",
        "国家税务总局湖南省税务局", "湖南省税务局行政执法信息公示平台（税务行政一般程序处罚结果）",
        HN_XZCF_URL,
        title_f=lambda t: nz(t.get("ajmc")) or (nz(t.get("jdswh")) + "-税务行政处罚"),
        rows_f=rows_f,
        sections_f=lambda t: [("违法事实", nz(t.get("cfsy"))),
                              ("处罚依据", nz(t.get("cfyj"))),
                              ("处罚结果", nz(t.get("cfjg")))],
        date_f=date_f,
        key_f=lambda t: nz(t.get("jdswh")) + "|" + str(t.get("cfsxq") or ""),
        url_f=lambda t: HN_XZCF_URL)


# ---------------------------------------------------------------- 青岛税案通报
def qd_news():
    import taxcase_scrape as tsc
    meta = load_jsonl(os.path.join(TMP, "qd", "news_arts.jsonl"))
    out_dir = os.path.join(LIB, "青岛市", "税案通报")
    os.makedirs(out_dir, exist_ok=True)
    stats = {"keep": 0, "del": 0, "exists": 0, "no_file": 0}
    BAD_RE = re.compile(r"送达公告|催缴|催报|文书公告|招聘|采购|招标")
    CASE_RE = re.compile(r"查处|曝光|虚开|骗税|骗取|偷税|偷逃|逃避缴纳税款|追缴|重大税收违法|失信|少缴|违法")
    for d in meta:
        if BAD_RE.search(d.get("title") or "") or not CASE_RE.search(d.get("title") or ""):
            stats["no_file"] += 1
            continue
        if not d.get("file") or not os.path.exists(d["file"]):
            stats["no_file"] += 1
            continue
        h = open(d["file"], encoding="utf-8").read()
        ex = tsc.extract_detail(h, d["url"], d.get("title") or "", d.get("date") or "")
        title = ex.get("title") or d.get("title") or "未命名"
        pub = ex.get("date") or d.get("date") or ""
        body_md = (ex.get("md") or "").strip()
        if len(re.findall(r"[一-鿿]", body_md)) < 80:
            stats["del"] += 1
            continue
        if pub and pub < DATE_FROM:
            stats["del"] += 1
            continue
        verdict, fl, why = decide("税案通报", "青岛市", body_md)
        if verdict != "KEEP":
            stats["del"] += 1
            continue
        fn = f"{pub or 'nodate'}_{safe_filename(title)[:80]}.md"
        path = os.path.join(out_dir, fn)
        if os.path.exists(path):
            stats["exists"] += 1
            continue
        body = "# " + title + chr(10) + chr(10) + body_md + chr(10)
        fm = make_fm(title, "国家税务总局青岛市税务局", "税案通报", "青岛市",
                     pub, ex.get("source_org") or "青岛市税务局网站",
                     d["url"])
        write_md(path, fm, body)
        stats["keep"] += 1
    print("[税案通报]", stats)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="all",
                    choices=["qd_xzcf", "qd_sswf", "qd_news", "hn_sx", "hn_xzcf", "all"])
    args = ap.parse_args()
    fns = {"qd_xzcf": qd_xzcf, "qd_sswf": qd_sswf, "qd_news": qd_news,
           "hn_sx": hn_sx, "hn_xzcf": hn_xzcf}
    if args.kind == "all":
        for f in fns.values():
            f()
    else:
        fns[args.kind]()


if __name__ == "__main__":
    main()
