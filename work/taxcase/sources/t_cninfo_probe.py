# -*- coding: utf-8 -*-
"""R16 调研：巨潮 fulltextSearch 实测 北交所/新三板 税务公告标题级命中量"""
import json, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from curl_cffi import requests

URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
H = {
    "Referer": "http://www.cninfo.com.cn/new/fulltextSearch",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

def classify(code):
    c = (code or "").strip()
    if c.startswith(("600","601","603","605","688","689","900")): return "SH"
    if c.startswith(("000","001","002","003","300","301","200","420")): return "SZ"
    if c.startswith("920"): return "BJ(920)"
    if c.startswith("8"): return "8xx(BJ/NEEQ)"
    if c.startswith("4"): return "4xx(NEEQ老三板)"
    return "other:" + c

def probe(searchkey, type_param=None, pages=3):
    total = None; dist = {}; sample = []
    for p in range(1, pages + 1):
        data = {"searchkey": searchkey, "isfulltext": "false", "pageNum": str(p), "pageSize": "30"}
        if type_param: data["type"] = type_param
        try:
            r = requests.post(URL, data=data, headers=H, impersonate="chrome124", timeout=30)
            j = r.json()
        except Exception as e:
            print(f"  [pg{p}] ERR {e}"); time.sleep(2); continue
        if p == 1:
            total = j.get("totalRecordNum") or j.get("totalrecordnum")
            # 打印一条完整记录的键，看有无板块字段
            anns = j.get("announcements") or []
            if anns:
                keys = sorted(anns[0].keys())
                print(f"  [字段] {keys}")
        anns = j.get("announcements") or []
        if not anns: break
        for a in anns:
            d = classify(a.get("secCode"))
            dist[d] = dist.get(d, 0) + 1
            if len(sample) < 5 and d in ("BJ(920)", "8xx(BJ/NEEQ)"):
                sample.append((a.get("secCode"), a.get("secName"), a.get("announcementTitle","")[:40]))
        time.sleep(1.2)
    return total, dist, sample

CASES = [
    ("税务行政处罚决定书", None),
    ("税务行政处罚决定书", "shj"),
    ("补缴税款", None),
    ("补缴税款", "shj"),
    ("税务处罚", "shj"),
    ("税务处理决定书", "shj"),
    ("税务事项通知书", "shj"),
    ("税收保全", "shj"),
]
out = {}
for kw, tp in CASES:
    tag = f"{kw}{'|type=' + tp if tp else '|无type'}"
    print(f"\n== {tag} ==")
    total, dist, sample = probe(kw, tp)
    print(f"  total={total}  前缀分布(抽样<=3页)={dist}")
    for s in sample: print(f"    样本 {s}")
    out[tag] = {"total": total, "dist": dist}
    time.sleep(1.5)

with open(r"E:\ai_coding_xiangmu\China_Law\work\taxcase\sources\t_cninfo_probe_result.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\nDONE -> t_cninfo_probe_result.json")
