# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""税务案例要素结构化提取（规则版 v1）
参考结构：CAIL/LeCaRD 字段约定 + 实务要素表（案件/税种/违法类型/金额/法条/处罚/倍数/移送/行业/程序）
输出：
  1. 每件 md 的 front matter 追加 `标签:` 与 `要素:` 块（幂等：已有则替换）
  2. taxcase_structured.jsonl —— 全库结构化行（微调/RAG用）
用法： python structure_extract.py [--no-write-md]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, argparse, hashlib

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题", "税务案例"))
OUT_JSONL = os.path.join(ROOT, "taxcase_structured.jsonl")

# ---------- 词典 ----------

TAX_TYPES = [
    "增值税", "消费税", "企业所得税", "个人所得税", "城市维护建设税", "城建税",
    "印花税", "土地增值税", "房产税", "城镇土地使用税", "契税", "车船税",
    "资源税", "环境保护税", "耕地占用税", "车辆购置税", "关税", "出口退税",
    "烟叶税", "船舶吨税", "教育费附加", "地方教育附加", "残保金",
]
VIOLATIONS = [
    ("虚开发票", r"虚开(?:增值税专用发票|增值税普通发票|发票|农产品收购发票|用于骗取出口退税发票)"),
    ("骗取出口退税", r"骗取出口退税|骗(取|享)出口退税款|买单配票|假报出口"),
    ("偷税", r"偷税|偷逃(?:税款|税)|进行虚假纳税申报|隐匿(?:收入|销售收入|账簿)、|私设账簿|两套账"),
    ("私户隐匿收入", r"个人(?:账户|银行账户|账户)收(?:款|取|入)|私户|私人账户|微信|支付宝收款|收取.*现金未入账"),
    ("未按规定申报", r"未按(?:时|期|规定)*(?:办理|进行)?(?:纳税)?申报|未申报|逾期申报|未按期申报"),
    ("编造虚假计税依据", r"编造虚假计税依据"),
    ("未履行扣缴义务", r"未(按规定)?代扣代缴|扣缴义务人未|未履行代扣代缴|未履行扣缴"),
    ("发票违规", r"未按规定(开具|取得|保管|存放|报送)发票|违规(使用|开具)发票|发票违章|取得不符合规定的发票| accepting"),
    ("逃避追缴欠税", r"逃避追缴欠税|转移(?:或|、)?隐匿财产"),
    ("骗取税收优惠", r"骗取(?:税收优惠|留抵退税|留抵税额)|违规享受(?:税收优惠|加计扣除|小微|小规模纳税人)|虚假填报.*优惠|骗享"),
    ("抗税", r"抗税|暴力抗税"),
    ("虚假列支", r"虚列(?:成本|支出|费用)|多列(?:支出|进项)|白条入账|编造(?:虚假)?计税依据|取得虚开发票.*抵扣|违规抵扣"),
    ("未按规定报送资料", r"未按规定(报送|提供|保存)(?:有关|纳税|账簿|凭证|资料)"),
    ("未按规定设置账簿", r"未按规定设置(账簿|账册)|未按照规定设置账簿"),
]
INDUSTRIES = [
    ("建筑安装", r"建筑(?:工程|安装|施工)|建设工程|施工企业|工程款|劳务分包"),
    ("房地产", r"房地产|商品房|楼盘|置业|置业|地产"),
    ("商贸", r"贸易|商贸|商行|百货|电子商务|电商|网店|直播带货|网络主播"),
    ("制造", r"制造|制品|加工|服饰|服装|食品|纺织|五金|机械|电子|材料|科技有限|光电|汽车零部件"),
    ("医药医疗", r"医药|药业|医疗|器械|门诊|诊所|药品"),
    ("餐饮住宿", r"餐饮|饭店|酒店|住宿|餐厅|食品经营"),
    ("教育培训", r"教育培训|培训学校|教育科技|幼儿园|语言培训|艺术培训|课外培训|驾校"),
    ("交通运输物流", r"运输|物流|货运|仓储|快递"),
    ("金融投资", r"金融|投资管理|基金|资产管理|融资|担保|小额贷款"),
    ("文化娱乐", r"文化传播|文化传媒|娱乐|影视|广告"),
    ("农业", r"农业|种植|养殖|农产品|合作社"),
    ("中介服务", r"代理记账|税务师事务所|会计师事务所|中介|咨询"),
]
LAW_PATTERNS = [
    r"《[^》]{2,30}》第[一二三四五六七八九十百零\d]+条(?:第[一二三四五六七八九十\d]+款)?(?:第[一二三四五六七八九十\d]+项)?",
    r"《[^》]{2,30}》(?:施行|实施)?(?:办法|公告)",
]
MULTI_RE = re.compile(r"([0-9０-９][0-9０-９.,，]*)\s*倍的罚款|罚款.*?([0-9０-９][0-9０-９.,，]*)\s*倍")
AMOUNT_RES = [
    ("少缴税款", r"(?:少缴|不缴|偷逃|逃避缴纳|追缴)(?:税款|各项税款)?[^。；]{0,25}?([0-9][0-9,，.]*\.?[0-9]*)\s*万?元"),
    ("罚款金额", r"(?:罚款|处以罚款|并处罚款|处罚款)[^。；]{0,30}?([0-9][0-9,，.]*\.?[0-9]*)\s*万?元"),
    ("价税合计", r"价税合计[^。；]{0,20}?([0-9][0-9,，.]*\.?[0-9]*)\s*万?元"),
    ("涉案金额", r"涉案(?:金额|税款)[^。；]{0,15}?([0-9][0-9,，.]*\.?[0-9]*)\s*万?元"),
]
PROCEDURE_MAP = {
    "行政处罚公示": "行政处罚（稽查/处罚决定）",
    "行政处罚公示（信用广东）": "行政处罚（稽查/处罚决定）",
    "税案通报": "稽查通报（新闻发布）",
    "文书送达公告": "文书公告送达（催报催缴/限期缴纳）",
    "稽查公布": "稽查随机抽查公示",
    "处罚决定书送达公告": "处罚决定书公告送达",
    "行政复议公告送达": "行政复议文书送达",
    "税务合规典型企业案例": "合规典型案例（正面）",
    "会计信息质量检查公告": "会计信息质量检查",
    "财会监督检查公告": "财会监督检查",
    "涉税行政处罚": "证监会行政处罚",
    "以案释法": "以案释法（普法案例）",
    "通知公告涉税案例": "通知公告涉税案例",
    "12366热点问答": "实务问答（12366）",
    "12366办税流程": "办税流程指南（12366）",
    "12366表证单书": "表证单书说明（12366）",
    "重大税收违法失信公布": "重大税收违法失信公布",
    "欠税公告": "欠税公告",
    "执法公告": "执法公告",
    "随机抽查公示": "稽查随机抽查公示",
    "上市公司税务披露": "上市公司税务信息披露",
}
WENSU_CAUSE_HINTS = [
    ("刑事判决", r"刑事|刑初字|刑终|刑申"),
    ("行政判决", r"行初|行终|行申|行政"),
]

