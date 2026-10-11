#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""一次性：把 .doc 老格式文件经 flk 官方 API 重取为 docx（用 cookie 池）。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import glob
import json
import os
import re
import sys
import time

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
BASE = "https://flk.npc.gov.cn"


def load_cookie_session():
    d = json.load(open(os.path.join(ROOT, "lists", "flk_cookies.json"), encoding="utf-8"))
    s = requests.Session()
    s.headers.update({
        "User-Agent": d.get("ua") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131",
        "Referer": "https://flk.npc.gov.cn/",
        "Origin": "https://flk.npc.gov.cn",
        "Accept": "application/json, text/plain, */*",
    })
    for c in d.get("cookies", []):
        s.cookies.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))
    return s


def refresh_cookies(s):
    try:
        s.get(BASE + "/", timeout=20)
    except Exception:
        pass


def main():
    # 从进度文件建 file -> bbbs 映射
    file2bbbs = {}
    for pf in glob.glob(os.path.join(ROOT, "lists", "flk_dl_progress_*.jsonl")):
        for line in open(pf, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    if rec.get("file"):
                        file2bbbs[rec["file"]] = rec["bbbs"]
                except Exception:
                    pass
    files = glob.glob(os.path.join(ROOT, "downloads", "flk", "**", "*.doc"), recursive=True)
    print("待转 docx:", len(files))
    s = load_cookie_session()
    ok = fail = 0
    for fp in files:
        fn = os.path.splitext(os.path.basename(fp))[0]
        bbbs = file2bbbs.get(fn + ".doc")
        if not bbbs:
            # 兜底：去扩展名精确匹配
            bbbs = file2bbbs.get(os.path.basename(fp))
        if not bbbs:
            fail += 1
            print("  ✗ 无bbbs:", fn[:50])
            continue
        try:
            r = s.get(BASE + "/law-search/download/pc", params={"format": "docx", "bbbs": bbbs}, timeout=30)
            j = r.json()
            url = (j.get("data") or {}).get("url", "")
            if not url:
                raise RuntimeError("no url")
            r2 = s.get(url, timeout=60)
            if r2.status_code != 200 or len(r2.content) < 2000 or not r2.content[:2] == b"PK":
                raise RuntimeError(f"bad content {len(r2.content)}")
            new_path = fp[:-4] + ".docx"
            with open(new_path, "wb") as f:
                f.write(r2.content)
            # 记录到对应类别进度
            cat = os.path.basename(os.path.dirname(fp))
            pf = os.path.join(ROOT, "lists", f"flk_dl_progress_{cat}.jsonl")
            with open(pf, "a", encoding="utf-8") as f:
                f.write(json.dumps({"bbbs": bbbs, "ok": True,
                                    "file": os.path.basename(new_path),
                                    "source": "官方API-docx重取",
                                    "bytes": len(r2.content)}, ensure_ascii=False) + "\n")
            os.remove(fp)  # 移除老 .doc
            ok += 1
        except Exception as e:
            fail += 1
            print("  ✗", fn[:50], e)
            refresh_cookies(s)
        time.sleep(0.6)
    print(f"完成: {ok} 成功, {fail} 失败")


if __name__ == "__main__":
    main()
