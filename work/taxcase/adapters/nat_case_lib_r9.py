# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R9 课程与书籍线 · 国家税务总局官网「海外税收案例库」专栏采集
入口：https://www.chinatax.gov.cn/chinatax/c102448/ssalk.html
（面包屑：税收服务"一带一路"倡议专题 > 海外税收案例库；江苏局 col9652 为其镜像，22/74）
合规性质：税务总局官网主动公开发布的官方案例库（含案例简介/处理步骤/分析），完全公开免费。
每篇结构：关键词 / 一、案例简介 / 二、…（争点、步骤、结果、启示），正文 .article-content。
用法：python adapters/nat_case_lib_r9.py
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, io, json, time, random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup
from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国",
                   "实务课程与书籍", "总局·海外税收案例库")
PROG = os.path.join(HERE, "..", "progress", "courses_books_r9.jsonl")
INDEX = "https://www.chinatax.gov.cn/chinatax/c102448/ssalk.html"
TODAY = "2026-10-11"


def log_rec(rec):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_done():
    done = set()
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line).get("url", ""))
                except Exception:
                    pass
    return done


def write_md(title, date, body, url):
    taxes, types, ctry = [], [], []
    if re.search(r"常设机构", body): types.append("常设机构认定")
    if re.search(r"反避税|一般反避税|GAAR", body): types.append("反避税/特别纳税调整")
    if re.search(r"转让定价|独立交易原则|关联交易", body): types.append("转让定价")
    if re.search(r"税收协定|协定待遇", body): types.append("税收协定适用")
    if re.search(r"非居民|源泉扣缴", body): types.append("非居民税收")
    if re.search(r"资本弱化", body): types.append("资本弱化")
    if re.search(r"受控外国企业|CFC", body): types.append("受控外国企业")
    kw = re.search(r"关键词：(.+)", body)
    if kw:
        ctry = [w.strip() for w in re.split(r"[　\s，,]", kw.group(1)) if w.strip()][:3]
    yaosu = json.dumps({"税种": [], "违法类型": types, "行业": [], "适用法条": [],
                        "是否移送司法": False, "程序类型": "官方案例库（海外税收案例）",
                        "关键词": ctry}, ensure_ascii=False)
    tags = {}
    if types: tags["事项类型"] = types
    if ctry: tags["涉案国家/地区"] = ctry
    fn = f"{date}_{title}"
    fn = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", fn)[:90].strip()
    path = os.path.join(OUT, fn + ".md")
    if os.path.exists(path):
        return None
    fm = ("---\n"
          f'title: "{title}"\n'
          '来源机关: "国家税务总局"\n'
          '栏目: "实务课程与书籍·总局海外税收案例库"\n'
          '地区: "全国"\n'
          f'发布日期: {date}\n'
          '原文来源: "国家税务总局官网·税收服务一带一路倡议专题·海外税收案例库（官方主动公开）"\n'
          f'抓取日期: {TODAY}\n'
          f'原文链接: {url}\n'
          f'标签: {json.dumps(tags, ensure_ascii=False)}\n'
          f'要素: {yaosu}\n'
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + "\n\n---\n\n来源：国家税务总局官网 海外税收案例库\n")
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    done = load_done()
    sess = cr.Session(impersonate="chrome124")
    r = sess.get(INDEX, timeout=30)
    links = list(dict.fromkeys(re.findall(r'href="(/chinatax/c102448/[^"]+)"', r.text)))
    print("index links:", len(links))
    kept = skip = 0
    for i, l in enumerate(links, 1):
        u = "https://www.chinatax.gov.cn" + l
        if u in done:
            continue
        try:
            rr = sess.get(u, timeout=30)
        except Exception as e:
            print(i, u, "ERR", e)
            time.sleep(2)
            continue
        time.sleep(1.2 + random.uniform(0.1, 0.4))
        soup = BeautifulSoup(rr.text, "lxml")
        h = None
        for cand in (soup.select(".article-title") + soup.select("h1")
                     + soup.select("h2")):
            txt = cand.get_text(" ", strip=True)
            if txt and "您所在的位置" not in txt:
                h = cand
                break
        cont = soup.select_one(".article-content")
        if not h or not cont:
            log_rec({"url": u, "status": "no-content", "keep": False})
            skip += 1
            continue
        title = h.get_text(strip=True)
        if "您所在的位置" in title or ">" in title:
            title = title.split(">")[-1].strip()
        if not title or len(title) < 4:
            m = re.search(r"<title>([^<]+)</title>", rr.text)
            title = m.group(1).strip() if m else os.path.basename(l)
        body = cont.get_text("\n", strip=True)
        body = re.sub(r"\n{3,}", "\n\n", body)
        dates = re.findall(r"20\d{2}-\d{2}-\d{2}", rr.text)
        date = dates[0] if dates else TODAY
        if len(re.findall(r"[\u4e00-\u9fff]", body)) < 300 or not re.search(
                r"[0-9０-９一二三四五六七八九十百千万亿]", body):
            log_rec({"url": u, "status": "quality-reject", "keep": False, "title": title})
            skip += 1
            continue
        p = write_md(title, date, body, u)
        if p:
            kept += 1
            log_rec({"url": u, "status": "ok", "keep": True, "path": p})
        if i % 10 == 0:
            print(f"[{i}/{len(links)}] kept={kept} skip={skip}")
    print(f"DONE kept={kept} skip={skip}")


if __name__ == "__main__":
    main()
