# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R10 税务媒体线 · 中国税务报（中国税网 ctaxnews.com.cn）官网公开内容采集
合规性质：总局主管官方媒体主动公开发布的税案通报/合规典型案例报道。
源结构（2026-10 实测，round3 曾误报域名已死，本轮实测 200 复活）：
  - 税案通报 /sswfaj/node_23.html，分页 node_23_{2..10}.html（第 11 页起 HTTP 500，
    在线归档仅至 2026-04，全量收）
  - 合规案例 /zt/node_8131.html 单页（2025-08→2026-10 全量在页）
文章页：.article-wrap 内 标题(p×n)/.publish-time/.source/.article-main。
质量门槛：媒体文章须含具体案情或操作路径（纯政策转述/活动预告拒收）：
  cjk>=300 且 (CASE_RE 或 OP_RE) 且 含数字；标题含活动/征订/招聘类词拒收。
用法：python adapters/ctaxnews_r10.py [--limit N]
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
OUT_BASE = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国", "税务媒体与专栏")
OUT_CASE = os.path.join(OUT_BASE, "中国税务报·税案通报")
OUT_HG = os.path.join(OUT_BASE, "中国税务报·合规案例")
PROG = os.path.join(HERE, "..", "progress", "media_r10.jsonl")
BASE = "https://www.ctaxnews.com.cn"
TODAY = "2026-10-11"

CASE_RE = re.compile(r"以案|案例|案说|案号|当事人|某公司|该公司|本案|该案|稽查|查处|经查|听证|"
                     r"行政复议|行政诉讼|辩护|判决|裁定|处罚决定|虚开|偷税|骗取|逃税|追缴|"
                     r"滞纳金|罚款|移送|侦办")
OP_RE = re.compile(r"应对|抗辩|救济|合规建议|操作路径|操作要点|实务要点|风险提示|防控|流程|"
                   r"步骤|自查|合规管理|合规经营|路径")
NUM_RE = re.compile(r"\d")
REJECT_TITLE = re.compile(r"征订|招聘|广告|年会|获奖|访谈|直播|培训通知|报纸版|电子报|订阅|"
                          r"公告\d{4}|本报评论员|图片新闻|摄影|征稿")


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
    rec["source"] = "ctaxnews"
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
    if re.search(r"社保|社会保险费", text): types.append("社会保险费")
    if re.search(r"反避税|特别纳税|转让定价|关联交易", text): types.append("反避税/特别纳税调整")
    if re.search(r"非居民|源泉扣缴|常设机构|税收协定", text): types.append("非居民税收")
    if re.search(r"虚开", text): types.append("虚开发票")
    if re.search(r"偷税|逃税", text): types.append("偷税/逃税")
    if re.search(r"骗取出口退税|骗税", text): types.append("骗取出口退税")
    if re.search(r"留抵退税", text): types.append("骗取留抵退税")
    if re.search(r"研发费|加计扣除", text): types.append("研发加计扣除")
    return taxes, types


def write_md(out_dir, title, date, body, url, col, source_note, prog_type):
    taxes, types = classify_tags(title + body)
    tags = {}
    if types: tags["违法类型/事项"] = types
    if taxes: tags["税种"] = taxes
    fn = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", f"{date}_{title}")[:90].strip()
    path = os.path.join(out_dir, fn + ".md")
    if os.path.exists(path):
        return None
    yaosu = json.dumps({"税种": taxes, "违法类型": types, "行业": [], "适用法条": [],
                        "是否移送司法": bool(re.search(r"移送|公安机关|侦办|判处", body)),
                        "程序类型": prog_type}, ensure_ascii=False)
    fm = ("---\n"
          f'title: "{title}"\n'
          '来源机关: "中国税务报（中国税网）"\n'
          f'栏目: "{col}"\n'
          '地区: "全国"\n'
          f'发布日期: {date}\n'
          f'原文来源: "{source_note}"\n'
          f'抓取日期: {TODAY}\n'
          f'原文链接: {url}\n'
          f'标签: {json.dumps(tags, ensure_ascii=False)}\n'
          f'要素: {yaosu}\n'
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + "\n\n---\n\n来源：" + source_note + "\n")
    return path


