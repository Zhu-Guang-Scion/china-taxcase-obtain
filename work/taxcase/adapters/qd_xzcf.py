# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""青岛市税务局 税收执法公示平台 —— 行政处罚（一般程序处罚结果）收割器
平台: https://etax.qingdao.chinatax.gov.cn:6883/newdzswj/
  列表: sszfgsptReportList.do?type=gotoList&tyid=803079ca9d454d268f464306f73e0601&swjgdm=13702000000
  翻页: 站内 getPage(3)（#page 输入 + cxinit() AJAX），渲染后读 #tbodylist innerHTML
  记录: 摘要行(文号/案件名/日期/机关) + 内联详情表(案件名称..处罚事由..执法依据..处罚结果..法代)
产出: tmp/qd/xzcf_pages/pNNN.html + tmp/qd/xzcf_records.jsonl（断点 progress/qd_hn_r6.jsonl）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time, argparse
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "qd")
PAGES = os.path.join(TMP, "xzcf_pages"); os.makedirs(PAGES, exist_ok=True)
RECS = os.path.join(TMP, "xzcf_records.jsonl")
PROG = os.path.join(ROOT, "progress", "qd_hn_r6.jsonl"); os.makedirs(os.path.dirname(PROG), exist_ok=True)

LIST_URL = ("https://etax.qingdao.chinatax.gov.cn:6883/newdzswj/sszfgsptReportList.do"
            "?type=gotoList&tyid=803079ca9d454d268f464306f73e0601&swjgdm=13702000000")
DELAY = (1.8, 3.0)
DATE_FROM = "2023-01-01"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def parse_tbody(html):
    """tbodylist innerHTML → 记录列表。
    结构: 摘要 <tr>(arrow, idx, 文号, 案件名, 日期, 机关) 后跟详情 <tr><td colspan=5><table>字段表</table>"""
    recs = []
    # 以摘要行为锚：含 ar.png 的 tr
    summ_iter = list(re.finditer(
        r"<tr[^>]*>\s*<td[^>]*><img[^>]*ar\.png[^>]*></td>(.*?)</tr>", html, re.S))
    for i, m in enumerate(summ_iter):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)
        vals = [re.sub(r"<[^>]+>|\s+", "", t) for t in tds]
        # vals: [idx, 文号, 案件名, 日期, 机关]（img-td 已被锚点消费）
        if len(vals) < 5:
            continue
        rec = {"idx": vals[0], "wh": vals[1], "ajmc": vals[2],
               "date": vals[3], "jiguan": vals[4]}
        # 详情：摘要行之后直到下一个摘要行之间的嵌套表
        seg_end = summ_iter[i + 1].start() if i + 1 < len(summ_iter) else len(html)
        seg = html[m.end():seg_end]
        # 字段表：label td 后跟 value td
        kv = {}
        pair = re.findall(
            r'bgcolor="#F4F4F4"[^>]*>([^<]+)</td>\s*<td[^>]*>(.*?)</td>', seg, re.S)
        for k, v in pair:
            v = re.sub(r"<[^>]+>", "", v)
            v = re.sub(r"\s+", " ", v).strip()
            k = re.sub(r"\s+", "", k)
            if k and (k not in kv or not kv[k]):
                kv[k] = v
        rec["fields"] = kv
        recs.append(rec)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe-last", action="store_true")
    args = ap.parse_args()
    # 已收页
    done_pages = set()
    if os.path.exists(RECS):
        for ln in open(RECS, encoding="utf-8"):
            try:
                done_pages.add(json.loads(ln).get("_page"))
            except Exception:
                pass

    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        pg.goto(LIST_URL, timeout=60000, wait_until="domcontentloaded")
        time.sleep(7)
        meta = pg.evaluate("""() => ({total: document.getElementById('totalNum')?.innerText,
                                       tp: document.getElementById('totalPage')?.innerText,
                                       rows: document.querySelectorAll('#tbodylist tr[img], #tbodylist tr').length})""")
        total, tp = int(meta["total"]), int(meta["tp"])
        log(f"platform ready: total={total} pages={tp}")

        fw = open(RECS, "a", encoding="utf-8")
        got_all = 0
        target_pages = [tp] if args.probe_last else range(1, tp + 1)
        for n in target_pages:
            if n in done_pages and not args.probe_last:
                continue
            # 翻页：GO 到第 n 页
            if n > 1:
                try:
                    pg.evaluate(
                        "(n) => { document.getElementById('page').value = String(n); getPage(3); }", n)
                except Exception as e:
                    log(f"p{n} goto exc {str(e)[:60]}")
                    time.sleep(3)
                    continue
                # 等 tbodylist 刷新（首页行 idx=1 出现且页码= n）
                ok = False
                for _ in range(20):
                    time.sleep(1)
                    cur = pg.evaluate(
                        "() => document.getElementById('page_no_now')?.innerText || ''")
                    if str(n) == cur.strip():
                        ok = True
                        break
                if not ok:
                    log(f"p{n} page_no_now={cur!r} timeout")
            tb = pg.evaluate(
                "() => document.getElementById('tbodylist')?.innerHTML || ''")
            open(os.path.join(PAGES, f"p{n:03d}.html"), "w", encoding="utf-8").write(tb)
            recs = parse_tbody(tb)
            for r in recs:
                r["_page"] = n
                fw.write(json.dumps(r, ensure_ascii=False) + "\n")
            fw.flush()
            got_all += len(recs)
            dates = [r["date"] for r in recs if r.get("date")]
            log(f"p{n}/{tp}: recs={len(recs)} cum={got_all} dates={dates[:1]}..{dates[-1:]}"
                if dates else f"p{n}/{tp}: recs={len(recs)}")
            mark({"phase": "qd_xzcf_page", "page": n, "recs": len(recs),
                  "ts": time.strftime("%F %T")})
            time.sleep(1.5 + (n % 3) * 0.5)
        fw.close()
        b.close()
    log("done")


if __name__ == "__main__":
    main()
