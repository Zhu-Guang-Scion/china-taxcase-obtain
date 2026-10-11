# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""修复 structure_extract v1 误删的 front matter 附件 URL 列表。
对「有 附件: 字段但无缩进 URL 行」的 md：重访原文链接，重提附件 URL，插回 附件: 行之后。
断点：work/taxcase/progress/repair_att.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxcase_scrape as t

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例"))
PROG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress", "repair_att.jsonl")
os.makedirs(os.path.dirname(PROG), exist_ok=True)


def main():
    # 审查修复：加 main 守卫 —— 原先 import 即开始遍历全库并重访原文链接
    done = set()
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r.get("ok"):
                    done.add(r["file"])
            except json.JSONDecodeError:
                pass

    n_fixed = n_skip = n_fail = 0
    out = open(PROG, "a", encoding="utf-8")
    for dp, _, fs in os.walk(ROOT):
        for fn in sorted(fs):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, ROOT)
            if rel in done:
                continue
            txt = open(p, encoding="utf-8").read()
            m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
            if not m:
                continue
            fm = m.group(1)
            if not re.search(r"^附件:\s*$", fm, re.M):
                continue
            if re.search(r"^附件:\n\s+- ", fm, re.M):
                n_skip += 1
                out.write(json.dumps({"file": rel, "ok": True, "note": "intact"}) + "\n")
                continue
            url_m = re.search(r"^原文链接: (\S+)", fm, re.M)
            if not url_m:
                continue
            page_url = url_m.group(1)
            resp = t.polite_get(page_url, 2.2)
            atts = []
            if resp is not None:
                atts = re.findall(r'href="([^"]+\.(?:pdf|docx?|xlsx?)[^"]*)"', resp.text, re.I)
                atts = [a.replace("&amp;", "&") for a in atts]
                from urllib.parse import urljoin
                atts = [urljoin(page_url, a) for a in atts]
            if not atts:
                # 详情提取器再试
                if resp is not None:
                    d = t.extract_detail(resp.text, page_url, "", "")
                    atts = d.get("attachments", []) if d else []
            if atts:
                lines = fm.split("\n")
                idx = next(i for i, l in enumerate(lines) if l.startswith("附件:"))
                new_lines = lines[:idx + 1] + [f"  - {a}" for a in atts] + lines[idx + 1:]
                new_txt = "---\n" + "\n".join(new_lines) + "\n---\n" + txt[m.end():]
                open(p, "w", encoding="utf-8", newline="\n").write(new_txt)
                n_fixed += 1
                out.write(json.dumps({"file": rel, "ok": True, "atts": len(atts)}) + "\n")
            else:
                n_fail += 1
                out.write(json.dumps({"file": rel, "ok": False, "err": "no att found"}) + "\n")
            out.flush()
    out.close()
    print(f"fixed={n_fixed} intact_skip={n_skip} fail={n_fail}")



if __name__ == "__main__":
    main()
