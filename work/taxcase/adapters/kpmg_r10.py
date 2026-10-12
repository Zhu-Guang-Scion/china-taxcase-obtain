# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R10 税务媒体线 · 毕马威（KPMG）中国"税务快讯"官网公开文章采集
背景：四大官网列表页多为 JS 渲染（德勤/安永/普华永道本轮实测列表不可直抓），
毕马威 china-tax-alert 列表页为静态 HTML（64 条 2023-08→2025-12 在页）→ 四大线代表源。
源结构（2026-10 实测）：
  - 列表 /cn/zh/services/tax/china-tax-insights/china-tax-alert.html（静态 64 条）
  - 文章 /cn/zh/insights/{YYYY}/{MM}/china-tax-alert-{N}.html，URL 自带年月（近三年过滤用）
  - 正文在 AEM 容器（.root.container…），标题 h1，日期 JSON-LD datePublished
质量门槛：媒体文章须含具体案情或操作路径：cjk>=800 且 (CASE_RE 或 OP_RE) 且含数字。
用法：python adapters/kpmg_r10.py [--limit N]
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
                   "毕马威（KPMG）·中国税务快讯")
PROG = os.path.join(HERE, "..", "progress", "media_r10.jsonl")
BASE = "https://kpmg.com"
LIST_URL = "/cn/zh/services/tax/china-tax-insights/china-tax-alert.html"
TODAY = "2026-10-11"
DATE_FROM = "2023/10"  # 近三年（URL 路径格式 YYYY/MM，斜杠别写成连字符否则字符串比较恒真）

CASE_RE = re.compile(r"以案|案例|案说|案号|当事人|某公司|该公司|本案|该案|稽查|查处|经查|听证|"
                     r"行政复议|行政诉讼|辩护|判决|裁定|处罚决定|虚开|偷税|骗取|逃税|追缴|"
                     r"滞纳金|罚款|移送")
OP_RE = re.compile(r"应对|实务|操作|影响|建议|处理|适用|合规|风险提示|步骤|路径|要点|分析")
REJECT_TITLE = re.compile(r"招聘|研讨会|圆桌|直播报名|调查问卷|奖项|年报评分")


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
    rec["source"] = "kpmg"
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
    if re.search(r"反避税|特别纳税|转让定价|关联交易|支柱二|全球最低税", text): types.append("反避税/国际税改")
    if re.search(r"非居民|源泉扣缴|常设机构|税收协定", text): types.append("非居民税收")
    if re.search(r"虚开", text): types.append("虚开发票")
    if re.search(r"关税|海关", text): types.append("关税/海关")
    return taxes, types


def write_md(title, date, body, url, prog_type):
    taxes, types = classify_tags(title + body)
    tags = {}
    if types: tags["违法类型/事项"] = types
    if taxes: tags["税种"] = taxes
    fn = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", f"{date}_{title}")[:90].strip()
    path = os.path.join(OUT, fn + ".md")
    if os.path.exists(path):
        return None
    yaosu = json.dumps({"税种": taxes, "违法类型": types, "行业": [], "适用法条": [],
                        "是否移送司法": False, "程序类型": prog_type}, ensure_ascii=False)
    fm = ("---\n"
          f'title: "{title}"\n'
          '来源机关: "毕马威中国（KPMG China）"\n'
          '栏目: "税务媒体与专栏·毕马威中国税务快讯"\n'
          '地区: "全国"\n'
          f'发布日期: {date}\n'
          '原文来源: "毕马威中国官网税务快讯（主动公开发布）"\n'
          f'抓取日期: {TODAY}\n'
          f'原文链接: {url}\n'
          f'标签: {json.dumps(tags, ensure_ascii=False)}\n'
          f'要素: {yaosu}\n'
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + "\n\n---\n\n来源：毕马威（KPMG）中国官网\n")
    return path


def quality(title, body):
    if REJECT_TITLE.search(title):
        return "activity"
    cjk = cjk_len(body)
    if cjk < 800:
        return f"too-short({cjk})"
    if not (CASE_RE.search(body) or OP_RE.search(body)):
        return "no-case-no-path"
    if not re.search(r"\d", body):
        return "no-digit"
    if not re.search(r"税|发票|关税", body):
        return "off-topic"
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    done = load_done()
    sess = cr.Session(impersonate="edge101")

    r = sess.get(BASE + LIST_URL, headers={"accept-language": "zh-CN,zh;q=0.9"}, timeout=40)
    links = list(dict.fromkeys(re.findall(r'href="(/cn/zh/insights/\d{4}/\d{2}/[a-z0-9-]{5,110}\.html)"', r.text)))
    # 近三年过滤（URL 自带年月）
    links = [l for l in links if (l.split("/insights/")[1][:7]) >= DATE_FROM]
    print("kpmg links (3y):", len(links))
    time.sleep(1.5)

    kept = skipped = 0
    for i, path in enumerate(links, 1):
        u = BASE + path
        if u in done:
            continue
        if a.limit and kept >= a.limit:
            break
        try:
            r2 = sess.get(u, headers={"accept-language": "zh-CN,zh;q=0.9"}, timeout=40)
        except Exception as e:
            print(f"[{i}] ERR {e}")
            time.sleep(2)
            continue
        time.sleep(1.3 + random.uniform(0.1, 0.4))
        if r2.status_code != 200:
            log_rec({"url": u, "status": "http" + str(r2.status_code), "keep": False})
            skipped += 1
            continue
        soup = BeautifulSoup(r2.text, "lxml")
        h1 = soup.select_one("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""
        # AEM 的 datePublished 实测为整站迁移日（多文件同日、与内容期不符），
        # 快讯真实发布期以 URL 路径 /insights/YYYY/MM/ 为准（正文刊头亦为该月）
        m2 = re.search(r'/insights/(\d{4})/(\d{2})/', u)
        date = f"{m2.group(1)}-{m2.group(2)}-01" if m2 else TODAY
        root = soup.select_one(".root.container") or soup.body
        for tag in root.select("script,style,nav,footer,header"):
            tag.decompose()
        body = root.get_text("\n", strip=True)
        # 去导航/页脚噪声
        for marker in ["相关内容", "分享此文", "联系我们", "订阅毕马威", "© 20", "隐私政策",
                       "使用条款", "Accessibility", "© Copyright"]:
            idx = body.find(marker)
            if idx > 500:
                body = body[:idx]
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        if not title:
            title = (re.sub(r"\s+", " ", body[:40]) or "KPMG税务快讯")
        qd = quality(title, body)
        if qd is True:
            p = write_md(title, date, body, u, "税务快讯评析（四大官网公开发布）")
            if p:
                kept += 1
                log_rec({"url": u, "status": "ok", "keep": True, "path": p})
        else:
            skipped += 1
            log_rec({"url": u, "status": "quality-reject", "keep": False,
                     "reason": qd, "title": title[:50]})
        if i % 10 == 0:
            print(f"[{i}/{len(links)}] kept={kept} skip={skipped}")
    print(f"DONE kept={kept} skip={skipped}")


if __name__ == "__main__":
    main()
