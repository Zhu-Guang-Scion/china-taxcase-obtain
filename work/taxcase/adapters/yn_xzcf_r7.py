# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""云南 r7（补充）：税务行政普通程序处罚结果（/pub/info/topic 服务端渲染表）。
入口： https://yunnan.chinatax.gov.cn/pub/info/topic?id=7add1dde...&pageNumber=N
列： 决定书文号|案件名称|处罚类别|处罚事由|处罚依据|相对人名称|相对人代码|法定代表人|处罚结果|处罚机关|处罚日期
量控： 241 页约 3,100 条，按省量控收前 115 页（~1,475 条，2024-10→2026-10）。
断点： progress/yunnan_xzcf_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from curl_cffi import requests as cr
from bs4 import BeautifulSoup
from quality_prune import decide

URL_T = ("https://yunnan.chinatax.gov.cn/pub/info/topic?"
         "id=7add1dde1f5145c38116951262909832&parentId=c22386b90f4b45fb8614d53c4e635ede"
         "&department=15300000000&wfxwmc=&nsrmc=&nsrsbh=&swjgmc=&pageNumber={pn}")
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "..", "..", "lawlibrary", "专题", "税务案例",
                                    "云南省", "行政处罚公示"))
PROG = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "progress", "yunnan_xzcf_r7.jsonl"))
os.makedirs(OUT, exist_ok=True)
TODAY = "2026-10-11"
H = {"Referer": "https://yunnan.chinatax.gov.cn/pub/info?id=c22386b90f4b45fb8614d53c4e635ede&department=15300000000"}
COLS = ["决定书文号", "案件名称", "处罚类别", "处罚事由", "处罚依据", "行政相对人名称",
        "行政相对人代码", "法定代表人姓名", "处罚结果", "处罚机关", "处罚日期"]
MAX_PAGES = 115


def safe_fn(s, maxlen=70):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s).strip("_. ")
    return s[:maxlen] or "untitled"


def fetch(pn):
    r = cr.get(URL_T.format(pn=pn), impersonate="chrome124", timeout=200, headers=H)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}")
    return r.content.decode("utf-8", errors="replace")


def parse_rows(html):
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != len(COLS):
            continue
        cells = [c.get_text(" ", strip=True) for c in tds]
        if cells[0] == COLS[0] or not cells[5]:
            continue
        rows.append(dict(zip(COLS, cells)))
    return rows


def build(d):
    title = d["案件名称"] or d["行政相对人名称"]
    date = (d.get("处罚日期") or "")[:10]
    body = f"# {title}\n\n"
    body += f"- **行政相对人（纳税人名称）**：{d['行政相对人名称']}\n"
    body += f"- **统一社会信用代码（纳税人识别号）**：{d['行政相对人代码']}\n"
    if d.get("法定代表人姓名"):
        body += f"- **法定代表人**：{d['法定代表人姓名']}\n"
    body += f"- **处罚类别**：{d['处罚类别']}\n"
    body += f"- **决定书文号**：{d['决定书文号']}\n"
    if d.get("处罚机关"):
        body += f"- **处罚机关**：{d['处罚机关']}\n"
    body += f"- **处罚日期**：{date}\n"
    body += f"\n## 违法事实及处理处罚情况\n\n"
    body += f"处罚事由：{d['处罚事由']}\n\n"
    body += f"处罚依据：{d['处罚依据']}\n\n"
    body += f"处罚结果：{d['处罚结果']}\n"
    fm = ("---\n"
          f'title: "{safe_fn(title, 80)}"\n'
          '来源机关: "国家税务总局云南省税务局"\n'
          '栏目: "行政处罚公示"\n'
          '地区: "云南省"\n'
          f"发布日期: {date or TODAY}\n"
          '原文来源: "云南省税务局行政执法信息公示平台（税务行政普通程序处罚结果）"\n'
          f"抓取日期: {TODAY}\n"
          f"原文链接: https://yunnan.chinatax.gov.cn/pub/info/topic?id=7add1dde1f5145c38116951262909832"
          f"&parentId=c22386b90f4b45fb8614d53c4e635ede&department=15300000000\n"
          "---\n\n")
    return date, title, fm + body


def main():
    done = set()
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass
    n_ok = n_del = n_err = 0
    for pn in range(1, MAX_PAGES + 1):
        time.sleep(1.8 + random.uniform(0, 1.0))
        try:
            html = fetch(pn)
        except Exception as e:
            print(f"p{pn} ERR {e}", flush=True)
            time.sleep(5)
            try:
                html = fetch(pn)
            except Exception as e2:
                print(f"p{pn} ERR2 skip {e2}", flush=True)
                continue
        rows = parse_rows(html)
        if not rows:
            print(f"p{pn}: 0 rows (stop)", flush=True)
            break
        for d in rows:
            key = f"{d['决定书文号']}|{d['行政相对人代码']}|{d['处罚日期']}"
            if key in done:
                continue
            date, title, md = build(d)
            verdict, fl, why = decide("行政处罚公示", "云南省", md.split("---\n\n", 1)[-1])
            if verdict == "DEL":
                n_del += 1
                with open(PROG, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"key": key, "st": "del", "why": why, "fl": fl},
                                       ensure_ascii=False) + "\n")
                done.add(key)
                continue
            fn = f"{date or TODAY}_{safe_fn(title)}.md"
            p = os.path.join(OUT, fn)
            k = 1
            while os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    if f"决定书文号**：{d['决定书文号']}" in f.read() and d["决定书文号"]:
                        p = None
                        break
                k += 1
                p = os.path.join(OUT, f"{date or TODAY}_{safe_fn(title)}_{k}.md")
            if p is None:
                continue
            with open(p, "w", encoding="utf-8") as f:
                f.write(md)
            n_ok += 1
            done.add(key)
            with open(PROG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "st": "ok", "f": os.path.basename(p)},
                                   ensure_ascii=False) + "\n")
        print(f"page {pn}: rows={len(rows)} ok={n_ok} del={n_del}", flush=True)
    print(f"FINISHED ok={n_ok} del={n_del} err={n_err}")


if __name__ == "__main__":
    main()
