#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""政府会计准则及非营利/行业会计制度 批量下载器（财政部官网/会计司）。

用法: python std_gov_acct.py [keys...]   # 无参数=全部
产物: downloads/standards/政府及行业会计制度/<文件> + lists/standards_政府及行业会计制度.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import html as htmllib
import json
import os
import random
import re
import sys
import time
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gov_download as gd
from gov_download import sanitize, make_session, extract_body, extract_body_generic, body_to_blocks, make_docx, _STYLE_SCRIPT_RE

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_DIR = os.path.join(ROOT, "downloads", "standards", "政府及行业会计制度")
LIST_PATH = os.path.join(ROOT, "lists", "standards_政府及行业会计制度.jsonl")
PROG_PATH = os.path.join(ROOT, "lists", "standards_dl_progress_政府及行业会计制度.jsonl")
os.makedirs(OUT_DIR, exist_ok=True)

KJS = "http://kjs.mof.gov.cn"
ZF = "http://kjs.mof.gov.cn/zhengcefabu/"

# ---- 目标清单 ---------------------------------------------------------------
T = []
def add(key, fname, title, url, note="", source="财政部会计司", date=""):
    T.append(dict(key=key, fname=fname, title=title, url=url, note=note,
                  source=source, date=date))

# A. 政府会计准则
add("basic", "政府会计准则_基本准则_财政部令第78号", "政府会计准则——基本准则（财政部令第78号）",
    ZF + "201511/t20151110_1553267.htm", date="2015-11-10")
add("gas14", "政府会计准则_第1至4号存货投资固定资产无形资产_财会〔2016〕12号",
    "财政部关于印发《政府会计准则第1号——存货》等4项具体准则的通知（财会〔2016〕12号）",
    ZF + "201607/t20160714_2357356.htm", date="2016-07-14")
add("gas3guide", "政府会计准则_第3号固定资产应用指南", "财政部关于印发《政府会计准则第3号——固定资产》应用指南的通知",
    ZF + "201702/t20170228_2543859.htm", date="2017-02-28")
add("gas5", "政府会计准则_第5号公共基础设施", "财政部关于印发《政府会计准则第5号——公共基础设施》的通知",
    ZF + "201704/t20170425_2586955.htm", date="2017-04-25")
add("gas6", "政府会计准则_第6号政府储备物资", "财政部关于印发《政府会计准则第6号——政府储备物资》的通知",
    ZF + "201708/t20170803_2665602.htm", date="2017-08-03")
add("gas7", "政府会计准则_第7号会计调整", "财政部关于印发《政府会计准则第7号——会计调整》的通知",
    ZF + "201810/t20181031_3058858.htm", date="2018-10-31")
add("gas8", "政府会计准则_第8号负债", "财政部关于印发《政府会计准则第8号——负债》的通知",
    ZF + "201811/t20181115_3069973.htm", date="2018-11-15")
add("gas9", "政府会计准则_第9号财务报表编制和列报", "财政部关于印发《政府会计准则第9号——财务报表编制和列报》的通知",
    ZF + "201812/t20181229_3111340.htm", date="2018-12-29")
add("gas10", "政府会计准则_第10号政府和社会资本合作项目合同_财会〔2019〕23号",
    "财政部关于印发《政府会计准则第10号——政府和社会资本合作项目合同》的通知（财会〔2019〕23号）",
    "https://www.mof.gov.cn/zcsjtsgb/gfxwj/201912/t20191217_3583723.htm",
    note="有资料显示财政部令第114号（2024-01，第十四批废止目录）将其废止，官方页面未见效力标注，存疑收录",
    source="财政部官网", date="2019-12-17")
add("gas11", "政府会计准则_第11号文物资源及应用指南",
    "财政部关于印发《政府会计准则第11号——文物资源》及其应用指南的通知",
    ZF + "202311/t20231107_3914974.htm", date="2023-11-07")

