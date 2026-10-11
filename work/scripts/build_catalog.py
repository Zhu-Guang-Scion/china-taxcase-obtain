# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
构建法规库多维目录索引（只读扫描 lawlibrary，输出到独立的 法规目录索引/ 文件夹）。
维度：法源层级 / 法律部门 / 主题领域(含会计审计、税务专项目录) / 地域 / 发文机关 / 年份
输出：索引总表.csv + 各维度 Markdown 目录
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import json
import os
import re
from collections import Counter, defaultdict

ROOT = os.environ.get("CHINA_LAW_WORK") or os.path.join(os.getcwd(), "work")
BASE = os.path.dirname(ROOT) if os.path.basename(ROOT) == "work" else os.getcwd()
LIB = os.path.join(BASE, "lawlibrary")
OUT = os.path.join(BASE, "法规目录索引")

PROVINCES = [
    "北京市", "天津市", "上海市", "重庆市", "河北省", "山西省", "内蒙古自治区",
    "辽宁省", "吉林省", "黑龙江省", "江苏省", "浙江省", "安徽省", "福建省",
    "江西省", "山东省", "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区",
    "海南省", "四川省", "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省",
    "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
]

def load_flfg_names():
    d = json.load(open(os.path.join(ROOT, "lists", "enumData.json"), encoding="utf-8"))
    names = {}

    def walk(node):
        if node.get("codeId") is not None:
            names[node["codeId"]] = node.get("name") or ""
        for ch in node.get("children") or []:
            walk(ch)

    for top in d.get("flfgfl", {}).get("children") or []:
        walk(top)
    return names

FLFG = load_flfg_names()
LAW_DEPT_CODES = {110, 120, 130, 140, 150, 155, 160, 170, 180, 190, 195, 200}

# ---- 官方制定机关码 -> 省份（170北京 … 470新疆，市级人大共用所属省码）----
_ed = json.load(open(os.path.join(ROOT, "lists", "enumData.json"), encoding="utf-8"))
_ztree = [c for c in _ed["zdjgfl"]["children"] if c["name"] == "地方人大及其常委会"][0]
ZDJG2PROV = {}
for _pn in _ztree["children"]:
    _full = next((p for p in PROVINCES if p.startswith(_pn["name"])), None)
    if _full:
        ZDJG2PROV[_pn["codeId"]] = _full

# ---- 从 flk 地方数据自动构建 行政区划名->省 映射 ----
ORG2PROV = {p: p for p in PROVINCES}
_ld = os.path.join(ROOT, "lists")
for fn in os.listdir(_ld):
    if not (fn.startswith("flk_地方法规") and fn.endswith(".jsonl")):
        continue
    with open(os.path.join(_ld, fn), encoding="utf-8") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            prov = ZDJG2PROV.get(o.get("zdjgCodeId"))
            org = o.get("zdjgName") or ""
            if prov and org:
                key = re.sub(r"(人民政府|人民代表大会常务委员会|人大常务委员会|人民代表大会)$", "", org)
                if key and key not in ORG2PROV:
                    ORG2PROV[key] = prov

def load_flk_meta():
    meta = {}
    for fn in os.listdir(_ld):
        if fn.startswith("flk_") and fn.endswith(".jsonl"):
            with open(os.path.join(_ld, fn), encoding="utf-8") as f:
                for line in f:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("bbbs"):
                        meta[o["bbbs"]] = o
    return meta

FLK = load_flk_meta()

def norm_path(p):
    return p.replace("\\", "/").strip() if p else ""

def region_from_org(org):
    if not org:
        return None
    for p in PROVINCES:
        if org.startswith(p):
            return p
    key = re.sub(r"(人民政府|人民代表大会常务委员会|人大常务委员会|人民代表大会)$", "", org)
    return ORG2PROV.get(key) or ORG2PROV.get(org)

