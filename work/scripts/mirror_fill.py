#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""用 lawtext 镜像 docx 按 bbbs 补齐 flk 官方下载缺口。

镜像文件名格式: {title}_{gbrq_compact}_{bbbs}.docx  (gbrq 如 20210610)
输出到 work/downloads/flk/<cat>/，命名与官方下载一致: {flxz}_{title}_{gbrq}_{status}.docx
进度记录进对应 flk_dl_progress_<cat>.jsonl (source=lawtext)。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import glob
import json
import os
import re
import shutil
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
DL_ROOT = os.path.join(ROOT, "downloads", "flk")
SXX_MAP = {1: "已废止", 2: "已修改", 3: "有效", 4: "尚未生效"}


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name.strip().rstrip(".")[:100] or "unnamed"


def load_progress(cat):
    """返回 (path, done_ok, md_sourced)。md_sourced = 最新记录 ok 且 source=lawtext_md（可升级）。"""
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
    done = {b: r.get("ok", False) for b, r in latest.items()}
    md_sourced = {b for b, r in latest.items()
                  if r.get("ok") and r.get("source") == "lawtext_md"}
    return path, done, md_sourced


def main():
    # 收集镜像 docx: bbbs -> path
    mirrors = []
    for base in [os.path.join(ROOT, "..", "mirrors", "law-flk-vol1", "docx"),
                 os.path.join(ROOT, "..", "mirrors", "legal-data-docx")]:
        base = os.path.abspath(base)
        if os.path.isdir(base):
            mirrors.append(base)
    index = {}
    for base in mirrors:
        for fp in glob.glob(os.path.join(base, "**", "*.docx"), recursive=True):
            fn = os.path.splitext(os.path.basename(fp))[0]
            m = re.search(r"([0-9a-f]{32})$", fn)
            if m:
                index[m.group(1)] = fp
    print(f"镜像索引: {len(index)} 个 docx (来自 {len(mirrors)} 个镜像源)")

    total_filled = 0
    for cat in ["宪法", "法律", "行政法规", "监察法规", "地方法规", "司法解释"]:
        list_path = os.path.join(LISTS, f"flk_{cat}.jsonl")
        if not os.path.exists(list_path):
            continue
        prog_path, done, md_sourced = load_progress(cat)
        items = [json.loads(l) for l in open(list_path, encoding="utf-8") if l.strip()]
        # 待补 = 未ok + lawtext_md 来源（升级为官方 docx）
        missing = [it for it in items if not done.get(it["bbbs"])]
        upgrade = [it for it in items if it["bbbs"] in md_sourced]
        filled = 0
        mirror_hit = 0
        upgraded = 0
        with open(prog_path, "a", encoding="utf-8") as pf:
            for it in missing + upgrade:
                bbbs = it["bbbs"]
                src = index.get(bbbs)
                if not src:
                    continue
                out_dir = os.path.join(DL_ROOT, cat)
                os.makedirs(out_dir, exist_ok=True)
                status = SXX_MAP.get(it.get("sxx"), "未知")
                name = sanitize(f"{it.get('flxz') or cat}_{it['title']}_{it.get('gbrq','')}_{status}")
                dst = os.path.join(out_dir, name + ".docx")
                n = 1
                while os.path.exists(dst) and os.path.getsize(dst) < 2000 and n < 5:
                    dst = os.path.join(out_dir, f"{name}_{n}.docx")
                    n += 1
                if os.path.exists(dst) and os.path.getsize(dst) > 2000:
                    pass  # 已有文件，仅记进度
                else:
                    shutil.copy2(src, dst)
                size = os.path.getsize(dst) if os.path.exists(dst) else 0
                if size > 2000:
                    is_upgrade = bbbs in md_sourced and bbbs not in {m["bbbs"] for m in missing}
                    pf.write(json.dumps({"bbbs": bbbs, "ok": True,
                                         "file": os.path.basename(dst),
                                         "source": "lawtext", "bytes": size,
                                         **({"upgraded_from": "lawtext_md"} if is_upgrade else {})},
                                        ensure_ascii=False) + "\n")
                    filled += 1
                    mirror_hit += 1
                    if is_upgrade:
                        upgraded += 1
        total_filled += filled
        print(f"[{cat}] 缺口 {len(missing)}，镜像补齐 {filled}（其中升级md来源 {upgraded}），"
              f"剩 {len(missing)-filled}")
    print(f"共补齐 {total_filled}")


if __name__ == "__main__":
    main()
