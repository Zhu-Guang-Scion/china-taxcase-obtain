# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
山东+四川 税案通报 抓取 adapter（微信公众号官方发布通道 via 搜狗微信搜索）
背景：两省税务局官网 shandong/sichuan.chinatax.gov.cn 均被网宿 wswaf JS挑战阻断
（412→JS计算cookie→400），改从省/市税务局官方微信公众号抓「税案通报/曝光台」类文章。
链路：weixin.sogou.com 搜索 → /link 解析（JS拼接URL）→ mp.weixin.qq.com 文章页。
用法：python sd_sc_weixin.py shandong|sichuan [--dry-run]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, io, json, time, random, argparse
from datetime import date, datetime
from urllib.parse import quote, urljoin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 审查修复：stdout 重包加 hasattr 保护（pytest/IDE 等无 buffer 属性的环境跳过，避免 import 即崩）
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import taxcase_scrape as t
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))  # China_Law
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

PROFILES = {
    "shandong": {
        "region": "山东省",
        "out_dir": os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "山东省", "税案通报"),
        "geo": ["山东", "青岛", "济南", "烟台", "潍坊", "临沂", "淄博", "威海", "济宁",
                "泰安", "日照", "德州", "聊城", "滨州", "菏泽", "枣庄", "东营"],
        "queries": [
            "山东税务 查处 曝光 案件",
            "山东税务 虚开 发票 案件",
            "山东税务 骗取留抵退税 案件",
            "山东税务 偷税 处罚",
            "山东 税警联合 查处",
            "山东税务 重大税收违法 失信",
            "青岛税务 曝光 案件",
            "济南税务 稽查 查处",
            "山东税务 曝光",
            "山东 税务局 通报 虚开",
            "山东 骗取出口退税",
            "山东税务 稽查局 案件",
        ],
    },
    "sichuan": {
        "region": "四川省",
        "out_dir": os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "四川省", "税案通报"),
        "geo": ["四川", "成都", "绵阳", "德阳", "宜宾", "泸州", "南充", "达州", "乐山",
                "自贡", "攀枝花", "眉山", "雅安", "遂宁", "内江", "广元", "广安",
                "资阳", "巴中", "凉山", "阿坝", "甘孜"],
        "queries": [
            "四川税务 查处 曝光 案件",
            "四川税务 虚开 发票 案件",
            "四川税务 骗取留抵退税 案件",
            "四川税务 偷税 处罚",
            "四川 税警联合 查处",
            "四川税务 重大税收违法 失信",
            "成都税务 曝光 案件",
            "成都税务 稽查 查处",
            "四川税务 曝光",
            "四川 税务局 通报 虚开",
            "四川 骗取出口退税",
            "四川税务 稽查局 案件",
        ],
    },
}

CASE_PAT = re.compile(r"查处|曝光|虚开|骗税|骗取|偷税|逃税|处罚|案件|通报|稽查|失信|违法")
DATE_FROM = "2023-01-01"


