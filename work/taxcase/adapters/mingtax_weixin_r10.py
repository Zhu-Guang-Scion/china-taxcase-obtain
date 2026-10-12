# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R10 税务媒体线 · 明税（北京明税律师事务所）微信公众号公开文章——断点增量
复用 R9 mingtax_weixin_r9.py 链路（搜狗微信搜索 type=2 → /link → mp 文章页），
差异：产出改入 税务媒体与专栏/明税·涉税实务评析；断点 media_r10.jsonl；
done 集 = r9 courses_books_r9.jsonl ∪ media_r10.jsonl（避免重收 r9 已收 12 件）。
antispider 策略照旧：拦截即 420s 冷却重建会话，本轮上限 3 次。
质量门槛：媒体文章须含具体案情或操作路径：cjk>=600 且 (CASE_RE 或 OP_RE) 且涉税。
用法：python adapters/mingtax_weixin_r10.py [--dry-run]
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
OUT = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国", "税务媒体与专栏",
                   "明税·涉税实务评析")
PROG = os.path.join(HERE, "..", "progress", "media_r10.jsonl")
PROG_R9 = os.path.join(HERE, "..", "progress", "courses_books_r9.jsonl")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TODAY = "2026-10-11"

QUERIES = [
    "明税 涉税案例", "明税 税务稽查", "明税 行政复议", "明税 以案释法",
    "明税 涉税刑事", "明税 虚开", "明税 转让定价", "明税 土地增值税", "明税 关税",
]

CASE_RE = re.compile(r"以案|案例|案说|案号|当事人|某公司|该公司|本案|该案|稽查|听证|"
                     r"陈述申辩|申辩|行政复议|行政诉讼|辩护|判决|裁定|处罚决定|虚开|偷税|"
                     r"骗取|逃税|追缴|滞纳金|罚款")
OP_RE = re.compile(r"应对|抗辩|救济|合规建议|操作路径|操作要点|实务要点|风险提示|"
                   r"防控|步骤|自查|路径")


def log_rec(rec):
    rec["source"] = "mingtax"
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_done():
    done = set()
    for p in (PROG, PROG_R9):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        u = json.loads(line).get("url", "")
                        if u:
                            done.add(u)
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
          '栏目: "税务媒体与专栏·明税涉税实务评析"\n'
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
                print("  antispider at resolve, cooldown 300s")
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
