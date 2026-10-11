# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
广东深挖（第九轮）：合规指导类案例 + 稀疏类型 + 横琴/南沙新频道 + 深圳合规词
================================================================================
背景（R9）：此前广东仅扫 查处/曝光/稽查 类强案件词，合规指导类案例（正反面）
与稀疏类型（非居民/转让定价/代扣代缴/社保费/股权转让）是盲区；横琴(zhhqsw)
与南沙(gznssw)频道不在 round2 的 21 市名单内从未被扫；深圳站同理未扫合规词。

信源（实测 2026-10-11）：
  C1 广东省站 search5（POST /search5/search/s，siteCode=bm29190001，覆盖省站+
     市县子站）关键词：以案释法/典型案例/风险提醒/合规指引/普法/警示/调解/
     转让定价/非居民/股权转让/社保费 处罚/代扣代缴/中介 涉税/税务师 处罚/
     土地增值税 案例
     —— 广东站无 was5（404，福建契约不适用，勿走弯路）
  C2 横琴粤澳深度合作区频道（/gdsw/zhhqsw_*）与广州南沙频道（/gdsw/gznssw_*）：
     TRS gdtaxejs JSON 列表接口（channelId 藏在 city_list.shtml 内联 JS），
     横琴 tzgg=174df131ae53444eb37a7507edfd7929 swxw=a8c2558906f4452ebbdef26d901f24b5
     dmtxc=bf2de2d2c3c64ed0be6d737dc11d9f85；南沙 tzgg=e2616e6c9a8641fbad4124f2c49bca0c
     swxw=cc91d1af19b345249e2df2f0f7a018c8。
     横琴/南沙 tzgg 的送达/催缴批次为空正文+.xls 名单附件（程序性），标题预筛跳过
  C3 深圳站开普云搜索（POST https://zs.kaipuyun.cn/search5/search/s，
     siteCode=bm29360001，Origin/Referer 须带 shenzhen.chinatax.gov.cn）合规词扫

质量：自家 gate（叙事标记+具体性三选一）→ quality_prune2.decide()，DEL 不入库。
量控：每源 ≤800；日期 ≥2023-01-01；全局 URL 去重含 gd_cases/gd_city_cases/sz_cases。
用法：python gd_deep_r9.py [--src gd|hq|sz|all]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import argparse
import json
import os
import re
import sys
import time
from datetime import date
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import taxcase_scrape as t  # noqa: E402
from quality_prune2 import decide  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

GD_HOST = "https://guangdong.chinatax.gov.cn"
SZ_HOST = "https://shenzhen.chinatax.gov.cn"
SZ_SEARCH = "https://zs.kaipuyun.cn/search5/search/s"
DELAY = 1.5
DATE_FROM = "2023-01-01"
PROG = os.path.join(ROOT, "progress", "gd_deep_r9.jsonl")
LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例"))
SRC_CAP = 800

# ---------------- C1/C3 关键词 ----------------
GD_TERMS = [
    "以案释法", "典型案例", "风险提醒", "合规指引", "普法", "警示", "调解",
    "转让定价", "非居民", "股权转让", "社保费 处罚", "代扣代缴",
    "中介 涉税", "税务师 处罚", "土地增值税 案例",
]
SZ_TERMS = [
    "以案释法", "典型案例", "风险提醒", "合规指引", "警示", "调解",
    "转让定价", "非居民", "股权转让", "代扣代缴",
]

# 标题过滤：命中才要（合规指导/案例/执法标记词，补 round1/round2 的盲区词）
TITLE_KW = re.compile(
    r"以案|案例|税案|释法|风险提醒|风险提示|警示|误区|红线|自查|指引|普法|"
    r"查处|曝光|骗取|虚开|偷税|逃税|欠税|追缴|追征|查补|补缴|失信|违法|处罚|"
    r"移送|复议|调解|合规|转让定价|非居民|股权|代扣代缴|社保费")
