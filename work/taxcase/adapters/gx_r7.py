# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""广西 r7：重大税收违法失信主体信息公布栏 全量收割。
接口： GET https://guangxi.chinatax.gov.cn/restSearch
      channelid=290909 & searchword=(NF=YYYY) & orderby=RELEVANCE & page & pageSize=100
行自带全文： ZYWFSS(主要违法事实) + XGFL_CFQK(相关法律处理处罚情况)。
质量门槛： quality_prune.decide 就地判定，DEL 不入库。
断点： progress/guangxi_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from curl_cffi import requests as cr
from quality_prune import decide

API = "https://guangxi.chinatax.gov.cn/restSearch"
REF = "https://guangxi.chinatax.gov.cn/nsfw/sscx/sswfanj/"
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "..", "..", "lawlibrary", "专题", "税务案例",
                                    "广西壮族自治区", "重大税收违法失信公布"))
PROG = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "progress", "guangxi_r7.jsonl"))
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.dirname(PROG), exist_ok=True)

TODAY = "2026-10-11"


def safe_fn(s, maxlen=70):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s).strip("_. ")
    return s[:maxlen] or "untitled"


def fetch(year, page, size=100):
    r = cr.get(API, params={"channelid": "290909", "searchword": f"(NF={year})",
                            "orderby": "RELEVANCE", "page": str(page), "pageSize": str(size)},
               impersonate="chrome124", timeout=200, headers={"Referer": REF})
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}")
    return r.json()


def build_md(d):
    date_raw = (d.get("DOCRELTIME") or d.get("DOCPUBTIME") or "")[:10].replace(".", "-")
    name = (d.get("NSR_NAME") or "").strip()
    title = f"{name}（重大税收违法失信主体）" if name else "未具名失信主体"
    ajxz = d.get("AJXZ") or ""
    body = f"# {title}\n\n"
    body += f"- **纳税人名称**：{name}\n"
    if d.get("NSR_ID"):
        body += f"- **纳税人识别号**：{d['NSR_ID']}\n"
    if d.get("REG_ADDR"):
        body += f"- **注册地址**：{d['REG_ADDR']}\n"
    body += f"- **案件性质**：{ajxz}\n"
    if d.get("ADDR"):
        body += f"- **公示机关/地区**：{d['ADDR']}\n"
    if d.get("FDDBR_NAME"):
        body += f"- **法定代表人**：{d['FDDBR_NAME']}\n"
    body += f"\n## 主要违法事实\n\n{d.get('ZYWFSS','').strip()}\n"
    cf = (d.get("XGFL_CFQK") or "").strip()
    if cf:
        body += f"\n## 相关处理处罚情况\n\n{cf}\n"
    fm = ("---\n"
          f'title: "{safe_fn(title, 80)}"\n'
          '来源机关: "国家税务总局广西壮族自治区税务局"\n'
          '栏目: "重大税收违法失信公布"\n'
          '地区: "广西壮族自治区"\n'
          f"发布日期: {date_raw or TODAY}\n"
          '原文来源: "广西壮族自治区税务局重大税收违法失信主体信息公布栏"\n'
          f"抓取日期: {TODAY}\n"
          f"原文链接: {d.get('DOCPUBURL','')}\n"
          "---\n\n")
    return date_raw, title, fm + body


def main():
    done = set()
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass
    n_ok = n_del = 0
    for year in range(2014, 2027):
        page = 1
        total = None
        while True:
            time.sleep(1.8 + random.uniform(0, 1.2))
            try:
                j = fetch(year, page)
            except Exception as e:
                print(f"Y{year} p{page} ERR {e}", flush=True)
                time.sleep(5)
                try:
                    j = fetch(year, page)
                except Exception as e2:
                    print(f"Y{year} p{page} ERR2 skip {e2}", flush=True)
                    break
            pager = j.get("pager", {})
            total = pager.get("dataCount", 0)
            datas = j.get("datas", []) or []
            if not datas:
                break
            for d in datas:
                key = str(d.get("METADATAID") or d.get("DOCPUBURL"))
                if not key or key in done:
                    continue
                date_raw, title, md = build_md(d)
                verdict, fl, why = decide("重大税收违法失信公布", "广西壮族自治区",
                                          md.split("---\n\n", 1)[-1])
                if verdict == "DEL":
                    n_del += 1
                    with open(PROG, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"key": key, "st": "del", "why": why,
                                            "fl": fl}, ensure_ascii=False) + "\n")
                    done.add(key)
                    continue
                fn = f"{date_raw or TODAY}_{safe_fn(title)}.md"
                p = os.path.join(OUT, fn)
                k = 1
                while os.path.exists(p) and os.path.getsize(p) > 0:
                    # 同名不同主体： 加序号
                    with open(p, encoding="utf-8") as f:
                        if f"原文链接: {d.get('DOCPUBURL','')}" in f.read():
                            p = None
                            break
                    k += 1
                    p = os.path.join(OUT, f"{date_raw or TODAY}_{safe_fn(title)}_{k}.md")
                if p is None:
                    continue
                with open(p, "w", encoding="utf-8") as f:
                    f.write(md)
                n_ok += 1
                done.add(key)
                with open(PROG, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"key": key, "st": "ok", "f": os.path.basename(p)},
                                       ensure_ascii=False) + "\n")
            if page * 100 >= total:
                break
            page += 1
        print(f"year {year}: total={total} done (ok={n_ok} del={n_del})", flush=True)
    print(f"FINISHED ok={n_ok} del={n_del}")


if __name__ == "__main__":
    main()
