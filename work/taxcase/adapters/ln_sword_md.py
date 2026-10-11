# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
辽宁 sword 处罚公示 + 主站失信公布 → md 入库（含质量门槛）
==========================================================
输入：progress/ln_sword.jsonl（平台处罚）、progress/ln_sx.jsonl（主站失信）
输出：
  lawlibrary/专题/税务案例/辽宁省/行政处罚公示/*.md
  lawlibrary/专题/税务案例/辽宁省/重大税收违法失信公布/*.md
质量门槛（强制）：quality_prune.decide() 判定，DEL 不入库。
用法： python ln_sword_md.py [--kind xzcf|sx|all]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, argparse, hashlib
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402
from taxcase_scrape import safe_filename  # noqa: E402

LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例", "辽宁省"))
OUT_XZCF = os.path.join(LIB, "行政处罚公示")
OUT_SX = os.path.join(LIB, "重大税收违法失信公布")
PROG_XZCF = os.path.join(ROOT, "progress", "ln_sword.jsonl")
PROG_SX = os.path.join(ROOT, "progress", "ln_sx.jsonl")
PLATFORM_URL = "https://etax.liaoning.chinatax.gov.cn:8090/sword?ctrl=XzzfgsptHomeCtrl_index"
TODAY = date.today().isoformat()


def nz(v):
    return "" if v is None else str(v).strip()


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                if r.get("ok"):
                    out.append(r)
            except json.JSONDecodeError:
                pass
    return out


def write_md(path, body):
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def conv_xzcf():
    os.makedirs(OUT_XZCF, exist_ok=True)
    recs = load_jsonl(PROG_XZCF)
    stats = {"keep": 0, "del": 0, "skip_exists": 0}
    reasons = {}
    seen = set()
    for r in recs:
        t = r["rec"]
        key = r["key"]
        if key in seen:
            continue
        seen.add(key)
        ajmc = nz(t.get("ajmc"))
        nsrmc = nz(t.get("nsrmc"))
        cfrq = nz(t.get("cfrq"))
        title = ajmc or (nsrmc + "-税务行政处罚")
        lines = ["# " + title, ""]
        rows = [
            ("行政处罚决定书文号", nz(t.get("xzcfjdswh"))),
            ("处罚类别", nz(t.get("cflb"))),
            ("案件名称", ajmc),
            ("行政相对人名称", nsrmc),
            ("统一社会信用代码/纳税人识别号", nz(t.get("nsrsbh"))),
            ("法定代表人", nz(t.get("fddbrxm"))),
            ("处罚机关", nz(t.get("cfjg"))),
            ("处罚日期", cfrq),
        ]
        for k, v in rows:
            if v:
                lines.append(f"- **{k}**：{v}")
        lines += ["", "## 违法事实", "", nz(t.get("wfsd")) or "（未公示）", "",
                  "## 处罚依据", "", nz(t.get("swxzcfyj")) or "（未公示）", "",
                  "## 处罚结果", "", nz(t.get("cfjd")) or "（未公示）"]
        fkje = nz(t.get("fkje"))
        if fkje:
            lines.append(f"\n罚款金额：{fkje} 元")
        body = "\n".join(lines) + "\n"
        # 质量门槛
        verdict, fl, why = decide("行政处罚公示", "辽宁省", body)
        if verdict != "KEEP":
            stats["del"] += 1
            reasons[why] = reasons.get(why, 0) + 1
            continue
        fn = f"{cfrq or 'nodate'}_{safe_filename(title)}.md"
        path = os.path.join(OUT_XZCF, fn)
        if os.path.exists(path):
            stats["skip_exists"] += 1
            continue
        fm = ("---\n"
              f"title: \"{title.replace(chr(34), '')}\"\n"
              "来源机关: \"国家税务总局辽宁省税务局\"\n"
              "栏目: \"行政处罚公示\"\n"
              "地区: \"辽宁省\"\n"
              f"发布日期: {cfrq or 'nodate'}\n"
              "原文来源: \"辽宁省税务局行政执法信息公示平台\"\n"
              f"抓取日期: {TODAY}\n"
              f"原文链接: {PLATFORM_URL}\n"
              f"决定书文号: \"{nz(t.get('xzcfjdswh')).replace(chr(34), '')}\"\n"
              f"记录KEY: {hashlib.md5(key.encode()).hexdigest().upper()}\n"
              "---\n\n")
        write_md(path, fm + body)
        stats["keep"] += 1
    print("[xzcf]", stats, "del_reasons:", reasons)
    return stats


def conv_sx():
    os.makedirs(OUT_SX, exist_ok=True)
    recs = load_jsonl(PROG_SX)
    stats = {"keep": 0, "del": 0, "skip_exists": 0}
    reasons = {}
    seen = set()
    for r in recs:
        t = r["rec"]
        key = r["key"]
        if key in seen:
            continue
        seen.add(key)
        nsrmc = nz(t.get("nsrmc"))
        fbrq = nz(t.get("fbrq")) or nz(t.get("fbsj"))
        title = nsrmc or f"重大税收违法失信主体_{key}"
        lines = ["# " + title + "（重大税收违法失信主体）", ""]
        rows = [
            ("纳税人名称", nsrmc),
            ("纳税人识别号或统一社会信用代码", nz(t.get("nsrsbh"))),
            ("注册地址", nz(t.get("zcdz"))),
            ("法定代表人（负责人）", nz(t.get("fddbr")) +
                (("（" + nz(t.get("fddbr_xb")) + "）") if nz(t.get("fddbr_xb")) else "")),
            ("案件性质", nz(t.get("ajxz"))),
        ]
        for k, v in rows:
            if v:
                lines.append(f"- **{k}**：{v}")
        lines += ["", "## 主要违法事实", "", nz(t.get("wfsd")) or "（未公示）", "",
                  "## 相关法律依据及税务处理处罚情况", "", nz(t.get("cfyj_cl")) or "（未公示）"]
        body = "\n".join(lines) + "\n"
        verdict, fl, why = decide("重大税收违法失信公布", "辽宁省", body)
        if verdict != "KEEP":
            stats["del"] += 1
            reasons[why] = reasons.get(why, 0) + 1
            continue
        fn = f"{fbrq or 'nodate'}_{safe_filename(title)}.md"
        path = os.path.join(OUT_SX, fn)
        if os.path.exists(path):
            stats["skip_exists"] += 1
            continue
        fm = ("---\n"
              f"title: \"{title.replace(chr(34), '')}\"\n"
              "来源机关: \"国家税务总局辽宁省税务局\"\n"
              "栏目: \"重大税收违法失信公布\"\n"
              "地区: \"辽宁省\"\n"
              f"发布日期: {fbrq or 'nodate'}\n"
              "原文来源: \"辽宁省税务局重大税收违法失信主体公布栏\"\n"
              f"抓取日期: {TODAY}\n"
              f"原文链接: {nz(t.get('url'))}\n"
              f"记录KEY: {hashlib.md5(('sx' + key).encode()).hexdigest().upper()}\n"
              "---\n\n")
        write_md(path, fm + body)
        stats["keep"] += 1
    print("[sx]", stats, "del_reasons:", reasons)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="all", choices=["xzcf", "sx", "all"])
    args = ap.parse_args()
    if args.kind in ("xzcf", "all"):
        conv_xzcf()
    if args.kind in ("sx", "all"):
        conv_sx()


if __name__ == "__main__":
    main()