def parse_article(html, url):
    soup = BeautifulSoup(html, "lxml")
    wrap = soup.select_one(".article-wrap")
    if wrap is None:
        return None
    # 标题：.article-info 之前的所有 p 拼接（长标题被拆成多个 p）
    ps = []
    info = wrap.select_one(".article-info")
    for el in wrap.children:
        if el is info:
            break
        if getattr(el, "name", None) == "p":
            t = el.get_text(" ", strip=True)
            if t:
                ps.append(t)
    title = "".join(ps).strip()
    if not title:
        t3 = wrap.select_one("h3")
        title = t3.get_text(" ", strip=True) if t3 else ""
    if not title:
        title = (soup.select_one("title").get_text(strip=True) if soup.title else url.rsplit("/", 1)[-1])
    # 日期
    date = ""
    pt = wrap.select_one(".publish-time")
    if pt:
        m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", pt.get_text())
        if m:
            date = "%s-%s-%s" % m.groups()
    src_el = wrap.select_one(".source")
    src_note0 = src_el.get_text(strip=True).replace("来源：", "") if src_el else ""
    main = wrap.select_one(".article-main")
    body = main.get_text("\n", strip=True) if main else ""
    body = re.sub(r"\n{3,}", "\n\n", body)
    return {"title": title, "date": date or TODAY, "body": body, "src": src_note0}


def quality(art):
    if REJECT_TITLE.search(art["title"]):
        return "activity/notice"
    cjk = cjk_len(art["body"])
    if cjk < 300:
        return f"too-short({cjk})"
    if not (CASE_RE.search(art["body"]) or OP_RE.search(art["body"])):
        return "no-case-no-path"
    if not NUM_RE.search(art["body"]):
        return "no-digit"
    return True


def collect_list_urls(sess, pages):
    urls = []
    for pg in pages:
        u = f"{BASE}/sswfaj/node_23.html" if pg == 1 else f"{BASE}/sswfaj/node_23_{pg}.html"
        try:
            r = sess.get(u, timeout=30)
        except Exception as e:
            print("list ERR", u, e)
            continue
        time.sleep(1.2 + random.uniform(0.1, 0.4))
        if r.status_code != 200:
            print("list http", r.status_code, u)
            continue
        found = re.findall(r'href="(?:https?://www\.ctaxnews\.com\.cn)?(/sswfaj/\d{4}-\d{2}/\d{2}/content_\d+\.html)"', r.text)
        urls.extend(found)
    return list(dict.fromkeys(urls))


def collect_zt_urls(sess):
    urls = []
    u = f"{BASE}/zt/node_8131.html"
    try:
        r = sess.get(u, timeout=40)
        if r.status_code == 200:
            urls = re.findall(r'href="(?:https?://www\.ctaxnews\.com\.cn)?(/zt/\d{4}-\d{2}/\d{2}/content_\d+\.html)"', r.text)
    except Exception as e:
        print("zt ERR", e)
    return list(dict.fromkeys(urls))


def fetch_articles(sess, urls, out_dir, col, source_note, prog_type, done, limit):
    kept = skipped = 0
    for i, path in enumerate(urls, 1):
        u = BASE + path
        if u in done:
            continue
        if limit and kept >= limit:
            break
        try:
            r = sess.get(u, timeout=30)
        except Exception as e:
            print(f"[{i}/{len(urls)}] ERR {e}")
            time.sleep(2)
            continue
        time.sleep(1.2 + random.uniform(0.1, 0.4))
        if r.status_code != 200:
            log_rec({"url": u, "status": "http" + str(r.status_code), "keep": False})
            skipped += 1
            continue
        art = parse_article(r.text, u)
        if not art:
            log_rec({"url": u, "status": "no-body", "keep": False})
            skipped += 1
            continue
        qd = quality(art)
        if qd is True:
            sn = f"中国税务报（中国税网）官网{source_note}（{art['src']}，主动公开发布）" if art["src"] \
                else f"中国税务报（中国税网）官网{source_note}（主动公开发布）"
            p = write_md(out_dir, art["title"], art["date"], art["body"], u, col, sn, prog_type)
            if p:
                kept += 1
                log_rec({"url": u, "status": "ok", "keep": True, "path": p})
        else:
            skipped += 1
            log_rec({"url": u, "status": "quality-reject", "keep": False,
                     "reason": qd, "title": art["title"][:50]})
        if i % 20 == 0:
            print(f"[{i}/{len(urls)}] kept={kept} skipped={skipped}")
    return kept, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(OUT_CASE, exist_ok=True)
    os.makedirs(OUT_HG, exist_ok=True)
    done = load_done()
    sess = cr.Session(impersonate="chrome124")

    urls = collect_list_urls(sess, range(1, 11))
    print("sswfaj urls:", len(urls))
    k1, s1 = fetch_articles(sess, urls, OUT_CASE, "税务媒体与专栏·中国税务报税案通报",
                            "税案通报栏", "税案通报（官方媒体报道）", done, a.limit)
    print(f"sswfaj kept={k1} skip={s1}")

    zt = collect_zt_urls(sess)
    print("zt urls:", len(zt))
    time.sleep(1.5)
    k2, s2 = fetch_articles(sess, zt, OUT_HG, "税务媒体与专栏·中国税务报合规案例",
                            "合规案例栏", "合规典型案例（官方媒体报道）", done, a.limit)
    print(f"zt kept={k2} skip={s2}")
    print("TOTAL kept:", k1 + k2)


if __name__ == "__main__":
    main()
