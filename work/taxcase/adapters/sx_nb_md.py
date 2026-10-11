# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
陕西+宁波 离线转 md（HTML → lawlibrary/专题/税务案例/<省>/<栏目>/）
数据：tmp/sx_nb/shixin_meta.jsonl（陕西失信167）、nbsx_*.html（宁波失信）、
      nbnt_*.html（宁波涉税通知）、xzcf_records.jsonl（陕西处罚，若有）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, sys, hashlib
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.normpath(os.path.join(ROOT, "..", "..", "tmp", "sx_nb"))
LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例"))
TODAY = date.today().isoformat()

sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402


def log(m):
    print(f"[{m}]", flush=True)


def safe_fn(title):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", title or "").strip("_ ")
    return s[:60] or "untitled"


DATE_RE = re.compile(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})")


def norm_date(s):
    m = DATE_RE.search(s or "")
    if not m:
        return ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return ""
    return f"{y}-{mo:02d}-{d:02d}"


def zoom_body(h):
    """宁波文章正文容器 #zoom（info-cont）。"""
    m = re.search(r'<div[^>]*id="zoom"[^>]*>(.*)', h, re.S)
    if not m:
        return ""
    seg = m.group(1)
    # 平衡截断到 footer / article-qrcode
    for stop in ['<div class="article-qrcode"', '<div class="footer"',
                 '<div class="article-letter"']:
        j = seg.find(stop)
        if j > 0:
            seg = seg[:j]
    return html2text(seg).strip()


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
        cells = [re.sub(r"<[^>]+>|\s+", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        cells = [c for c in cells if c not in ("", "|", ">")]
        if len(cells) < 2:
            continue
        label = cells[0]
        value = "".join(cells[1:]) if len(cells) > 2 else cells[1]
        # 过滤导航行
        if any(k in label for k in ["首页", ">", "当前位置", "字号"]) or label.startswith("您的位置"):
            continue
        out.append((label[:30], value[:1500]))
    return out


def pairs2body(pairs):
    lines = []
    for lab, val in pairs:
        if not val:
            continue
        # 合并标签行（如"主要违法事实相关法律依据及税务处理处罚情况"）：
        # 值是完整叙述，挂到"主要违法事实"名下（质量门槛按此识别）
        if "主要违法事实" in lab or "违法事实" in lab:
            lines.append(f"**主要违法事实**：\n{val}")
        else:
            lines.append(f"**{lab}**：{val}")
    return "\n\n".join(lines)


def write_md(path, fm, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        for k, v in fm.items():
            f.write(f'{k}: "{v}"\n' if not str(v).startswith("<") else f"{k}: {v}\n")
        f.write("---\n\n")
        f.write(body)


# ---------------------------------------------------------- 陕西失信
def sx_shixin_md():
    meta_path = os.path.join(TMP, "shixin_meta.jsonl")
    outdir = os.path.join(LIB, "陕西省", "重大税收违法失信公布")
    if not os.path.exists(meta_path):
        log("sx shixin meta missing")
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
        # 标签值成对表格 → **标签**：值
        pairs = table_pairs(h)
        title = ""
        for lab, val in pairs:
            if lab in ("纳税人名称", "失信主体名称"):
                title = val
                break
        if not title:
            tm = re.search(r"<title>(.*?)</title>", h, re.S)
            title = (tm.group(1).strip().split(" ")[-1].strip()
                     if tm else "") or a.get("title") or "失信主体"
        d = norm_date(a.get("date") or "") or ""
        if not d:
            um = re.search(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/", a["url"])
            if um:
                d = f"{um.group(1)}-{int(um.group(2)):02d}-{int(um.group(3)):02d}"
        if not d:
            dm = re.search(r"发布时间[：:]\s*(20\d{2}-\d{2}-\d{2})", html2text(h))
            d = dm.group(1) if dm else ""
        body = pairs2body(pairs)
        if len(body) < 60:
            continue
        # 质量门槛
        md_body = f"# {title}\n\n{body}\n"
        verdict, fl, why = decide("重大税收违法失信公布", "陕西省", md_body)
        stats[verdict] = stats.get(verdict, 0) + 1
        if verdict == "DEL":
            continue
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{a.get('key','')[:6]}.md"
        write_md(os.path.join(outdir, fn), {
            "title": title, "来源机关": "国家税务总局陕西省税务局",
            "栏目": "重大税收违法失信公布", "地区": "陕西省",
            "发布日期": d, "原文来源": "", "抓取日期": TODAY,
            "原文链接": a["url"]}, f"# {title}\n\n{body}\n")
        n += 1
    log(f"SX shixin md: keep={n} {stats}")
    return n


# ---------------------------------------------------------- 宁波失信
def nb_shixin_md():
    meta_path = os.path.join(TMP, "nb_shixin_meta.jsonl")
    outdir = os.path.join(LIB, "宁波市", "重大税收违法失信公布")
    if not os.path.exists(meta_path):
        log("nb shixin meta missing")
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
            tm = re.search(r"<title>(.*?)</title>", h, re.S)
            title = (tm.group(1).strip() if tm else "") or a.get("name") or "失信主体"
        d = ""
        pdm = re.search(r'<meta name="PubDate" content="(20\d{2}-\d{2}-\d{2})', h)
        if pdm:
            d = pdm.group(1)
        if not d:
            um = re.search(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/", a["url"])
            if um:
                d = f"{um.group(1)}-{int(um.group(2)):02d}-{int(um.group(3)):02d}"
        if not d:
            dm = re.search(r"发布时间[：:]\s*(20\d{2}-\d{2}-\d{2})", html2text(h))
            d = dm.group(1) if dm else ""
        body = pairs2body(pairs)
        if len(body) < 60:
            continue
        md_body = f"# {title}\n\n{body}\n"
        verdict, fl, why = decide("重大税收违法失信公布", "宁波市", md_body)
        stats[verdict] = stats.get(verdict, 0) + 1
        if verdict == "DEL":
            continue
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{a.get('key','')[:6]}.md"
        write_md(os.path.join(outdir, fn), {
            "title": title, "来源机关": "国家税务总局宁波市税务局",
            "栏目": "重大税收违法失信公布", "地区": "宁波市",
            "发布日期": d, "原文来源": "", "抓取日期": TODAY,
            "原文链接": a["url"]}, md_body)
        n += 1
    log(f"NB shixin md: keep={n} {stats}")
    return n


# ---------------------------------------------------------- 宁波涉税通知
def nb_notice_md():
    meta_path = os.path.join(TMP, "nb_notice_meta.jsonl")
    outdir = os.path.join(LIB, "宁波市", "通知公告涉税公告")
    if not os.path.exists(meta_path):
        log("nb notice meta missing")
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
        title = a.get("title") or ""
        tm = re.search(r"<title>(.*?)</title>", h, re.S)
        if not title and tm:
            title = tm.group(1).strip()
        d = norm_date(a.get("date") or "")
        if not d:
            pdm = re.search(r'<meta name="PubDate" content="(20\d{2}-\d{2}-\d{2})', h)
            if pdm:
                d = pdm.group(1)
        if not d:
            um = re.search(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/", a["url"])
            if um:
                d = f"{um.group(1)}-{int(um.group(2)):02d}-{int(um.group(3)):02d}"
        # 正文：#zoom 容器（宁波 jpaas 文章）
        body = zoom_body(h)
        if len(body) < 80:
            continue
        # 栏目细分：送达公告类
        col = "通知公告涉税公告"
        if "送达" in title:
            col = "文书送达公告"
        md_body = f"# {title}\n\n{body}\n"
        verdict, fl, why = decide(col, "宁波市", md_body)
        stats[col + ":" + verdict] = stats.get(col + ":" + verdict, 0) + 1
        if verdict == "DEL":
            continue
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{a.get('key','')[:6]}.md"
        write_md(os.path.join(outdir if col == "通知公告涉税公告"
                              else os.path.join(LIB, "宁波市", col), fn), {
            "title": title, "来源机关": "国家税务总局宁波市税务局",
            "栏目": col, "地区": "宁波市",
            "发布日期": d, "原文来源": "", "抓取日期": TODAY,
            "原文链接": a["url"]}, md_body)
        n += 1
    log(f"NB notice md: keep={n} {stats}")
    return n


# ---------------------------------------------------------- 陕西处罚
FIELD_MAP = {
    "field_806": "决定书文号", "field_807": "案件名称", "field_808": "处罚类别",
    "field_1450": "处罚事由", "field_1451": "处罚依据", "field_811": "行政相对人名称",
    "field_812": "行政相对人代码（统一社会信用代码）", "field_813": "法定代表人姓名",
    "field_814": "处罚结果", "field_815": "处罚机关", "field_816": "处罚日期",
    "field_817": "处罚决定日期", "field_818": "公示到期日",
}


def sx_xzcf_md():
    rec_path = os.path.join(TMP, "xzcf_records.jsonl")
    outdir = os.path.join(LIB, "陕西省", "行政处罚公示")
    if not os.path.exists(rec_path):
        log("sx xzcf records missing")
        return 0
    seen = set()
    n = 0
    stats = {}
    for ln in open(rec_path, encoding="utf-8"):
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        # 键名适配
        row = {}
        for k, v in rec.items():
            kk = k if k.startswith("field_") else FIELD_MAP.get(k, k)
            row[kk] = v
        wh = row.get("决定书文号") or ""
        key = wh or json.dumps(rec, ensure_ascii=False)[:80]
        if key in seen:
            continue
        seen.add(key)
        title = row.get("案件名称") or (row.get("行政相对人名称") or "处罚公示")
        d = norm_date(str(row.get("处罚决定日期") or row.get("处罚日期") or ""))
        lines = [f"# {title}", ""]
        for cn in ["决定书文号", "案件名称", "处罚类别", "处罚事由", "处罚依据",
                   "行政相对人名称", "行政相对人代码（统一社会信用代码）",
                   "法定代表人姓名", "处罚结果", "处罚机关", "处罚决定日期"]:
            v = row.get(cn)
            if v:
                lines.append(f"**{cn}**：{v}")
        body = "\n".join(lines)
        md_body = body + "\n"
        verdict, fl, why = decide("行政处罚公示", "陕西省", md_body)
        stats[verdict] = stats.get(verdict, 0) + 1
        if verdict == "DEL":
            continue
        fn = f"{d or '0000-00-00'}_{safe_fn(title)}_{hashlib.md5(key.encode()).hexdigest()[:6]}.md"
        write_md(os.path.join(outdir, fn), {
            "title": title, "来源机关": "国家税务总局陕西省税务局",
            "栏目": "行政处罚公示", "地区": "陕西省",
            "发布日期": d, "原文来源": "陕西省税务执法公示平台",
            "抓取日期": TODAY,
            "原文链接": "<http://zfgs.shaanxi.chinatax.gov.cn:88/col/col7/index.html>"},
            md_body)
        n += 1
    log(f"SX xzcf md: keep={n} {stats}")
    return n


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all")
    args = ap.parse_args()
    if args.part in ("sxshixin", "all"):
        sx_shixin_md()
    if args.part in ("nbshixin", "all"):
        nb_shixin_md()
    if args.part in ("nbnotice", "all"):
        nb_notice_md()
    if args.part in ("sxxzcf", "all"):
        sx_xzcf_md()
