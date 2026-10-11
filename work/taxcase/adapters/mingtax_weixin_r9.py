# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R9 课程与书籍线 · 明税（北京明税律师事务所）微信公众号公开文章采集
合规性质：律所官方公众号主动公开发布的涉税案例评析（作者主动公开渠道，非盗版）。
链路：搜狗微信搜索（type=2）→ /link 解析 → mp.weixin.qq.com 文章页。
账号过滤：仅收 公众号名含「明税」的文章（明税/明税律师/M&T Lawyers）。
质量门槛：cjk>=600 且 含案例要素或操作路径要素；纯资讯/活动拒收。
用法：python adapters/mingtax_weixin_r9.py [--dry-run]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, io, json, time, random, argparse
from datetime import datetime
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国",
                   "实务课程与书籍", "明税·涉税实务评析")
PROG = os.path.join(HERE, "..", "progress", "courses_books_r9.jsonl")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TODAY = "2026-10-11"

QUERIES = [
    "明税 涉税案例",
    "明税 税务稽查",
    "明税 行政复议",
    "明税 以案",
    "明税 涉税 刑事",
    "明税 合规 案例",
    "明税 转让定价",
    "明税 土地增值税",
]

CASE_RE = re.compile(r"以案|案例|案说|案号|当事人|某公司|该公司|本案|该案|稽查|听证|"
                     r"陈述申辩|申辩|行政复议|行政诉讼|辩护|判决|裁定|处罚决定|虚开|偷税|"
                     r"骗取|逃税|追缴|滞纳金|罚款")
OP_RE = re.compile(r"应对|抗辩|救济|合规建议|操作路径|操作要点|实务要点|风险提示|"
                   r"防控|步骤|自查|路径")


def log_rec(rec):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_done():
    done = set()
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line).get("url", ""))
                except Exception:
                    pass
    return done