# B. 政府会计准则制度解释 1-7
_expl = [
    ("1", ZF + "201907/t20190723_3305846.htm", "2019-07-23"),
    ("2", ZF + "201912/t20191225_3449679.htm", "2019-12-25"),
    ("3", "http://kjs.mof.gov.cn/gongzuodongtai/202010/t20201023_3609731.htm", "2020-10-23"),
    ("4", ZF + "202112/t20211229_3779124.htm", "2021-12-29"),
    ("5", ZF + "202209/t20220928_3843245.htm", "2022-09-28"),
    ("6", ZF + "202310/t20231030_3913646.htm", "2023-10-30"),
    ("7", ZF + "202401/t20240126_3927362.htm", "2024-01-26"),
]
for n, u, d in _expl:
    add(f"expl{n}", f"政府会计准则_制度解释第{n}号", f"财政部关于印发《政府会计准则制度解释第{n}号》的通知",
        u, date=d)

# C. 政府会计制度
add("gasys", "政府会计制度_行政事业单位会计科目和报表_财会〔2017〕25号",
    "财政部关于印发《政府会计制度——行政事业单位会计科目和报表》的通知（财会〔2017〕25号）",
    ZF + "201711/t20171109_2746877.htm", date="2017-11-09")
add("gasys_link", "政府会计制度_与行政事业单位会计制度衔接规定",
    "财政部关于印发《政府会计制度——行政事业单位会计科目和报表》与《行政单位会计制度》《事业单位会计制度》有关衔接问题处理规定的通知",
    ZF + "201802/t20180208_2810424.htm", date="2018-02-08")

# D. 行业补充规定/衔接规定
_supp = [
    ("sup_hosp", "政府会计制度_医院补充规定和衔接规定", "财政部关于印发医院执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201808/t20180831_3003935.htm", "2018-08-31"),
    ("sup_phc", "政府会计制度_基层医疗卫生机构补充规定和衔接规定", "财政部关于印发基层医疗卫生机构执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201809/t20180904_3006282.htm", "2018-09-04"),
    ("sup_univ", "政府会计制度_高等学校补充规定和衔接规定", "财政部关于印发高等学校执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201808/t20180816_2988842.htm", "2018-08-16"),
    ("sup_school", "政府会计制度_中小学校补充规定和衔接规定", "财政部关于印发中小学校执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201808/t20180817_2989842.htm", "2018-08-17"),
    ("sup_sci", "政府会计制度_科学事业单位补充规定和衔接规定", "财政部关于印发科学事业单位执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201808/t20180824_2997110.htm", "2018-08-24"),
    ("sup_geo", "政府会计制度_地质勘查事业单位衔接规定", "财政部关于印发地质勘查事业单位执行《政府会计制度——行政事业单位会计科目和报表》的衔接规定的通知", ZF + "201807/t20180725_2972244.htm", "2018-07-25"),
    ("sup_map", "政府会计制度_测绘事业单位衔接规定", "财政部关于印发测绘事业单位执行《政府会计制度——行政事业单位会计科目和报表》的衔接规定的通知", ZF + "201807/t20180725_2972233.htm", "2018-07-25"),
    ("sup_forest", "政府会计制度_国有林场和苗圃补充规定和衔接规定", "财政部关于印发国有林场和苗圃执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201807/t20180717_2962673.htm", "2018-07-17"),
    ("sup_lottery", "政府会计制度_彩票机构补充规定和衔接规定", "财政部关于印发彩票机构执行《政府会计制度——行政事业单位会计科目和报表》的补充规定和衔接规定的通知", ZF + "201809/t20180904_3006286.htm", "2018-09-04"),
]
for k, f, t, u, d in _supp:
    add(k, f, t, u, date=d)

# E. 非营利/行业会计制度
add("npo_new", "会计制度_民间非营利组织会计制度_2025年修订",
    "财政部关于印发《民间非营利组织会计制度》的通知（2025年发布，2026年1月1日施行）",
    ZF + "202501/t20250103_3951055.htm", date="2025-01-03")
