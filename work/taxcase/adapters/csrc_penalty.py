# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
证监会 涉税行政处罚 抓取 adapter
============================================================
入口：
  - 行政处罚栏目页 http://www.csrc.gov.cn/csrc/c101928/common_list.shtml
    （栏目 channelid=28de6b87eda140cb93de4dd10d11867d，同页还有 市场禁入/行政复议 子栏目）
  - 列表接口（render.js 揭示）：
    /searchList/{channelid}?_isAgg=true&_isJson=true&_pageSize=20&_template=index&page=N
    → JSON data.results[].url(//开头)/publishedTimeStr。pageSize 服务端封顶20。
  - 决议书详情 /csrc/c101928/cNNNNNN/content.shtml，标题全部相同
    （"中国证券监督管理委员会行政处罚决定书"），文号与当事人在正文里。
筛选：近2年全部决定书逐篇取正文，按税关键词命中数过滤（涉税场景：
  股权转让偷逃税、并购重组税务违规、虚增利润等），量控50件。
输出目录：lawlibrary/专题/税务案例/证监会/涉税行政处罚/
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, sys, json
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import taxcase_scrape as t

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
ROOT = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "证监会", "涉税行政处罚")
LIST_JSON = os.path.join(os.path.dirname(HERE), "tmp", "csrc_list.json")

TAX_KWS = ["税款", "税务", "纳税", "偷逃税", "逃税", "个人所得税", "增值税",
           "企业所得税", "印花税", "出口退税", "欠税", "骗税", "虚开", "税前列支",
           "代扣代缴", "股权转让"]


def fetch_one(url):
    r = t.polite_get(url, delay=2.5, referer="http://www.csrc.gov.cn/csrc/c101928/common_list.shtml")
    if r is None:
        return None
    d = t.extract_detail(r.text, url, "", "")
    if not d or len(d["md"]) < 200:
        return None
    md = d["md"]
    # 去掉头部"索引号/分类/发布机构"元数据表
    m = re.search(r"#\s*中国证券监督管理委员会", md)
    if m:
        md = md[m.start():]
    # 去尾部噪音
    for mark in ["扫一扫", "相关附件", "【打印】", "版权声明", "主办单位"]:
        i = md.find(mark)
        if i != -1:
            md = md[:i]
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    # 文号与当事人
    wh = ""
    m = re.search(r"〔20\d{2}〕\s*(\d+)\s*号", md)
    if m:
        wh = m.group(0).replace(" ", "")
    party = ""
    m = re.search(r"当事人[:：]\s*([^\n,，。;；]{2,30})", md)
    if m:
        party = m.group(1).strip()
    hits = sum(md.count(k) for k in TAX_KWS)
    kws = sorted({k for k in TAX_KWS if k in md})
    return {"md": md, "wh": wh, "party": party, "hits": hits, "kws": kws}


def scan():
    items = json.load(open(LIST_JSON, encoding="utf-8"))
    prog_path = os.path.join(t.PROG_DIR, "csrc_scan.jsonl")
    done = set()
    if os.path.exists(prog_path):
        for line in open(prog_path, encoding="utf-8"):
            try:
                rec = json.loads(line)
                if rec.get("fetched"):
                    done.add(rec["url"])
            except json.JSONDecodeError:
                pass
    prog = open(prog_path, "a", encoding="utf-8")
    n = 0
    for it in items:
        if it["url"] in done:
            continue
        res = fetch_one(it["url"])
        if res is None:
            prog.write(json.dumps({"url": it["url"], "fetched": False},
                                  ensure_ascii=False) + "\n")
        else:
            prog.write(json.dumps({"url": it["url"], "fetched": True,
                                   "date": it["date"], "wh": res["wh"],
                                   "party": res["party"], "hits": res["hits"],
                                   "kws": res["kws"]},
                                  ensure_ascii=False) + "\n")
        prog.flush()
        n += 1
        if n % 20 == 0:
            print(f"scanned {n}")
    print("scan done", n)


def save(min_hits=5):
    prog_path = os.path.join(t.PROG_DIR, "csrc_scan.jsonl")
    cands = []
    for line in open(prog_path, encoding="utf-8"):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("fetched") and rec.get("hits", 0) >= min_hits:
            cands.append(rec)
    cands.sort(key=lambda r: -r["hits"])
    print(f"candidates(>={min_hits} hits): {len(cands)}")
    for c in cands[:60]:
        print(" ", c["date"], c["wh"], c["party"][:20], "hits:", c["hits"], c["kws"])
    return cands


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        scan()
    elif len(sys.argv) > 1 and sys.argv[1] == "save":
        save(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    else:
        scan()
