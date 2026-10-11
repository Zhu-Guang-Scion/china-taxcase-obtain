#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""中注协执业准则体系批量下载：准则原文 + 应用指南 + 问题解答 + 新系列。
下载 PDF 到 downloads/standards/执业准则/，写 lists/standards_执业准则.jsonl。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import glob
import html as H
import json
import os
import random
import re
import sys
import time
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(__file__))
import gov_download as gd

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
OUT_DIR = os.path.join(REPO, "work", "downloads", "standards", "执业准则")
LIST_OUT = os.path.join(REPO, "work", "lists", "standards_执业准则.jsonl")
ENUM = os.path.join(REPO, "work", "lists", "cicpa_enum_raw.jsonl")
LOGS = os.path.join(REPO, "work", "logs")

TZGG = "https://www.cicpa.org.cn/xxfb/tzgg/"
ZYZZ = "https://www.cicpa.org.cn/ztzl1/Professional_standards/xxzztx/zyzz/"

NOTICES = {
    # notice path (relative to tzgg/) -> (category, publish_date, note)
    "202304/t20230410_64066.html": ("应用指南", "2023-04-10", "关于印发《<审计准则第1101号>应用指南》等34项应用指南的通知（会协〔2023〕19号）"),
    "202302/t20230207_63923.html": ("应用指南", "2023-02-07", "关于印发《<审计准则第1211号>应用指南》等两项应用指南的通知"),
    "202201/t20220120_63335.html": ("应用指南", "2022-01-20", "关于印发《<鉴证业务基本准则>应用指南》等15项应用指南的通知"),
    "202112/t20211221_63266.html": ("应用指南", "2021-12-21", "关于印发《<审计准则第1601号>应用指南》等三项应用指南的通知"),
    "202111/t20211102_63018.html": ("应用指南", "2021-11-02", "关于印发《<质量管理准则第5101号>应用指南》等三项应用指南的通知"),
    "202401/t20240129_64670.html": ("问题解答", "2024-01-29", "关于印发《审计准则问题解答第17号——商誉减值的审计》的通知"),
    "202501/t20250123_65228.html": ("问题解答", "2025-01-23", "关于印发《问题解答第18号》《问题解答第19号》的通知"),
    "202601/t20260127_65792.html": ("可持续信息鉴证业务准则", "2026-01-27", "财政部关于印发《可持续信息鉴证业务准则第6101号——基本准则（试行）》的通知"),
}

# 未下载但登记说明的条目（超出执业准则体系范围等）
NOTE_ONLY = [
    {"title": "中国注册会计师独立性准则第1号——财务报表审计和审阅业务对独立性的要求（2025年1月发布）",
     "url": "https://www.cicpa.org.cn/xxfb/tzgg/202409/t20240918_65047.html",
     "note": "中注协网站归入『职业道德规范』栏目，属职业道德准则体系而非执业准则体系，按任务范围跳过；其应用指南通知 https://www.cicpa.org.cn/xxfb/tzgg/202602/t20260213_65821.html"},
    {"title": "中国注册会计师职业道德守则（2020年12月修订）",
     "url": "https://www.cicpa.org.cn/ztzl1/Professional_standards/xxzztx/zyddsz/",
     "note": "职业道德守则不属执业准则体系，按任务范围跳过"},
]

YEAR_RE = re.compile(r"[（(](\d{4})\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*(?:修订|发布|施行)[）)]")
NO_RE = re.compile(r"第\s*(\d{4})\s*号")


def short_name(title: str) -> str:
    """取 —— 之后的名称做短名。"""
    parts = re.split(r"——|─|—", title)
    name = parts[1] if len(parts) > 1 else title
    name = re.sub(r"[《》〈〉\s]", "", name)
    name = re.sub(r"[（(].*?[）)]", "", name)
    return name[:16] or "正文"


def series_of(title: str):
    if "审计准则" in title:
        return "审计准则"
    if "审阅准则" in title:
        return "审阅准则"
    if "其他鉴证业务准则" in title:
        return "其他鉴证业务准则"
    if "相关服务准则" in title:
        return "相关服务准则"
    if "质量管理准则" in title:
        return "质量管理准则"
    if "鉴证业务基本准则" in title:
        return "鉴证业务基本准则"
    if "可持续信息鉴证业务准则" in title:
        return "可持续信息鉴证业务准则"
    return "其他"