add("npo_new_link", "会计制度_民间非营利组织新旧衔接规定_2025",
    "财政部关于印发《民间非营利组织新旧会计制度有关衔接问题的处理规定》的通知",
    ZF + "202504/t20250424_3962660.htm", date="2025-04-24")
add("npo_old", "会计制度_民间非营利组织会计制度_财会〔2004〕7号_已废止",
    "财政部关于印发《民间非营利组织会计制度》的通知（财会〔2004〕7号，已被2025年修订版替代）",
    "http://www.mof.gov.cn/gp/xxgkml/hjs/200807/t20080704_2501187.htm",
    note="历史版本，2026-01-01起被修订版替代", source="财政部官网", date="2004-08-18")
add("rural_new", "会计制度_农村集体经济组织会计制度_财会〔2023〕14号",
    "财政部关于印发《农村集体经济组织会计制度》的通知（财会〔2023〕14号）",
    ZF + "202309/t20230922_3908544.htm", date="2023-09-22")
add("rural_new_link", "会计制度_农村集体经济组织新旧衔接规定_2023",
    "财政部关于印发《农村集体经济组织新旧会计制度有关衔接问题的处理规定》的通知",
    ZF + "202311/t20231101_3914192.htm", date="2023-11-01")
add("rural_old", "会计制度_村集体经济组织会计制度_财会〔2004〕12号_已废止",
    "财政部关于印发《村集体经济组织会计制度》的通知（财会〔2004〕12号，已被财会〔2023〕14号修订替代）",
    "http://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/2004zcfb/200805/t20080519_20888.htm",
    note="历史版本，2024-01-01起被《农村集体经济组织会计制度》替代", source="财政部官网", date="2004-09-30")
add("coop_new", "会计制度_农民专业合作社会计制度_2022",
    "财政部关于印发《农民专业合作社会计制度》的通知（2023年1月1日施行）",
    ZF + "202201/t20220114_3782667.htm", date="2022-01-14")
add("coop_new_link", "会计制度_农民专业合作社新旧衔接规定_2022",
    "财政部关于印发《农民专业合作社新旧会计制度有关衔接问题的处理规定》的通知",
    ZF + "202201/t20220118_3783065.htm", date="2022-01-18")
add("coop_old", "会计制度_农民专业合作社财务会计制度试行_财会〔2007〕15号_已废止",
    "财政部关于印发《农民专业合作社财务会计制度（试行）》的通知（财会〔2007〕15号，已被2022年《农民专业合作社会计制度》替代）",
    "http://www.mof.gov.cn/zhengwuxinxi/zhengcefabu/2007zcfb/200805/t20080519_29083.htm",
    note="历史版本，2023-01-01起被《农民专业合作社会计制度》替代", source="财政部官网", date="2007-12-20")
add("union", "会计制度_工会会计制度_2021",
    "财政部关于印发《工会会计制度》的通知（2022年1月1日施行）",
    ZF + "202104/t20210421_3689673.htm", date="2021-04-22")
add("union_link", "会计制度_工会新旧衔接规定_2021",
    "财政部关于印发《工会新旧会计制度有关衔接问题的处理规定》的通知",
    ZF + "202107/t20210706_3731544.htm", date="2021-07-07")
add("ssf", "会计制度_社会保险基金会计制度_2017",
    "财政部关于印发《社会保险基金会计制度》的通知",
    ZF + "201712/t20171214_2776576.htm", date="2017-12-14")
add("ssf_link", "会计制度_社会保险基金新旧衔接规定_2017",
    "财政部关于印发《新旧社会保险基金会计制度有关衔接问题的处理规定》的通知",
    ZF + "201712/t20171214_2776577.htm", date="2017-12-14")
