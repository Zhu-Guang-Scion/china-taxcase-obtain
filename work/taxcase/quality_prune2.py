# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""质量门禁 v2（更严）：要求「案例经过（含具体性）+ 处罚结果」双要素。
v1 教训：30 字门槛挡不住——①法条+金额凑字数（信用广东型）②分类模板句超30字（云南/湖南 cfsy 型）
        ③事实段落有但无任何数字/单位（上海短语型）。
v2 规则：
  KEEP 条件（处罚公示类/失信类）：
    (a) 案情具体性：事实段 ≥30字 且 （≥2个数字 + 单位词） 或 （≥80字 且 ≥1数字 且 含行为动词）
    (b) 处罚结果：正文含 结果要素（罚款/追缴/没收/移送/判处/裁定/停止办理/纳入/吊销/公告送达视为送达除外）
  叙事类栏目（通报/案例/判决/问答/流程/表单/部委）保持 KEEP（其本身即全文叙事）。
  程序性栏目（送达/催缴/欠税）沿用 v1（附件全文+具体性才留）。
用法： python quality_prune2.py [--go]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, argparse

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例"))
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)

NARRATIVE_KEEP = ["税案通报", "典型案例", "指导性案例", "合规典型", "以案释法", "检察",
                  "依法惩治", "会计信息质量检查", "财会监督检查", "涉税行政处罚", "12366",
                  "案例解读", "税务合规", "公益诉讼", "专项监督", "打击骗取留抵退税",
                  "行政处罚决定", "裁判文书", "税案通报", "批复", "税函", "答复",
                  "税务媒体", "专栏", "评析"]  # R10: 批复/函件=官方问答型富文本；媒体专栏=叙事性评析
PROCEDURAL = ["送达公告", "催缴", "催报", "欠税公告"]

FACT_KWS = ["违法事实", "主要违法事实", "案件事实", "处罚事由", "违法事实及处罚依据",
            "违法事实及处理处罚", "违法情形", "经查"]
OUTCOME_KWS = ["处罚结果", "处理处罚", "处理结果", "处罚决定", "裁量", "判决结果", "处罚内容"]
OUTCOME_MARK = re.compile(r"罚款|追缴|没收|移送|判处|裁定|停止办理|纳入|吊销|责成|不予处罚|免予处罚|公告送达")
UNIT_RE = re.compile(r"万?元|份|倍|%|税率|车|张|笔|条|人")
VERB_RE = re.compile(r"开具|取得|接受|收取|隐匿|虚开|抵扣|申报|入账|转给|勾结|伪造|篡改|"
                     "编造|冒用|骗取|逃避|偷逃|不报|隐瞒|冲抵|代开|变更|注销|冲红")


def fm_get(fml, key):
    m = re.search(rf"^{key}:\s*\"?([^\"\n]*)\"?", fml, re.M)
    return m.group(1).strip() if m else ""


def section_text(body, kws):
    out = []
    for kw in kws:
        for m in re.finditer(rf"#{{1,3}}\s*{kw}|\*\*{kw}\*\*", body):
            seg = body[m.start():]
            stop = re.search(r"\n#{1,3}\s|\n-\s\*\*", seg[5:])
            if stop:
                seg = seg[:5 + stop.start()]
            out.append(seg)
    t = re.sub(r"#{1,6}|\*|-|｜|:|：", "", "\n".join(out))
    return re.sub(r"\s", "", t)


def facts_specific(facts):
    n = len(facts)
    if n < 30:
        return False, "facts<30"
    digits = len(re.findall(r"\d", facts))
    has_unit = bool(UNIT_RE.search(facts))
    if digits >= 2 and has_unit:
        return True, "digits+unit"
    if n >= 80 and digits >= 1 and VERB_RE.search(facts):
        return True, "long+verb"
    return False, f"no-specific(n={n},d={digits})"


