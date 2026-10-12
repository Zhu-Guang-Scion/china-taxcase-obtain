# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
R10 · 税务批复/函件 —— 信源二：税屋 shui5.cn（中央年份列 + 省份列）
====================================================================
机制（2026-10-11 实测，调研见 _research/pifu_sources_r10.md）：
  墙: 阿里云 WAF（acw_sc__v2 JS 挑战）。playwright 有头一次过（headless 也曾通过，
      本脚本默认有头，SHUI5_HEADLESS=1 切无头）；离线解 JS 会挂反调试，勿走。
      挑战页特征：正文含 renderData 且 len<12000。会话过期 → 重建 page/整浏览器。
  列: /article/{slug}/ 第1页，/article/{slug}/{colid}_{page}.html 翻页；
      条目块 <div class="xwt2">：xwt2_a>title / xwt2_d>p.p3 发布日期 / p.p4>栏目名。
      年份 slug 从站内年份导航提取（2017-2019 为全小写 2018nianshuishoufagui，
      其余驼峰；2021+ 为 {yr}NianFaGui）——大小写敏感，勿自造。
  文: /article/{2hex}/{id}.html，正文 <!--arcContent--> … <!--/arcContent-->；
      长文分页 {id}_{n}.html（n≥2），逐页拼接。
  礼貌: 单线程，2.2-3.2s 抖动间隔。

采集口径（brief R10）：
  central 优先反转：2020/2019/2018 函+批复全收 → 1994-2017 只收"批复"类 →
  2021-2026 函类扫描（近年中央函≈0，快速过）。
  prov：粤苏浙沪京 5 省，文号年份≥2023 的省税函，≤1000 件。

去重：norm_docno（pifu_r10.py 复用）——fgk 已入库文号键为权威，税屋同文跳过
      （记 dup_of）；fgk 与 12366/法规库实测零重叠。

用法:
  python adapters/shui5_r10.py --mode central   # 中央年份列（列表缓存+详情断点）
  python adapters/shui5_r10.py --mode prov      # 5 省省税函
  python adapters/shui5_r10.py --mode central --list-only   # 只枚举列表
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import argparse
import json
import os
import random
import re
import sys
import time
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import taxcase_scrape as t  # noqa: E402
from pifu_r10 import (norm_docno, docno_from_title, title_key,  # noqa: E402
                      strip_tags_keep_lines, cn_chars, TITLE_BLACKLIST)

REPO = os.environ.get(
    "CHINALAW_ROOT", os.path.normpath(os.path.join(HERE, "..", "..", "..")))
LIB = os.path.join(REPO, "lawlibrary", "专题", "税务案例", "全国", "税务批复与函件")
JOB = "pifu_r10"
DELAY = (2.2, 3.2)          # 税屋单线程慎频
HEADLESS = os.environ.get("SHUI5_HEADLESS") == "1"
MAX_CENTRAL = 2400          # 全局 ≤4000：fgk 530 + prov 1000 预留
MAX_PROV = 1000

# 年份 slug（站内年份导航实测提取；2017-2019 全小写）
YEAR_SLUGS = {
    **{yr: f"{yr}NianShuiShouFaGui" for yr in range(1994, 2017)},
    2017: "2017nianshuishoufagui", 2018: "2018nianshuishoufagui",
    2019: "2019nianshuishoufagui", 2020: "2020NianShuiShouFaGui",
    **{yr: f"{yr}NianFaGui" for yr in range(2021, 2027)},
}
PROV_SLUGS = {   # brief 重点省
    "广东": "GuangDongShengCaiShuiFaGu", "江苏": "JiangSuShengCaiShuiFaGui",
    "浙江": "ZheJiangShengCaiShuiFaGui", "上海": "ShangHaiShiCaiShuiFaGui",
    "北京": "BeiJingShiCaiShuiFaGui",
}
# 文号机关段口径
HAN_ORGS = {"国税函", "国税函发", "国税函字", "税总函", "税总办函", "税函"}
CENTRAL_ORGS = HAN_ORGS | {"国税发", "税总发", "税总办发"}
# 省税函机关段（沪税函/沪国税函/粤税函/苏税函/浙税函/京税函/浙国税函/沪地税函…）
PROV_DOC_RE = re.compile(r"^(.{1,6}税.{0,3}函)$")


