# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# ============================================================
"""侦察：深交所/上交所/巨潮 涉税公告检索接口可用性与形态"""
import json, sys, time
sys.path.insert(0, r"E:\ai_coding_xiangmu\China_Law\work\taxcase")
from curl_cffi import requests as cffi_requests

def _post(url, **kw):
    kw.setdefault("timeout", 400)
    kw.setdefault("impersonate", "chrome124")
    return cffi_requests.post(url, **kw)

def _get(url, **kw):
    kw.setdefault("timeout", 400)
    kw.setdefault("impersonate", "chrome124")
    return cffi_requests.get(url, **kw)

# ---------- 1) 深交所 annList（全文关键词走 title 字段） ----------
def szse_probe(kw, page=1):
    url = "http://www.szse.cn/api/disc/announcement/annList"
    payload = {"seDate": ["2020-01-01", "2026-10-12"], "stock": None,
               "channelCode": None, "pageSize": 30, "pageNum": page, "title": kw}
    r = _post(url, json=payload, headers={
        "Referer": "http://www.szse.cn/disclosure/announcements/index.html",
        "Origin": "http://www.szse.cn"})
    try:
        d = r.json()
    except Exception:
        print("SZSE", kw, "非JSON:", r.status_code, r.text[:150]); return
    rows = (d.get("data") or {}).get("announcements") or []
    print(f"SZSE[{kw}] total={((d.get('data') or {}).get('totalAnnouncement'))} 本页={len(rows)}")
    for a in rows[:3]:
        print("   -", a.get("secCode"), a.get("secName"), "|", a.get("announcementTitle"),
              "|", (a.get("adjunctUrl", "") or "")[-50:])

# ---------- 2) 上交所公告 ESSearch ----------
def sse_probe(kw):
    url = ("https://query.sse.com.cn/search/getESSearch.do?sqlId=BS_GGLL&"
           f"keyword={kw}&page=0&limit=10&direction=0&isPagination=true")
    r = _get(url, headers={
        "Referer": "https://www.sse.com.cn/", "Origin": "https://www.sse.com.cn"})
    try:
        d = r.json()
    except Exception:
        print("SSE", kw, "非JSON:", r.status_code, r.text[:150]); return
    recs = (d.get("data") or {}).get("record") or []
    total = d.get("total")
    print(f"SSE[{kw}] total={total} 本页={len(recs)}")
    for a in recs[:3]:
        print("   -", a.get("security_Type"), a.get("security_Code"), "|", (a.get("title") or "")[:60])

# ---------- 3) 巨潮（深交所法定平台，覆盖两所公告全文检索） ----------
def cninfo_probe(kw):
    url = "http://www.cninfo.com.cn/new/fulltextSearch/full"
    payload = {"searchkey": kw, "sdate": "", "edate": "", "isfulltext": "true",
               "sortName": "pubdate", "sortType": "desc", "type": "shj"}
    r = _post(url, data=payload, headers={
        "Referer": "http://www.cninfo.com.cn/new/fulltextSearch",
        "X-Requested-With": "XMLHttpRequest"})
    try:
        d = r.json()
    except Exception:
        print("CNINFO", kw, "非JSON:", r.status_code, r.text[:150]); return
    anns = (d.get("announcements") or [])
    print(f"CNINFO[{kw}] total={d.get('totalAnnouncement')} 本页={len(anns)}")
    for a in anns[:3]:
        print("   -", a.get("secCode"), a.get("secName"), "|", a.get("announcementTitle"),
              "|", (a.get("adjunctUrl") or "")[-50:])

if __name__ == "__main__":
    for kw in ["税务行政处罚", "补缴税款", "虚开", "偷税"]:
        szse_probe(kw); time.sleep(1.5)
        sse_probe(kw); time.sleep(1.5)
        cninfo_probe(kw); time.sleep(1.5)
        print()
