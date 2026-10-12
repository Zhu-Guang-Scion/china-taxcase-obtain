# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# ============================================================
"""沪深交易所上市公司税务公告抓取（巨潮资讯通道）

信源：巨潮资讯网 cninfo（深交所旗下法定披露平台，沪深公告同源）
接口：POST /new/fulltextSearch/full 标题级检索（isfulltext=false）
坑位（实测 2026-10）：
  * 翻页参数是 pageNum（page 无效，永远返回第一页）
  * type:"shj" 会把检索锁在新三板/退市板块——收沪深主板必须不传 type
  * market 参数无效；市场过滤靠 secCode 前缀
  * 标题含 <em> 高亮需剥除；announcementTime 是毫秒时间戳
用法：
  python cninfo_taxcase.py            # 全流程：建池→下载PDF→抽文本→入库
  python cninfo_taxcase.py --recon    # 仅重建检索池
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"

import os, re, json, time, argparse, sys

BASE = r"E:\ai_coding_xiangmu\China_Law"
sys.path.insert(0, os.path.join(BASE, "work", "taxcase"))
from taxcase_scrape import polite_get  # 限速+chrome指纹

ROOT = os.path.join(BASE, "lawlibrary", "专题", "税务案例")
TMP = os.path.join(BASE, "work", "taxcase", "tmp")
POOL_F = os.path.join(TMP, "cninfo_pool.json")
PROG_F = os.path.join(BASE, "work", "taxcase", "progress", "cninfo_taxcase.jsonl")
os.makedirs(os.path.dirname(PROG_F), exist_ok=True)
os.makedirs(TMP, exist_ok=True)

SEARCH_URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
PDF_HOST = "http://static.cninfo.com.cn/"
TODAY = time.strftime("%Y-%m-%d")

KWS = ["税务行政处罚决定书", "税务处理决定书", "补缴税款", "税务事项通知书",
       "税务稽查", "虚开发票", "税务处罚", "税收事项通知书", "补缴相关税款",
       "税收保全措施决定书", "税务行政复议决定书"]

# 标题噪音：摘要/更正/英文/取消等无正文价值的公告
TITLE_JUNK = re.compile(r"摘要|更正后|取消|英文|（撤销）|回答|路演|说明会|投资者说明")

def mkt(code):
    code = str(code or "")
    if code[:3] in ("600", "601", "603", "605", "688", "689", "900"):
        return "上交所", "上海市"
    if code[:3] in ("000", "001", "002", "003", "300", "301", "200", "420"):
        return "深交所", "深圳市"
    return None, None

def _post_search(kw, pageNum):
    from curl_cffi import requests as cr
    payload = {"searchkey": kw, "sdate": "", "edate": "", "isfulltext": "false",
               "sortName": "pubdate", "sortType": "desc", "pageNum": pageNum}
    r = cr.post(SEARCH_URL, data=payload, timeout=400, impersonate="chrome124", headers={
        "Referer": "http://www.cninfo.com.cn/new/fulltextSearch",
        "X-Requested-With": "XMLHttpRequest"})
    return r.json()

def build_pool():
    pool = {}
    for kw in KWS:
        p, total = 1, None
        while True:
            try:
                d = _post_search(kw, p)
            except Exception as e:
                print(f"  [{kw}] p{p} 失败: {e}"); time.sleep(5); continue
            anns = d.get("announcements") or []
            total = d.get("totalAnnouncement")
            if not anns:
                break
            for a in anns:
                pool[a["adjunctUrl"]] = a
            if p * 10 >= total:
                break
            p += 1
            time.sleep(1.4)
        print(f"[{kw}] total={total} 池累计={len(pool)}")
        time.sleep(1.4)
    rows = []
    for a in pool.values():
        title = re.sub(r"</?em>", "", a.get("announcementTitle") or "").strip()
        title = re.sub(r"^\[[^\]]{1,8}\]", "", title)  # 剥 [临时公告] 前缀
        if TITLE_JUNK.search(title):
            continue
        ex, region = mkt(a.get("secCode"))
        if not ex:
            continue  # 只要沪深两所
        rows.append({"code": a["secCode"], "name": a["secName"], "title": title,
                     "url": a["adjunctUrl"], "ts": a["announcementTime"],
                     "exchange": ex, "region": region})
    json.dump(rows, open(POOL_F, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"池落盘: {len(rows)} 件（沪深两所，已滤噪音）")
    return rows

def pdf_to_text(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    txt = "\n".join(pg.get_text() for pg in doc)
    doc.close()
    # PDF 逐行文本 → 段落重排：空行分段，段内行合并（中文无空格，遇句读自然衔接）
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
        rows = build_pool()
    else:
        rows = json.load(open(POOL_F, encoding="utf-8"))

    done = set()
    for ln in (open(PROG_F, encoding="utf-8") if os.path.exists(PROG_F) else []):
        try:
            done.add(json.loads(ln)["url"])
        except Exception:
            pass
    print(f"断点: {len(done)} 件已完成，待抓 {sum(1 for r in rows if r['url'] not in done)}")

    from structure_extract import extract
    import hashlib
    ok = fail = 0
    for r in rows:
        if r["url"] in done:
            continue
        pdf_url = PDF_HOST + r["url"]
        pdf_path = os.path.join(TMP, "cninfo_" + r["url"].split("/")[-1])
        try:
            resp = polite_get(pdf_url, delay=1.3,
                              referer="http://www.cninfo.com.cn/new/fulltextSearch")
            if resp is None or resp.status_code != 200:
                raise RuntimeError(f"HTTP {getattr(resp, 'status_code', '?')}")
            open(pdf_path, "wb").write(resp.content)
            body = pdf_to_text(pdf_path)
            if len(re.sub(r"\s", "", body)) < 80:
                raise RuntimeError("文本过短(疑似扫描件)")
        except Exception as e:
            fail += 1
            open(PROG_F, "a", encoding="utf-8").write(
                json.dumps({"url": r["url"], "ok": False, "err": str(e)[:100]}, ensure_ascii=False) + "\n")
            print(f"  FAIL {r['code']} {r['title'][:30]}: {e}")
            continue

        pub = time.strftime("%Y-%m-%d", time.localtime(r["ts"] / 1000))
        fm_meta = {"栏目": "上市公司税务披露"}
        tags, elem = extract(body, fm_meta)
        d = os.path.join(ROOT, r["exchange"], "上市公司税务披露")
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, f"{pub}_{fname_safe(r['title'])}.md")
        fm = [
            f'title: "{r["title"]}"',
            f'来源机关: "{r["name"]}（{r["code"]}，{r["exchange"]}上市）"',
            '栏目: "上市公司税务披露"',
            f'地区: "{r["region"]}"',
            f"发布日期: {pub}",
            '原文来源: "巨潮资讯网（沪深交易所法定披露平台）"',
            f"抓取日期: {TODAY}",
            f"原文链接: {pdf_url}",
            "标签: " + json.dumps(tags, ensure_ascii=False),
            "要素: " + json.dumps(elem, ensure_ascii=False),
        ]
        open(fp, "w", encoding="utf-8", newline="\n").write(
            "---\n" + "\n".join(fm) + "\n---\n\n" + body + "\n")
        os.remove(pdf_path)  # 抽完即弃，省磁盘
        ok += 1
        open(PROG_F, "a", encoding="utf-8").write(
            json.dumps({"url": r["url"], "ok": True, "file": os.path.relpath(fp, ROOT)},
                       ensure_ascii=False) + "\n")
        if ok % 20 == 0:
            print(f"  进度 ok={ok} fail={fail}")
    print(f"完成: ok={ok} fail={fail}")

if __name__ == "__main__":
    main()
