# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# ============================================================
"""沪深交易所监管措施（涉税）抓取

信源与接口（2026-10 实测，详见 sources/cninfo_r16.md）：
  上交所监管措施  commonSoaQuery.do sqlId=BS_KCB_GGLL_NEW channelId=10007-10010（5,555 条）
                  → docURL 字段直给 PDF 相对路径（需 http: 前缀）
  深交所监管措施  ShowReport/data CATALOGID=1800_jgxxgk（4,855 条）
                  → hjnr 里 encode-open='/UpFiles/zqjghj/xxx.pdf'
  两接口均无关键词参数 → 全量翻页建池 → 标题筛涉税 → 下载 PDF 抽文本
坑：
  * 上交所 jsonCallBack=jsonp 包装（直接不带该参数也返回纯 JSON？实测带 isPagination 才有分页）
  * 深交所 random 参数防缓存（必带随机数）；PAGENO 从 1 起
  * 监管函标题含事由（"关于XX公司YY事项的监管工作函"），筛涉税靠标题词
用法：
  python exchange_measure.py            # 全流程
  python exchange_measure.py --recon    # 仅重建元数据池
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"

import os, re, json, time, argparse, random as rd, sys

BASE = r"E:\ai_coding_xiangmu\China_Law"
sys.path.insert(0, os.path.join(BASE, "work", "taxcase"))
from taxcase_scrape import polite_get

ROOT = os.path.join(BASE, "lawlibrary", "专题", "税务案例")
TMP = os.path.join(BASE, "work", "taxcase", "tmp")
POOL_F = os.path.join(TMP, "exchange_measure_pool.json")
PROG_F = os.path.join(BASE, "work", "taxcase", "progress", "exchange_measure.jsonl")
os.makedirs(os.path.dirname(PROG_F), exist_ok=True)
os.makedirs(TMP, exist_ok=True)
TODAY = time.strftime("%Y-%m-%d")

from curl_cffi import requests as cr

# 标题级涉税筛词（监管函标题事由段）
TAX_TITLE = re.compile(r"税收|税务|税.{0,4}事项|补缴|增值税|所得税|消费税|发票|虚开|偷税|骗税|留抵|税负|纳税|完税|欠税|汇算")

def _get(url, referer):
    r = cr.get(url, timeout=400, impersonate="chrome124", headers={"Referer": referer})
    return r

# ---------- 上交所 ----------
def sse_pool():
    rows, page = [], 1
    while True:
        u = ("https://query.sse.com.cn/commonSoaQuery.do?isPagination=true"
             "&pageHelp.pageSize=100&pageHelp.pageNo={p}&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1"
             "&sqlId=BS_KCB_GGLL_NEW&siteId=28&channelId=10007,10008,10009,10010"
             "&type=&stockcode=&extWTFL=&createTime=&createTimeEnd=&order=createTime|desc,stockcode|asc").format(p=page)
        r = _get(u, "https://www.sse.com.cn/disclosure/credibility/supervision/measures/")
        d = r.json()
        ph = d.get("pageHelp") or {}
        recs = d.get("result") or []
        if not recs:
            break
        for a in recs:
            rows.append({"ex": "上交所", "code": a.get("stockcode") or "",
                         "name": a.get("extGSJC") or "",
                         "title": a.get("docTitle") or "",
                         "type": a.get("extWTFL") or "",
                         "date": (a.get("cmsOpDate") or "")[:10],
                         "pdf": "http://" + (a.get("docURL") or "").lstrip("/") if a.get("docURL") else ""})
        if page % 10 == 0:
            print(f"  SSE p{page}/{(int(ph.get('total') or 0)+99)//100}")
        if page * 100 >= int(ph.get("total") or 0):
            break
        page += 1
        time.sleep(1.3)
    return rows

# ---------- 深交所 ----------
def szse_pool():
    rows, page = [], 1
    while True:
        u = f"https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1800_jgxxgk&PAGENO={page}&random={rd.random()}"
        r = _get(u, "https://www.szse.cn/disclosure/supervision/measure/measure/index.html")
        d = r.json()[0]
        md = d.get("metadata") or {}
        recs = d.get("data") or []
        if not recs:
            break
        for a in recs:
            m = re.search(r"encode-open='([^']+)'", a.get("hjnr") or "")
            rows.append({"ex": "深交所", "code": a.get("gkxx_gsdm") or "",
                         "name": a.get("gkxx_gsjc") or "",
                         "title": f"{a.get('gkxx_jgcs') or ''}：{a.get('gkxx_gsjc') or ''}（{a.get('gkxx_gdrq') or ''}）",
                         "type": a.get("gkxx_jgcs") or "",
                         "date": a.get("gkxx_gdrq") or "",
                         # IAB 实测：encode-open 相对路径挂在 reportdocs.static.szse.cn 静态域（www 域 404）
                         "pdf": "https://reportdocs.static.szse.cn" + m.group(1) if m else ""})
        if page % 10 == 0:
            print(f"  SZSE p{page}/{md.get('pagecount')}")
        if page >= int(md.get("pagecount") or 0):
            break
        page += 1
        time.sleep(1.3)
    return rows

def build_pool():
    pool = []
    print("上交所监管措施翻页…"); sse = sse_pool()
    time.sleep(2)
    print("深交所监管措施翻页…"); szse = szse_pool()
    # 上交所标题含事由可筛；深交所列表无事由字段 → 全量进 hits 由 PDF 全文把关
    hits = [r for r in sse if TAX_TITLE.search(r["title"])] + \
           [r for r in szse if r["pdf"]]
    json.dump({"pool": sse + szse, "hits": hits}, open(POOL_F, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"元数据 SSE {len(sse)} + SZSE {len(szse)}；待下 PDF：SSE 标题命中 {sum(1 for r in sse if TAX_TITLE.search(r['title']))} + SZSE 全量 {len(szse)}")
    return hits

def pdf_to_text(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    txt = "\n".join(pg.get_text() for pg in doc)
    doc.close()
    paras, cur = [], []
    for ln in txt.split("\n"):
        ln = ln.strip()
        if not ln:
            if cur:
                paras.append("".join(cur)); cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append("".join(cur))
    return "\n\n".join(p for p in paras if p)

def fname_safe(s, n=90):
    s = re.sub(r'[\\/:*?"<>|\r\n]', "", s)
    return s[:n].rstrip("．. ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recon", action="store_true")
    args = ap.parse_args()
    if args.recon or not os.path.exists(POOL_F):
        hits = build_pool()
    else:
        hits = json.load(open(POOL_F, encoding="utf-8"))["hits"]

    done = set()
    if os.path.exists(PROG_F):
        for ln in open(PROG_F, encoding="utf-8"):
            try:
                done.add(json.loads(ln)["pdf"])
            except Exception:
                pass
    todo = [r for r in hits if r["pdf"] and r["pdf"] not in done]
    print(f"断点 {len(done)}，待抓 {len(todo)}")

    from structure_extract import extract
    ok = fail = 0
    for r in todo:
        pdf_path = os.path.join(TMP, "exm_" + r["pdf"].split("/")[-1])
        try:
            resp = polite_get(r["pdf"], delay=1.3, referer=r["pdf"])
            if resp is None or resp.status_code != 200:
                raise RuntimeError(f"HTTP {getattr(resp, 'status_code', '?')}")
            open(pdf_path, "wb").write(resp.content)
            body = pdf_to_text(pdf_path)
            if len(re.sub(r"\s", "", body)) < 60:
                raise RuntimeError("文本过短")
            # 全文涉税复核（深交所全量进池、上交所防标题误命中，都以此把关）
            flat = re.sub(r"\s", "", body)
            if not TAX_TITLE.search(flat) and not re.search(r"[一二三四五六七八九十]?税[种务收款]", flat[:2000]):
                open(PROG_F, "a", encoding="utf-8").write(
                    json.dumps({"pdf": r["pdf"], "ok": False, "err": "skip:全文无税要素"}, ensure_ascii=False) + "\n")
                os.remove(pdf_path)
                continue
        except Exception as e:
            fail += 1
            open(PROG_F, "a", encoding="utf-8").write(
                json.dumps({"pdf": r["pdf"], "ok": False, "err": str(e)[:100]}, ensure_ascii=False) + "\n")
            print(f"  FAIL {r['title'][:30]}: {e}")
            continue
        fm_meta = {"栏目": "监管措施"}
        tags, elem = extract(body, fm_meta)
        d = os.path.join(ROOT, r["ex"], "监管措施")
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, f"{r['date'] or '未知日期'}_{fname_safe(r['title'])}.md")
        fm = [
            f'title: "{r["title"]}"',
            f'来源机关: "{r["name"]}（{r["code"]}，{r["ex"]}上市）"',
            '栏目: "监管措施"',
            f'地区: "{"上海市" if r["ex"] == "上交所" else "深圳市"}"',
            f"发布日期: {r['date']}",
            f'原文来源: "{r["ex"]}官网监管信息公开"',
            f"抓取日期: {TODAY}",
            f"原文链接: {r['pdf']}",
            "标签: " + json.dumps(tags, ensure_ascii=False),
            "要素: " + json.dumps(elem, ensure_ascii=False),
        ]
        open(fp, "w", encoding="utf-8", newline="\n").write(
            "---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n")
        os.remove(pdf_path)
        ok += 1
        open(PROG_F, "a", encoding="utf-8").write(
            json.dumps({"pdf": r["pdf"], "ok": True, "file": os.path.relpath(fp, ROOT)}, ensure_ascii=False) + "\n")
        if ok % 20 == 0:
            print(f"  进度 ok={ok} fail={fail}")
    print(f"完成: ok={ok} fail={fail}")

if __name__ == "__main__":
    main()
