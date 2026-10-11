#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""企业会计准则体系批量下载器。
来源: kjs.mof.gov.cn(会计司政策发布/准则实施专题) / fgk.mof.gov.cn(财政部法规库) / czj.sh.gov.cn(上海转载)。
每件: 页面附件原件优先, 否则正文转 docx。
输出: downloads/standards/企业会计准则/*.docx|pdf|doc|rar + lists/standards_企业会计准则.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import gov_download as gd

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(ROOT, "downloads", "standards", "企业会计准则")
LIST_PATH = os.path.join(ROOT, "lists", "standards_企业会计准则.jsonl")
os.makedirs(OUT_DIR, exist_ok=True)

KJS = "http://kjs.mof.gov.cn"
FGK = "http://fgk.mof.gov.cn"

ATT_RE = re.compile(r'href="([^"]+?\.(?:pdf|doc|docx|xls|xlsx|zip|rar|wps))"', re.I)
DOCNO_RE = re.compile(
    r"(财会|财办会|财政部令)\s*[〔\[\(（]\s*(20\d{2})\s*[〕\]\)）]\s*[〔\[]?\s*(\d+)\s*[〕\]]?\s*号")
DOCNO_RE2 = re.compile(r"(财政部令第\s*(\d+)\s*号)")
DATE_RE = re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def fetch(s, url, binary=False, retries=3, verify=True):
    last = None
    for i in range(retries):
        try:
            r = s.get(url, timeout=60, verify=verify)
            if r.status_code != 200:
                raise RuntimeError(f"http {r.status_code}")
            if binary:
                return r.content
            enc = r.apparent_encoding or "utf-8"
            if enc.lower() in ("gb2312", "gbk"):
                enc = "gb18030"
            return r.content.decode(enc, errors="replace")
        except Exception as e:
            last = e
            time.sleep(1 + i)
    raise last


_STYLE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.S | re.I)


def extract_content(html: str) -> str:
    """kjs/mof 页面正文: my_doccontent > my_conboxzw > TRS_Editor > pages_content > generic。"""
    html = _STYLE.sub("", html)
    for marker in ['class="my_doccontent"', "class=my_doccontent", 'class="my_conboxzw"',
                   'class=TRS_Editor', 'class="TRS_Editor"', 'class="pages_content"',
                   'class="trs_editor_view']:
        i = html.find(marker)
        if i >= 0:
            start = html.find(">", i) + 1
            # 平衡 div 深度截取
            depth, pos = 1, start
            limit = min(len(html), start + 400000)
            while depth > 0 and pos < limit:
                no = html.find("<div", pos)
                nc = html.find("</div>", pos)
                if nc < 0:
                    break
                if 0 <= no < nc:
                    depth += 1
                    pos = no + 4
                else:
                    depth -= 1
                    if depth == 0:
                        return html[start:nc]
                    pos = nc + 6
            return html[start:limit]
    return gd.extract_body_generic(html)


def attachments(html: str, page_url: str):
    """返回 [(绝对url, 附件名)]。"""
    out = []
    for m in ATT_RE.finditer(html):
        href = m.group(1)
        name = href.rsplit("/", 1)[-1]
        if href.startswith("./"):
            base = page_url.rsplit("/", 1)[0]
            href = base + "/" + href[2:]
        elif href.startswith("../"):
            base = page_url.rsplit("/", 1)[0]
            while href.startswith("../"):
                base = base.rsplit("/", 1)[0]
                href = href[3:]
            href = base + "/" + href
        elif href.startswith("/"):
            href = re.match(r"(https?://[^/]+)", page_url).group(1) + href
        elif not href.startswith("http"):
            base = page_url.rsplit("/", 1)[0]
            href = base + "/" + href
        out.append((href, name))
    return out


def extract_meta(html, prefer_config_no=None, prefer_config_date=None):
    """文号: 正文区顶部(前600字)优先; 日期: 优先配置值, 否则正文区提取。避免页面页脚污染。"""
    content = extract_content(html)
    ctext = re.sub(r"\s+", "", re.sub(r"<[^>]+>", " ", content))
    doc_no, date = "", ""
    m = DOCNO_RE.search(ctext[:600]) or DOCNO_RE.search(ctext)
    if m:
        doc_no = f"{m.group(1)}〔{m.group(2)}〕{m.group(3)}号"
    else:
        m2 = DOCNO_RE2.search(ctext[:600]) or DOCNO_RE2.search(ctext)
        if m2:
            doc_no = m2.group(0)
    if prefer_config_no:
        doc_no = doc_no or prefer_config_no
    dm = DATE_RE.search(ctext[-3000:]) or DATE_RE.search(ctext)
    if dm:
        date = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    if prefer_config_date:
        date = prefer_config_date or date
    return doc_no, date


def docno_fn(doc_no: str) -> str:
    """文号 -> 文件名片段: 财会〔2014〕14号 -> 财会2014_14号"""
    m = DOCNO_RE.search(doc_no or "")
    if m:
        return f"{m.group(1)}{m.group(2)}_{m.group(3)}号"
    m2 = DOCNO_RE2.search(doc_no or "")
    if m2:
        return m2.group(0)
    return gd.sanitize(doc_no)[:40] if doc_no else ""


def save_binary(s, url, fpath, verify=True):
    data = fetch(s, url, binary=True, verify=verify)
    open(fpath, "wb").write(data)
    return len(data)


def page_to_docx(s, page_url, title, fpath, verify=True, doc_no="", date=""):
    html = fetch(s, page_url, verify=verify)
    content = extract_content(html)
    dn, dt = extract_meta(html, prefer_config_no=doc_no, prefer_config_date=date)
    blocks = gd.body_to_blocks(content)
    if len(blocks) < 2:
        raise RuntimeError(f"正文块过少 {len(blocks)}")
    meta = {"cat": "企业会计准则", "org": "财政部", "date": dt or date,
            "doc_num": dn or doc_no, "url": page_url}
    gd.make_docx(title, blocks, meta, fpath)
    return dn or doc_no, dt or date, os.path.getsize(fpath)


STRUCT_RE = re.compile(r"第[一二三四五六七八九十百千零\d]+\s*[条章节]|总则|一、|施行|为了规范|问[：:]")


def _docx_text(fpath):
    from docx import Document
    d = Document(fpath)
    return "\n".join(p.text for p in d.paragraphs)


def _raw_doc_text(path):
    """OLE/PK/MHTML .doc 统一抽文本用于结构校验。"""
    raw = open(path, "rb").read()
    try:
        import zipfile
        if raw[:2] == b"PK":
            z = zipfile.ZipFile(path)
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", "", xml)
    except Exception:
        pass
    if raw.startswith(b"MIME"):
        import quopri
        import html as hl
        for part in raw.split(b"------=_NextPart"):
            if b"text/html" in part[:400]:
                body = part.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in part else b""
                h = quopri.decodestring(body).decode("utf-8", errors="ignore")
                return hl.unescape(re.sub(r"<[^>]+>", "", h))
    # OLE: utf-16-le / gb18030 混合探测
    for enc in ("utf-16-le", "gb18030"):
        t = raw.decode(enc, errors="ignore")
        if "第" in t or "总则" in t or "准则" in t:
            return t
    return raw.decode("gb18030", errors="ignore")


def verify_file(fpath):
    """返回 (ok, desc)。"""
    if not os.path.exists(fpath):
        return False, "文件不存在"
    size = os.path.getsize(fpath)
    with open(fpath, "rb") as f:
        head = f.read(8)
    if fpath.endswith((".pdf",)):
        if not head.startswith(b"%PDF"):
            return False, "非PDF头"
        return size > 20000, f"{size}B"
    if fpath.endswith((".doc",)):
        if not (head.startswith(b"\xd0\xcf\x11\xe0") or head.startswith(b"PK")
                or raw_str_head(head).startswith("MIME")):
            return False, "非Word文档头"
        if size < 15000:
            return False, f"{size}B 过小"
        t = _raw_doc_text(fpath)
        return bool(STRUCT_RE.search(t)), f"{size}B 结构{'OK' if STRUCT_RE.search(t) else '缺失'}"
    if fpath.endswith((".docx",)):
        try:
            txt = _docx_text(fpath)
        except Exception as e:
            return False, f"docx损坏:{e}"
        return size > 2000 and bool(STRUCT_RE.search(txt)), f"{size}B 结构{'OK' if STRUCT_RE.search(txt) else '缺失'}"
    if fpath.endswith((".rar", ".zip")):
        return head.startswith(b"Rar!") or head.startswith(b"PK"), f"{size}B"
    return size > 2000, f"{size}B"


def raw_str_head(head: bytes) -> str:
    return head.decode("ascii", errors="ignore")


RESULTS = []


def record(item, file, source, doc_no="", date="", note="", ok=True, url=""):
    rec = {"title": item["title"], "doc_no": doc_no or item.get("doc_no", ""),
           "date": date or item.get("date", ""),
           "url": url or item.get("url", ""), "file": file, "source": source}
    note = (note + " " + item.get("note", "")).strip() or item.get("note", "")
    if note:
        rec["note"] = note
    RESULTS.append((ok, rec))
    flag = "OK " if ok else "FAIL"
    print(f"[{flag}] {item['title']} -> {file or '(无文件)'} {note}", flush=True)


def process_page_item(s, item):
    """下载页面类条目: 附件优先(可指定附件序号), 否则正文docx。"""
    url = item["url"]
    fn_base = item["fname"]
    try:
        html = fetch(s, url, verify=item.get("verify", True))
    except Exception as e:
        record(item, "", "页面抓取失败", note=f"{type(e).__name__}: {e}", ok=False)
        return
    doc_no, date = extract_meta(html, prefer_config_no=item.get("doc_no", ""),
                                 prefer_config_date=item.get("date", ""))
    tag = docno_fn(doc_no) or date.replace("-", "") or "无文号"
    atts = attachments(html, url)
    # 附件筛选: 排除 favicon 等
    atts = [a for a in atts if not re.search(r"(favicon|logo)", a[0], re.I)]
    if atts:
        idx = item.get("att_index", 0)
        pick = atts[min(idx, len(atts) - 1)]
        ext = pick[0].rsplit(".", 1)[-1].lower()
        fpath = os.path.join(OUT_DIR, gd.sanitize(f"{fn_base}_{tag}") + "." + ext)
        try:
            n = save_binary(s, pick[0], fpath, verify=item.get("verify", True))
            ok, desc = verify_file(fpath)
            record(item, os.path.basename(fpath), item.get("source", "kjs.mof.gov.cn") + "/附件",
                   doc_no, date, note=desc if not ok else "", ok=ok,
                   url=url)
            return
        except Exception as e:
            print(f"  附件下载失败({e}), 转正文", flush=True)
    # 正文 docx
    fpath = os.path.join(OUT_DIR, gd.sanitize(f"{fn_base}_{tag}") + ".docx")
    try:
        dn, dt, size = page_to_docx(s, url, item["title"], fpath,
                                    verify=item.get("verify", True),
                                    doc_no=item.get("doc_no", ""), date=item.get("date", ""))
        ok, desc = verify_file(fpath)
        record(item, os.path.basename(fpath), item.get("source", "kjs.mof.gov.cn") + "/正文HTML",
               dn or doc_no, dt or date, note=desc if not ok else "", ok=ok, url=url)
    except Exception as e:
        record(item, "", "正文转换失败", note=f"{type(e).__name__}: {e}", ok=False, url=url)


def process_fgk_item(s, item):
    """fgk 条目: 取原始 .doc 下载; 失败则 law_html 正文转 docx。"""
    info_id = item["fgk_id"]
    page_url = f"{FGK}/ui/src/views/law_html/{info_id}.html"
    fn_base = item["fname"]
    try:
        r = s.get(f"{FGK}/file/f/get", params={"infoId": info_id, "fileType": "90"}, timeout=30)
        files = (r.json().get("data") or [])
    except Exception as e:
        files = []
        print(f"  fgk文件接口失败: {e}", flush=True)
    if files:
        f = files[0]
        furl = f["serverIp"] + f["fileUrl"]
        ext = f.get("extension") or "doc"
        doc_no, date = item.get("doc_no", ""), item.get("date", "")
        tag = docno_fn(doc_no) or date.replace("-", "")
        fpath = os.path.join(OUT_DIR, gd.sanitize(f"{fn_base}_{tag}") + "." + ext)
        try:
            save_binary(s, furl, fpath)
            ok, desc = verify_file(fpath)
            record(item, os.path.basename(fpath), "fgk.mof.gov.cn(财政部法规库)/原始doc",
                   doc_no, date, note=desc if not ok else "", ok=ok, url=page_url)
            return
        except Exception as e:
            print(f"  fgk doc下载失败({e}), 转页面正文", flush=True)
    # 回退 law_html 正文
    process_page_item(s, {**item, "url": page_url, "source": "fgk.mof.gov.cn(财政部法规库)"})


def process_local_item(item, src_path, doc_no, date, source, note=""):
    """本地文件(RAR解包出的原件)复制入库。"""
    fn_base = item["fname"]
    tag = docno_fn(doc_no) or date.replace("-", "")
    ext = src_path.rsplit(".", 1)[-1].lower()
    fpath = os.path.join(OUT_DIR, gd.sanitize(f"{fn_base}_{tag}") + "." + ext)
    with open(src_path, "rb") as fi, open(fpath, "wb") as fo:
        fo.write(fi.read())
    ok, desc = verify_file(fpath)
    record(item, os.path.basename(fpath), source, doc_no, date,
           note=(note + " " + desc).strip() if not ok else note, ok=ok,
           url=item.get("url", ""))


# ============ 目标清单 ============
K = "http://kjs.mof.gov.cn/zhengcefabu/"
TOPIC = "http://kjs.mof.gov.cn/zt/kjzzss/kuaijizhunzeshishi/"

# 2006版(财会〔2006〕3号) - 从官方RAR解包PDF取原件
CAS2006 = {
    1: "存货", 3: "投资性房地产", 4: "固定资产", 5: "生物资产", 6: "无形资产",
    8: "资产减值", 10: "企业年金基金", 11: "股份支付", 13: "或有事项",
    15: "建造合同", 17: "借款费用", 18: "所得税", 19: "外币折算", 20: "企业合并",
    26: "再保险合同", 27: "石油天然气开采", 28: "会计政策、会计估计变更和差错更正",
    29: "资产负债表日后事项", 31: "现金流量表", 32: "中期财务报告",
    34: "每股收益", 35: "分部报告", 36: "关联方披露", 38: "首次执行企业会计准则",
}

# 修订/新增版 - kjs 政策发布通知页
CAS_REVISED = [
    (2, "长期股权投资", "财会〔2014〕14号", "2014-02-17", K + "201403/t20140319_1057127.htm"),
    (7, "非货币性资产交换", "财会〔2019〕8号", "2019-05-09", K + "201905/t20190516_3258929.htm"),
    (9, "职工薪酬", "财会〔2014〕8号", "2014-01-27", K + "201401/t20140129_1040561.htm"),
    (12, "债务重组", "财会〔2019〕9号", "2019-05-16", K + "201905/t20190529_3267525.htm"),
    (14, "收入", "财会〔2017〕22号", "2017-07-05", K + "201707/t20170719_2653110.htm"),
    (16, "政府补助", "财会〔2017〕15号", "2017-05-10", K + "201705/t20170525_2608690.htm"),
    (21, "租赁", "财会〔2018〕35号", "2018-12-07", K + "201812/t20181213_3092629.htm"),
    (22, "金融工具确认和计量", "财会〔2017〕7号", "2017-03-31", K + "201704/t20170406_2575699.htm"),
    (23, "金融资产转移", "财会〔2017〕8号", "2017-03-31", K + "201704/t20170406_2575702.htm"),
    (24, "套期会计", "财会〔2017〕9号", "2017-03-31", K + "201704/t20170406_2575705.htm"),
    (33, "合并财务报表", "财会〔2014〕10号", "2014-02-17", K + "201402/t20140220_1045206.htm"),
    (37, "金融工具列报", "财会〔2017〕14号", "2017-05-02", K + "201705/t20170515_2600144.htm"),
    (39, "公允价值计量", "财会〔2014〕6号", "2014-01-26", K + "201401/t20140128_1040392.htm"),
    (40, "合营安排", "财会〔2014〕11号", "2014-02-17", K + "201402/t20140220_1045209.htm"),
    (41, "在其他主体中权益的披露", "财会〔2014〕16号", "2014-03-14", K + "201403/t20140327_1060353.htm"),
    (42, "持有待售的非流动资产处置组和终止经营", "财会〔2017〕13号", "2017-04-28", K + "201705/t20170516_2601445.htm"),
]

INTERPRETATIONS = [
    (1, K + "200805/t20080522_33804.htm", "财会〔2007〕14号", "2007-11-16"),
    (2, K + "200809/t20080912_74645.htm", "财会〔2008〕11号", "2008-08-07"),
    (3, K + "200906/t20090625_172281.htm", "财会〔2009〕8号", "2009-06-11"),
    (4, K + "201008/t20100809_332092.htm", "财会〔2010〕15号", "2010-07-14"),
    (5, K + "201211/t20121122_701308.htm", "财会〔2012〕19号", "2012-11-05"),
    (6, K + "201401/t20140123_1038629.htm", "财会〔2014〕1号", "2014-01-17"),
    (7, K + "201511/t20151113_1559056.htm", "财会〔2015〕19号", "2015-11-04"),
    (8, K + "201601/t20160104_1643346.htm", "财会〔2015〕23号", "2015-12-16"),
    (9, K + "201706/t20170621_2628433.htm", "财会〔2017〕16号", "2017-06-12"),
    (10, K + "201706/t20170621_2628435.htm", "财会〔2017〕17号", "2017-06-12"),
    (11, K + "201706/t20170621_2628437.htm", "财会〔2017〕18号", "2017-06-12"),
    (12, K + "201706/t20170621_2628439.htm", "财会〔2017〕19号", "2017-06-12"),
    (13, K + "201912/t20191213_3441493.htm", "财会〔2019〕21号", "2019-12-10"),
    (14, K + "202102/t20210202_3653110.htm", "财会〔2021〕1号", "2021-01-26"),
    (15, K + "202112/t20211231_3779983.htm", "财会〔2021〕35号", "2021-12-30"),
    (16, "http://www.mof.gov.cn/gkml/caizhengwengao/wg2022/wg202212/202304/t20230407_3877737.htm", "财会〔2022〕31号", "2022-11-30"),
    (17, K + "202311/t20231109_3915491.htm", "财会〔2023〕21号", "2023-10-25"),
    (18, K + "202412/t20241223_3950344.htm", "财会〔2024〕24号", "2024-12-23"),
    (19, K + "202512/t20251218_3979556.htm", "财会〔2025〕32号", "2025-12-18"),
    (20, K + "202606/t20260615_3991686.htm", "财会〔2026〕7号", "2026-06-15"),
]

OTHERS = [
    dict(title="企业会计准则——基本准则（2014年修订）", fname="企业会计准则_基本准则",
         kind="fgk", fgk_id="83958", doc_no="财政部令第76号", date="2014-07-23"),
    dict(title="企业会计准则第25号——保险合同", fname="企业会计准则_第25号保险合同",
         kind="page", url=TOPIC + "202202/t20220224_3790240.htm", doc_no="财会〔2020〕20号",
         date="2020-12-19",
         source="kjs.mof.gov.cn/会计准则实施专题",
         note="另存财政部法规库导出的通知原文doc（MHTML格式）"),
    dict(title="企业会计制度", fname="企业会计制度",
         kind="fgk", fgk_id="84860", doc_no="财会〔2000〕25号", date="2000-12-29"),
    dict(title="小企业会计准则", fname="企业会计准则_小企业会计准则",
         kind="page", url=K + "201111/t20111107_605525.htm", doc_no="财会〔2011〕17号",
         date="2011-10-18", att_index=0),
    dict(title="小企业执行《小企业会计准则》有关问题衔接规定", fname="企业会计准则_小企业执行衔接规定",
         kind="page", url=K + "201211/t20121113_693817.htm", doc_no="财会〔2012〕20号",
         date="2012-10-29"),
    dict(title="增值税会计处理规定", fname="企业会计准则_增值税会计处理规定",
         kind="page", url=K + "201612/t20161212_2479869.htm", doc_no="财会〔2016〕22号",
         date="2016-12-03"),
    dict(title="企业会计准则第30号——财务报表列报（2026年修订）", fname="企业会计准则_第30号财务报表列报",
         kind="page", url=K + "202608/t20260805_3994927.htm", doc_no="财会〔2026〕11号",
         date="2026-08-05"),
]

SUPPLEMENTS = [
    ("关于修订印发2019年度一般企业财务报表格式的通知", K + "201905/t20190510_3254992.htm", "财会〔2019〕6号", "2019-04-30"),
    ("关于修订印发合并财务报表格式（2019版）的通知", K + "201909/t20190927_3394088.htm", "财会〔2019〕17号", "2019-09-19"),
    ("关于印发《金融负债与权益工具的区分及相关会计处理规定》的通知", K + "201403/t20140321_1057952.htm", "财会〔2014〕13号", "2014-03-17"),
    ("关于印发《永续债相关会计处理的规定》的通知", K + "201901/t20190130_3138955.htm", "财会〔2019〕2号", "2019-01-18"),
    ("关于印发《碳排放权交易有关会计处理暂行规定》的通知", K + "201912/t20191223_3448268.htm", "财会〔2019〕22号", "2019-12-16"),
    ("关于印发《企业数据资源相关会计处理暂行规定》的通知", K + "202308/t20230821_3903354.htm", "财会〔2023〕11号", "2023-08-01"),
    ("关于印发《企业破产清算有关会计处理规定》的通知", K + "201612/t20161227_2505655.htm", "财会〔2016〕23号", "2016-12-20"),
]


def main():
    s = gd.make_session()
    t38 = os.path.join(OUT_DIR, "_附件解包_2006年38项准则")
    tzn = os.path.join(OUT_DIR, "_附件解包_应用指南2006")

    # 清理上次运行的过时文件（保留 RAR 与解包目录）
    keep_prefix = ("企业会计准则_2006年38项具体准则", "企业会计准则_应用指南_财会2006_18号.rar",
                   "企业会计准则_应用指南附录")
    for f in os.listdir(OUT_DIR):
        p = os.path.join(OUT_DIR, f)
        if os.path.isfile(p) and not f.startswith(keep_prefix):
            os.remove(p)

    # 1. 2006版具体准则 (RAR解包PDF原件)
    rar_note = {15: "2006版；已被《企业会计准则第14号——收入》(2017年修订)吸收代替",
                26: "2006版；已被《企业会计准则第25号——保险合同》(财会〔2020〕20号)废止"}
    for num, name in sorted(CAS2006.items()):
        src = os.path.join(t38, f"企业会计准则第{num}号——{name}.pdf")
        if not os.path.exists(src):
            record(dict(title=f"企业会计准则第{num}号——{name}（2006）"), "", "RAR解包缺失", ok=False,
                   note=f"解包目录无此文件")
            continue
        process_local_item(
            dict(title=f"企业会计准则第{num}号——{name}（2006年版）",
                 fname=f"企业会计准则_第{num}号{name}",
                 url=K + "200805/t20080522_33653.htm"),
            src, "财会〔2006〕3号", "2006-02-15",
            "kjs.mof.gov.cn/官方RAR附件解包", note=rar_note.get(num, ""))

    # 2. 修订/新增版通知页
    for num, name, docno, date, url in CAS_REVISED:
        item = dict(title=f"企业会计准则第{num}号——{name}（现行版）",
                    fname=f"企业会计准则_第{num}号{name}", kind="page",
                    url=url, doc_no=docno, date=date)
        process_page_item(s, item)

    # 3. 解释第1~20号
    for num, url, docno, date in INTERPRETATIONS:
        item = dict(title=f"企业会计准则解释第{num}号",
                    fname=f"企业会计准则解释第{num}号", kind="page",
                    url=url, doc_no=docno, date=date)
        process_page_item(s, item)

    # 4. 其他核心件
    for item in OTHERS:
        if item["kind"] == "fgk":
            process_fgk_item(s, item)
        else:
            process_page_item(s, item)

    # 4b. CAS25 保险合同: 另存财政部法规库导出的通知原文 doc
    try:
        r = s.get(f"{FGK}/file/f/get", params={"infoId": "85329", "fileType": "90"}, timeout=30)
        f0 = (r.json().get("data") or [None])[0]
        if f0:
            furl = f0["serverIp"] + f0["fileUrl"]
            fp = os.path.join(OUT_DIR, "企业会计准则_第25号保险合同_财会2020_20号_通知原文.doc")
            save_binary(s, furl, fp)
            print(f"[OK ] (附加) CAS25通知原文doc {os.path.getsize(fp)}B", flush=True)
    except Exception as e:
        print(f"[FAIL] (附加) CAS25通知原文doc: {e}", flush=True)

    # 5. 38项合订RAR + 应用指南 (已下载的RAR登记)
    for fn, title, docno, date, url, src_note in [
        ("企业会计准则_2006年38项具体准则_财会2006_3号.rar", "企业会计准则第1号——存货等38项具体准则（2006年合订附件）",
         "财会〔2006〕3号", "2006-02-15", K + "200805/t20080522_33653.htm", "kjs.mof.gov.cn/附件"),
        ("企业会计准则_应用指南_财会2006_18号.rar", "企业会计准则——应用指南（含32项指南及附录：会计科目和主要账务处理）",
         "财会〔2006〕18号", "2006-10-30",
         "https://czj.sh.gov.cn/zys_8908/zcfg_8983/zcfb_8985/hj_9035/cwhjjbzdgf/20061201/0017-156907.html",
         "上海市财政局转载/附件（财政部官网未提供电子原文）"),
    ]:
        fpath = os.path.join(OUT_DIR, fn)
        ok, desc = verify_file(fpath)
        record(dict(title=title, url=url, doc_no=docno, date=date),
               fn if ok else "", src_note, docno, date, note=desc if not ok else "（含全部解包文件于_附件解包_*目录）",
               ok=ok)

    # 6. 应用指南附录单列
    appdx = os.path.join(tzn, "附录-会计科目和主要账务处理.pdf")
    if os.path.exists(appdx):
        process_local_item(
            dict(title="《企业会计准则——应用指南》附录——会计科目和主要账务处理",
                 fname="企业会计准则_应用指南附录_会计科目和主要账务处理",
                 url="https://czj.sh.gov.cn/zys_8908/zcfg_8983/zcfb_8985/hj_9035/cwhjjbzdgf/20061201/0017-156907.html"),
            appdx, "财会〔2006〕18号", "2006-10-30", "上海市财政局转载/附件解包")

    # 7. 补充相关会计处理规定
    for title, url, docno, date in SUPPLEMENTS:
        item = dict(title=title, fname="企业会计准则_相关规定_" + title.replace("关于印发《", "").replace("》的通知", "").replace("关于修订印发", ""),
                    kind="page", url=url, doc_no=docno, date=date)
        process_page_item(s, item)

    # 8. 未能取得的件 (记录note)
    record(dict(title="《企业会计准则第14号——收入》应用指南(2018)、《企业会计准则第21号——租赁》应用指南(2019)、《企业会计准则第22/23/24/37号》金融工具相关应用指南(2018)等单行本"),
           "", "未找到", note="官方未发布电子原文，仅中国财政经济出版社出版纸质书；财政部官网及法规库均无电子版", ok=False, url="")

    # 写清单
    with open(LIST_PATH, "w", encoding="utf-8") as f:
        for ok, rec in RESULTS:
            if not ok and not rec.get("file"):
                rec = dict(rec)
                rec.setdefault("url", "")
                rec["note"] = (rec.get("note", "") + " 未取得").strip()
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    n_ok = sum(1 for ok, _ in RESULTS if ok)
    print(f"\n=== 完成: {n_ok}/{len(RESULTS)} 成功 ===")
    print(f"清单: {LIST_PATH}")


if __name__ == "__main__":
    main()