def want_central(year, org, title):
    """中央列收件口径：A 组(2018-2020)函+批复；B 组(1994-2017)批复；C 组(2021+)函。"""
    if org in HAN_ORGS:
        return True
    if year >= 2018 and year <= 2020 and "批复" in title and org in CENTRAL_ORGS:
        return True
    if year <= 2017 and "批复" in title and org in CENTRAL_ORGS:
        return True
    return False


def want_prov(org, year, title):
    if TITLE_BLACKLIST.search(title):
        return False
    try:
        y = int(year)
    except (TypeError, ValueError):
        return False
    return bool(PROV_DOC_RE.match(org)) and y >= 2023


# ---------------- WAF 会话 ----------------

class Shui5:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.n_req = 0
        self.start()

    def start(self):
        from playwright.sync_api import sync_playwright
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
        self.pw = sync_playwright().start()
        launch = dict(
            args=["--disable-blink-features=AutomationControlled"])
        try:
            self.browser = self.pw.chromium.launch(headless=HEADLESS, **launch)
        except Exception:
            self.browser = self.pw.chromium.launch(headless=True, **launch)
        self.ctx = self.browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900})
        self.page = self.ctx.new_page()

    def _nav(self, url):
        self.page.goto(url, timeout=60000, wait_until="domcontentloaded")

    def fetch(self, url, tries=2):
        """过 WAF 抓取；返回 HTML（'File not found.' 短页原样返回由调用方判）。"""
        for attempt in range(tries):
            time.sleep(random.uniform(*DELAY))
            self.n_req += 1
            try:
                self._nav(url)
                for _ in range(22):
                    time.sleep(1)
                    c = self.page.content()
                    if "renderData" not in c and len(c) > 12000:
                        return c
                    if "File not found" in c:
                        return c
                # 挑战未过 → 换 page 再来
                print(f"  [waf] challenge persist @ {url[-40:]} renew page")
                self.page = self.ctx.new_page()
            except Exception as e:
                print(f"  [waf] nav err {str(e)[:60]} @ {url[-40:]}")
                try:
                    self.page = self.ctx.new_page()
                except Exception:
                    self.start()
        # 两轮失败 → 重开整个浏览器再来一次
        print("  [waf] restart browser")
        try:
            self.start()
        except Exception:
            pass
        return ""

    def close(self):
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.pw.stop()
        except Exception:
            pass


# ---------------- 列表解析 ----------------

XWT2 = re.compile(
    r'<div class="xwt2_a"><a href="(https://www\.shui5\.cn/article/[0-9a-fA-F]{1,2}/\d+\.html)"'
    r'(?:[^>]*title="([^"]*)")?[^>]*>(.*?)</a>.*?'
    r'<p class="p3">([\d-]+)</p>\s*<p class="p4"><a href="[^"]*/article/([A-Za-z0-9]+)/',
    re.S)


def parse_list(c, slug):
    out = []
    for m in XWT2.finditer(c):
        url, t1, t2, dt, colslug = m.groups()
        title = re.sub(r"<[^>]+>", "", t1 or t2).strip()
        if not title or colslug.lower() != slug.lower():
            continue                      # 非本栏（侧栏/推荐位）剔除
        out.append({"url": url, "title": title, "date": dt})
    # 去重（同 url）
    seen, dedup = set(), []
    for it in out:
        if it["url"] not in seen:
            seen.add(it["url"])
            dedup.append(it)
    return dedup


def col_page1(c, slug):
    """返回 (colid, max_page)。"""
    pairs = re.findall(slug + r"/(\d+)_(\d+)\.html", c, re.I)
    if not pairs:
        return None, 1
    colid = pairs[0][0]
    mx = max(int(p[1]) for p in pairs)
    return colid, mx


# ---------------- 列表枚举 ----------------