# ---------------------------------------------------------------- 主题规则
TOPIC_RULES = [
    ("会计·审计·财务", [("会计", "审计", "注册会计师", "会计师事务所", "代理记账",
                    "总会计师", "会计档案", "财务报表", "财务报告", "财务通则", "财务规则",
                    "财务制度", "财务条例", "资产评估", "内部控制", "XBRL", "会计信息化",
                    "会计信息质量", "财会监督"), ()]),
    ("税务·税收", [("税", "发票", "税收", "征税", "纳税"), ()]),
    ("财政·预算·国资", [("预算", "决算", "国库", "国债", "彩票", "政府采购", "国有资产",
                    "国有资本", "产权登记", "产权转让", "财政", "转移支付",
                    "非税收入", "行政事业性收费", "专项债券", "清产核资"), ()]),
    ("金融·银行·证券·保险", [("银行", "证券", "期货", "信托", "外汇", "货币", "票据",
                    "反洗钱", "融资", "存款", "贷款", "典当", "金融", "债券", "黄金",
                    "征信", "支付", "资管", "上市公司", "保险", "基金", "再贷款"),
                    ("社会保险", "养老保险", "医疗保险", "工伤保险", "失业保险",
                     "生育保险", "基金会", "保险费")]),
    ("公司与商事·破产", [("公司", "合伙", "独资企业", "破产", "商事", "市场主体",
                    "监事会", "个体工商户和私营企业"), ()]),
    ("劳动·人事·社会保障", [("劳动", "就业", "社会保险", "养老", "失业", "工伤", "生育",
                    "工资", "农民工", "工会", "职业病", "人力资源", "带薪年", "劳动合同",
                    "劳动争议", "人才", "职业技能", "童工", "工时"), ()]),
    ("土地·房地产·不动产", [("土地", "房地产", "不动产", "房屋", "物业", "住房公积金",
                    "宅基地", "商品房", "住房", "耕地", "房产"), ()]),
    ("城乡建设·工程·规划", [("城乡规划", "建筑", "工程", "招标投标", "招投标", "测绘",
                    "勘察设计", "市容", "环卫", "市政", "城市建设", "村庄和集镇",
                    "建设工程", "造价", "供水", "排水", "供热", "公园", "绿化",
                    "燃气", "自来水", "绿道", "采暖", "供暖", "智慧城市"), ()]),
    ("生态环境·资源", [("环境", "污染", "生态", "节能", "碳", "水法", "水污染", "水资源",
                    "水土保持", "防汛", "河道", "湖泊", "森林", "草原", "湿地", "野生动物",
                    "野生植物", "自然保护", "矿产", "海洋", "海域", "海岛", "固体废物",
                    "噪声", "土壤", "核安全", "放射", "危险废物", "循环经济", "清洁生产",
                    "地下水", "饮用水", "水源", "扬尘", "大气", "水利", "水文", "水库",
                    "节水", "核材料", "病媒", "海滩", "流域"), ()]),
    ("能源", [("能源", "煤炭", "电力", "石油", "天然气", "核电", "电网", "供电"), ()]),
    ("农业农村·粮食", [("农业", "农村", "农民", "种子", "农药", "化肥", "畜牧", "兽医",
                    "饲料", "渔业", "承包", "乡村振兴", "扶贫", "农垦", "粮食", "农作物",
                    "植物检疫", "动物防疫", "畜禽", "养殖", "滩涂", "粮油", "灌溉",
                    "农机", "农田"), ()]),
    ("市场监管·质量标准", [("市场监管", "质量", "计量", "标准化", "特种设备",
                    "反垄断", "反不正当竞争", "消费者", "广告", "价格", "认证认可",
                    "检验检测", "烟草专卖", "食盐", "电梯", "气瓶", "召回", "信用",
                    "检验", "个体工商户", "私营企业"), ()]),
    ("教育·科技·文化·旅游", [("教育", "学校", "教师", "义务教育", "学位", "科学技术",
                    "科技进步", "科普", "科研", "出版", "电影", "广播", "电视", "新闻",
                    "文化", "文物", "非物质文化遗产", "博物馆", "旅游", "景区", "体育",
                    "语言文字", "档案", "风景名胜", "科技创新", "合成生物", "技术市场",
                    "教学成果", "职业技能培训"), ()]),
    ("卫生健康·食品药品", [("卫生", "医师", "护士", "医疗", "药品", "疫苗", "食品",
                    "传染病", "精神卫生", "母婴", "血液", "计划生育", "人口", "保健",
                    "中医药", "临床", "麻醉药品", "精神药品", "禁毒", "艾滋病", "献血"), ()]),
    ("交通运输·邮政", [("交通", "公路", "道路", "铁路", "民航", "航空", "航运", "船舶",
                    "港口", "海运", "机动车", "出租汽车", "轨道交通", "邮政", "高速公路",
                    "驾驶证", "航道", "电动自行车", "网约车", "客运", "货运", "停车",
                    "内河"), ()]),
    ("民事·婚姻家庭·继承", [("民法", "物权", "合同", "侵权", "人格权", "婚姻", "收养",
                    "继承", "遗嘱", "监护", "民事"), ()]),
    ("刑事·司法程序·法律职业", [("刑法", "刑事", "犯罪", "监狱", "律师", "公证", "仲裁",
                    "调解", "司法", "法官", "检察官", "陪审", "法律援助", "国家赔偿",
                    "社区矫正", "引渡"), ()]),
    ("行政·公务员·监察", [("公务员", "行政许可", "行政处罚", "行政强制", "行政复议",
                    "行政诉讼", "监察", "政府信息公开", "信访", "机构编制", "行政区划",
                    "国家安全", "保密", "户籍", "居民身份证", "出入境", "治安", "警察",
                    "护照", "国旗", "国徽", "国歌", "勋章", "游行示威", "行政执法",
                    "议事规则", "编制管理", "机关事务", "政务", "文明行为", "网格化",
                    "规章清理", "立法条例"), ()]),
    ("应急·安全生产", [("安全生产", "消防", "防灾", "防震", "突发事件", "应急", "救灾",
                    "事故", "救援", "危险化学品", "煤矿安全", "燃气安全"), ()]),
    ("知识产权", [("专利", "商标", "著作权", "版权", "集成电路", "植物新品种", "知识产权",
                    "地理标志", "特殊标志"), ()]),
    ("网络·数据·电信", [("网络", "数据", "电信", "互联网", "电子商务", "电子签名",
                    "个人信息", "域名", "无线电", "关键信息基础设施", "生成式",
                    "算法推荐"), ()]),
    ("海关·外贸·涉外", [("海关", "进出口", "对外贸易", "外贸", "关税", "外商投资", "外资",
                    "涉外", "领事", "条约", "公约", "协定", "边境", "自由贸易试验",
                    "出口管制", "两用物项", "反倾销", "反补贴", "保障措施"), ()]),
    ("国防·军事", [("国防", "军事", "兵役", "现役", "军官", "士兵", "民兵", "预备役",
                    "军队", "人民武装", "武器", "人民防空", "征兵", "军人"), ()]),
    ("民政·社会组织·民族宗教", [("慈善", "社会救助", "社会组织", "社会团体", "基金会",
                    "民办非企业", "志愿服务", "殡葬", "民族", "宗教", "华侨", "归侨",
                    "老年人", "残疾人", "未成年人", "妇女", "儿童", "红十字", "低保",
                    "婚姻登记", "收养登记", "居民委员会", "村民委员会", "业主大会",
                    "见义勇为", "烈士", "退役军人", "自治条例", "单行条例"), ()]),
]

