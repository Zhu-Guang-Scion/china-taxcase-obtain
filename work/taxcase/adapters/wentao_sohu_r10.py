# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R10 税务媒体线 · 税海涛声（段文涛）"文涛说税" 公开专栏采集——搜狐号兜底
背景：知乎专栏 c_1089525539886383104（文涛说税）2026-10 实测文章页/列表 API 全 403
（列表需登录、文章页 WAF 拦 curl_cffi 全系 impersonation），仅专栏元信息 API 可达
（api/v4/columns/{cid} 200 但 postsCount=None）→ 知乎通道落空，按调研预案转搜狐号同文镜像。
源结构（2026-10 实测）：
  - 搜狐号 税海涛声 作者 ID 467122（mp.sohu.com/profile?xpt=dGF4c2h0c0Bzb2h1LmNvbQ==）
  - v2.sohu.com/author-page-api/author-articles/pc/467122 → 最新 20 篇固定窗（分页参数失效）
  - 枚举主通道：搜狗网页搜索 "税海涛声 关键词" → 收 www.sohu.com/a/{id}_467122
  - 文章页需 impersonate=edge101（chrome124/131 被 sohu WAF 403）
质量门槛：媒体评析文章须含具体案情或操作路径：cjk>=500 且 (CASE_RE 或 OP_RE) 且
  含"税/发票"且含数字；纯政策转述（无案无路径）拒收。
用法：python adapters/wentao_sohu_r10.py [--limit N]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, io, json, time, random, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from bs4 import BeautifulSoup
from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国", "税务媒体与专栏",
                   "税海涛声（段文涛）·文涛说税")
PROG = os.path.join(HERE, "..", "progress", "media_r10.jsonl")
TODAY = "2026-10-11"
AUTHOR_ID = 467122

QUERIES = [
    "税海涛声 site:sohu.com", "税海涛声 段文涛 搜狐", "文涛说税 搜狐号",
    "税海涛声 虚开", "税海涛声 稽查 滞纳金", "税海涛声 偷税 处罚",
    "税海涛声 增值税 发票", "税海涛声 企业所得税 扣除",
]

CASE_RE = re.compile(r"以案|案例|案说|案号|当事人|某公司|该公司|本案|该案|稽查|查处|经查|听证|"
                     r"行政复议|行政诉讼|辩护|判决|裁定|处罚决定|虚开|偷税|骗取|逃税|追缴|"
                     r"滞纳金|罚款|移送")
OP_RE = re.compile(r"应对|抗辩|救济|合规建议|操作路径|操作要点|实务要点|风险提示|防控|流程|"
                   r"步骤|自查|路径|实务|处理|适用")
REJECT_TITLE = re.compile(r"招募|招聘|课程|讲座报名|年费|专栏付费")


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


def log_rec(rec):
    rec["source"] = "wentao_sohu"
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cjk_len(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def classify_tags(text):
    taxes, types = [], []
    if re.search(r"增值税", text): taxes.append("增值税")
    if re.search(r"企业所得税", text): taxes.append("企业所得税")
    if re.search(r"个人所得税", text): taxes.append("个人所得税")
    if re.search(r"消费税", text): taxes.append("消费税")
    if re.search(r"出口退税", text): taxes.append("出口退税")
    if re.search(r"土地增值税", text): taxes.append("土地增值税")
    if re.search(r"印花税", text): taxes.append("印花税")
    if re.search(r"反避税|特别纳税|转让定价|关联交易", text): types.append("反避税/特别纳税调整")
    if re.search(r"虚开", text): types.append("虚开发票")
    if re.search(r"偷税|逃税", text): types.append("偷税/逃税")
    if re.search(r"滞纳金", text): types.append("滞纳金争议")
    return taxes, types


def write_md(art, prog_type):
    taxes, types = classify_tags(art["title"] + art["md"])
    tags = {}
    if types: tags["违法类型/事项"] = types
    if taxes: tags["税种"] = taxes
    date = art["date"] or TODAY
    fn = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", f"{date}_{art['title']}")[:90].strip()
    path = os.path.join(OUT, fn + ".md")
    if os.path.exists(path):
        return None
    yaosu = json.dumps({"税种": taxes, "违法类型": types, "行业": [], "适用法条": [],
                        "是否移送司法": False, "程序类型": prog_type}, ensure_ascii=False)
    fm = ("---\n"
          f'title: "{art["title"]}"\n'
          '来源机关: "税海涛声（段文涛）"\n'
          '栏目: "税务媒体与专栏·税海涛声文涛说税"\n'
          '地区: "全国"\n'
          f'发布日期: {date}\n'
          '原文来源: "搜狐号·税海涛声（微信公众号同文同步，作者主动公开发布）"\n'
          f'抓取日期: {TODAY}\n'
          f'原文链接: {art["url"]}\n'
          f'标签: {json.dumps(tags, ensure_ascii=False)}\n'
          f'要素: {yaosu}\n'
          "---\n\n")
    body = art["md"].strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body + "\n\n---\n\n来源：搜狐号「税海涛声」（段文涛）\n")
    return path


def quality(art):
    body = art["md"]
    if REJECT_TITLE.search(art["title"]):
        return "activity/paywall"
    cjk = cjk_len(body)
    if cjk < 500:
        return f"too-short({cjk})"
    if not (CASE_RE.search(body) or OP_RE.search(body)):
        return "no-case-no-path"
    if not re.search(r"税|发票", body):
        return "off-topic"
    if not re.search(r"\d", body):
        return "no-digit"
    return True


