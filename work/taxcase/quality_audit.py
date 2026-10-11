# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""全库信息量审计：识别「无参考价值」文件（只有金额+法条、无具体事项/事由/处罚原因叙述）。
分级：
  RICH   = 有违法事实/事由叙述（≥120字情节文本）或全文性文书（判决/决定书全文/案例叙述）
  THIN   = 有一定情节线索但叙述不足（30-120字）
  INDEX  = 纯元数据/模板公告（文书号+相对人+日期，无情节）
输出：quality_report.json + 各栏目分级统计
用法： python quality_audit.py [--prune]   # --prune 删除 INDEX（保留清单留档）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, argparse, shutil
from collections import Counter, defaultdict

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例"))

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

# 情节叙述标志：案件叙事常见触发词
NARRATIVE_MARKERS = [
    "经查", "经检查发现", "检查发现", "违法事实", "存在以下违法", "经核实",
    "查明", "涉案", "手段", "通过.*方式", "案件事实", "基本情况",
    "经审理查明", "本院认为", "上述事实", "证据",
]
# 模板/程序性公告特征（无情节）
TEMPLATE_MARKERS = [
    "催报", "催缴", "限期缴纳", "尚未申报", "责令限期", "送达公告", "送达.*公告",
]
META_ONLY_PATTERNS = [
    r"^# .+\n+(- \*\*.+\*\*：.*)+$",   # 正文只有字段列表
]


def narrative_len(body):
    """粗估情节叙述量：命中叙述标志的句子总字数"""
    txt = re.sub(r"\s", "", body)
    total = 0
    for m in NARRATIVE_MARKERS:
        for mm in re.finditer(m, txt):
            # 取标志词后 200 字窗口内的内容量（去重近似：直接按窗口计一次）
            total = max(total, min(200, len(txt) - mm.start()))
    # 更简单可靠的量：正文中「事实/事由/手段/经查」段落长度
    for kw in ["违法事实", "处罚事由", "案件事实", "主要违法事实", "事实与理由", "经查", "经审理查明"]:
        for mm in re.finditer(kw, body):
            seg = body[mm.start():mm.start() + 600]
            seg = re.sub(r"^#{1,6}\s*", "", seg)
            # 段落到下一个小节为止
            stop = re.search(r"\n#{1,3} ", seg[10:])
            if stop:
                seg = seg[:10 + stop.start()]
            n = len(re.sub(r"\s", "", seg))
            total = max(total, n)
    return total


def classify(body, column):
    nl = narrative_len(body)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    # 特判栏目
    if any(k in column for k in ["税案通报", "典型案例", "指导性案例", "合规典型", "以案释法",
                                  "检察", "依法惩治", "检查公告", "财会监督"]):
        return "RICH" if cjk >= 150 else ("THIN" if cjk >= 60 else "INDEX"), nl
    if "判决" in column or "案例解读" in column:
        return "RICH" if cjk >= 200 else "THIN", nl
    if "12366" in column:
        return "RICH", nl  # 实务问答独立价值，不按叙事判
    if any(k in column for k in ["催报", "催缴", "送达公告"]):
        # 江苏处罚决定书送达公告若含「附件全文」则 RICH
        if "附件（" in body and cjk >= 800:
            return "RICH", nl
        return ("INDEX" if nl < 60 else "THIN"), nl
    if "失信" in column:
        return ("RICH" if nl >= 80 else "INDEX"), nl
    if "欠税" in column:
        return "INDEX", nl  # 欠税名单=金额+名单，无事由
    if "信用浙江" in column:
        return "INDEX", nl  # 详情未取的索引型
    # 处罚公示类（含信用广东/山东/上海/四川/北京…）
    if nl >= 120 or cjk >= 600:
        return "RICH", nl
    if nl >= 40 or cjk >= 150:
        return "THIN", nl
    return "INDEX", nl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true")
    args = ap.parse_args()
    report = defaultdict(lambda: Counter())
    files_lvl = {}
    removed = kept = 0
    for dirpath, _, files in os.walk(ROOT):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            txt = open(p, encoding="utf-8").read()
            m = FM_RE.match(txt)
            fm = {}
            if m:
                for line in m.group(1).split("\n"):
                    mm = re.match(r"^([^\s:]+):\s*(.*)$", line)
                    if mm:
                        fm[mm.group(1)] = mm.group(2).strip().strip('"')
            body = txt[m.end():] if m else txt
            column = fm.get("栏目", "")
            region = fm.get("地区", "")
            lvl, nl = classify(body, column)
            key = f"{region}|{column}"
            report[key][lvl] += 1
            files_lvl[rel] = lvl
            if args.prune and lvl == "INDEX":
                os.remove(p)
                removed += 1
            else:
                kept += 1
    out = {k: dict(v) for k, v in sorted(report.items())}
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "quality_report.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    total_idx = sum(v.get("INDEX", 0) for v in report.values())
    total_thin = sum(v.get("THIN", 0) for v in report.values())
    total_rich = sum(v.get("RICH", 0) for v in report.values())
    print(f"RICH={total_rich} THIN={total_thin} INDEX={total_idx}")
    print("\nINDEX 占比最高的栏目：")
    for k, v in sorted(report.items(), key=lambda x: -x[1].get("INDEX", 0))[:18]:
        print(f"  {k}: {dict(v)}")


if __name__ == "__main__":
    main()
