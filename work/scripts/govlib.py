#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""国家规章库(gov.cn) 工具：athenaappkey 本地生成 + 全量枚举 + HTML 抓取下载。

athenaappkey = urlEncode(base64(RSA_PKCS1v15_encrypt(PUBKEY, APPID)))  —— 从规章库前端 index.js 逆向，静态可复现。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import base64
import json
import os
import random
import re
import sys
import time
from urllib.parse import quote

import requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

SEARCH_URL = "https://sousuoht.www.gov.cn/athena/forward/BD8730CDDA12515E2D9E1B21AA11C0D6"
PUBKEY_B64 = ("MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCWGTHvPbNkzQNxTJwSZbsgHKyLl/OK11kCZNmVVS"
              "FK3lUbmHgh7Ain1gdaf7G/ETh/wQm/9BAO/U36yWPizzlwHCUcWJXBRsY10PsnYIlBXH/cjqQaEbmE"
              "ghxcjdYtLtkudoMfoMDiJk+tPC7UEZd8TI2u26vttNF++6tHi1HdeQIDAQAB")
APPID = "f8f49ea85885466598c5261f7f8607fb"
APPNAME = quote("规章库")

# 字段映射（来自 gov_api.py / 前端JS）
F_TITLE = "f_202321360426"
F_TYPE = "f_202321807875"
F_SXX = "f_202321864401"
F_DATE = "f_202321915922"
F_SOURCE = "f_202323394765"
F_ORG = "f_202355832506"
F_ORG2 = "f_202328191239"
F_DOC_NUM = "f_202344311304"
F_URL = "doc_pub_url"

RESULT_FIELDS = [F_TITLE, F_TYPE, F_SXX, F_DATE, F_SOURCE, F_ORG, F_ORG2,
                 F_DOC_NUM, F_URL, "f_20232124962", "f_2023425676953",
                 "f_2023425808265", "f_20232380533", "f_20232151076"]


def gen_appkey() -> str:
    key = RSA.import_key(base64.b64decode(PUBKEY_B64))
    ct = PKCS1_v1_5.new(key).encrypt(APPID.encode())
    return quote(base64.b64encode(ct).decode(), safe="")


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Content-Type": "application/json;charset=UTF-8",
        "athenaappname": APPNAME,
        "athenaappkey": gen_appkey(),
        "Origin": "https://www.gov.cn",
        "Referer": "https://www.gov.cn/zhengce/xxgk/gjgzk/index.htm",
    })
    return s


def search(s, reg_type=None, page=1, size=10, retries=5):
    fields = [
        {"fieldName": F_TYPE, "searchType": "TERM", "withHighLight": True},
        {"fieldName": F_TITLE, "withHighLight": True, "searchWord": ""},
        {"fieldName": "f_202321758948", "withHighLight": True},
    ]
    if reg_type:
        fields[0]["searchWord"] = reg_type
    body = {
        "code": "18258ab0ac9",
        "searchFields": fields,
        "sorts": [{}, {"sortField": F_DATE, "sortOrder": "DESC"}],
        "resultFields": RESULT_FIELDS,
        "trackTotalHits": "true",
        "tableName": "t_1860c735d31",
        "pageSize": size, "pageNo": page,
        "granularity": "ALL",
    }
    for i in range(retries):
        try:
            r = s.post(SEARCH_URL, json=body, timeout=30)
            j = r.json()
            res = j.get("result", {})
            code = (res.get("resultCode") or {})
            cstr = code.get("code", "") if isinstance(code, dict) else str(code)
            if isinstance(cstr, str) and cstr.startswith("athena_"):
                # key 失效，重新生成
                s.headers["athenaappkey"] = gen_appkey()
                continue
            data = res.get("data")
            if isinstance(data, list):
                return int(res.get("totalCount", 0)), data
            pager = (data or {}).get("pager", {})
            return int(pager.get("total", 0)), (data or {}).get("list", [])
        except Exception:
            if i == retries - 1:
                raise
            s.headers["athenaappkey"] = gen_appkey()
            time.sleep(1.5 * (i + 1))
    return 0, []


def _clean(t):
    if t is None:
        return ""
    if isinstance(t, list):
        t = t[0] if t else ""
    return re.sub(r"</?em[^>]*>", "", str(t))


def parse_item(item):
    def g(f):
        v = item.get(f, "")
        if isinstance(v, list):
            return v[0] if v else ""
        return v or ""
    return {
        "title": _clean(g(F_TITLE)),
        "type": _clean(g(F_TYPE)),
        "sxx": _clean(g(F_SXX)),
        "date": _clean(g(F_DATE)).split(" ")[0],
        "org": _clean(g("f_20232151076") or g(F_ORG) or g(F_ORG2)),
        "doc_num": _clean(g(F_DOC_NUM)),
        "url": _clean(g(F_URL)),
    }


def enumerate_all(reg_type, out_path, size=100, delay=0.6):
    s = make_session()
    total, _ = search(s, reg_type=reg_type, page=1, size=1)
    print(f"[{reg_type}] total={total}", flush=True)
    seen = set()
    rows = []
    page = 1
    while True:
        t, items = search(s, reg_type=reg_type, page=page, size=size)
        if not items:
            break
        for it in items:
            rec = parse_item(it)
            url = rec["url"]
            if not url or url in seen:
                continue
            seen.add(url)
            rec["cat"] = reg_type
            rows.append(rec)
        print(f"[{reg_type}] page {page}: 累计 {len(rows)}/{total}", flush=True)
        if len(rows) >= total or len(items) < size and page * size >= total:
            break
        page += 1
        time.sleep(delay + random.random() * 0.3)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[{reg_type}] 完成 {len(rows)} -> {out_path}", flush=True)
    return rows


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "lists")
    os.makedirs(out_dir, exist_ok=True)
    for rt in ["部门规章", "地方政府规章"]:
        enumerate_all(rt, os.path.join(out_dir, f"gov_{rt}.jsonl"))
