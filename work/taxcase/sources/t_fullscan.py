# -*- coding: utf-8 -*-
"""R16: 全量扫描 shj(三板+京) 税务标题命中 + 两所官网页面可达性"""
import json, time, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from curl_cffi import requests

URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
H = {
    "Referer": "http://www.cninfo.com.cn/new/fulltextSearch",
    "X-Requested-With": "XMLHttpRequest",
}

def scan(kw, max_pages=40):
    seen = {}
    for p in range(1, max_pages + 1):
        data = {"searchkey": kw, "isfulltext": "false", "type": "shj",
                "pageNum": str(p), "pageSize": "30"}
        try:
            j = requests.post(URL, data=data, headers=H, impersonate="chrome124", timeout=30).json()
        except Exception as e:
            print(f"  pg{p} ERR {e}"); time.sleep(2); continue
        anns = j.get("announcements") or []
        if not anns: break
        for a in anns:
            aid = a.get("announcementId")
            seen[aid] = {
                "code": a.get("secCode"), "name": a.get("secName"),
                "col": a.get("columnId"), "type": a.get("announcementTypeName"),
                "t": a.get("announcementTime"),
            }
        if p % 5 == 0: print(f"  pg{p} cum={len(seen)}")
        time.sleep(1.0)
    return seen

allhits = {}
for kw in ["税务行政处罚决定书", "税务处罚", "税务处理决定书", "税务事项通知书", "补缴税款", "税收保全"]:
    print(f"\n== scan {kw} (type=shj) ==")
    s = scan(kw)
    allhits.update(s)
    print(f"  uniq={len(s)}")

def cls(c):
    c = (c or "").strip()
    for p in ("600","601","603","605","688","689","900"): 
        if c.startswith(p): return "SH"
    for p in ("000","001","002","003","300","301","200","420"):
        if c.startswith(p): return "SZ"
    if c.startswith("920"): return "BJ920"
    if c.startswith(("83","87","88")): return "NEEQ_8"
    if c.startswith("4"): return "NEEQ_4"
    return "other"

dist = {}
for aid, v in allhits.items():
    k = cls(v["code"])
    dist.setdefault(k, []).append(v)

print(f"\n== 汇总（{len(allhits)} 条去重后） ==")
for k, v in sorted(dist.items(), key=lambda x: -len(x[1])):
    codes = {a["code"] for a in v}
    print(f"  {k}: {len(v)} 条 / {len(codes)} 家")
    if k == "BJ920":
        for a in v[:10]: print("    920样本:", a["code"], a["name"])
    if k in ("SH", "SZ"):
        for a in v[:5]: print("    沪深样本(shj里):", a["code"], a["name"])

# columnId 分布（看能否区分北交所）
colset = {}
for v in allhits.values():
    colset[str(v["col"])] = colset.get(str(v["col"]), 0) + 1
print("  columnId 分布:", colset)
tset = {}
for v in allhits.values():
    tset[str(v["type"])] = tset.get(str(v["type"]), 0) + 1
print("  announcementTypeName 分布:", tset)

with open(r"E:\ai_coding_xiangmu\China_Law\work\taxcase\sources\t_shj_full.json", "w", encoding="utf-8") as f:
    json.dump({k: dist[k] for k in dist}, f, ensure_ascii=False, indent=1)
print("saved t_shj_full.json")

# ---- 两所官网页面可达性 ----
print("\n== 官网页面可达性 ==")
pages = {
    "SZSE纪律处分页": "https://www.szse.cn/disclosure/supervision/measure/index.html",
    "SZSE问询函件页": "https://www.szse.cn/disclosure/supervision/inquire/index.html",
    "SSE纪律处分页": "http://www.sse.com.cn/disclosure/credibility/supervision/measures/",
    "SSE监管问询页": "http://www.sse.com.cn/disclosure/inquiry/",
    "上交所审核网listing": "https://listing.sse.com.cn/",
    "深交所审核网listing": "https://listing.szse.cn/",
    "股转信息披露": "https://www.neeq.com.cn/disclosure.html",
    "北交所官网": "https://www.bse.cn/",
    "SSE债券信息网": "https://bond.sse.com.cn/",
}
for name, u in pages.items():
    try:
        r = requests.get(u, impersonate="chrome124", timeout=25,
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"})
        ok = "200" if r.status_code == 200 else str(r.status_code)
        size = len(r.text)
        print(f"  {name}: {ok} len={size}")
    except Exception as e:
        print(f"  {name}: EXC {type(e).__name__} {str(e)[:80]}")
    time.sleep(1.0)