def fetch_article(sess, aid):
    u = f"https://www.sohu.com/a/{aid}_{AUTHOR_ID}"
    try:
        r = sess.get(u, timeout=30)
    except Exception:
        return None
    if r.status_code != 200:
        return {"aid": aid, "url": u, "status": "http" + str(r.status_code)}
    soup = BeautifulSoup(r.text, "lxml")
    t_el = soup.select_one("h1")
    title = t_el.get_text(" ", strip=True) if t_el else ""
    art = soup.select_one("article") or soup.select_one(".article") or soup.select_one("#mp-editor")
    if art is None:
        return {"aid": aid, "url": u, "status": "no-body"}
    for tag in art.select("script,style"):
        tag.decompose()
    body = art.get_text("\n", strip=True)
    body = re.sub(r"\n{3,}", "\n\n", body)
    # 尾部运营文案截断
    for marker in ["返回搜狐，查看更多", "责任编辑", "声明：本文由", "（作者：", "特别声明"]:
        i = body.find(marker)
        if i > 300:
            body = body[:i].rstrip()
    date = ""
    m = re.search(r'"(?:pubTime|newsTime|publicTime)"\s*:\s*"(\d{4})[.-](\d{2})[.-](\d{2})', r.text) \
         or re.search(r'(\d{4})-(\d{2})-(\d{2}) \d{2}:\d{2}', r.text)
    if m:
        date = "%s-%s-%s" % m.groups()
    return {"aid": aid, "url": u, "title": title, "md": body, "date": date,
            "status": "ok"}


class EnumEngine:
    """百度（主）+ 360（辅）网页搜索枚举搜狐号文章 id；搜狗已被 antispider 弃用"""

    def __init__(self):
        self.s = cr.Session(impersonate="edge101")

    def baidu(self, query, pn):
        time.sleep(2.6 + random.uniform(0.5, 1.5))
        from urllib.parse import quote
        u = f"https://www.baidu.com/s?wd={quote(query)}&pn={pn}&rn=20"
        try:
            r = self.s.get(u, headers={"accept-language": "zh-CN,zh;q=0.9"}, timeout=35)
        except Exception:
            return None
        if r.status_code != 200 or "百度安全验证" in r.text[:3000]:
            return None
        aids = re.findall(r'(?:www|business|mp)\.sohu\.com/a/(\d+)_' + str(AUTHOR_ID), r.text)
        return list(dict.fromkeys(aids))

    def so360(self, query, pn):
        time.sleep(2.6 + random.uniform(0.5, 1.5))
        from urllib.parse import quote
        u = f"https://www.so.com/s?q={quote(query)}&pn={pn}"
        try:
            r = self.s.get(u, headers={"accept-language": "zh-CN,zh;q=0.9"}, timeout=35)
        except Exception:
            return None
        if r.status_code != 200:
            return None
        aids = re.findall(r'/a/(\d+)_' + str(AUTHOR_ID), r.text)
        return list(dict.fromkeys(aids))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=600)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    done = load_done()
    sess = cr.Session(impersonate="edge101")

    # 1) v2 API 最新窗
    ids = []
    try:
        r = sess.get(f"https://v2.sohu.com/author-page-api/author-articles/pc/{AUTHOR_ID}?page=1&size=20",
                     headers={"accept": "application/json", "referer": "https://mp.sohu.com/"}, timeout=30)
        for it in r.json().get("data", {}).get("pcArticleVOS", []):
            ids.append(str(it.get("id")))
            print("[api]", (it.get("title") or "")[:40])
    except Exception as e:
        print("v2 api err:", e)
    time.sleep(1.5)

    # 2) 百度+360 枚举
    eng = EnumEngine()
    for qi, q in enumerate(QUERIES):
        if len(set(ids)) >= a.limit * 2:
            break
        for pn in (0, 20, 40, 60):
            got = eng.baidu(q, pn)
            if got is None:
                print(f"  baidu-blocked/empty '{q}' pn={pn}")
                break
            ids.extend(got)
        got3 = eng.so360(q, 1)
        if got3:
            ids.extend(got3)
        print(f"[{qi+1}/{len(QUERIES)}] '{q}' 累计 {len(set(ids))}")

    ids = list(dict.fromkeys(ids))
    print("distinct ids:", len(ids))

    kept = skipped = 0
    for n, aid in enumerate(ids, 1):
        if kept >= a.limit:
            break
        u = f"https://www.sohu.com/a/{aid}_{AUTHOR_ID}"
        if u in done:
            continue
        time.sleep(1.4 + random.uniform(0.2, 0.6))
        art = fetch_article(sess, aid)
        if not art or art.get("status") != "ok":
            skipped += 1
            log_rec({"url": u, "status": (art or {}).get("status", "err"), "keep": False})
            continue
        qd = quality(art)
        if qd is True:
            p = write_md(art, "实务评析（个人税务专栏公开发布）")
            if p:
                kept += 1
                log_rec({"url": u, "status": "ok", "keep": True, "path": p})
        else:
            skipped += 1
            log_rec({"url": u, "status": "quality-reject", "keep": False,
                     "reason": qd, "title": art["title"][:50]})
        if n % 10 == 0:
            print(f"[{n}/{len(ids)}] kept={kept} skip={skipped}")
    print(f"DONE kept={kept} skip={skipped}")


if __name__ == "__main__":
    main()