add("ssf_supp", "会计制度_社会保险基金会计制度补充规定_2026",
    "财政部关于印发《〈社会保险基金会计制度〉补充规定》的通知",
    ZF + "202601/t20260112_3981685.htm", date="2026-01-13")
add("lottery_old", "会计制度_彩票机构会计制度_2014",
    "财政部关于印发《彩票机构会计制度》的通知",
    ZF + "201401/t20140106_1033016.htm", date="2014-01-06")
add("lottery_old_link", "会计制度_彩票机构新旧衔接规定_2014",
    "财政部关于印发《彩票机构新旧会计制度有关衔接问题的处理规定》的通知",
    ZF + "201401/t20140128_1040262.htm", date="2014-01-28")
add("road_fund", "会计制度_道路交通事故社会救助基金会计核算办法_2022",
    "财政部关于印发《道路交通事故社会救助基金会计核算办法》的通知",
    ZF + "202206/t20220622_3819920.htm", date="2022-06-23")

# ---- 提取器 -----------------------------------------------------------------
_DOCNO_RE = re.compile(r"(财会|财办会)[〔\[（(]\d{4}[〕\]）)]\d+号|财政部令第\d+号")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def extract_trs(html_text: str) -> str:
    """提取 <div ... TRS_Editor ...> 或 my_doccontent 容器（kjs 与 www 两代模板通用），保留内部 HTML。"""
    html_text = _STYLE_SCRIPT_RE.sub("", html_text)
    m = re.search(r'<div[^>]*TRS_Editor[^>]*>', html_text)
    if not m:
        m = re.search(r'<div[^>]*my_doccontent[^>]*>', html_text)
    if not m:
        return ""
    start = m.end()
    depth, pos = 1, start
    while depth > 0 and pos < len(html_text):
        no = html_text.find("<div", pos)
        nc = html_text.find("</div>", pos)
        if nc < 0:
            break
        if 0 <= no < nc:
            depth += 1
            pos = no + 4
        else:
            depth -= 1
            if depth == 0:
                return html_text[start:nc]
            pos = nc + 6
    return html_text[start:pos] if depth >= 0 else ""


def get_docno(text: str) -> str:
    # 去空白后再匹配（文号常被 span 拆分/夹空格），并优先财会文号
    squeezed = re.sub(r"[\s　]+", "", text)
    m = re.search(r"(?:财会|财办会)[〔\[（(]\d{4}[〕\]）)]\d+号", squeezed)
    if not m:
        m = re.search(r"财政部令第\d+号", squeezed)
    if not m:
        return ""
    s = m.group(0)
    return re.sub(r"[()\[\]]", lambda c: {"(": "〔", ")": "〕", "[": "〔", "]": "〕"}[c.group(0)], s)


def fetch(s, url, timeout=40):
    r = s.get(url, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"http {r.status_code}")
    enc = r.apparent_encoding or "utf-8"
    if enc and enc.lower() in ("iso-8859-1", "ascii", "windows-1254"):
        enc = "utf-8"
    return r.content.decode(enc, errors="replace")


ATT_RE = re.compile(r'href="([^"]+?\.(?:pdf|doc|docx|xls|xlsx|wps|et|zip|rar))"', re.I)


def find_attachments(html_text, base_url):
    """返回 [(绝对url, 链接文字)]，去重。"""
    out, seen = [], set()
    for m in ATT_RE.finditer(html_text):
        href = m.group(1)
        if href.startswith("javascript") or href.startswith("#"):
            continue
        absu = urljoin(base_url, href)
        if absu in seen:
            continue
        seen.add(absu)
        # 链接文字
        seg = html_text[m.end():m.end() + 300]
        tm = re.search(r">([^<>]{1,80})<", seg)
        label = tm.group(1).strip() if tm else ""
        out.append((absu, label))
    return out