def cjk_len(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def write_md(art):
    taxes, types = [], []
    body = art["md"]
    if re.search(r"增值税", body): taxes.append("增值税")
    if re.search(r"企业所得税", body): taxes.append("企业所得税")
    if re.search(r"个人所得税", body): taxes.append("个人所得税")
    if re.search(r"消费税", body): taxes.append("消费税")
    if re.search(r"出口退税", body): taxes.append("出口退税")
    if re.search(r"土地增值税", body): taxes.append("土地增值税")
    if re.search(r"反避税|特别纳税|转让定价|关联交易", body): types.append("反避税/特别纳税调整")
    if re.search(r"非居民|源泉扣缴|常设机构|税收协定", body): types.append("非居民税收")
    if re.search(r"虚开", body): types.append("虚开发票")
    if re.search(r"偷税|逃税", body): types.append("偷税/逃税")
    if re.search(r"骗取出口退税|骗税", body): types.append("骗取出口退税")
    if re.search(r"股权", body): types.append("股权转让")
    if re.search(r"研发费|加计扣除", body): types.append("研发加计扣除")
    tags = {}
    if types: tags["违法类型/事项"] = types
    if taxes: tags["税种"] = taxes
    yaosu = json.dumps({"税种": taxes, "违法类型": types, "行业": [], "适用法条": [],
                        "是否移送司法": False,
                        "程序类型": "实务评析（律所公众号公开发布）"}, ensure_ascii=False)
    date = art["date"] or TODAY
    fn = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", f"{date}_{art['title']}")[:90].strip()
    path = os.path.join(OUT, fn + ".md")
    if os.path.exists(path):
        return None
    fm = ("---\n"
          f'title: "{art["title"]}"\n'
          '来源机关: "北京明税律师事务所"\n'
          '栏目: "实务课程与书籍·明税涉税实务评析"\n'
          '地区: "全国"\n'
          f'发布日期: {date}\n'
          f'原文来源: "微信公众号·{art["account"]}（作者主动公开发布）"\n'
          f'抓取日期: {TODAY}\n'
          f'原文链接: {art["url"]}\n'
          f'标签: {json.dumps(tags, ensure_ascii=False)}\n'
          f'要素: {yaosu}\n'
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + f"\n\n---\n\n来源：微信公众号「{art['account']}」\n")
    return path


class Sogou:
    def __init__(self):
        self.s = cr.Session(impersonate="chrome124")

    def search(self, query):
        time.sleep(13.0 + random.uniform(1.0, 3.0))
        url = f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}&page=1"
        r = self.s.get(url, headers={"User-Agent": UA,
                                     "Referer": "https://weixin.sogou.com/"}, timeout=40)
        if r.status_code != 200 or "antispider" in r.url or "验证码" in r.text[:2000]:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        out = []
        for li in soup.select("ul.news-list > li"):
            a = li.select_one("div.txt-box h3 a")
            if not a or not a.has_attr("href") or "/link" not in a["href"]:
                continue
            out.append((a.get_text(" ", strip=True), a["href"]))
        return out

    def resolve(self, href, referer):
        time.sleep(1.2)
        r = self.s.get("https://weixin.sogou.com" + href,
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
        pub = ""
        m = re.search(r"var\s+ct\s*=\s*\"?(\d{10})", r.text)
        if m:
            pub = datetime.fromtimestamp(int(m.group(1))).strftime("%Y-%m-%d")
        content = soup.select_one("#js_content")
        if content is None:
            return None
        for tag in content.select("script,style"):
            tag.decompose()
        canon = ""
        m = re.search(r'var\s+msgLink\s*=\s*[\'"]([^\'"]+)[\'"]', r.text)
        if m:
            canon = m.group(1).replace("&amp;", "&")
        md = MarkdownConverter(heading_style="ATX", bullets="-").convert_soup(content)
        md = re.sub(r"\n{3,}", "\n\n", md)
        md = re.sub(r"[ \t]+\n", "\n", md).strip()
        md = re.sub(r"!\\?\[\]\([^)]*\)", "", md)
        for marker in ["[|服务热线|]", "推荐阅读", "猜你喜欢", "往期回顾"]:
            i = md.find(marker)
            if i > 200:
                md = md[:i].rstrip().rstrip("-*—- \n")
        md = re.sub(r"\n{3,}", "\n\n", md).strip()
        return {"title": title or "untitled", "account": account, "date": pub,
                "md": md, "url": canon or url}


def quality(art):
    body = art["md"]
    if cjk_len(body) < 600:
        return f"short({cjk_len(body)})"
    if not (CASE_RE.search(body) or OP_RE.search(body)):
        return "no-case-no-path"
    if not re.search(r"税|发票", body):
        return "off-topic"
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    done = load_done()
    sw = Sogou()
    seen_titles = set()
    kept = rej = skip = 0
    spider = 0
    for qi, q in enumerate(QUERIES):
        items = sw.search(q)
        while items is None and spider < 3:
            spider += 1
            print(f"  antispider round {spider}, cooldown 420s")
            time.sleep(420)
            sw = Sogou()
            items = sw.search(q)
        if items is None:
            print(f"q'{q}' dead after cooldowns")
            continue
        print(f"[{qi+1}/{len(QUERIES)}] '{q}' -> {len(items)}")
        for title, href in items:
            if title in seen_titles:
                skip += 1
                continue
            seen_titles.add(title)
            target = sw.resolve(href, f"https://weixin.sogou.com/weixin?type=2&query={quote(q)}&page=1")
            if target == "ANTISPIDER":
                spider += 1
                print("  antispider at resolve, cooldown")
                time.sleep(300)
                sw = Sogou()
                continue
            if not target or "mp.weixin.qq.com" not in target:
                skip += 1
                continue
            if target in done:
                skip += 1
                continue
            art = sw.article(target)
            if not art or "明税" not in art["account"]:
                if art:
                    log_rec({"url": target, "status": "wrong-account",
                             "account": art["account"], "keep": False})
                skip += 1
                continue
            qd = quality(art)
            if qd is True:
                if a.dry_run:
                    print("  [dry]", art["title"][:50])
                    kept += 1
                    continue
                p = write_md(art)
                if p:
                    kept += 1
                    log_rec({"url": target, "status": "ok", "keep": True, "path": p})
            else:
                rej += 1
                log_rec({"url": target, "status": "quality-reject", "keep": False,
                         "reason": qd, "title": art["title"]})
    print(f"DONE kept={kept} rej={rej} skip={skip}")


if __name__ == "__main__":
    main()
