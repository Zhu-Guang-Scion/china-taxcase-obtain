# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""精化清理：删除无参考价值文件（无具体事项/事由叙述的告示）。

*** 警告：本脚本 v1 已被 quality_prune2.py 取代（审查修复标注）——
*** v2 的 KEEP_COLUMNS 更全（含"裁判文书"等），误用本 v1 重跑会删掉
*** 判决书等应保留文件。新任务请用 quality_prune2.py；本文件仅留作
*** pruned_files.json（v1 留档）的规则追溯，不要再执行 --go。

规则（用户标准：须有具体事项、事由、处罚原因）：
  删除类：
    - 信用浙江索引型（详情未取，纯文号/相对人/日期）
    - 催报催缴/文书送达公告（程序性送达，无案情）——但含「附件全文」的保留
    - 欠税公告（名单+金额）
    - 处罚公示类：违法事实/处罚内容叙述 <30 中文字符（只剩 文号+法条+金额 模式）
  保留类：
    - 12366 问答/办税流程/表单、税案通报/典型案例/判决/指导案例/检察
    - 失信公布（含主要违法事实叙述）——事实叙述 <30 也删
    - 处罚公示：事实叙述 ≥30 字，或正文含附件全文
用法： python quality_prune.py [--go]    # 不带 --go 仅统计
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, argparse, shutil

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例"))
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

FACT_SECTIONS = ["违法事实", "主要违法事实", "案件事实", "处罚事由", "违法事实及依据",
                 "处罚内容", "事实与理由", "违法情形"]
KEEP_COLUMNS = ["税案通报", "典型案例", "指导性案例", "合规典型", "以案释法", "检察",
                "依法惩治", "会计信息质量检查", "财会监督检查", "涉税行政处罚", "12366",
                "案例解读", "税务合规", "公益诉讼", "专项监督", "打击骗取留抵退税",
                "行政处罚决定",
                # 审查修复：防止误用 v1 重跑时删掉判决书（v2 已含，v1 补齐兜底）
                "裁判文书"]
DEL_COLUMNS = ["信用浙江", "欠税公告"]


def fm_get(fml, key):
    m = re.search(rf"^{key}:\s*\"?([^\"\n]*)\"?", fml, re.M)
    return m.group(1).strip() if m else ""


def facts_text(body):
    """提取事实类小节文本（含小节标题下内容直到下一小节）"""
    out = []
    for kw in FACT_SECTIONS:
        for m in re.finditer(rf"#{{1,3}}\s*{kw}|\*\*{kw}\*\*|{kw}[:：]", body):
            seg = body[m.start():]
            stop = re.search(r"\n#{1,3}\s|\n-\s\*\*", seg[5:])
            if stop:
                seg = seg[:5 + stop.start()]
            out.append(seg)
    txt = "\n".join(out)
    txt = re.sub(r"#{1,6}|\*|-|｜|:", " ", txt)
    return re.sub(r"\s", "", txt)


def has_attachment_full(body):
    return ("附件（" in body and len(re.findall(r"[\u4e00-\u9fff]", body)) >= 600)


def decide(column, region, body):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    facts = facts_text(body)
    fl = len(re.findall(r"[\u4e00-\u9fff]", facts))
    # 1) 永久保留栏目
    for k in KEEP_COLUMNS:
        if k in column:
            return "KEEP", fl, "keep-column"
    # 2) 永久删除栏目
    for k in DEL_COLUMNS:
        if k in column:
            return "DEL", fl, "index-column"
    # 3) 送达类：程序性公告，除非含附件全文
    if "送达公告" in column or "催缴" in column or "催报" in column:
        if has_attachment_full(body):
            return "KEEP", fl, "attachment-full"
        return "DEL", fl, "procedural"
    # 4) 随机抽查：名单类删除（除非含结果叙述）
    if "随机抽查" in column:
        return ("KEEP" if fl >= 50 else "DEL"), fl, "spot-check"
    # 5) 失信公布：需事实叙述
    if "失信" in column:
        return ("KEEP" if fl >= 30 or cjk >= 500 else "DEL"), fl, "dishonesty"
    # 6) 一般处罚公示（含信用广东/山东/上海/四川/北京/深圳…）：事实叙述门槛
    if has_attachment_full(body) and fl >= 30:
        return "KEEP", fl, "attachment-full"
    if fl >= 30:
        return "KEEP", fl, "facts>=30"
    if cjk >= 800 and fl >= 15:
        return "KEEP", fl, "long-but-thin-facts"
    return "DEL", fl, "facts<30"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args()
    stats = {}
    to_del = []
    for dp, _, fs in os.walk(ROOT):
        for fn in sorted(fs):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            txt = open(p, encoding="utf-8").read()
            m = FM_RE.match(txt)
            fml = m.group(1) if m else ""
            col = fm_get(fml, "栏目")
            reg = fm_get(fml, "地区")
            body = txt[m.end():] if m else txt
            verdict, fl, why = decide(col, reg, body)
            key = f"{reg}|{col}"
            stats.setdefault(key, {}).setdefault(verdict, 0)
            stats[key][verdict] += 1
            if verdict == "DEL":
                to_del.append((p, why, fl))
    print(f"{'删除' if args.go else '将删除'} {len(to_del)} 件")
    for k, v in sorted(stats.items(), key=lambda x: -sum(x[1].values())):
        print(f"  {k}: keep={v.get('KEEP',0)} del={v.get('DEL',0)}")
    if args.go:
        # 删除 + 留档清单
        log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pruned_files.json")
        with open(log, "w", encoding="utf-8") as f:
            json.dump([{"file": os.path.relpath(p, ROOT), "why": w, "facts_len": fl}
                       for p, w, fl in to_del], f, ensure_ascii=False, indent=1)
        for p, _, _ in to_del:
            os.remove(p)
        # 清空目录清理
        for dp, dns, fs in os.walk(ROOT, topdown=False):
            if not os.listdir(dp) and dp != ROOT:
                os.rmdir(dp)
        print("已删除并留档 pruned_files.json")


if __name__ == "__main__":
    main()
