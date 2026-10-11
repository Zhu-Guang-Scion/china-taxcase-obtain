# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""R9 课程与书籍线 · 华税律师事务所官网（www.huashui.com）公开内容采集
合规性质：律所官网主动公开发布的原创涉税实务文章与经典案例（作者主动公开，非盗版非付费）。
源结构（2026-10 实测）：
  - 中文站前缀 /zh-hans/（根路径强制 302 到 /en/，changeLanguage('zh-hans') 前端切换）
  - 前沿观点 /zh-hans/frontier/list/0.html（0=全部，1..9=行业分类），分页 ?page=N，10 条/页
    详情 /zh-hans/frontier/detail/{id}.html，id 128-530 全量 390 条
  - 成功案例 /zh-hans/case/list/more/{0..3}.html 四类：稽查应对/处罚听证/复议诉讼/刑事辩护，
    每条为一段含金额与结果的案例摘要（.cases-item div）
质量门槛：正文 cjk>=600 且 含案例要素（案/当事人/稽查/复议/听证/辩护/判决…）或
  操作路径要素（应对/合规建议/步骤/抗辩/救济…）；纯活动/招聘/所讯拒收。
用法：python adapters/huashui_r9.py [--limit N] [--frontier-only|--cases-only]
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
OUT_FRONTIER = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国",
                            "实务课程与书籍", "华税·涉税实务评析")
OUT_CASES = os.path.join(PROJ, "lawlibrary", "专题", "税务案例", "全国",
                         "实务课程与书籍", "华税·经典案例")
PROG = os.path.join(HERE, "..", "progress", "courses_books_r9.jsonl")
BASE = "https://www.huashui.com"
TODAY = "2026-10-11"

CASE_RE = re.compile(r"以案|案例|案说|案号|当事人|某公司|该公司|本案|该案|稽查|听证|"
                     r"陈述申辩|申辩|行政复议|行政诉讼|辩护|判决|裁定|处罚决定|虚开|偷税|"
                     r"骗取|逃税|追缴|滞纳金|罚款")
OP_RE = re.compile(r"应对|抗辩|救济|合规建议|操作路径|操作要点|实务要点|风险提示|"
                   r"防控|流程|步骤|自查|申辩策略|路径")
NUM_RE = re.compile(r"\d")
REJECT_TITLE = re.compile(r"招聘|年会|讲座报名|获奖|荣膺|入职|公益|运动会|所讯|签约|"
                          r"圆满举行|成功举办|华税活动|培训通知|招聘信息")


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
    if re.search(r"非居民|源泉扣缴|常设机构|税收协定", text): types.append("非居民税收")
    if re.search(r"虚开", text): types.append("虚开发票")
    if re.search(r"偷税|逃税", text): types.append("偷税/逃税")
    if re.search(r"骗取出口退税|骗税", text): types.append("骗取出口退税")
    if re.search(r"留抵退税", text): types.append("骗取留抵退税")
    if re.search(r"股权", text): types.append("股权转让")
    if re.search(r"研发费|加计扣除", text): types.append("研发加计扣除")
    if re.search(r"土地增值税清算", text): types.append("土地增值税清算")
    return taxes, types


def write_md(out_dir, title, date, body, url, col, source_note, extra):
    taxes, types = classify_tags(title + body)
    tags = {}
    if types: tags["违法类型/事项"] = types
    if taxes: tags["税种"] = taxes
    fn = f"{date}_{title}" if date else f"{TODAY}_{title}"
    fn = re.sub(r"[\\/:*?\"<>|\r\n\t]", "", fn)[:90].strip()
    path = os.path.join(out_dir, fn + ".md")
    if os.path.exists(path):
        return None
    yaosu = json.dumps({"税种": taxes, "违法类型": types, "行业": [],
                        "适用法条": [], "是否移送司法": False, "程序类型": extra},
                       ensure_ascii=False)
    fm = ("---\n"
          f'title: "{title}"\n'
          '来源机关: "华税律师事务所"\n'
          f'栏目: "{col}"\n'
          '地区: "全国"\n'
          f'发布日期: {date or TODAY}\n'
          f'原文来源: "{source_note}"\n'
          f'抓取日期: {TODAY}\n'
          f'原文链接: {url}\n'
          f'标签: {json.dumps(tags, ensure_ascii=False)}\n'
          f'要素: {yaosu}\n'
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body.strip() + "\n\n---\n\n来源：" + source_note + "\n")
    return path


def list_frontier_ids(sess):
    ids, page = set(), 1
    while page < 60:
        u = f"{BASE}/zh-hans/frontier/list/0.html?page={page}"
        try:
            r = sess.get(u, timeout=30)
        except Exception:
            time.sleep(3); continue
        det = set(int(x) for x in re.findall(
            r'href="/zh-hans/frontier/detail/(\d+)\.html"', r.text))
        new = det - ids
        ids |= det
        if not new and page > 1:
            break
        page += 1
        time.sleep(0.7 + random.uniform(0.2, 0.6))
    return sorted(ids)