def classify_topics(title, org=""):
    hits = []
    for topic, (incl, excl) in TOPIC_RULES:
        if any(k in title for k in incl) and not any(k in title for k in excl):
            hits.append(topic)
    return hits or ["综合及其他"]

ACC_SUB = [
    ("企业会计准则——基本准则与具体准则", r"企业会计准则第|企业会计准则——基本准则|企业基本会计准则|小企业会计准则"),
    ("企业会计准则——解释公告", r"企业会计准则解释"),
    ("企业会计准则——应用指南与衔接规定", r"应用指南|指南|衔接|讲解|增值税会计处理|会计处理"),
    ("政府会计准则与制度", r"政府会计"),
    ("行业与专项会计制度", r"会计制度|财务制度"),
    ("会计基础工作与人员管理", r"会计法\b|会计法$|会计人员|总会计师|代理记账|会计基础工作|会计档案|会计管理条例|会计管理|会计基础"),
    ("内部控制与风险管理", r"内部控制"),
    ("财务报告与决算", r"财务报表|财务报告|财务通则|财务规则|决算|财务条例"),
    ("资产评估与专业服务", r"资产评估"),
    ("执业准则——审计与审阅准则", r"审计准则|审阅准则|鉴证业务准则"),
    ("执业准则——其他鉴证与相关服务准则", r"其他鉴证|相关服务|预测|商定程序"),
    ("执业准则——质量控制准则", r"质量控制|质量管理"),
    ("职业道德与独立性准则", r"职业道德|独立性"),
    ("注册会计师与行业管理", r"注册会计师|会计师事务所|证券资格|执业许可"),
    ("会计监督与检查公告", r"会计信息质量|财会监督"),
    ("政府审计与内部审计", r"审计"),
]

def acc_sub(title, dept=""):
    """会计审计子类。dept 为准则清单类别时走专用顺序，避免标题歧义。"""
    if dept == "执业准则":
        if re.search(r"职业道德|独立性", title):
            return "职业道德与独立性准则"
        if re.search(r"质量管理|质量控制", title):
            return "执业准则——质量控制准则"
        if "应用指南" in title:
            return "执业准则——执业准则应用指南"
        if re.search(r"其他鉴证|相关服务|商定程序|预测", title):
            return "执业准则——其他鉴证与相关服务准则"
        if re.search(r"审计准则|审阅|鉴证", title):
            return "执业准则——审计与审阅准则"
        return "执业准则——其他"
    if dept == "政府及行业会计制度":
        if "政府会计" in title:
            return "政府会计准则与制度"
        if re.search(r"决算|财务报表|财务报告", title):
            return "财务报告与决算"
        return "行业与专项会计制度"
    for name, pat in ACC_SUB:
        if re.search(pat, title):
            return name
    return "其他会计审计事项"

TAX_SUB = [
    ("税收征收管理与程序", r"征收管理|征管|税务登记|纳税申报|税务稽查|稽查|税务代理|税务师|纳税服务|税务行政处罚|强制执行|欠税|催缴|税务检查|代扣代缴|代收代缴|委托代征|税收管理员|发票票证|税收票证"),
    ("发票管理", r"发票"),
    ("增值税", r"增值税"),
    ("消费税", r"消费税"),
    ("企业所得税", r"企业所得税"),
    ("个人所得税", r"个人所得税"),
    ("土地与房地产税收", r"房产税|契税|土地增值税|耕地占用税|城镇土地使用税|土地使用税"),
    ("财产行为与其他税种", r"印花税|车船税|车辆购置税|资源税|环境保护税|环境税|烟叶税|船舶吨税|城市维护建设税|附加|营业税|屠宰税|筵席税|固定资产投资方向调节税"),
    ("关税与进出口税收", r"关税|进出口税|出口退税|船舶吨税|进出境物品|行邮税"),
    ("国际税收", r"国际税收|避免双重征税|税收协定|非居民|转让定价|CRS|金融账户涉税|协定"),
    ("税收优惠与专项政策", r"优惠|减免|西部大开发|自贸|自由贸易试验|高新技术|小微企业|加计扣除|留抵退税|专项附加扣除"),
    ("税务案例与欠税公告", r"公告|案例|公示|送达"),
]

def tax_sub(title, level=""):
    # 法律层级且以"法"结尾 → 税收法律
    if level == "法律" and re.search(r"法$", title):
        return "税收法律（各税种法与征管法）"
    for name, pat in TAX_SUB:
        if re.search(pat, title):
            return name
    return "综合性税收规定"

TAX_ORDER = [name for name, _ in TAX_SUB]
TAX_ORDER.insert(0, "税收法律（各税种法与征管法）")
TAX_ORDER.append("综合性税收规定")

# ---------------------------------------------------------------- 加载条目
entries = []

def add(title, level, dept, topics, asub, tsub, region, org, date, year,
        status, docno, md, url, src):
    entries.append(dict(title=title, level=level, dept=dept, topics=topics,
                        asub=asub, tsub=tsub, region=region, org=org, date=date,
                        year=year, status=status, no=docno, md=md, url=url, src=src))