def build_tasks():
    tasks = []
    # 1) 准则原文（zyzz 各子栏目直链 PDF）
    for line in open(ENUM, encoding="utf-8"):
        r = json.loads(line)
        t = r["title"]
        if r["section_key"] == "wtjd":
            continue  # 问题解答另行处理
        ym = YEAR_RE.search(t)
        year = ym.group(1) if ym else ""
        ser = series_of(t)
        m = NO_RE.search(t)
        no = f"第{m.group(1)}号" if m else ""
        if ser == "鉴证业务基本准则":
            no = ""
        base = f"{ser}{no}{short_name(t)}" if no or ser == "鉴证业务基本准则" else ser + short_name(t)
        fname = gd.sanitize(f"执业准则_{base}_{year}.pdf") if year else gd.sanitize(f"执业准则_{base}.pdf")
        tasks.append({
            "cat": "准则", "series": ser, "no": no, "title": t,
            "doc_no": "", "date": year, "url": r["url"], "file": fname,
            "source": r["list_page"], "note": ""})

    # 2) 通知附件：应用指南 / 问题解答17-19 / 可持续6101
    for f, (cat, date, note) in NOTICES.items():
        fname_html = f.split("/")[-1]
        p = os.path.join(LOGS, f"notice_{fname_html}")
        h = open(p, encoding="utf-8").read()
        year = date[:4]
        # 逐个 <a href=pdf> 提取完整内文标题
        atts = {}
        for m in re.finditer(r'<a[^>]+href="([^"]+\.(?:pdf|zip))"[^>]*>(.*?)</a>', h, re.S | re.I):
            u, inner = m.group(1), m.group(2)
            t = H.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            t = re.sub(r"\s+", "", t)
            if not t or re.fullmatch(r"\d{1,2}[.．。]?", t):
                continue
            atts.setdefault(u, t)
        for u, t in atts.items():
            absu = urljoin(TZGG + f, u)
            if u.endswith(".zip"):
                tasks.append({"cat": cat, "series": "打包", "no": "", "title": t,
                              "doc_no": "", "date": date, "url": absu, "file": "",
                              "source": TZGG + f, "note": "23项准则打包zip，单项PDF已另行收集，不下载"})
                continue
            ser = series_of(t)
            m = NO_RE.search(t)
            no = f"第{m.group(1)}号" if m else ""
            if cat == "应用指南":
                base = f"应用指南_{ser}{no}" if no else f"应用指南_{ser}"
                fname = gd.sanitize(f"执业准则_{base}_{year}.pdf")
            elif cat == "问题解答":
                qm = re.search(r"问题解答第\s*(\d+)\s*号", t)
                qno = qm.group(1) if qm else ""
                qn = re.sub(r"[《》\s]", "", re.split(r"——", t)[1])[:12] if "——" in t else ""
                fname = gd.sanitize(f"执业准则_问题解答第{qno}号{qn}_{year}.pdf")
            else:
                fname = gd.sanitize(f"执业准则_{ser}{no}{short_name(t)}_{year}.pdf")
            tasks.append({
                "cat": cat, "series": ser, "no": no, "title": t,
                "doc_no": "", "date": date, "url": absu, "file": fname,
                "source": TZGG + f, "note": note})

    # 3) 问题解答 1-16 直链（wtjd 栏目）
    for line in open(ENUM, encoding="utf-8"):
        r = json.loads(line)
        if r["section_key"] != "wtjd":
            continue
        t = r["title"]
        if not r["url"].endswith(".pdf"):
            continue  # 17/18/19 已由通知附件覆盖
        ym = YEAR_RE.search(t)
        year = ym.group(1) if ym else ""
        qm = re.search(r"问题解答第\s*(\d+)\s*号", t)
        qno = qm.group(1) if qm else ""
        qn = re.sub(r"[《》\s]", "", re.split(r"——", t)[1])[:12] if "——" in t else ""
        fname = gd.sanitize(f"执业准则_问题解答第{qno}号{qn}_{year}.pdf") if year else \
            gd.sanitize(f"执业准则_问题解答第{qno}号{qn}.pdf")
        tasks.append({
            "cat": "问题解答", "series": "问题解答", "no": f"解答第{qno}号", "title": t,
            "doc_no": "", "date": year, "url": r["url"], "file": fname,
            "source": r["list_page"], "note": ""})
    return tasks


def download(tasks):
    s = gd.make_session()
    ok = fail = 0
    for t in tasks:
        if not t["file"]:
            continue
        fp = os.path.join(OUT_DIR, t["file"])
        if os.path.exists(fp) and os.path.getsize(fp) > 10000:
            t["status"] = "ok"
            ok += 1
            continue
        done = False
        for attempt in range(4):
            try:
                r = s.get(t["url"], timeout=90)
                if r.status_code != 200:
                    raise RuntimeError(f"http {r.status_code}")
                ct = r.headers.get("Content-Type", "")
                if b"%PDF" not in r.content[:1024] and "pdf" not in ct.lower():
                    raise RuntimeError(f"not pdf ct={ct} head={r.content[:60]!r}")
                if len(r.content) < 8000:
                    raise RuntimeError(f"too small {len(r.content)}")
                with open(fp, "wb") as f:
                    f.write(r.content)
                t["status"] = "ok"
                t["bytes"] = len(r.content)
                done = True
                ok += 1
                break
            except Exception as e:
                t["error"] = f"{type(e).__name__}: {e}"
                time.sleep(1.5 * (attempt + 1) + random.random())
        if not done:
            t["status"] = "fail"
            fail += 1
        print(f"[{t['status']}] {t['file']} ({t.get('bytes','')})" +
              (f" ERR={t.get('error','')}" if not done else ""), flush=True)
        time.sleep(0.5 + random.random() * 0.5)
    print(f"downloaded ok={ok} fail={fail}")
    return tasks


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tasks = build_tasks()
    print(f"total tasks: {len(tasks)}")
    tasks = download(tasks)
    with open(LIST_OUT, "w", encoding="utf-8") as f:
        for t in tasks:
            rec = {
                "title": t["title"], "doc_no": t["doc_no"], "date": t["date"],
                "url": t["url"], "file": t["file"], "source": t["source"],
                "cat": t["cat"], "series": t["series"], "no": t["no"],
                "status": t.get("status", ""), "note": t.get("note", ""),
            }
            if t.get("error"):
                rec["error"] = t["error"]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        for n in NOTE_ONLY:
            f.write(json.dumps({"title": n["title"], "doc_no": "", "date": "",
                                "url": n["url"], "file": "", "source": "cicpa.org.cn",
                                "cat": "范围外", "series": "", "no": "",
                                "status": "skip", "note": n["note"]},
                               ensure_ascii=False) + "\n")
    # 汇总
    from collections import Counter
    c = Counter((t["cat"], t.get("status", "")) for t in tasks)
    for k, v in sorted(c.items()):
        print(k, v)


if __name__ == "__main__":
    main()
