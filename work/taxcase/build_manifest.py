# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""税务案例库汇总整理：manifest.csv + 统计 + 微调语料 jsonl
用法: python build_manifest.py
扫描 lawlibrary/专题/税务案例/**/*.md，解析 front matter，
- 按 原文链接 去重（重复文件改名加 .dup 后缀或记录后删除 --prune）
- 生成 manifest.csv（地区/栏目/标题/发布日期/来源机关/文件/链接/字数）
- 生成 taxcase_corpus.jsonl（微调友好：id/text/meta，正文去掉 front matter）
- 打印统计表
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, csv, json, argparse, hashlib

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例"))

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def parse_md(path):
    txt = open(path, encoding="utf-8").read()
    m = FM_RE.match(txt)
    if not m:
        return None, txt
    fm, body = {}, txt[m.end():]
    for line in m.group(1).split("\n"):
        mm = re.match(r'^([^\s:]+):\s*(.*)$', line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"')
    return fm, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true", help="删除重复文件(同原文链接保留最早)")
    args = ap.parse_args()
    rows, corpus, seen = [], [], {}
    # 先统计 URL 出现次数：平台型来源（处罚公示平台/裁判文书镜像）多条记录共用一个入口 URL，
    # 共享 URL 不参与去重（否则会把不同案件误判为重复，--prune 会整批误删——P0 审查修复）
    url_counts = {}
    _pre = []
    for dirpath, _, files in os.walk(ROOT):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            fm, body = parse_md(p)
            if fm is None:
                print("无front matter:", os.path.relpath(p, ROOT))
                continue
            _pre.append((p, fm, body))
            u = fm.get("原文链接", "")
            if u:
                url_counts[u] = url_counts.get(u, 0) + 1
    SHARED = 5  # 同一 URL 挂 >5 个文件 = 平台入口（索引型 URL），仅作字段不去重
    for p, fm, body in _pre:
            rel = os.path.relpath(p, ROOT)
            url = fm.get("原文链接", "")
            rec = {
                "地区": fm.get("地区", ""),
                "栏目": fm.get("栏目", ""),
                "标题": fm.get("title", ""),
                "发布日期": fm.get("发布日期", ""),
                "来源机关": fm.get("来源机关", ""),
                "文件": rel,
                "原文链接": url,
                "正文字数": len(re.sub(r"\s", "", body)),
            }
            # 去重键：唯一 URL→URL；共享平台 URL→URL+标题；无 URL→文件名
            if url and url_counts[url] <= SHARED:
                key = url
            elif url:
                key = url + "|" + rec["标题"]
            else:
                key = "file|" + rel
            is_dup = key in seen
            if is_dup and args.prune:
                os.remove(p)
                continue
            rec["重复"] = "是" if is_dup else ""
            if not is_dup:
                seen[key] = p
            rows.append(rec)
            corpus.append({
                "id": hashlib.md5(key.encode()).hexdigest()[:16],
                "meta": {k: fm.get(k, "") for k in
                         ("title", "来源机关", "栏目", "地区", "发布日期", "原文链接")},
                "text": body.strip(),
            })
    manifest = os.path.join(ROOT, "manifest.csv")
    with open(manifest, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["地区", "栏目", "标题", "发布日期", "来源机关",
                                          "文件", "原文链接", "正文字数", "重复"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    cj = os.path.join(ROOT, "taxcase_corpus.jsonl")
    with open(cj, "w", encoding="utf-8") as f:
        for c in corpus:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    # 统计
    stat = {}
    for r in rows:
        key = (r["地区"], r["栏目"])
        stat[key] = stat.get(key, 0) + 1
    print(f"总计 {len(rows)} 件 md → manifest.csv")
    for (reg, col), n in sorted(stat.items(), key=lambda x: -x[1]):
        print(f"  {reg} | {col}: {n}")
    print(f"微调语料: {cj} ({len(corpus)} 行)")


if __name__ == "__main__":
    main()