# 1) 主清单
with open(os.path.join(LIB, "manifest.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        title = row["标题"].strip()
        lib, cat = row["库"], row["类别"]
        org = row["公布机关"].strip()
        date = (row["公布日期"] or "").strip()[:10]
        m = re.search(r"detail\?id=([0-9a-f]{32})", row["原文链接"] or "")
        bbbs = m.group(1) if m else None
        fm = FLK.get(bbbs) or {}
        code = fm.get("flfgCodeId")

        if lib == "国家法律法规数据库":
            level = cat
            dept = FLFG.get(code, "") if cat in ("法律", "宪法") and code else ""
            if cat == "地方法规":
                region = ZDJG2PROV.get(fm.get("zdjgCodeId")) or region_from_org(org)
            else:
                region = None
        elif lib == "国家规章库":
            level = cat
            dept = ""
            region = region_from_org(org) if cat == "地方政府规章" else None
        else:
            level = "国资监管专题"
            dept = cat
            region = None

        topics = classify_topics(title, org)
        asub = acc_sub(title) if "会计·审计·财务" in topics else ""
        tsub = tax_sub(title, level) if "税务·税收" in topics else ""
        year = date[:4] if re.match(r"^\d{4}", date) else ""
        add(title, level, dept, topics, asub, tsub, region, org, date, year,
            row["时效性"], "", norm_path(row["Markdown"]), row["原文链接"], lib)

# 2) 会计准则与执业准则（清单 Markdown 列已含顶层目录，勿再加前缀）
with open(os.path.join(LIB, "会计准则与执业准则", "manifest.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        title = row["标题"].strip()
        cat = row["类别"].strip()
        org = row["机关"].strip()
        date = (row["公布日期"] or "").strip()[:10]
        topics = ["会计·审计·财务"]
        if re.search(r"政府会计|决算|预算会计", title):
            topics.append("财政·预算·国资")
        add(title, "会计准则与执业准则", cat, topics, acc_sub(title, cat), "",
            None, org, date, date[:4] if date else "", row["时效性"], row["文号"],
            norm_path(row["Markdown"]), row["链接"], "财政部/中注协官方")

# 3) 税务案例：清单为主 + 磁盘扫描补全（清单只登记了部分文件）
case_root = os.path.join(LIB, "专题", "税务案例")
man_by_path = {}
with open(os.path.join(case_root, "manifest.csv"), encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        man_by_path[norm_path(row["文件"])] = row

disk_cases = []
for dirpath, _dirs, files in os.walk(case_root):
    for fn in files:
        if not fn.lower().endswith(".md"):
            continue
        full = os.path.join(dirpath, fn)
        rel = norm_path(os.path.relpath(full, case_root))
        disk_cases.append((rel, full))
print("taxcase files on disk:", len(disk_cases))

for rel, full in disk_cases:
    row = man_by_path.get(rel)
    if row:
        title = row["标题"].strip()
        date = (row["发布日期"] or "").strip()[:10]
        org = row["来源机关"].strip()
        region = row["地区"].strip()
        column = row["栏目"].strip()
        status = "疑似重复" if row.get("重复") == "是" else ""
        url = row["原文链接"]
    else:
        parts = rel.split("/")
        region, column = parts[0], (parts[1] if len(parts) > 2 else "其他栏目")
        base = os.path.splitext(parts[-1])[0]
        m = re.match(r"^(\d{4}-\d{2}-\d{2})_(.+)$", base)
        date, title = (m.group(1), m.group(2)) if m else ("", base)
        org, status, url = "", "清单外补录", ""
    topics = ["税务·税收"]
    if re.search(r"会计信息质量|财会监督|会计师事务所", title):
        topics.append("会计·审计·财务")
    add(title, "税务案例公告", column, topics,
        acc_sub(title) if "会计·审计·财务" in topics else "",
        tax_sub(title, "税务案例公告"), region or "其他", org, date,
        date[:4] if date else "", status, "", "专题/税务案例/" + rel, url,
        "各地税务局公告")

print("entries:", len(entries))

# ---------------------------------------------------------------- 覆盖度核对（只报告）
MIRROR_DIRS = ("专题/涉税法规/", "专题/涉会计法规/", "专题/国资监管法规/")
canonical_ima = {e["md"] for e in entries if e["level"] == "国资监管专题" and e["md"]}
disk_all = set()
for dirpath, _dirs, files in os.walk(LIB):
    for fn in files:
        if fn.lower().endswith(".md"):
            disk_all.add(norm_path(os.path.relpath(os.path.join(dirpath, fn), LIB)))

# 清单路径与磁盘不符时，按目录+文件名主干回退解析（如磁盘带类别前缀）
stem_index = defaultdict(list)
for p in disk_all:
    d, b = os.path.split(p)
    stem = re.sub(r"^(地方政府规章|部门规章)_", "", b)
    stem_index[(d, stem)].append(p)
fixed = 0
for e in entries:
    if not e["md"] or e["md"] in disk_all:
        continue
    d, b = os.path.split(e["md"])
    stem = re.sub(r"^(地方政府规章|部门规章)_", "", b)
    cand = [p for p in stem_index.get((d, stem), []) if p not in MIRROR_DIRS]
    if len(cand) == 1:
        e["md"] = cand[0]
        fixed += 1
print("stem-resolution fixed:", fixed)

idx_md = {e["md"] for e in entries if e["md"]}
disk_md = {p for p in disk_all
           if not p.startswith(MIRROR_DIRS) or p in canonical_ima}
mirror_cnt = len(disk_all) - len(disk_md)
missing = sorted(disk_md - idx_md)
ghost = sorted(idx_md - disk_all)
print("md on disk(excl mirrors):", len(disk_md), "| mirror copies:", mirror_cnt,
      "| in index:", len(idx_md))
print("disk-not-in-index:", len(missing), missing[:5])
print("index-not-on-disk:", len(ghost), ghost[:5])

# ---- 孤儿文件并入（清单外的磁盘文件，按目录推断层级、文件名推断标题/日期）----
orphan_added = 0
for p in missing:
    parts = p.split("/")
    level = "未归类"
    if parts[0] == "国家法律法规数据库" and len(parts) >= 2:
        level = parts[1]
    elif parts[0] == "国家规章库" and len(parts) >= 2:
        level = parts[1]
    elif parts[0] == "会计准则与执业准则":
        level = "会计准则与执业准则"
    base = os.path.splitext(parts[-1])[0]
    base = re.sub(r"^(地方政府规章|部门规章)_", "", base)
    m = re.match(r"^(.*?)_(\d{4}-\d{2}-\d{2})$", base)
    if m:
        title, date = m.group(1), m.group(2)
    else:
        m2 = re.match(r"^(\d{4}-\d{2}-\d{2})_(.*)$", base)
        title, date = (m2.group(2), m2.group(1)) if m2 else (base, "")
    org = ""
    region = None
    if level == "地方政府规章":
        mm = re.match(r"^(.{2,10}?(?:市|自治州|地区|盟|县))", title)
        if mm:
            org = mm.group(1) + "人民政府"
            region = region_from_org(org)
    topics = classify_topics(title)
    add(title, level, "", topics,
        acc_sub(title) if "会计·审计·财务" in topics else "",
        tax_sub(title, level) if "税务·税收" in topics else "",
        region, org, date, date[:4] if date else "", "清单外磁盘补录", "",
        p, "", "磁盘扫描补录")
    orphan_added += 1
if orphan_added:
    print("orphans ingested:", orphan_added)
    idx_md = {e["md"] for e in entries if e["md"]}
    still = sorted(disk_md - idx_md)
    print("still missing after ingest:", len(still), still[:5])

# 输出目录就绪 + 按维度清理陈旧文件（避免残留上一轮结果；单文件删除失败仅告警）
os.makedirs(OUT, exist_ok=True)

def clean_stale(subdir, keep_names):
    d = os.path.join(OUT, subdir)
    os.makedirs(d, exist_ok=True)
    removed = failed = 0
    for fn in os.listdir(d):
        if fn in keep_names:
            continue
        try:
            os.remove(os.path.join(d, fn))
            removed += 1
        except OSError:
            failed += 1
    if removed or failed:
        print("clean %s: removed %d, locked %d" % (subdir, removed, failed))

def esc(s):
    return (s or "").replace("|", "丨").replace("\n", " ").strip()

def line_of(e):
    seg = [e["org"]] if e["org"] else []
    if e["no"]:
        seg.append(e["no"])
    if e["status"] in ("疑似重复", "清单外补录", "清单外磁盘补录"):
        seg.append(e["status"])
    tail = "（%s）" % "，".join(seg) if seg else ""
    if not e["md"]:
        return "- %s **%s**（仅有原文件，未转 md）" % (e["date"] or "----", esc(e["title"]))
    return "- %s **%s**%s `%s`" % (e["date"] or "----", esc(e["title"]), tail, esc(e["md"]))

def write_page(relpath, title, body):
    fp = os.path.join(OUT, relpath)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write("# %s\n\n%s" % (title, body))

LEVEL_ORDER = ["宪法", "法律", "行政法规", "监察法规", "司法解释",
               "部门规章", "地方政府规章", "地方法规", "会计准则与执业准则",
               "国资监管专题", "税务案例公告"]

def group_entries(items, keyfn, order=None):
    g = defaultdict(list)
    for e in items:
        g[keyfn(e)].append(e)
    keys = sorted(g.keys(), key=lambda k: (order.index(k) if order and k in order else 999, k))
    return keys, g

# ---------------------------------------------------------------- 索引总表.csv
COLS = ["标题", "法源层级", "分类/法律部门", "主题标签", "会计审计子类", "税务子类",
        "地域", "发文机关", "日期", "年份", "时效性/备注", "文号", "md路径", "来源库", "原文链接"]
with open(os.path.join(OUT, "索引总表.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(COLS)
    for e in sorted(entries, key=lambda x: (LEVEL_ORDER.index(x["level"]) if x["level"] in LEVEL_ORDER else 99, x["level"], x["title"])):
        w.writerow([e["title"], e["level"], e["dept"], ";".join(e["topics"]),
                    e["asub"], e["tsub"], e["region"] or "", e["org"], e["date"],
                    e["year"], e["status"], e["no"], e["md"], e["src"], e["url"]])
print("csv done")

# ---------------------------------------------------------------- 按法源层级
clean_stale("按法源层级", {"宪法.md", "法律_按法律部门.md", "行政法规.md", "监察法规.md",
                          "司法解释.md", "部门规章.md", "地方性法规与地方政府规章_分省索引.md",
                          "会计准则与执业准则.md", "国资监管专题.md"})
def emit_level_file(level, fn, dept_split=False):
    items = [e for e in entries if e["level"] == level]
    if not items:
        return 0
    if dept_split:
        keys, g = group_entries(items, lambda e: e["dept"] or "未分部门")
        body = ""
        for k in keys:
            body += "\n## %s（%d 件）\n\n" % (k, len(g[k]))
            body += "\n".join(line_of(e) for e in sorted(g[k], key=lambda x: x["title"])) + "\n"
    else:
        body = "共 %d 件。\n\n" % len(items) + "\n".join(
            line_of(e) for e in sorted(items, key=lambda x: x["title"])) + "\n"
    write_page(os.path.join("按法源层级", fn), level, body)
    return len(items)

for lv, fn, dept in [("宪法", "宪法.md", False), ("法律", "法律_按法律部门.md", True),
                     ("行政法规", "行政法规.md", False), ("监察法规", "监察法规.md", False),
                     ("司法解释", "司法解释.md", False), ("部门规章", "部门规章.md", False)]:
    print("level", lv, emit_level_file(lv, fn, dept_split=dept))

loc_n = sum(1 for e in entries if e["level"] in ("地方法规", "地方政府规章"))
prov_cnt = Counter(e["region"] or "未识别省份" for e in entries if e["level"] in ("地方法规", "地方政府规章"))
body = ["地方法规 + 地方政府规章 共 %d 件，按省份拆分至 `按地域/` 目录：\n" % loc_n,
        "| 省份 | 件数 | 文件 |", "|---|---:|---|"]
for p, n in prov_cnt.most_common():
    body.append("| %s | %d | 按地域/%s.md |" % (p, n, p))
write_page(os.path.join("按法源层级", "地方性法规与地方政府规章_分省索引.md"),
           "地方性法规与地方政府规章（分省索引）", "\n".join(body) + "\n")

items = [e for e in entries if e["level"] == "会计准则与执业准则"]
keys, g = group_entries(items, lambda e: e["dept"])
body = ("共 %d 件，覆盖财政部企业会计准则/政府及行业会计制度与中注协执业准则。\n"
        "时效性说明：全部为现行有效或最新公布版本（CAS30 为 2014 现行版 + 2026 已公布待施行版并存）。\n" % len(items))
for k in keys:
    body += "\n## %s（%d 件）\n\n" % (k, len(g[k]))
    for e in sorted(g[k], key=lambda x: (x["date"], x["title"])):
        seg = [e["org"], e["no"]] if e["no"] else [e["org"]]
        body += "- %s **%s**（%s） `%s`\n" % (e["date"] or "----", esc(e["title"]),
                                             "，".join(filter(None, seg)), esc(e["md"]))
write_page(os.path.join("按法源层级", "会计准则与执业准则.md"), "会计准则与执业准则全目录", body)

items = [e for e in entries if e["level"] == "国资监管专题"]
if items:
    keys, g = group_entries(items, lambda e: e["dept"])
    body = "共 %d 件（IMA 国资法律法规知识库补充）。\n" % len(items)
    for k in keys:
        body += "\n## %s（%d 件）\n\n" % (k, len(g[k]))
        body += "\n".join(line_of(e) for e in sorted(g[k], key=lambda x: x["date"])) + "\n"
    write_page(os.path.join("按法源层级", "国资监管专题.md"), "国资监管专题", body)

# ---------------------------------------------------------------- 按主题领域
clean_stale("按主题领域", {t.replace("·", "_") + ".md" for t, _ in TOPIC_RULES} | {"综合及其他.md"})
topic_cnt = Counter()
for e in entries:
    for t in e["topics"]:
        topic_cnt[t] += 1

acc_items = [e for e in entries if "会计·审计·财务" in e["topics"]]
_ACC_PAGE_ORDER = [n for n, _ in ACC_SUB] + ["执业准则——执业准则应用指南", "执业准则——其他", "其他会计审计事项"]
keys, g = group_entries(acc_items, lambda e: e["asub"], order=_ACC_PAGE_ORDER)
body = ("共 %d 件（多标签统计）。涵盖：会计法律法规、企业/政府/行业会计准则与制度、"
        "内部控制、财务报告与决算、资产评估、注册会计师行业管理、中注协执业准则"
        "（审计/审阅/其他鉴证/相关服务/质量控制）、职业道德与独立性、政府审计与内部审计、"
        "会计信息质量检查公告。\n"
        "条目格式：日期 **标题**（机关，文号） `md相对路径`（相对于 lawlibrary/）。\n" % len(acc_items))
for k in keys:
    body += "\n## %s（%d 件）\n\n" % (k, len(g[k]))
    body += "\n".join(line_of(e) for e in sorted(g[k], key=lambda x: (x["date"] or "", x["title"]))) + "\n"
write_page(os.path.join("按主题领域", "会计审计与财务.md"), "专题目录：会计·审计·财务", body)
print("acc topic:", len(acc_items))

tax_items = [e for e in entries if "税务·税收" in e["topics"]]
noncase = [e for e in tax_items if e["level"] != "税务案例公告"]
case_n = len(tax_items) - len(noncase)
keys, g = group_entries(noncase, lambda e: e["tsub"], order=TAX_ORDER)
body = ("共 %d 件法规 + %d 份税务案例公告（后者的完整目录见 `税务案例索引/`）。"
        "涵盖：各税种法律/条例/细则、税收征管、发票、关税与国际税收、税收优惠、"
        "地方税收配套规定。\n子类按关键词顺序取先命中者（单标签）。\n" % (len(noncase), case_n))
for k in keys:
    nat = [e for e in g[k] if e["level"] not in ("地方法规", "地方政府规章")]
    loc = [e for e in g[k] if e["level"] in ("地方法规", "地方政府规章")]
    body += "\n## %s（%d 件；另有地方规定 %d 件）\n\n" % (k, len(nat), len(loc))
    if nat:
        body += "\n".join(line_of(e) for e in sorted(nat, key=lambda x: x["date"] or "")) + "\n"
    if loc:
        pk, pg = group_entries(loc, lambda e: e["region"] or "未识别省份")
        for p in pk:
            body += "\n### %s（%d 件）\n\n" % (p, len(pg[p]))
            body += "\n".join(line_of(e) for e in sorted(pg[p], key=lambda x: x["date"] or "")) + "\n"
body += ("\n## 税务案例公告（%d 份）\n\n按地区×栏目组织，详见 `税务案例索引/税务案例公告目录.md`。\n" % case_n)
write_page(os.path.join("按主题领域", "税务与税收.md"), "专题目录：税务·税收", body)
print("tax topic:", len(tax_items))

for topic, _ in TOPIC_RULES:
    if topic in ("会计·审计·财务", "税务·税收"):
        continue
    items = [e for e in entries if topic in e["topics"]]
    if not items:
        continue
    nat = [e for e in items if e["level"] not in ("地方法规", "地方政府规章", "税务案例公告")]
    loc = [e for e in items if e["level"] in ("地方法规", "地方政府规章")]
    body = "共 %d 件（全国层面 %d，地方层面 %d）。\n" % (len(items), len(nat), len(loc))
    keys, g = group_entries(nat, lambda e: e["level"])
    for k in keys:
        body += "\n## %s（%d 件）\n\n" % (k, len(g[k]))
        body += "\n".join(line_of(e) for e in sorted(g[k], key=lambda x: x["date"] or "")) + "\n"
    if loc:
        pk, pg = group_entries(loc, lambda e: e["region"] or "未识别省份")
        body += "\n## 地方层面（%d 件，按省份）\n" % len(loc)
        for p in pk:
            body += "\n### %s（%d 件）\n\n" % (p, len(pg[p]))
            body += "\n".join(line_of(e) for e in sorted(pg[p], key=lambda x: x["date"] or "")) + "\n"
    write_page(os.path.join("按主题领域", topic.replace("·", "_") + ".md"),
               "主题目录：" + topic, body)

# 综合及其他（未命中主题关键词）
items = [e for e in entries if "综合及其他" in e["topics"]]
if items:
    nat = [e for e in items if e["level"] not in ("地方法规", "地方政府规章")]
    loc = [e for e in items if e["level"] in ("地方法规", "地方政府规章")]
    body = ("共 %d 件未能归入既定主题（多为地方性专项事务管理规定）。"
            "可经 `索引总表.csv` 按标题检索。\n" % len(items))
    keys, g = group_entries(nat, lambda e: e["level"])
    for k in keys:
        body += "\n## %s（%d 件）\n\n" % (k, len(g[k]))
        body += "\n".join(line_of(e) for e in sorted(g[k], key=lambda x: x["date"] or "")) + "\n"
    if loc:
        pk, pg = group_entries(loc, lambda e: e["region"] or "未识别省份")
        body += "\n## 地方层面（%d 件，按省份）\n" % len(loc)
        for p in pk:
            body += "\n### %s（%d 件）\n\n" % (p, len(pg[p]))
            body += "\n".join(line_of(e) for e in sorted(pg[p], key=lambda x: x["date"] or "")) + "\n"
    write_page(os.path.join("按主题领域", "综合及其他.md"), "主题目录：综合及其他", body)

# ---------------------------------------------------------------- 税务案例索引
clean_stale("税务案例索引", {"税务案例公告目录.md"})
cases = [e for e in entries if e["level"] == "税务案例公告"]
pk, pg = group_entries(cases, lambda e: e["region"] or "其他")
body = ("共 %d 份（各地税务局税案通报/行政处罚公示/文书送达公告/欠税催缴等）。"
        "按地区→栏目组织；标注（疑似重复）为清单标记的重复文书，（清单外补录）为磁盘补扫文件。\n" % len(cases))
for p in pk:
    kk, kg = group_entries(pg[p], lambda e: e["dept"] or "其他栏目")
    body += "\n## %s（%d 份）\n" % (p, len(pg[p]))
    for k in kk:
        body += "\n### %s（%d 份）\n\n" % (k, len(kg[k]))
        body += "\n".join(line_of(e) for e in sorted(kg[k], key=lambda x: x["date"] or "")) + "\n"
write_page(os.path.join("税务案例索引", "税务案例公告目录.md"), "税务案例公告目录", body)

# ---------------------------------------------------------------- 按地域
loc_items = [e for e in entries if e["level"] in ("地方法规", "地方政府规章")]
pk, pg = group_entries(loc_items, lambda e: e["region"] or "未识别省份")
clean_stale("按地域", {p + ".md" for p in pk})
for p in pk:
    items = pg[p]
    fk, fg = group_entries(items, lambda e: e["level"])
    body = "共 %d 件（地方性法规 + 地方政府规章）。\n" % len(items)
    for k in fk:
        og, gg = group_entries(fg[k], lambda e: e["org"] or "（机关不详）")
        body += "\n## %s（%d 件）\n" % (k, len(fg[k]))
        for o in og:
            body += "\n### %s（%d 件）\n\n" % (o, len(gg[o]))
            body += "\n".join(line_of(e) for e in sorted(gg[o], key=lambda x: x["date"] or "")) + "\n"
    write_page(os.path.join("按地域", p + ".md"), p + " 地方法规规章目录", body)

# ---------------------------------------------------------------- 按发文机关
clean_stale("按发文机关", {"国务院部门规章.md"})
items = [e for e in entries if e["level"] == "部门规章"]
og, gg = group_entries(items, lambda e: e["org"] or "（机关不详）")
body = "国务院部门规章共 %d 件，按发布机关分组。\n" % len(items)
for o in og:
    body += "\n## %s（%d 件）\n\n" % (o, len(gg[o]))
    body += "\n".join(line_of(e) for e in sorted(gg[o], key=lambda x: x["date"] or "")) + "\n"
write_page(os.path.join("按发文机关", "国务院部门规章.md"), "部门规章按发文机关目录", body)

# ---------------------------------------------------------------- 按年份
clean_stale("按年份", {"年代分布矩阵.md"})
DECADES = ["1949-1959", "1959-1979", "1979-1989", "1989-1999", "1999-2009",
           "2009-2019", "2019-2026", "年份不详"]

def decade(y):
    if not y:
        return "年份不详"
    v = int(y)
    for lo, hi, name in [(1949, 1959, "1949-1959"), (1959, 1979, "1959-1979"),
                         (1979, 1989, "1979-1989"), (1989, 1999, "1989-1999"),
                         (1999, 2009, "1999-2009"), (2009, 2019, "2009-2019"),
                         (2019, 2100, "2019-2026")]:
        if lo <= v < hi:
            return name
    return "年份不详"

mat = defaultdict(Counter)
for e in entries:
    mat[e["level"]][decade(e["year"])] += 1
lines = ["| 法源层级 | " + " | ".join(DECADES) + " | 合计 |", "|" + "---:|" * (len(DECADES) + 2)]
for lv in LEVEL_ORDER + [l for l in mat if l not in LEVEL_ORDER]:
    if lv not in mat:
        continue
    row = [str(mat[lv].get(d, 0)) for d in DECADES]
    lines.append("| %s | %s | %d |" % (lv, " | ".join(row), sum(mat[lv].values())))
write_page(os.path.join("按年份", "年代分布矩阵.md"), "法规年代分布矩阵（按公布/发布年份）",
           "\n".join(lines) + "\n")

# ---------------------------------------------------------------- README
levels_cnt = Counter(e["level"] for e in entries)
readme = []
readme.append("# 法规目录索引（lawlibrary 检索总目录）")
readme.append("")
readme.append("> 生成时间：2026-10-10。本目录是对 `lawlibrary/` 全部 Markdown 文件的**只读索引**，"
              "不改动任何源文件；按 6 个维度组织，供知识库与 agent 检索调用。")
readme.append("")
readme.append("## 一、收录范围与口径")
readme.append("")
readme.append("- **收录**：国家法律法规数据库现行有效库（宪法/法律/行政法规/监察法规/司法解释/地方性法规）"
              "+ 国家规章库（部门规章/地方政府规章）+ 会计准则与执业准则（财政部/中注协官方）"
              "+ 国资监管专题 + 税务案例公告（含清单外磁盘补录）。")
readme.append("- **条目总数**：%d 条（含 %d 份税务案例公告）。主题为多标签统计，各主题页条目可重叠。" % (len(entries), len(cases)))
readme.append("- **镜像说明**：`专题/涉税法规`、`专题/涉会计法规`、`专题/国资监管法规` 为早期专题镜像目录，"
              "内容已并入本索引各维度（含 md 路径），无需单独检索。")
readme.append("- **边界**：依据《立法法》法源体系收录；一般规范性文件未入主库。")
readme.append("")
readme.append("## 二、维度体系")
readme.append("")
readme.append("| 维度 | 目录 | 说明 |")
readme.append("|---|---|---|")
readme.append("| 机器可读总表 | `索引总表.csv` | 每行一个文件：标题/法源层级/法律部门/主题标签/会计审计子类/税务子类/地域/发文机关/日期/文号/md路径/链接 |")
readme.append("| 法源层级 | `按法源层级/` | 宪法、法律（按立法法部门法分节）、行政法规、监察法规、司法解释、部门规章、准则全目录、国资专题、地方分省索引 |")
readme.append("| 主题领域 | `按主题领域/` | 24 个主题（多标签）+ 综合及其他。**会计审计与财务**、**税务与税收**为旗舰专题，含细分子类 |")
readme.append("| 地域 | `按地域/` | 按省份，页内分 地方性法规/地方政府规章 → 发文机关 |")
readme.append("| 发文机关 | `按发文机关/` | 国务院部门规章按机关分组 |")
readme.append("| 年份 | `按年份/` | 法源层级 × 年代 计数矩阵 |")
readme.append("| 税务案例 | `税务案例索引/` | %d 份税务局公告，地区×栏目 |" % len(cases))
readme.append("")
readme.append("## 三、主题规模一览")
readme.append("")
readme.append("| 主题 | 条目数 |")
readme.append("|---|---:|")
for t, n in topic_cnt.most_common():
    readme.append("| %s | %d |" % (t, n))
readme.append("")
readme.append("## 四、法源层级规模")
readme.append("")
readme.append("| 层级 | 条目数 |")
readme.append("|---|---:|")
for lv in LEVEL_ORDER:
    if levels_cnt.get(lv):
        readme.append("| %s | %d |" % (lv, levels_cnt[lv]))
readme.append("")
readme.append("## 五、agent 检索指引")
readme.append("")
readme.append("1. **按主题找法**：先查 `按主题领域/`（如 `会计审计与财务.md`、`税务与税收.md`），"
              "条目给出 md 相对路径（相对于 `lawlibrary/`）。")
readme.append("2. **精确定位**：`索引总表.csv` 按标题/文号/机关过滤，`md路径` 列即文件位置。")
readme.append("3. **地方规定**：`按地域/<省份>.md`；税收地方配套另见 `按主题领域/税务与税收.md` 各子类的省份小节。")
readme.append("4. **准则检索**：`按法源层级/会计准则与执业准则.md`（企业会计准则/政府及行业会计制度/执业准则三节，含文号）。")
readme.append("5. 主题与子类为关键词自动标注（多标签），存在少量边界模糊；以标题原文为准。")
readme.append("")
readme.append("## 六、重新生成")
readme.append("")
readme.append("库内容更新后，运行 `python work/scripts/build_catalog.py` 即可按最新磁盘状态重建全部索引"
              "（只读扫描 `lawlibrary/`，输出到本目录；各维度会自动清理上一轮的陈旧页面）。"
              "税务案例目录如有新增，重跑即可纳入。")
readme.append("")
open(os.path.join(OUT, "README.md"), "w", encoding="utf-8", newline="\n").write("\n".join(readme) + "\n")

print("OUT:", OUT)
print("levels:", dict(levels_cnt.most_common()))
print("unmapped-region local:", sum(1 for e in loc_items if not e["region"]))
print("empty-md by level:", dict(Counter(e["level"] for e in entries if not e["md"])))
print("topic counts:", dict(topic_cnt.most_common(30)))
