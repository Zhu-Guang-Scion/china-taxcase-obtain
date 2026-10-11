# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""贵州 r7（补充）：行政处罚结果公示（双公示平台 swxzybcxcf 渠道，channelId=5793970）。
同 /irs/front/list API。字段（本渠道映射）：
  f_2022118981169 相对人 / f_2022118439324 证件号 / f_2022118461091 违法事实
  f_2022118992009 处罚依据 / f_2022118615143 罚款 / f_2022118237203 文书字轨
  f_2022118305177 法定代表人 / f_202211845 主管税务机关 / f_2022118888238 决定日期
质量门槛强制（事实<30 汉字 DEL 不入库）。
断点： progress/guizhou_xzcf_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from curl_cffi import requests as cr
from quality_prune import decide

API = "https://guizhou.chinatax.gov.cn/irs/front/list"
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "..", "..", "lawlibrary", "专题", "税务案例",
                                    "贵州省", "行政处罚公示"))
PROG = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "progress", "guizhou_xzcf_r7.jsonl"))
os.makedirs(OUT, exist_ok=True)
TODAY = "2026-10-11"
H = {"Referer": "https://guizhou.chinatax.gov.cn/xzzfxxgspts/gzsswj/xzcf/swxzybcxcf/",
     "Content-Type": "application/json;charset=UTF-8",
     "Origin": "https://guizhou.chinatax.gov.cn"}


def safe_fn(s, maxlen=70):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s).strip("_. ")
    return s[:maxlen] or "untitled"


def clean(s):
    return re.sub(r"<[^>]+>|\s+", " ", s or "").strip()


def fetch(pageNo, pageSize=100):
    body = {
        "pageNo": pageNo, "pageSize": pageSize, "tenantId": 71,
        "tableName": "t_17e6b2c59ad", "searchFields": [],
        "sorts": [{"sortField": "save_time", "sortOrder": "DESC"}],
        "customFilter": {"operator": "or", "properties": [
            {"property": "f_202211853800", "operator": "eq", "value": "5793970"}]},
        "channelId": "5793970", "isPage": True,
    }
    r = cr.post(API, data=json.dumps(body), impersonate="chrome124", timeout=200, headers=H)
    j = r.json()
    if not j.get("success"):
        raise RuntimeError(j.get("msg"))
    return j["data"]


def build(d):
    rel = clean(d.get("f_2022118981169")) or "未具名相对人"
    typ = clean(d.get("f_2022118164183") or d.get("f_2022118876022"))
    title = clean(d.get("f_2022118977430")) or f"{rel}-{typ}" or rel
    date = clean(d.get("f_2022118888238"))[:10] or (d.get("save_time") or "")[:10]
    fact = clean(d.get("f_2022118461091"))
    body = f"# {title}\n\n"
    body += f"- **相对人（纳税人名称）**：{rel}\n"
    zj = clean(d.get("f_2022118439324"))
    if zj:
        body += f"- **社会信用代码（纳税人识别号）**：{zj}\n"
    if typ:
        body += f"- **违法类型**：{typ}\n"
    ws = clean(d.get("f_2022118237203"))
    if ws:
        body += f"- **处罚文书字轨**：{ws}\n"
    jg = clean(d.get("f_202211845"))
    if jg:
        body += f"- **处罚机关**：{jg}\n"
    fddbr = clean(d.get("f_2022118305177"))
    if fddbr and fddbr != rel:
        body += f"- **法定代表人**：{fddbr}\n"
    body += f"\n## 违法事实\n\n{fact}\n"
    yj = clean(d.get("f_2022118992009"))
    fk = clean(d.get("f_2022118615143"))
    if yj or fk:
        body += "\n## 处罚依据及结果\n\n"
        if yj:
            body += f"处罚依据：{yj}\n\n"
        if fk:
            body += f"应缴罚款合计：{fk} 元\n"
    fm = ("---\n"
          f'title: "{safe_fn(title, 80)}"\n'
          '来源机关: "国家税务总局贵州省税务局"\n'
          '栏目: "行政处罚公示"\n'
          '地区: "贵州省"\n'
          f"发布日期: {date or TODAY}\n"
          '原文来源: "贵州省税务局行政执法信息公示平台（行政处罚结果公示）"\n'
          f"抓取日期: {TODAY}\n"
          f"原文链接: {d.get('doc_pub_url', '')}\n"
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
    n_ok = n_del = 0
    pageNo = 1
    total = None
    while True:
        time.sleep(1.8 + random.uniform(0, 1.0))
        try:
            data = fetch(pageNo)
        except Exception as e:
            print(f"p{pageNo} ERR {e}", flush=True)
            time.sleep(5)
            try:
                data = fetch(pageNo)
            except Exception as e2:
                print(f"p{pageNo} ERR2 stop {e2}", flush=True)
                break
        total = data["pager"]["total"]
        lst = data.get("list") or []
        if not lst:
            break
        for d in lst:
            key = str(d.get("rec_id") or d.get("doc_pub_url"))
            if not key or key in done:
                continue
            date, title, md = build(d)
            verdict, fl, why = decide("行政处罚公示", "贵州省", md.split("---\n\n", 1)[-1])
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
                    if f"原文链接: {d.get('doc_pub_url','')}" in f.read():
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
        print(f"page {pageNo}/{(total + 99) // 100} total={total} ok={n_ok} del={n_del}", flush=True)
        if pageNo * 100 >= total:
            break
        pageNo += 1
    print(f"FINISHED ok={n_ok} del={n_del}")


if __name__ == "__main__":
    main()
