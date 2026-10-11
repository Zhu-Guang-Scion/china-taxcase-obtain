# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R7 三省 md 转换器：山西处罚记录(jsonl) + 内蒙古失信详情(html) → lawlibrary
质量门槛：quality_prune.decide() 就地判定，DEL 不入库。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, sys, hashlib
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.normpath(os.path.join(ROOT, "..", "..", "work", "taxcase", "tmp")) \
    if False else os.path.normpath(os.path.join(ROOT, "tmp"))
LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例"))
TODAY = date.today().isoformat()
sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402


def log(m):
    print(f"[{m}]", flush=True)


def safe_fn(title):
    s = re.sub(r'[\/:*?"<>|\r\n\t]', "_", title or "").strip("_ ")
    return s[:60] or "untitled"


def write_md(path, fm, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        for k, v in fm.items():
            v = str(v)
            f.write(f'{k}: "{v}"\n' if not v.startswith("<") else f"{k}: {v}\n")
        f.write("---\n\n")
        f.write(body)


def html2text(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", h,
               flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</p>|</tr>|</div>", "\n", h, flags=re.I)
    h = re.sub(r"</t[dh]>", " | ", h, flags=re.I)
    txt = re.sub(r"<[^>]+>", "", h)
    import html as ihtml
    txt = ihtml.unescape(txt)
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()


def table_pairs(h):
    """[标签,值] 成对表格 → [(label, value)]（跨列拼接值单元格）。"""
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, re.S):
        cells = [re.sub(r"<[^>]+>|\s+|&nbsp;", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        cells = [c for c in cells if c not in ("", "|", ">")]
        if len(cells) < 2:
            continue
        label = cells[0]
        value = "".join(cells[1:]) if len(cells) > 2 else cells[1]
        if any(k in label for k in ["首页", ">", "当前位置", "字号"]) or label.startswith("您的位置"):
            continue
        out.append((label[:40], value[:2000]))
    return out



ANJ_MAP = {
    "虚开增值税专用发票(普通发票)案件": "虚开增值税专用发票或者虚开用于骗取出口退税、抵扣税款的其他发票案件",
    "虚开增值税专用发票（普通发票）案件": "虚开增值税专用发票或者用于骗取出口退税、抵扣税款的其他发票",
    "偷税案件(自然人)": "私自印制、伪造、变造发票，非法制造发票防伪专用品，伪造发票监制章案件",
    "其他-违法情节严重、有较大社会影响": "多种违法类型案件",
    "偷税案件（隐瞒销售收入）": "走逃（失联)",
    "偷税案件": "逃避缴纳税款",
    "逃避追缴欠税案件": "逃避追缴欠税",
    "虚开普通发票案件": "虚开普通发票",
    "骗取出口退税案件": "骗取出口退税",
}


def clean_anj(val):
    m = re.search(r"varanj\s*=\s*'([^']+)'", val)
    if not m:
        return val
    anj = m.group(1)
    return ANJ_MAP.get(anj, anj)

def pairs2body(pairs):
    lines = []
    for lab, val in pairs:
        if not val or val == "，，":
            continue
        if "违法事实" in lab:
            lines.append(f"**主要违法事实**：\n{val}")
        elif lab.startswith("案件性质"):
            lines.append(f"**案件性质**：{clean_anj(val) if 'varanj' in val else val}")
        else:
            lines.append(f"**{lab}**：{val}")
    return "\n\n".join(lines)


# ---------------------------------------------------------- 内蒙古失信
def nmg_md():
    meta_path = os.path.join(TMP, "nmg", "zdaj_meta.jsonl")
    outdir = os.path.join(LIB, "内蒙古自治区", "重大税收违法失信公布")
    if not os.path.exists(meta_path):
        log("nmg meta missing")
        return 0
    n = 0
    stats = {}
    for ln in open(meta_path, encoding="utf-8"):
        try:
            a = json.loads(ln)
        except Exception:
            continue
        fp = a.get("file")
        if not fp or not os.path.exists(fp):
            continue
        h = open(fp, encoding="utf-8").read()
        pairs = table_pairs(h)
        title = ""
        for lab, val in pairs:
            if lab in ("纳税人名称", "失信主体名称"):
                title = val
                break
        if not title:
            title = (a.get("name") or "").split(">")[-1] or "失信主体"
        d = ""
        pdm = re.search(r'<meta name="PubDate" content="(20\d{2}-\d{2}-\d{2})', h)
        if pdm:
            d = pdm.group(1)
        if not d:
            um = re.search(r"/t(20\d{2})(\d{2})(\d{2})_", a["url"])
            if um:
                d = f"{um.group(1)}-{um.group(2)}-{um.group(3)}"
        body = pairs2body(pairs)
        if len(body) < 60:
            continue
        md_body = f"# {title}\n\n{body}\n"
        verdict, fl, why = decide("重大税收违法失信公布", "内蒙古自治区", md_body)
        stats[f"{verdict}:{why}"] = stats.get(f"{verdict}:{why}", 0) + 1
        if verdict == "DEL":
            continue
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{a.get('key', '')[:6]}.md"
        write_md(os.path.join(outdir, fn), {
            "title": title, "来源机关": "国家税务总局内蒙古自治区税务局",
            "栏目": "重大税收违法失信公布", "地区": "内蒙古自治区",
            "发布日期": d, "原文来源": "", "抓取日期": TODAY,
            "原文链接": a["url"]}, md_body)
        n += 1
    log(f"NMG md: keep={n} {stats}")
    return n


# ---------------------------------------------------------- 山西处罚
SX_FIELDS = [("JDSWH", "决定书文号"), ("AJMC", "案件名称"), ("CFLB", "处罚类别"),
             ("CFSY", "处罚事由"), ("CFYJ", "处罚依据"), ("XZXDRMC", "行政相对人名称"),
             ("XZXDRDM", "行政相对人代码（统一社会信用代码）"), ("FDDBRXM", "法定代表人姓名"),
             ("CFJG", "处罚内容"), ("CFSWJG", "处罚机关"), ("CFRQ", "处罚决定日期")]


def sx_md():
    rec_path = os.path.join(TMP, "sx_r7", "xzcf_records.jsonl")
    outdir = os.path.join(LIB, "山西省", "行政处罚公示")
    if not os.path.exists(rec_path):
        log("sx records missing")
        return 0
    seen = set()
    n = 0
    stats = {}
    for ln in open(rec_path, encoding="utf-8"):
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        wh = (rec.get("JDSWH") or "") + "|" + (rec.get("XZXDRDM") or "")
        key = hashlib.md5(wh.encode()).hexdigest()[:10]
        if key in seen:
            continue
        seen.add(key)
        title = rec.get("AJMC") or (rec.get("XZXDRMC") or "处罚公示")
        d = (rec.get("CFRQ") or "").strip()[:10]
        lines = [f"# {title}", ""]
        for k, cn in SX_FIELDS:
            v = (rec.get(k) or "").strip()
            if v and v not in ("，，",):
                lines.append(f"**{cn}**：{v}")
        md_body = "\n".join(lines) + "\n"
        verdict, fl, why = decide("行政处罚公示", "山西省", md_body)
        stats[f"{verdict}:{why}"] = stats.get(f"{verdict}:{why}", 0) + 1
        if verdict == "DEL":
            continue
        orgid = rec.get("_orgid") or "11400"
        link = (f"<https://shanxi.chinatax.gov.cn/xzzfgsptWeb/xzcfweb/swxzybcfjg/"
                f"{orgid}-2662>")
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{key[:6]}.md"
        write_md(os.path.join(outdir, fn), {
            "title": title, "来源机关": "国家税务总局山西省税务局",
            "栏目": "行政处罚公示", "地区": "山西省",
            "发布日期": d, "原文来源": "山西省税务行政执法信息公示平台",
            "抓取日期": TODAY, "原文链接": link}, md_body)
        n += 1
    log(f"SX md: keep={n} {stats}")
    return n




# ---------------------------------------------------------- 河北处罚
HB_FIELDS = [("XZCFJDSWH", "决定书文号"), ("AJMC", "案件名称"), ("CFLB", "处罚类别"),
             ("CFSY", "处罚事由"), ("CFYJ", "处罚依据"), ("NSRMC", "行政相对人名称"),
             ("NSRSBH", "行政相对人代码（统一社会信用代码）"), ("FDDBRXM", "法定代表人姓名"),
             ("CFJG", "处罚内容"), ("CFSWJG", "处罚机关"), ("ZCGCFRQ", "处罚决定日期")]


def hb_md():
    rec_path = os.path.join(TMP, "hb_r7", "penalty_all.jsonl")
    outdir = os.path.join(LIB, "河北省", "行政处罚公示")
    if not os.path.exists(rec_path):
        log("hb records missing")
        return 0
    seen = set()
    n = 0
    stats = {}
    for ln in open(rec_path, encoding="utf-8"):
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        wh = (rec.get("XZCFJDSWH") or "") + "|" + (rec.get("uid") or rec.get("NSRSBH") or "")
        key = hashlib.md5(wh.encode()).hexdigest()[:10]
        if key in seen:
            continue
        seen.add(key)
        title = rec.get("AJMC") or (rec.get("NSRMC") or "处罚公示")
        d = (rec.get("ZCGCFRQ") or "")[:10].replace("/", "-")
        lines = [f"# {title}", ""]
        for k, cn in HB_FIELDS:
            v = (rec.get(k) or "").strip() if isinstance(rec.get(k), str) else rec.get(k)
            if v:
                lines.append(f"**{cn}**：{v}")
        md_body = chr(10).join(lines) + chr(10)
        verdict, fl, why = decide("行政处罚公示", "河北省", md_body)
        stats[f"{verdict}:{why}"] = stats.get(f"{verdict}:{why}", 0) + 1
        if verdict == "DEL":
            continue
        city = rec.get("_city") or ""
        link = "<http://wzyy.hebei.chinatax.gov.cn/LawPublicity/law/adPenalty/taxPenaltyResult>"
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{key[:6]}.md"
        write_md(os.path.join(outdir, fn), {
            "title": title, "来源机关": "国家税务总局河北省税务局",
            "栏目": "行政处罚公示", "地区": "河北省",
            "发布日期": d, "原文来源": "河北省税务执法信息公示平台（" + city + "）",
            "抓取日期": TODAY, "原文链接": link}, md_body)
        n += 1
    log(f"HB md: keep={n} {stats}")
    return n


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", choices=["nmg", "sx", "hb", "all"])
    args = ap.parse_args()
    if args.part in ("nmg", "all"):
        nmg_md()
    if args.part in ("sx", "all"):
        sx_md()
    if args.part in ("hb", "all"):
        hb_md()