TITLE_EXCL = re.compile(
    r"采购|招标|中标|招聘|遴选|听证|征求意见|党纪|党课|党委|纪委|巡视|"
    r"新闻发布|发布会$|成果展|表彰|演练|物业管理|运维|遴选|询价|竞争性磋商|"
    r"录取|任职|任免|笔试|面试")
URL_EXCL = re.compile(r"/(zcwj|zcjd|wzjd|zjfg|ssfggds|bmfw|bszn)/")

# C2 通知公告标题预筛（跳过程序性催缴/催报名单批次）
TZ_SKIP = re.compile(r"送达|催缴|催报|限期缴纳|责令限期改正|核定|定期定额")
TZ_KW = re.compile(r"欠税|处罚|失信|非正常户|违法")

# 21 市 + 横琴/南沙频道码（URL /gdsw/{code}_{col}/ → 目录）
CITY_CODE = {
    "gzsw": "广州市", "zhsw": "珠海市", "stsw": "汕头市", "fssw": "佛山市",
    "sgsw": "韶关市", "hysw": "河源市", "hzsw": "惠州市", "swsw": "汕尾市",
    "dgsw": "东莞市", "zssw": "中山市", "jmsw": "江门市", "yjsw": "阳江市",
    "zjsw": "湛江市", "mmsw": "茂名市", "zqsw": "肇庆市", "qysw": "清远市",
    "czsw": "潮州市", "jysw": "揭阳市", "yfsw": "云浮市",
    "zhhqsw": "横琴粤澳深度合作区", "gznssw": "广州市南沙区",
}

# ---------------- 内容 gate（自家门槛，先于 quality_prune2） ----------------
NARR_RE = re.compile(r"案例|案情|经查|经税务机关|经稽查|风险|警惕|警示|误区|红线|"
                     r"自查|某公司|某企业|某纳税人|该纳税人|纳税人.{0,12}(应当|不得|避免|注意)")
UNIT_RE = re.compile(r"万?元|份|倍|%|税率|车|张|笔|条|人|万元|亿元")
VERB_RE = re.compile(r"开具|取得|接受|收取|隐匿|虚开|抵扣|申报|入账|转给|勾结|伪造|"
                     r"篡改|编造|冒用|骗取|逃避|偷逃|不报|隐瞒|冲抵|代开|变更|注销|"
                     r"冲红|补缴|追缴|转让|分配|扣缴")
ENF_RE = re.compile(r"稽查|查处|偷税|虚开|骗取|隐匿|追缴|查补|移送|失信|欠税|处罚")
CASE_MK = re.compile(r"某公司|某企业|某纳税人|案例[一二三四五六七八九十1-9]|案情|"
                     r"以案|涉案|该公司被|一户|一名")
RISK_RE = re.compile(r"风险提醒|风险提示|误区|红线|警惕|自查|合规指引|不得|避免")