class SogouWeixin:
    def __init__(self):
        self.s = cr.Session(impersonate="chrome124")

    def _wait(self, base=2.8):
        time.sleep(base + random.uniform(0.4, 1.6))

    def search(self, query, page=1):
        """返回 [(title, account_hint, href_sogou)]；None=触发反爬"""
        self._wait(14.0)  # 搜狗微信反爬激进：搜索间隔拉长
        url = (f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}"
               f"&page={page}")
        r = self.s.get(url, headers={"User-Agent": UA,
                                     "Referer": "https://weixin.sogou.com/"}, timeout=40)
        if r.status_code != 200 or "antispider" in r.url or "验证码" in r.text[:2000]:
            return None  # 触发反爬
        soup = BeautifulSoup(r.text, "lxml")
        out = []
        for li in soup.select("ul.news-list > li"):
            a = li.select_one("div.txt-box h3 a")
            if not a or not a.has_attr("href") or "/link" not in a["href"]:
                continue
            title = a.get_text(" ", strip=True)
            acc_el = li.select_one("div.s-p a") or li.select_one("a[uigs*='account']")
            acc = acc_el.get_text(strip=True) if acc_el else ""
            out.append((title, acc, a["href"]))
        return out

    def resolve(self, href_sogou, referer):
        """解析 /link 跳转（JS 拼接 URL）"""
        self._wait(1.2)
        r = self.s.get("https://weixin.sogou.com" + href_sogou,
                       headers={"User-Agent": UA, "Referer": referer}, timeout=40)
        if r.status_code != 200:
            return None
        if "antispider" in r.url:
            return "ANTISPIDER"
        parts = re.findall(r"url \+= '([^']*)'", r.text)
        if parts:
            return "".join(parts)
        m = re.search(r'URL=[\'"]?([^\'" >]+)', r.text)
        if m:
            return m.group(1)
        m = re.search(r"location\.replace\([\"']([^\"']+)[\"']\)", r.text)
        return m.group(1) if m else None

    def article(self, url):
        """抓微信文章 → dict or None"""
        r = self.s.get(url, headers={"User-Agent": UA,
                                     "Referer": "https://mp.weixin.qq.com/"}, timeout=40)
        if r.status_code != 200 or len(r.text) < 8000:
            return None
        if "环境异常" in r.text[:3000] or "此内容因违规无法查看" in r.text:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        t_el = soup.select_one("#activity-name")
        title = t_el.get_text(" ", strip=True) if t_el else ""
        acc_el = soup.select_one("#js_name")
        account = acc_el.get_text(strip=True) if acc_el else ""
        # 发布时间
        pub = ""
        m = re.search(r"var\s+ct\s*=\s*\"?(\d{10})", r.text)
        if m:
            pub = datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d")
        else:
            m = re.search(r"publish_time[^>]*>([^<]{8,25})<", r.text)
            if m:
                pub = m.group(1).strip()[:10]
        content = soup.select_one("#js_content")
        if content is None:
            return None
        for tag in content.select("script,style"):
            tag.decompose()
        # 规范化文章链接（搜狗带签名的链接会过期）
        canon = ""
        m = re.search(r'var\s+msgLink\s*=\s*[\'"]([^\'"]+)[\'"]', r.text)
        if m:
            canon = m.group(1).replace("&amp;", "&")
        md = MarkdownConverter(heading_style="ATX", bullets="-").convert_soup(content)
        md = re.sub(r"\n{3,}", "\n\n", md)
        md = re.sub(r"[ \t]+\n", "\n", md).strip()
        md = re.sub(r"!\\?\[\]\([^)]*\)", "", md)          # 空图片
        # 去掉页脚推荐阅读等噪音
        for marker in ["[|服务热线|]", "推荐阅读", "猜你喜欢", "往期回顾"]:
            i = md.find(marker)
            if i > 200:
                md = md[:i].rstrip().rstrip("-*—- \n")
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return {"title": title or "untitled", "account": account, "date": pub, "md": md,
                "url": canon or url}


PROVINCES = ["山东", "四川", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江",
             "安徽", "福建", "江西", "河南", "湖北", "湖南", "广东", "海南", "贵州",
             "云南", "陕西", "甘肃", "青海", "台湾", "内蒙古", "广西", "西藏", "宁夏",
             "新疆", "重庆", "天津", "北京", "上海"]


def org_from_account(account, region):
    """公众号名 → 机关全称（尽力映射）"""
    a = account.replace("国家税务总局", "").strip()
    if a.endswith("税务") or "税务局" in a:
        base = a[:-2] if a.endswith("税务") else a.replace("税务局", "")
        for pv in PROVINCES:
            if base == pv or base == pv + "省" or base == pv + "市":
                suffix = "市" if pv in ("重庆", "天津", "北京", "上海") else "省"
                return f"国家税务总局{pv}{suffix}税务局"
        for city in ("滨州", "德州", "聊城", "菏泽", "枣庄", "东营", "烟台", "威海",
                     "潍坊", "临沂", "济宁", "泰安", "日照", "淄博", "济南", "青岛",
                     "绵阳", "德阳", "宜宾", "泸州", "南充", "达州", "乐山", "自贡",
                     "攀枝花", "眉山", "雅安", "遂宁", "内江", "广元", "广安", "资阳",
                     "巴中"):
            if base == city:
                return f"国家税务总局{city}市税务局"
        if base.endswith("市") or base.endswith("州") or base.endswith("盟"):
            return f"国家税务总局{base}税务局"
        return f"国家税务总局{base}税务局"
    return f"国家税务总局{region[:-1]}税务局"


