#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""通过 gh-proxy 加速镜像把 lawtext_md 来源的地方法规升级为官方 docx（sha256 校验）。

多线程 + 断点：升级记录 append 到 flk_dl_progress_地方法规.jsonl (source=lawtext, upgraded_from=lawtext_md)
跳过已升级（最新记录 source != lawtext_md 视为已处理）。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import hashlib
import json
import os
import random
import re
import sys
import threading
import time

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


def fetch(proxies_idx, path, s, timeout=50):
    for off in range(len(PROXIES)):
        pi = (proxies_idx + off) % len(PROXIES)
        try:
            r = s.get(PROXIES[pi] + path, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 2000:
                return r.content, pi
        except Exception:
            continue
    return None, proxies_idx


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    idx = {}
    for l in open(IDX, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            idx[r["id"]] = r

    cat = "地方法规"
    items = [json.loads(l) for l in open(os.path.join(LISTS, f"flk_{cat}.jsonl"), encoding="utf-8") if l.strip()]
    prog_path = os.path.join(LISTS, f"flk_dl_progress_{cat}.jsonl")
    latest = {}
    if os.path.exists(prog_path):
        for line in open(prog_path, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    latest[rec["bbbs"]] = rec
                except Exception:
                    pass

    # 待升级 = 最新记录 source=lawtext_md 且镜像索引有
    todo = []
    for it in items:
        rec = latest.get(it["bbbs"])
        if rec and rec.get("ok") and rec.get("source") == "lawtext_md":
            if it["bbbs"] in idx:
                todo.append((it, idx[it["bbbs"]]))
    log(f"待升级 {len(todo)} 件 (md -> 官方docx)")

    out_dir = os.path.join(DL_ROOT, cat)
    stats = {"ok": 0, "fail": 0, "done": 0, "total": len(todo)}
    queue = list(todo)

    def worker(wid):
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131"})
        pidx = wid % len(PROXIES)
        while queue:
            try:
                it, r = queue.pop(0)
            except IndexError:
                break
            paths = [r.get("path")] + ([r["alias"]] if r.get("alias") else [])
            content = None
            for p in paths:
                if p:
                    content, pidx = fetch(pidx, p, s)
                    if content:
                        break
            with _prog_lock:
                if content:
                    h = hashlib.sha256(content).hexdigest()
                    hash_ok = h == r.get("hash")
                    name = sanitize(f"{it.get('flxz') or cat}_{it['title']}_{it.get('gbrq','')}_有效")
                    fpath = os.path.join(out_dir, name + ".docx")
                    n = 1
                    while os.path.exists(fpath) and os.path.getsize(fpath) > 2000 and n < 5:
                        fpath = os.path.join(out_dir, f"{name}_{n}.docx")
                        n += 1
                    with open(fpath, "wb") as f:
                        f.write(content)
                    with open(prog_path, "a", encoding="utf-8") as pf:
                        pf.write(json.dumps({"bbbs": it["bbbs"], "ok": True,
                                             "file": os.path.basename(fpath),
                                             "source": "lawtext", "bytes": len(content),
                                             "sha256_ok": hash_ok,
                                             "upgraded_from": "lawtext_md"},
                                            ensure_ascii=False) + "\n")
                    stats["ok"] += 1
                else:
                    with open(prog_path, "a", encoding="utf-8") as pf:
                        pf.write(json.dumps({"bbbs": it["bbbs"], "ok": True,
                                             "source": "lawtext_md",
                                             "note": "upgrade_fetch_failed_keep_md"},
                                            ensure_ascii=False) + "\n")
                    stats["fail"] += 1
                stats["done"] += 1
                d, o, f_ = stats["done"], stats["ok"], stats["fail"]
            if d % 100 == 0:
                log(f"进度 {d}/{stats['total']} 升级{o} 失败{f_}")
            time.sleep(0.15 + random.random() * 0.25)

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(workers)]
    for t in threads:
        t.start()
        time.sleep(0.5)
    for t in threads:
        t.join()
    log(f"结束: 升级 {stats['ok']}, 失败 {stats['fail']} / {stats['total']}")


if __name__ == "__main__":
    main()