def cjk_len(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def gate(md):
    """合规指导/案例类内容门槛：叙事标记 + 具体性（执法/案例/风险 三选一）"""
    cjk = cjk_len(md)
    if cjk < 300:
        return False, f"short({cjk})"
    if not NARR_RE.search(md):
        return False, "no-narr"
    digits = len(re.findall(r"\d", md))
    has_unit = bool(UNIT_RE.search(md))
    verbs = len(VERB_RE.findall(md))
    if ENF_RE.search(md) and digits >= 3:
        return True, "enf"
    if CASE_MK.search(md) and digits >= 2 and has_unit:
        return True, "case"
    if RISK_RE.search(md) and verbs >= 3 and digits >= 2:
        return True, "risk"
    return False, "no-specific"


def classify(title):
    if "以案释法" in title or "以案" in title:
        return "以案释法"
    if "典型案例" in title:
        return "典型案例"
    if re.search(r"合规|风险提醒|风险提示|警示|误区|红线|自查|指引|普法", title):
        return "税务合规"
    if re.search(r"行政复议|复议|调解", title):
        return "税案通报"
    return "税案通报"


# ---------------- progress / 去重 ----------------
_seen = {}


def load_prog():
    for p in ["gd_deep_r9.jsonl", "gd_cases.jsonl", "gd_city_cases.jsonl", "sz_cases.jsonl"]:
        fp = os.path.join(ROOT, "progress", p)
        if not os.path.exists(fp):
            continue
        for line in open(fp, encoding="utf-8"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            u = j.get("url") or j.get("k")
            if u:
                # 旧断点只登记已处理（ok/done）与已跳过，全部视为 seen 防重复抓
                _seen.setdefault(u, "old:" + p)


def mark(url, st, **kw):
    _seen[url] = st
    j = {"url": url, "st": st}
    j.update(kw)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(j, ensure_ascii=False) + "\n")


_stats = {"done": 0, "reject": 0, "old": 0, "fail": 0, "skip": 0}


# ---------------- 落盘 ----------------
def write_md(folder, region, column, url, title, ds, md, attachments, src_name):
    out_dir = os.path.join(LAWLIB, region, folder, column)
    os.makedirs(out_dir, exist_ok=True)
    fn = f"{ds or 'nodate'}_{t.safe_filename(title)}.md"
    p = os.path.join(out_dir, fn)
    if os.path.exists(p):
        return "exists"
    fm = ("---\n"
          f'title: "{title.replace(chr(34), "")}"\n'
          f'来源机关: "{src_name}"\n'
          f'栏目: "{column}"\n'
          f'地区: "{region}"\n'
          f"发布日期: {ds or ''}\n"
          '原文来源: "广东省税务局/深圳市税务局网站（第九轮深挖）"\n'
          f"抓取日期: {date.today().isoformat()}\n"
          f"原文链接: {url}\n")
    if attachments:
        fm += "附件:\n" + "\n".join(f"  - {a}" for a in attachments) + "\n"
    fm += "---\n\n"
    body = re.sub(r"\n{3,}", "\n\n", md).strip()
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(fm + body + "\n")
    return "done"


def city_of(url):
    m = re.search(r"/gdsw/([a-z]+)_", url)
    if m:
        return CITY_CODE.get(m.group(1), "")
    return ""


def process(url, title, ds, region_base):
    """详情抓取+双门槛+入库。返回状态。"""
    host = SZ_HOST if "shenzhen.chinatax" in url else GD_HOST
    r = t.polite_get(url, DELAY, referer=host + "/")
    if r is None:
        return "fetch-fail"
    d = t.extract_detail(r.text, url, title, ds)
    if not d or len(d.get("md") or "") < 100:
        return "parse-fail"
    md = re.sub(r"!\[\]\([^)]*icons/[a-z]+\.png\)", "", d["md"])
    md = re.sub(r"^(浏览次数|字号|打印本页|分享至|【打印】|【关闭】).*$", "", md,
                flags=re.M)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    ok, why = gate(md)
    if not ok:
        return "rejected:" + why
    title2 = (d.get("title") or title).strip() or "untitled"
    title2 = re.sub(r"\s+", " ", title2)
    ds2 = d.get("date") or ds or ""
    column = classify(title2)
    verdict, _why = decide(column, region_base, md)
    if verdict == "DEL":
        return "prune-del"
    if region_base == "深圳市":
        folder, src_name = "", "国家税务总局深圳市税务局"
    else:
        folder = city_of(url) or ""
        src_name = "国家税务总局广东省税务局"
    st = write_md(folder, region_base, column, url, title2, ds2, md,
                  d.get("attachments"), src_name)
    return st


# ---------------- C1/C3：search5 类接口 ----------------
def search5_page(api, site_code, term, page_num, origin_host):
    """search5 单页请求。空结果（total=0 且 docs 空）按瞬时节流处理重试——
    实测开普云后端对连续 POST 会偶发回 total=0 空集（200 状态），不重试会
    让整个关键词提前断流（首轮 普法/警示/非居民 等词全因此漏扫）。"""
    data = {"siteCode": site_code, "searchWord": quote(term), "column": "",
            "wordPlace": "0", "orderBy": "1", "pageSize": "15",
            "pageNum": str(page_num), "checkHandle": "1", "conditionsPattern": "1"}
    last = None
    for attempt in range(4):
        time.sleep(DELAY + 1.0 + (attempt if attempt else 0) * 2.0)
        try:
            rr = cr.post(api, data=data, impersonate="chrome124", timeout=45,
                         headers={"Origin": origin_host,
                                  "Referer": origin_host + "/"})
            if rr.status_code == 200:
                j = rr.json()
                sra = j.get("searchResultAll", {})
                docs = sra.get("searchTotal") or []
                if docs or (int(sra.get("total") or 0) > 0):
                    return j
                last = j  # 空响应，退避重试
        except Exception:
            pass
    return last  # 4 次仍空：真没结果（或持续节流），返回最后一次供上层判断


def run_search(api, site_code, terms, region_base, url_prefix, cap, tag):
    done0 = _stats["done"]
    for term in terms:
        page = 0
        total = None
        n_term = 0
        while _stats["done"] - done0 < cap:
            if total is not None and page * 15 >= min(total, 1500):
                break
            j = search5_page(api, site_code, term, page, url_prefix)
            if j is None:
                print(f"  [{tag}] {term} page{page} FAIL", flush=True)
                break
            sra = j.get("searchResultAll", {})
            docs = sra.get("searchTotal") or []
            total = int(sra.get("total") or 0)
            if not docs:
                break
            for d in docs:
                u = (d.get("url") or "").strip()
                # search5 对老文档返回 http:// scheme，统一归一 https 再比对前缀，
                # 否则 2023-2024 老件会被前缀检查静默丢掉（实测踩坑）
                if u.startswith("http://"):
                    u = "https://" + u[len("http://"):]
                ti = re.sub(r"<[^>]+>", "", d.get("title") or "").strip()
                ti = re.sub(r"\s+", " ", ti)
                pd = str(d.get("pubDate") or "")[:10]
                if not u or not ti:
                    continue
                if not u.startswith(url_prefix):
                    continue
                if URL_EXCL.search(u) or TITLE_EXCL.search(ti):
                    continue
                if not TITLE_KW.search(ti):
                    continue
                if u in _seen:
                    continue
                if pd and pd < DATE_FROM:
                    _seen[u] = "old"
                    _stats["old"] += 1
                    continue
                st = process(u, ti, pd, region_base)
                mark(u, st, src=tag, term=term, title=ti, date=pd)
                if st == "done":
                    _stats["done"] += 1
                    n_term += 1
                    print(f"    + [{tag}] {pd} {ti[:48]}", flush=True)
                elif st.startswith("rejected") or st == "prune-del":
                    _stats["reject"] += 1
                elif "fail" in st:
                    _stats["fail"] += 1
                if _stats["done"] - done0 >= cap:
                    break
            page += 1
            if page > 100:
                break
        print(f"  [{tag}] term={term!r} total={total} +{n_term} "
              f"(cum {tag}:{_stats['done']-done0})", flush=True)
    return _stats["done"] - done0


# ---------------- C2：gdtaxejs 频道列表 ----------------
# 注：横琴 dmtxc（多媒体宣传）channelId 经 JSON 接口 total=0，且其页面为
# 视频/微信壳页无文本层（实测），不纳入
HQ_CHANNELS = [
    ("横琴粤澳深度合作区", [
        ("通知公告", "174df131ae53444eb37a7507edfd7929"),
        ("税务新闻", "a8c2558906f4452ebbdef26d901f24b5")]),
    ("广州市南沙区", [
        ("通知公告", "e2616e6c9a8641fbad4124f2c49bca0c"),
        ("税务新闻", "cc91d1af19b345249e2df2f0f7a018c8")]),
]


def channel_page(ch, page):
    u = (f"{GD_HOST}/gdtaxejs/common/search/{ch}"
         f"?_pageSize=20&page={page}&_isAgg=true&_isJson=true&_template=index")
    for attempt in range(3):
        time.sleep(DELAY + 0.5)
        try:
            r = cr.get(u, impersonate="chrome124", timeout=40,
                       headers={"Referer": GD_HOST + "/"})
            if r.status_code == 200:
                j = json.loads(r.text)
                return j.get("data") or {}
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def run_channels(cap):
    done0 = _stats["done"]
    for city, cols in HQ_CHANNELS:
        for colname, ch in cols:
            page = 1
            n_col = 0
            while page <= 40 and _stats["done"] - done0 < cap:
                data = channel_page(ch, page)
                if data is None:
                    print(f"  [hq] {city}/{colname} page{page} FAIL", flush=True)
                    break
                items = data.get("results") or []
                if not items:
                    break
                stop = False
                for it in items:
                    raw = (it.get("url") or "").strip()
                    if raw.startswith("../../"):
                        u = GD_HOST + "/" + raw[6:]
                    elif raw.startswith("/"):
                        u = GD_HOST + raw
                    else:
                        u = GD_HOST + "/" + raw
                    ti = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "",
                                it.get("title") or "")).strip()
                    ds = (it.get("publishedTimeStr") or "")[:10]
                    if not u or not ti:
                        continue
                    if ds and ds < DATE_FROM:
                        _seen[u] = "old"
                        _stats["old"] += 1
                        stop = True
                        continue
                    if colname == "通知公告":
                        if TZ_SKIP.search(ti) or not TZ_KW.search(ti):
                            if u not in _seen:
                                mark(u, "skip-tz", src="hq", city=city, title=ti)
                                _seen[u] = "skip-tz"
                                _stats["skip"] += 1
                            continue
                    else:
                        if not TITLE_KW.search(ti) or TITLE_EXCL.search(ti):
                            if u not in _seen:
                                mark(u, "skip-kw", src="hq", city=city, title=ti)
                                _seen[u] = "skip-kw"
                                _stats["skip"] += 1
                            continue
                    if u in _seen:
                        continue
                    st = process(u, ti, ds, "广东省")
                    mark(u, st, src="hq", city=city, col=colname, title=ti, date=ds)
                    if st == "done":
                        _stats["done"] += 1
                        n_col += 1
                        print(f"    + [hq:{city}] {ds} {ti[:46]}", flush=True)
                    elif st.startswith("rejected") or st == "prune-del":
                        _stats["reject"] += 1
                    elif "fail" in st:
                        _stats["fail"] += 1
                    if _stats["done"] - done0 >= cap:
                        stop = True
                        break
                if stop:
                    break
                if page * 20 >= int(data.get("total") or 0):
                    break
                page += 1
            print(f"  [hq] {city}/{colname} +{n_col}", flush=True)
    return _stats["done"] - done0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="all", help="gd | hq | sz | all")
    args = ap.parse_args()
    load_prog()
    print(f"resume: seen={len(_seen)} stats={_stats}", flush=True)
    if args.src in ("gd", "all"):
        n = run_search(GD_HOST + "/search5/search/s", "bm29190001",
                       GD_TERMS, "广东省", GD_HOST, SRC_CAP, "gd")
        print(f"== C1 广东 search5 合规/稀疏词扫: +{n}", flush=True)
    if args.src in ("hq", "all"):
        n = run_channels(SRC_CAP)
        print(f"== C2 横琴/南沙频道: +{n}", flush=True)
    if args.src in ("sz", "all"):
        n = run_search(SZ_SEARCH, "bm29360001", SZ_TERMS, "深圳市",
                       SZ_HOST, SRC_CAP, "sz")
        print(f"== C3 深圳合规词扫: +{n}", flush=True)
    print(f"TOTAL stats={_stats}", flush=True)


if __name__ == "__main__":
    main()