def progress_load():
    d = {}
    if os.path.exists(PROG_PATH):
        with open(PROG_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        r = json.loads(line)
                        d[r["key"]] = r
                    except Exception:
                        pass
    return d


def process(item, s):
    key = item["key"]
    base = sanitize(item["fname"])
    html_path = os.path.join(OUT_DIR, base + ".html")
    docx_path = os.path.join(OUT_DIR, base + ".docx")
    files = []

    html_text = fetch(s, item["url"])
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_text)

    # 附件下载
    atts = find_attachments(html_text, item["url"])
    att_files = []
    for i, (au, label) in enumerate(atts, 1):
        ext = os.path.splitext(au)[1].lower()
        apath = os.path.join(OUT_DIR, f"{base}_附件{i}{ext}")
        okatt = False
        for attempt in range(3):
            try:
                rr = s.get(au, timeout=120)
                if rr.status_code == 200 and len(rr.content) > 2000:
                    with open(apath, "wb") as f:
                        f.write(rr.content)
                    att_files.append(os.path.basename(apath))
                    okatt = True
                    break
                raise RuntimeError(f"att http {rr.status_code} len={len(rr.content)}")
            except Exception as e:
                time.sleep(1.5 * (attempt + 1))
        if not okatt:
            print(f"    附件失败 {au}")
        time.sleep(0.5 + random.random() * 0.5)
    files.extend(att_files)

    # 正文
    body = extract_trs(html_text) or extract_body(html_text) or extract_body_generic(html_text)
    blocks = body_to_blocks(body) if body else []
    plain = re.sub(r"<[^>]+>", " ", body or "")
    plain = htmllib.unescape(re.sub(r"\s+", " ", plain))
    docno = get_docno(plain) or get_docno(html_text)

    if len(blocks) < 2:
        note_blocks = [("p", t) for t in [
            "（正文未能从页面提取，完整内容见附件原件）",
            f"来源：{item['url']}",
        ] if t]
        if att_files:
            note_blocks.insert(1, ("p", "附件：" + "、".join(att_files)))
        blocks = note_blocks or [("p", item["title"])]

    meta = {"cat": "政府及行业会计制度", "org": "财政部", "date": item["date"],
            "doc_num": docno, "url": item["url"]}
    make_docx(item["title"], blocks, meta, docx_path)
    if os.path.getsize(docx_path) < 1500:
        raise RuntimeError("docx 过小")
    files.append(os.path.basename(docx_path))

    return {"key": key, "title": item["title"], "doc_no": docno, "date": item["date"],
            "url": item["url"], "file": files[0] if files else "", "files": files,
            "source": item["source"], "note": item["note"]}


def main():
    wanted = set(sys.argv[1:])
    items = [it for it in T if not wanted or it["key"] in wanted]
    prog = progress_load()
    results = []
    for it in items:
        prev = prog.get(it["key"])
        if prev and prev.get("ok"):
            rec0 = prev.get("record", {})
            if any(os.path.exists(os.path.join(OUT_DIR, fn)) for fn in rec0.get("files", [rec0.get("file", "")]) if fn):
                results.append(rec0)
                print(f"[skip] {it['key']}")
                continue
        ok, rec, err = False, None, ""
        for attempt in range(3):
            try:
                rec = process(it, s_sessions[0])
                ok = True
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                time.sleep(1.5 * (attempt + 1) + random.random())
        if ok:
            results.append(rec)
            with open(PROG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": it["key"], "ok": True, "record": rec}, ensure_ascii=False) + "\n")
            print(f"[ok]   {it['key']} {rec['doc_no']} files={rec['files']}")
        else:
            with open(PROG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": it["key"], "ok": False, "error": err}, ensure_ascii=False) + "\n")
            print(f"[FAIL] {it['key']} {err}")
        time.sleep(0.5 + random.random() * 0.5)

    print(f"\n完成 {len(results)}/{len(items)}")


s_sessions = [make_session()]

if __name__ == "__main__":
    main()
