#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""gh-proxy 加速补抓 flk 缺口 docx（按 data-docx.jsonl 索引，sha256 校验）。

与 gap_fetch.py 的区别：优先走 gh-proxy 镜像（直连 raw.githubusercontent 在
国内被重置）。另：按内容魔数落 .doc/.docx 扩展名，与 verify.py 口径一致。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import hashlib
import io
import json
import os
import random
import re
import sys
import threading
import time
import zipfile

import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
DL_ROOT = os.path.join(ROOT, "downloads", "flk")
IDX = os.path.abspath(os.path.join(ROOT, "..", "mirrors", "data-docx.jsonl"))

PROXIES = [
    "https://gh-proxy.com/https://raw.githubusercontent.com/lawtext/legal-data-docx/main/docx/",
    "https://ghproxy.net/https://raw.githubusercontent.com/lawtext/legal-data-docx/main/docx/",
    "https://raw.githubusercontent.com/lawtext/legal-data-docx/main/docx/",
]

_print_lock = threading.Lock()
_prog_lock = threading.Lock()


def log(m):
    with _print_lock:
        print(m, flush=True)


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name.strip().rstrip(".")[:100] or "unnamed"


def load_latest(cat):
    path = os.path.join(LISTS, f"flk_dl_progress_{cat}.jsonl")
    latest = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    latest[rec["bbbs"]] = rec
                except Exception:
                    pass
    return path, latest


def sniff_ext(content: bytes, path: str) -> str:
    """docx(zip) / doc(OLE2) 按内容判断。"""
    if content[:2] == b"PK":
        return "docx"
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "doc"
    return "doc" if path.lower().split("?")[0].endswith(".doc") else "docx"


def fetch(pi, path, s, timeout=50):
    for off in range(len(PROXIES)):
        p = (pi + off) % len(PROXIES)
        try:
            r = s.get(PROXIES[p] + path, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 2000:
                return r.content, p
        except Exception:
            continue
    return None, pi


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    idx = {}
    for l in open(IDX, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            idx[r["id"]] = r

    cat = "地方法规"
    items = [json.loads(l) for l in
             open(os.path.join(LISTS, f"flk_{cat}.jsonl"), encoding="utf-8") if l.strip()]
    prog_path, latest = load_latest(cat)
    missing = [it for it in items if not latest.get(it["bbbs"], {}).get("ok")]
    todo = [(it, idx[it["bbbs"]]) for it in missing if it["bbbs"] in idx]
    log(f"[{cat}] 缺口 {len(missing)}，索引可补 {len(todo)}，索引外 {len(missing)-len(todo)}")

    out_dir = os.path.join(DL_ROOT, cat)
    os.makedirs(out_dir, exist_ok=True)
    stats = {"lock": threading.Lock(), "ok": 0, "fail": 0, "done": 0, "total": len(todo)}
    queue = list(todo)

    def worker(wid):
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131"})
        pi = wid % len(PROXIES)
        while queue:
            try:
                it, r = queue.pop(0)
            except IndexError:
                break
            # 双检：别的进程（gap_fetch/官方下载）可能刚补上
            _, lat = load_latest(cat)
            if lat.get(it["bbbs"], {}).get("ok"):
                with stats["lock"]:
                    stats["done"] += 1
                continue
            content = None
            for p in [r.get("path")] + ([r["alias"]] if r.get("alias") else []):
                if not p:
                    continue
                content, pi = fetch(pi, p, s)
                if content:
                    break
            with _prog_lock:
                if content:
                    h = hashlib.sha256(content).hexdigest()
                    hash_ok = h == r.get("hash")
                    ext = sniff_ext(content, r.get("path") or "")
                    name = sanitize(f"{it.get('flxz') or cat}_{it['title']}_{it.get('gbrq','')}_有效")
                    fpath = os.path.join(out_dir, name + "." + ext)
                    n = 1
                    while os.path.exists(fpath) and os.path.getsize(fpath) > 2000 and n < 5:
                        fpath = os.path.join(out_dir, f"{name}_{n}.{ext}")
                        n += 1
                    if not (os.path.exists(fpath) and os.path.getsize(fpath) > 2000):
                        with open(fpath, "wb") as f:
                            f.write(content)
                    with open(prog_path, "a", encoding="utf-8") as pf:
                        pf.write(json.dumps({"bbbs": it["bbbs"], "ok": True,
                                             "file": os.path.basename(fpath),
                                             "source": "lawtext", "bytes": len(content),
                                             "sha256_ok": hash_ok},
                                            ensure_ascii=False) + "\n")
                    with stats["lock"]:
                        stats["ok"] += 1
                else:
                    with open(prog_path, "a", encoding="utf-8") as pf:
                        pf.write(json.dumps({"bbbs": it["bbbs"], "ok": False,
                                             "error": "proxy fetch failed"},
                                            ensure_ascii=False) + "\n")
                    with stats["lock"]:
                        stats["fail"] += 1
                with stats["lock"]:
                    stats["done"] += 1
                    d, o, f_ = stats["done"], stats["ok"], stats["fail"]
            if d % 20 == 0:
                log(f"  {d}/{stats['total']} ok={o} fail={f_}")
            time.sleep(0.3 + random.random() * 0.4)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(workers)]
    for t in threads:
        t.start()
        time.sleep(0.5)
    for t in threads:
        t.join()
    log(f"[{cat}] 完成: 补 {stats['ok']}, 失败 {stats['fail']} / {stats['total']}")


if __name__ == "__main__":
    main()