def enum_central_lists(s5, cache_path):
    items = []
    order = ([2020, 2019, 2018] + list(range(2017, 1993, -1))
             + list(range(2021, 2027)))          # 优先反转：近三年→早年→现行年
    for yr in order:
        slug = YEAR_SLUGS[yr]
        try:
            c = s5.fetch(f"https://www.shui5.cn/article/{slug}/")
        except Exception as e:
            print(f"[c-list] {yr} ERR {str(e)[:60]}")
            continue
        if not c or "File not found" in c or 'class="xwt2"' not in c:
            print(f"[c-list] {yr} no column ({slug})")
            continue
        colid, mx = col_page1(c, slug)
        yr_items = parse_list(c, slug)
        n_han = 0
        for pg in range(2, mx + 1):
            c2 = s5.fetch(f"https://www.shui5.cn/article/{slug}/{colid}_{pg}.html")
            if not c2 or "File not found" in c2:
                continue
            yr_items += parse_list(c2, slug)
        # 去重 + 口径过滤
        seen = set()
        for it in yr_items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            nt = docno_from_title(it["title"])
            if not nt:
                continue
            org, dyear, dno, key = nt
            if int(dyear) != yr and yr >= 2018:
                pass                        # 列内偶有跨年文号，不剔除
            if not want_central(yr, org, it["title"]):
                continue
            if TITLE_BLACKLIST.search(it["title"]):
                continue
            it.update({"docno": f"{org}[{dyear}]{dno}号", "docno_key": key,
                       "year": yr, "region": "全国", "src2": "central"})
            items.append(it)
            n_han += 1
        print(f"[c-list] {yr}: pages={mx} items={len(seen)} kept={n_han}")
        json.dump(items, open(cache_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
    print(f"[c-list] central kept total={len(items)}")
    return items


def enum_prov_lists(s5, cache_path, cap):
    # 缓存按省存 {prov: [items]}，续跑跳过已枚举省份
    cache = {}
    if os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            cache = {}
    items = []
    for prov, slug in PROV_SLUGS.items():
        if prov in cache:
            items += cache[prov]
            print(f"[p-list] {prov} cached {len(cache[prov])}")
            continue
        c = s5.fetch(f"https://www.shui5.cn/article/{slug}/")
        if not c or "File not found" in c or 'class="xwt2"' not in c:
            print(f"[p-list] {prov} no column")
            continue
        colid, mx = col_page1(c, slug)
        yr_items = parse_list(c, slug)
        # 实测省列非严格时间倒序（第 1 页即混 2026/2019 文），早停会漏
        # ——全列翻页，按文号年份 ≥2023 过滤
        for pg in range(2, mx + 1):
            c2 = s5.fetch(f"https://www.shui5.cn/article/{slug}/{colid}_{pg}.html")
            if not c2 or "File not found" in c2:
                continue
            yr_items += parse_list(c2, slug)
            if pg % 20 == 0:
                print(f"[p-list] {prov} page {pg}/{mx}")
        seen = set()
        n_keep = 0
        kept = []
        for it in yr_items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            nt = docno_from_title(it["title"])
            if not nt:
                continue
            org, dyear, dno, key = nt
            if not want_prov(org, dyear, it["title"]):
                continue
            it.update({"docno": f"{org}[{dyear}]{dno}号", "docno_key": key,
                       "year": int(dyear), "region": prov, "src2": "prov"})
            kept.append(it)
            n_keep += 1
        cache[prov] = kept
        items += kept
        print(f"[p-list] {prov}: pages≤{mx} items={len(seen)} kept(2023+)={n_keep}")
        json.dump(cache, open(cache_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        if len(items) >= cap:
            items = items[:cap]
            break
    items = items[:cap]
    print(f"[p-list] prov kept total={len(items)}")
    return items


# ---------------- 详情 ----------------

ARC_RE = re.compile(r"<!--arcContent-->(.*?)<!--/arcContent-->", re.S)


def article_body(s5, c, url):
    """arcContent 抽取 + 多页拼接。"""
    parts = []
    m = ARC_RE.search(c)
    if m:
        parts.append(strip_tags_keep_lines(m.group(1)))
    aid = re.search(r"/(\d+)\.html", url).group(1)
    extra = sorted(set(re.findall(r'href="[^"]*/(\d+)_(\d+)\.html"', c)),
                   key=lambda x: int(x[1]))
    for base, pg in extra:
        if base == aid and int(pg) >= 2:
            u2 = url.replace(f"/{aid}.html", f"/{aid}_{pg}.html")
            c2 = s5.fetch(u2)
            if c2:
                m2 = ARC_RE.search(c2)
                if m2:
                    parts.append(strip_tags_keep_lines(m2.group(1)))
    return "\n\n".join(p for p in parts if p).strip()


def issuer_from_title(title, org):
    """税屋标题 '文号 机关…关于…' → 机关名；失败按文号前缀映射省局。"""
    m = re.match(r"^[^\s〔\[]+\s+([\u4e00-\u9fff][\u4e00-\u9fff ]{3,24}?)(?:关于|对|转发|印发|发布|公布)",
                 title)
    if m:
        return m.group(1).strip()
    prov_map = {"沪": "上海市税务局", "粤": "广东省税务局", "苏": "江苏省税务局",
                "浙": "浙江省税务局", "京": "北京市税务局"}
    if org and org[0] in prov_map and "税" in org:
        return prov_map[org[0]]
    if org and org.startswith(("国税", "税总")):
        return "国家税务总局"
    return "国家税务总局"


AGING_MAP = {"全文废止": "全文废止", "条款废止": "部分条款废止", "失效": "全文失效"}


def title_base(title):
    """去掉文号前缀与状态尾注的标题主体。"""
    s = re.sub(r"^[^〔\[]*[[〔(]\d{4}[]〕)]\d+号\s*", "", title)
    return re.sub(r"[〔\[]全文废止[〕\]]|[〔\[]条款废止[〕\]]", "", s)


def aging_from_title(title):
    for k, v in AGING_MAP.items():
        if k in title:
            return v
    return ""


def load_prog():
    path = os.path.join(t.PROG_DIR, JOB + ".jsonl")
    done, fgk_keys, shui5_keys = set(), set(), set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("url"):
                    done.add(rec["url"])
                if rec.get("docno_key"):
                    if rec.get("src") == "fgk" and rec.get("ok"):
                        fgk_keys.add(rec["docno_key"])
                    elif rec.get("src") == "shui5" and rec.get("ok"):
                        shui5_keys.add(rec["docno_key"])
    return done, fgk_keys, shui5_keys


def run_details(s5, items, max_n, tag):
    time_limit = float(os.environ.get("SHUI5_TIME_LIMIT") or 0)   # 分钟，0=不限
    t0 = time.time()
    done, fgk_keys, skeys = load_prog()
    prog_path = os.path.join(t.PROG_DIR, JOB + ".jsonl")
    os.makedirs(LIB, exist_ok=True)
    n_new = n_dup_fgk = n_dup_self = n_skip = 0
    pending = [it for it in items if it["url"] not in done]
    print(f"[run:{tag}] done={len(items)-len(pending)} to_fetch={len(pending)} "
          f"(fgk_keys={len(fgk_keys)})")
    with open(prog_path, "a", encoding="utf-8") as prog:
        for idx, it in enumerate(pending, 1):
            if n_new >= max_n:
                print(f"[run:{tag}] cap {max_n} reached, stop")
                break
            if time_limit and (time.time() - t0) / 60 > time_limit:
                print(f"[run:{tag}] time limit {time_limit}min reached @ {idx}, stop")
                break
            key = it["docno_key"]
            if key in fgk_keys or key in skeys:
                rec = {"url": it["url"], "ok": False, "src": "shui5",
                       "docno_key": key, "src2": it.get("src2")}
                rec["dup_of"] = "fgk" if key in fgk_keys else "shui5"
                prog.write(json.dumps(rec, ensure_ascii=False) + "\n")
                prog.flush()
                if key in fgk_keys:
                    n_dup_fgk += 1
                else:
                    n_dup_self += 1
                continue
            c = s5.fetch(it["url"])
            body = article_body(s5, c, it["url"]) if c else ""
            han = cn_chars(body)
            # <100 字纯转发/形式函不收；但 40+ 字且含"收悉/批复如下"的
            # 超短实质批复（如"核桃油按13%税率"类一口径批件）保留
            substantive_short = (40 <= han < 100
                                 and ("批复" in title_base(it["title"])
                                      or re.search(r"收悉|批复如下", body)))
            if han < 100 and not substantive_short:
                prog.write(json.dumps({"url": it["url"], "ok": False,
                                       "err": "low-content", "src": "shui5",
                                       "docno_key": key, "src2": it.get("src2"),
                                       "title": it["title"]},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_skip += 1
                continue
            title = re.sub(r"\s+", " ", it["title"]).strip().strip('"')
            # 税屋标题常以文号开头且重复一次：'税总函[2020]1号 税总函[2020]1号 关于…'
            dn = it["docno"]
            if title.startswith(dn):
                rest = title[len(dn):].strip()
                if rest.startswith(dn):
                    title = dn + " " + rest[len(dn):].strip()
            org = key.split("|")[0]
            fm_org = issuer_from_title(title, org)
            ag = aging_from_title(title)
            fname = t.safe_filename(f"{it['date']}_{title}") + ".md"
            fm = ("---\n"
                  f"title: \"{title}\"\n"
                  f"来源机关: \"{fm_org}\"\n"
                  "栏目: \"税务批复与函件\"\n"
                  f"地区: \"{it['region']}\"\n"
                  f"文号: \"{it['docno']}\"\n"
                  f"发布日期: {it['date']}\n"
                  f"时效性: \"{ag}\"\n"
                  "文件类型: \"函件\"\n"
                  "原文来源: \"税屋（shui5.cn）汇编转载官方文件\"\n"
                  f"抓取日期: {date.today().isoformat()}\n"
                  f"原文链接: {it['url']}\n---\n\n")
            with open(os.path.join(LIB, fname), "w", encoding="utf-8",
                      newline="\n") as f:
                f.write(fm + body + "\n")
            prog.write(json.dumps({"url": it["url"], "ok": True, "file": fname,
                                   "docno_key": key, "src": "shui5",
                                   "src2": it.get("src2"),
                                   "region": it["region"], "year": it.get("year"),
                                   "title": title, "date": it["date"]},
                                  ensure_ascii=False) + "\n")
            prog.flush()
            skeys.add(key)
            n_new += 1
            if n_new % 50 == 0:
                print(f"[run:{tag}] {idx}/{len(pending)} new={n_new} "
                      f"dupF={n_dup_fgk} dupS={n_dup_self} skip={n_skip}")
    print(f"[run:{tag}] DONE new={n_new} dup_fgk={n_dup_fgk} "
          f"dup_self={n_dup_self} skip={n_skip}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["central", "prov"])
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    args = ap.parse_args()
    cache_path = os.path.join(
        t.PROG_DIR, JOB + (".shui5_items.json" if args.mode == "central"
                           else ".shui5_prov_items.json"))
    s5 = Shui5()
    try:
        if args.mode == "prov":
            # 缓存按省 {prov: [..]}，enum_prov_lists 自行断点续枚举
            items = enum_prov_lists(s5, cache_path, args.max or MAX_PROV)
        elif os.path.exists(cache_path):
            items = json.load(open(cache_path, encoding="utf-8"))
            print(f"[list] cache loaded {len(items)} items")
        else:
            items = enum_central_lists(s5, cache_path)
        if args.list_only:
            for it in items[:15]:
                print("[dry]", it.get("year"), it["docno"], it["title"][:44])
            print("total:", len(items))
            return
        cap = args.max or (MAX_CENTRAL if args.mode == "central" else MAX_PROV)
        run_details(s5, items, cap, args.mode)
    finally:
        s5.close()


if __name__ == "__main__":
    main()