def fetch_frontier(sess, ids, done, limit):
    kept = skipped = 0
    for i, aid in enumerate(ids, 1):
        u = f"{BASE}/zh-hans/frontier/detail/{aid}.html"
        if u in done:
            continue
        if limit and kept >= limit:
            break
        try:
            r = sess.get(u, timeout=30)
        except Exception as e:
            print(f"[{i}/{len(ids)}] {u} ERR {e}")
            time.sleep(2.5)
            continue
        time.sleep(1.2 + random.uniform(0.1, 0.5))
        if r.status_code != 200:
            log_rec({"url": u, "status": "http" + str(r.status_code), "keep": False})
            skipped += 1
            continue
        soup = BeautifulSoup(r.text, "lxml")
        title_el = soup.select_one(".content .title") or soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else f"华税前沿观点{aid}"
        date_m = re.search(r"(\d{4}年\d{2}月\d{2}日)", soup.select_one(".content").get_text(" ", strip=True)
                           if soup.select_one(".content") else r.text)
        date = date_m.group(1).replace("年", "-").replace("月", "-").replace("日", "") if date_m else TODAY
        body_el = soup.select_one(".content") or soup.body
        body = body_el.get_text("\n", strip=True)
        body = re.sub(r"\n{3,}", "\n\n", body)
        body = re.sub(r"^\d*人浏览$", "", body, flags=re.M)
        ok = quality(title, body)
        if ok:
            p = write_md(OUT_FRONTIER, title, date, body, u, "实务课程与书籍·华税涉税实务评析",
                         "华税律师事务所官网（主动公开发布）", "实务评析（律所官网公开发布）")
            if p:
                kept += 1
                log_rec({"url": u, "status": "ok", "keep": True, "path": p})
        else:
            skipped += 1
            log_rec({"url": u, "status": "quality-reject", "keep": False,
                     "reason": ok if isinstance(ok, str) else "", "title": title})
        if i % 25 == 0:
            print(f"[{i}/{len(ids)}] kept={kept} skipped={skipped}")
    return kept, skipped


def quality(title, body):
    """返回 True 或拒收原因字符串"""
    if REJECT_TITLE.search(title):
        return "activity/news"
    cjk = cjk_len(body)
    if cjk < 600:
        return f"too-short({cjk})"
    has_case = bool(CASE_RE.search(body))
    has_op = bool(OP_RE.search(body))
    if not (has_case or has_op):
        return "no-case-no-path"
    if not NUM_RE.search(body):
        return "no-digit"
    return True


def fetch_cases(sess, done):
    cats = {}
    kept = 0
    for ci in range(4):
        u = f"{BASE}/zh-hans/case/list/more/{ci}.html"
        try:
            r = sess.get(u, timeout=30)
        except Exception as e:
            print(u, "ERR", e); continue
        time.sleep(1.2)
        soup = BeautifulSoup(r.text, "lxml")
        cat = soup.select_one(".cases .title")
        cat_name = cat.get_text(strip=True) if cat else f"分类{ci}"
        year_re = re.compile(r"（(20\d{2})）\s*$")
        for item in soup.select(".cases-item"):
            txt = re.sub(r"^\d+\.\s*", "", item.get_text(" ", strip=True))
            ym = year_re.search(txt)
            year = ym.group(1) if ym else ""
            body = txt
            if cjk_len(body) < 30 or not NUM_RE.search(body):
                continue
            title = txt[:38] + ("…" if len(txt) > 38 else "")
            p = write_md(OUT_CASES, f"{cat_name}·{title[:30]}", year or TODAY, body,
                         u, f"实务课程与书籍·华税经典案例（{cat_name}）",
                         "华税律师事务所官网·成功案例栏（主动公开发布）",
                         "案例解读（律所公开经典案例）")
            if p:
                kept += 1
        cats[cat_name] = kept
    return cats, kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mode", choices=["all", "frontier", "cases"], default="all")
    a = ap.parse_args()
    os.makedirs(OUT_FRONTIER, exist_ok=True)
    os.makedirs(OUT_CASES, exist_ok=True)
    done = load_done()
    sess = cr.Session(impersonate="chrome124")
    total_kept = 0
    if a.mode in ("all", "frontier"):
        ids = list_frontier_ids(sess)
        print(f"frontier ids: {len(ids)} (done already: {len([u for u in done if 'frontier' in u])})")
        k, s = fetch_frontier(sess, ids, done, a.limit)
        total_kept += k
        print(f"frontier kept={k} skipped={s}")
    if a.mode in ("all", "cases"):
        cats, k = fetch_cases(sess, done)
        total_kept += k
        print("case cats:", cats)
    print("TOTAL kept:", total_kept)


if __name__ == "__main__":
    main()