def run(profile_key, dry_run=False):
    prof = PROFILES[profile_key]
    out_dir = prof["out_dir"]
    os.makedirs(out_dir, exist_ok=True)
    job_id = f"{profile_key}_weixin"
    done, prog_path = t.load_progress(job_id)
    existing = set(os.listdir(out_dir))  # 文件名级去重（搜狗签名URL每次不同）
    sw = SogouWeixin()
    n_new = n_skip = n_rej = n_fail = 0
    seen_titles = set()
    COOLDOWN_S = 420  # 反爬触发后冷却7分钟
    MAX_SPIDER = 4    # 最多冷却重试4轮
    spider_rounds = 0
    queue = list(enumerate(prof["queries"]))
    with open(prog_path, "a", encoding="utf-8") as prog:
        while queue and spider_rounds <= MAX_SPIDER:
            qi, query = queue[0]
            stopped = False
            print(f"[{job_id}] search q{qi+1}/{len(prof['queries'])} '{query}' p1")
            items = sw.search(query, 1)
            if items is None:
                spider_rounds += 1
                print(f"  !! antispider (round {spider_rounds}/{MAX_SPIDER})，冷却{COOLDOWN_S}s")
                if spider_rounds <= MAX_SPIDER and queue:
                    time.sleep(COOLDOWN_S)
                    sw = SogouWeixin()  # 换新会话
                continue
            print(f"  got {len(items)} results")
            for title, acc_hint, href in items:
                if not CASE_PAT.search(title) or not any(
                        g in title or g in acc_hint for g in prof["geo"]):
                    n_rej += 1
                    continue
                if title in seen_titles:
                    n_skip += 1
                    continue
                seen_titles.add(title)
                target = sw.resolve(href, f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}&page=1")
                if target == "ANTISPIDER":
                    spider_rounds += 1
                    print(f"  !! antispider at resolve (round {spider_rounds}/{MAX_SPIDER})，冷却{COOLDOWN_S}s")
                    stopped = True
                    if spider_rounds <= MAX_SPIDER:
                        time.sleep(COOLDOWN_S)
                        sw = SogouWeixin()
                    break
                if not target or "mp.weixin.qq.com" not in target:
                    n_fail += 1
                    continue
                if target in done:
                    n_skip += 1
                    continue
                if dry_run:
                    print(f"  [dry] {title[:46]}")
                    n_new += 1
                    continue
                art = sw.article(target)
                if not art or len(art["md"]) < 200:
                    prog.write(json.dumps({"url": target, "ok": False,
                                           "err": "article"}, ensure_ascii=False) + "\n")
                    n_fail += 1
                    continue
                pub = art["date"] or date.today().isoformat()
                if pub < DATE_FROM:
                    prog.write(json.dumps({"url": target, "ok": False,
                                           "err": "too_old", "date": pub},
                                          ensure_ascii=False) + "\n")
                    continue
                account = art["account"]
                if "税务" not in account and "国家税务" not in account:
                    prog.write(json.dumps({"url": target, "ok": False,
                                           "err": f"account={account}"},
                                          ensure_ascii=False) + "\n")
                    n_rej += 1
                    continue
                fname = t.safe_filename(pub + "_" + art["title"]) + ".md"
                if fname in existing:
                    prog.write(json.dumps({"url": target, "ok": True, "file": fname,
                                           "title": art["title"], "date": pub,
                                           "account": account, "dup": True},
                                          ensure_ascii=False) + "\n")
                    prog.flush()
                    n_skip += 1
                    continue
                fpath = os.path.join(out_dir, fname)
                fm = ("---\n"
                      f"title: \"{art['title'].replace(chr(34), '')}\"\n"
                      f"来源机关: \"{org_from_account(account, prof['region'])}\"\n"
                      f"栏目: \"税案通报\"\n"
                      f"地区: \"{prof['region']}\"\n"
                      f"发布日期: {pub}\n"
                      f"原文来源: \"微信公众号·{account}\"\n"
                      f"抓取日期: {date.today().isoformat()}\n"
                      f"原文链接: {target}\n"
                      "---\n\n")
                with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                    f.write(fm + art["md"] + "\n")
                prog.write(json.dumps({"url": target, "ok": True, "file": fname,
                                       "title": art["title"], "date": pub,
                                       "account": account}, ensure_ascii=False) + "\n")
                prog.flush()
                n_new += 1
                print(f"  + {pub} [{account}] {art['title'][:44]}")
            if not stopped:
                queue.pop(0)  # 该查询完成
        print(f"[{job_id}] DONE new={n_new} skip={n_skip} rejected={n_rej} fail={n_fail}"
              f" spider_rounds={spider_rounds}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("profile", choices=["shandong", "sichuan"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run(args.profile, args.dry_run)