FM_BLOCK_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def norm_num(s):
    return s.replace("，", "").replace(",", "")


def extract(text, fm):
    body = text
    tags, elem = {}, {}
    elem["税种"] = [t for t in TAX_TYPES if t in body]
    viol = []
    for name, pat in VIOLATIONS:
        if re.search(pat, body):
            viol.append(name)
    elem["违法类型"] = viol
    ind_body = re.sub(r"教育费附加|地方教育附加|教育附加", "", body[:3000])  # 防行业误匹配
    ind = []
    for name, pat in INDUSTRIES:
        if re.search(pat, ind_body):
            ind.append(name)
    elem["行业"] = ind[:4]
    laws = set()
    for pat in LAW_PATTERNS:
        for m in re.finditer(pat, body):
            laws.add(m.group(0))
    elem["适用法条"] = sorted(laws)[:10]
    m = MULTI_RE.search(body)
    if m:
        v = norm_num(m.group(1) or m.group(2))
        try:
            elem["罚款倍数"] = float(v)
        except ValueError:
            pass
    amounts = {}
    for name, pat in AMOUNT_RES:
        mm = re.search(pat, body)
        if mm:
            amounts[name] = mm.group(1)
    if amounts:
        elem["涉案金额"] = amounts
    elem["是否移送司法"] = bool(re.search(r"移送(?:公安机关|司法机关|公安部门|法院)|已追究刑事责任|被(?:依法)?判处|公安机关(?:立案|侦办)", body))
    elem["程序类型"] = PROCEDURE_MAP.get(fm.get("栏目", ""), "其他")
    # 严重度粗分
    sev = []
    if "虚开发票" in viol or "骗取出口退税" in viol:
        sev.append("重大（虚开/骗税）")
    if elem.get("是否移送司法"):
        sev.append("涉刑")
    if "偷税" in viol:
        sev.append("偷税定性")
    tags["违法类型"] = viol
    tags["税种"] = elem["税种"]
    if sev:
        tags["风险等级"] = sev
    return tags, elem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write-md", action="store_true")
    args = ap.parse_args()
    out_rows = []
    n = n_noextract = 0
    for dirpath, _, files in os.walk(ROOT):
        for fn in sorted(files):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            txt = open(p, encoding="utf-8").read()
            m = FM_BLOCK_RE.match(txt)
            if not m:
                continue
            fm = {}
            for line in m.group(1).split("\n"):
                mm = re.match(r"^([^\s:]+):\s*(.*)$", line)
                if mm:
                    fm[mm.group(1)] = mm.group(2).strip().strip('"')
            body = txt[m.end():]
            tags, elem = extract(body, fm)
            row = {
                "id": hashlib.md5((fm.get("原文链接", "") + fn).encode()).hexdigest()[:16],
                "title": fm.get("title", ""),
                "地区": fm.get("地区", ""),
                "栏目": fm.get("栏目", ""),
                "来源机关": fm.get("来源机关", ""),
                "发布日期": fm.get("发布日期", ""),
                "文号": fm.get("决定书文号", ""),
                "原文链接": fm.get("原文链接", ""),
                "文件": os.path.relpath(p, ROOT),
                "标签": tags,
                "要素": elem,
                "正文字数": len(re.sub(r"\s", "", body)),
            }
            out_rows.append(row)
            if not args.no_write_md:
                # 幂等更新 front matter：仅去掉旧的 标签/要素 两行（保留缩进续行如附件列表）
                fm_lines = [l for l in m.group(1).split("\n")
                            if not l.startswith("标签:") and not l.startswith("要素:")]
                fm_lines = [l for l in fm_lines if l.strip() != ""] + \
                           ["标签: " + json.dumps(tags, ensure_ascii=False),
                            "要素: " + json.dumps(elem, ensure_ascii=False)]
                new_txt = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
                if new_txt != txt:
                    open(p, "w", encoding="utf-8", newline="\n").write(new_txt)
            n += 1
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 统计
    from collections import Counter
    c_v = Counter(v for r in out_rows for v in r["要素"]["违法类型"])
    c_t = Counter(t for r in out_rows for t in r["要素"]["税种"])
    c_r = Counter(r["要素"]["程序类型"] for r in out_rows)
    print(f"结构化 {n} 件 -> {OUT_JSONL}")
    print("违法类型:", dict(c_v.most_common(12)))
    print("税种:", dict(c_t.most_common(10)))
    print("程序:", dict(c_r.most_common(10)))
    multi = [r["要素"]["罚款倍数"] for r in out_rows if "罚款倍数" in r["要素"]]
    print("罚款倍数提取:", len(multi), "件, 样例:", sorted(set(multi))[:10])


if __name__ == "__main__":
    main()