def decide(col, region, body):
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    # 叙事类：全文文书，保留
    for k in NARRATIVE_KEEP:
        if k in col:
            return "KEEP", "narrative-column"
    # 程序类：附件全文才留（沿用 v1），且附件也要具体性
    for k in PROCEDURAL:
        if k in col:
            if "附件（" in body and cjk >= 600:
                facts = section_text(body, FACT_KWS) or re.sub(r"\s", "", body)
                ok, _ = facts_specific(facts)
                return ("KEEP" if ok else "DEL"), "procedural+att"
            return "DEL", "procedural"
    # 失信类：栏目标题本身即结果语义（确定为失信主体并公布），结果要素豁免，
    # 靠事实具体性把关（防止误杀采集截断但有具体案情的记录，如黑龙江两列表格切尾）
    if "失信" in col:
        facts = section_text(body, ["主要违法事实", "违法事实", "案件事实"] + FACT_KWS)
        ok, why = facts_specific(facts)
        return ("KEEP" if ok else "DEL"), f"dishonesty({why})"
    # 上市公司税务披露（交易所公告，R15）：公告标题即结果语义（收到决定书/补缴/保全），
    # 补税公告用「补缴/补交/滞纳金」不在通用 OUTCOME_MARK——语义词单独判；
    # 短公告正文整体即事实段（税要素+金额+有效中文字数），乱码件（老 PDF 无 ToUnicode）拦下
    if "上市公司税务披露" in col:
        flat = re.sub(r"\s", "", body)
        has_tax = bool(re.search(r"税款|税额|滞纳金|罚款|增值税|消费税|所得税|营业税|附加税|印花税|房产税|土地增值税|税收保全|留抵|关税|资源税|环保税|契税|车船税|车辆购置税|税务|稽查|纳税|发票", flat))
        # 金额形态：元/万元/亿元/外币/百分比/千分位逗号串（财务金额通式）
        has_amt = bool(re.search(r"\d[\d,，.]*\s*[万亿]{0,2}(?:元|欧元|美元|港币)|\d+(?:\.\d+)?%|\d{1,3}(?:,\d{3})+", flat))
        cjk = len(re.findall(r"[\u4e00-\u9fff]", flat))
        mojibake = flat.count("\ufffd") * 10 > len(flat)
        ok = not mojibake and has_tax and ((has_amt and cjk >= 60) or cjk >= 250)
        return ("KEEP" if ok else "DEL"), "exchange-disclosure"
    # 处罚公示类（信用平台/省平台/决定书）：双要素
    facts = section_text(body, FACT_KWS)
    if not facts:  # 无明确事实节，看正文整体（某些源字段平铺）
        facts = re.sub(r"\s", "", body)[:1200]
    ok, why = facts_specific(facts)
    has_out = bool(OUTCOME_MARK.search(body))
    if ok and has_out:
        return "KEEP", f"both({why})"
    return "DEL", f"missing({why},out={has_out})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    args = ap.parse_args()
    stats, to_del = {}, []
    for dp, _, fs in os.walk(ROOT):
        for fn in sorted(fs):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            txt = open(p, encoding="utf-8").read()
            m = FM_RE.match(txt)
            fml = m.group(1) if m else ""
            col, reg = fm_get(fml, "栏目"), fm_get(fml, "地区")
            body = txt[m.end():] if m else txt
            v, why = decide(col, reg, body)
            key = f"{reg}|{col}"
            stats.setdefault(key, {}).setdefault(v, 0)
            stats[key][v] += 1
            if v == "DEL":
                to_del.append((p, why))
    print(f"{'删除' if args.go else '将删除'} {len(to_del)} 件 / 全库")
    for k, v in sorted(stats.items(), key=lambda x: -x[1].get("DEL", 0))[:22]:
        print(f"  {k[:44]:46s} keep={v.get('KEEP',0):5d} del={v.get('DEL',0):5d}")
    if args.go:
        log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pruned_files_v2.json")
        json.dump([{"file": os.path.relpath(p, ROOT), "why": w} for p, w in to_del],
                  open(log, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for p, _ in to_del:
            os.remove(p)
        for dp, dns, fs in os.walk(ROOT, topdown=False):
            if not os.listdir(dp) and dp != ROOT:
                os.rmdir(dp)
        print("已删除，留档 pruned_files_v2.json")


if __name__ == "__main__":
    main()
