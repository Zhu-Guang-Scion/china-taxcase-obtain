#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""按 data-docx.jsonl 索引从 raw.githubusercontent.com 精准抓取剩余 flk 缺口 docx（sha256 校验）。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import time

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
DL_ROOT = os.path.join(ROOT, "downloads", "flk")
IDX = os.path.abspath(os.path.join(ROOT, "..", "mirrors", "data-docx.jsonl"))
RAW = "https://raw.githubusercontent.com/lawtext/legal-data-docx/main/docx/"
SXX_MAP = {3: "有效"}


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name.strip().rstrip(".")[:100] or "unnamed"


def main():
    idx = {}
    for l in open(IDX, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            idx[r["id"]] = r
    print("索引:", len(idx))

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131"})

    # 只处理地方法规（其他类已满）
    for cat in ["地方法规"]:
        items = [json.loads(l) for l in open(os.path.join(LISTS, f"flk_{cat}.jsonl"), encoding="utf-8") if l.strip()]
        prog_path = os.path.join(LISTS, f"flk_dl_progress_{cat}.jsonl")
        prog = {}
        if os.path.exists(prog_path):
            for line in open(prog_path, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        prog[rec["bbbs"]] = rec
                    except Exception:
                        pass
        missing = [it for it in items if not prog.get(it["bbbs"], {}).get("ok")]
        print(f"[{cat}] 缺口 {len(missing)}")
        ok = fail = 0
        out_dir = os.path.join(DL_ROOT, cat)
        os.makedirs(out_dir, exist_ok=True)
        with open(prog_path, "a", encoding="utf-8") as pf:
            for i, it in enumerate(missing):
                r = idx.get(it["bbbs"])
                if not r:
                    continue
                paths = [r.get("path")] + ([r["alias"]] if r.get("alias") else [])
                got = None
                for p in paths:
                    if not p:
                        continue
                    for attempt in range(4):
                        try:
                            resp = s.get(RAW + p, timeout=60)
                            if resp.status_code == 200 and len(resp.content) > 2000:
                                got = (p, resp.content)
                                break
                        except Exception:
                            pass
                        time.sleep(1.5 * (attempt + 1))
                    if got:
                        break
                if not got:
                    fail += 1
                    pf.write(json.dumps({"bbbs": it["bbbs"], "ok": False,
                                         "error": "raw fetch failed"}, ensure_ascii=False) + "\n")
                    continue
                p, content = got
                # sha256 校验
                h = hashlib.sha256(content).hexdigest()
                hash_ok = (h == r.get("hash"))
                name = sanitize(f"{it.get('flxz') or cat}_{it['title']}_{it.get('gbrq','')}_有效")
                fpath = os.path.join(out_dir, name + ".docx")
                n = 1
                while os.path.exists(fpath) and os.path.getsize(fpath) > 2000 and n < 5:
                    fpath = os.path.join(out_dir, f"{name}_{n}.docx")
                    n += 1
                with open(fpath, "wb") as f:
                    f.write(content)
                pf.write(json.dumps({"bbbs": it["bbbs"], "ok": True,
                                     "file": os.path.basename(fpath),
                                     "source": "lawtext", "bytes": len(content),
                                     "sha256_ok": hash_ok}, ensure_ascii=False) + "\n")
                ok += 1
                if (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(missing)} ok={ok} fail={fail}", flush=True)
                time.sleep(0.4)
        print(f"[{cat}] 完成: 补 {ok}, 失败 {fail}")


if __name__ == "__main__":
    main()
