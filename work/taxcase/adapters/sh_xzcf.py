# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
上海税务 —— 行政处罚公示（一般程序处罚结果）抓取器
==================================================
数据源：上海市税务局行政执法信息公示平台（WebLogic .pfv 接口）
  入口页: https://shanghai.chinatax.gov.cn/newxbwz/gspt/xzcf/xzcf.jsp
  数据接口: POST /newxbwz/gspt/xzcf/YbcxcfCtrl-ybxzcfcx.pfv
    form: ajmc= &xzcfsx=一般程序处罚 &xzxdrmc= &xzxdrdm= &cfjg=
          &gsptyzm= &yzmflag=1 &curPage=N
  关键点：yzmflag=1 可绕过验证码（客户端逻辑，服务端放行）
  分页：10条/页，返回 pageCount/totalRecords
用法：
  python sh_xzcf.py --sample          # 小样（第1页）
  python sh_xzcf.py                   # 正式抓取（进度断点续抓）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random
from datetime import date

from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from taxcase_scrape import safe_filename  # noqa: E402

BASE = "https://shanghai.chinatax.gov.cn"
ENTRY = BASE + "/newxbwz/gspt/xzcf/xzcf.jsp"
API = BASE + "/newxbwz/gspt/xzcf/YbcxcfCtrl-ybxzcfcx.pfv"
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT_DIR = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "上海市", "行政处罚公示")
PROG = os.path.join(ROOT, "progress", "sh_xzcf.jsonl")
DATE_FROM = "2023-01-01"
DELAY = 2.5

_session = None


def get_session():
    global _session
    if _session is None:
        _session = cr.Session(impersonate="chrome124")
        _session.get(ENTRY, timeout=40)
        time.sleep(DELAY + random.uniform(0, 1))
    return _session


def fetch_page(page):
    s = get_session()
    time.sleep(DELAY + random.uniform(0, 1.0))
    data = {"ajmc": "", "xzcfsx": "一般程序处罚", "xzxdrmc": "", "xzxdrdm": "",
            "cfjg": "", "gsptyzm": "", "yzmflag": "1", "curPage": str(page)}
    r = s.post(API, data=data, timeout=40,
               headers={"Referer": ENTRY, "X-Requested-With": "XMLHttpRequest"})
    if r.status_code != 200 or not r.text.strip():
        return None
    return json.loads(r.text)


def nz(v):
    """null/空 → ''"""
    return "" if v is None else str(v).strip()


def record_to_md(it):
    title = nz(it.get("ajMc")) or (nz(it.get("frMc")) + "税务行政处罚")
    d = nz(it.get("zccfrq")) or nz(it.get("fbrq")) or ""
    lines = ["# " + title, ""]
    rows = [
        ("行政处罚决定书文号", nz(it.get("xzcfswh"))),
        ("处罚类别", nz(it.get("cflb"))),
        ("被处罚对象", nz(it.get("frMc"))),
        ("统一社会信用代码/纳税人识别号", nz(it.get("tym"))),
        ("法定代表人（负责人）", nz(it.get("frXm")) or nz(it.get("zrrXm"))),
        ("主体性质", nz(it.get("kzzttxt"))),
        ("作出处罚机关", nz(it.get("zccfdw"))),
        ("作出处罚日期", nz(it.get("zccfrq"))),
        ("公示日期", nz(it.get("fbrq"))),
    ]
    for k, v in rows:
        if v:
            lines.append(f"- **{k}**：{v}")
    lines += ["", "## 违法事实", "", nz(it.get("cfsy")) or "（未公示）", "",
              "## 处罚依据", "", nz(it.get("cfyj")) or "（未公示）", "",
              "## 处罚结果", "", nz(it.get("cfyjjg")) or "（未公示）"]
    amt = nz(it.get("yjfkje"))
    if amt:
        lines.append(f"\n应缴罚款金额：{amt} 元")
    url = (ENTRY + "?xzcfswh=" + nz(it.get("xzcfswh"))).strip("?xzcfswh=")
    fm = ("---\n"
          f"title: \"{title.replace(chr(34), '')}\"\n"
          "来源机关: \"国家税务总局上海市税务局\"\n"
          "栏目: \"行政处罚公示\"\n"
          "地区: \"上海市\"\n"
          f"发布日期: {d or 'nodate'}\n"
          "原文来源: \"上海市税务局行政执法信息公示平台\"\n"
          f"抓取日期: {date.today().isoformat()}\n"
          f"原文链接: {ENTRY}\n"
          "---\n\n")
    return title, d, fm + "\n".join(lines) + "\n"


def load_done():
    done = set()
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("ok"):
                        done.add(rec["key"])
                except json.JSONDecodeError:
                    pass
    return done


def run(sample=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    done = load_done()
    j = fetch_page(1)
    if not j or "pageData" not in j:
        print("[sh_xzcf] first page failed"); return
    pages = int(j.get("pageCount", 1))
    total = int(j.get("totalRecords", 0))
    max_pages = pages if not sample else 1
    print(f"[sh_xzcf] totalRecords={total} pages={pages} sample={sample}")
    n_new = n_old = 0
    with open(PROG, "a", encoding="utf-8") as prog:
        for pg in range(1, max_pages + 1):
            if pg > 1:
                j = fetch_page(pg)
                if not j:
                    print(f"[sh_xzcf] page {pg} failed"); break
            for it in j.get("pageData", []):
                key = nz(it.get("xzcfswh")) + "|" + nz(it.get("frMc"))
                d = nz(it.get("zccfrq")) or nz(it.get("fbrq"))
                if d and d < DATE_FROM:
                    n_old += 1
                    continue
                if key in done:
                    continue
                title, dd, md = record_to_md(it)
                if len(md) < 150:
                    continue
                fname = safe_filename((dd or "nodate") + "_" + title) + ".md"
                with open(os.path.join(OUT_DIR, fname), "w",
                          encoding="utf-8", newline="\n") as f:
                    f.write(md)
                prog.write(json.dumps({"key": key, "ok": True, "file": fname,
                                       "title": title, "date": dd},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_new += 1
            if pg % 10 == 0:
                print(f"[sh_xzcf] page {pg}/{pages} new={n_new} old={n_old}")
    print(f"[sh_xzcf] DONE new={n_new} old={n_old}")


if __name__ == "__main__":
    run(sample="--sample" in sys.argv)
