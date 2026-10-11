# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
江西 行政处罚信息公示 · xlsx 附件展开收割（第七轮）
====================================================
结构（实测 2026-10-11）：
  - 入口：主站 信息公开 > 信用信息双公示 > 行政处罚信息公示 col32618
    https://jiangxi.chinatax.gov.cn/col/col32618/index.html
  - 列表：大汉 xxgk 动态模块（无验证码，直连 GET）
    /module/xxgk/search.jsp?infotypeId=&vc_title=&vc_number=&area=XZCFXXGS
        &divid=div1576&jdid=26&currpage={n}   （20 条/页，共 6111 条/306 页）
    行结构：<a href='...art_XXX_NNN.html?xxgkhide=1' syh='索引号' jg='机关'
            rq='日期' mc='标题'>   （mc 带全标题；标题含（无）=空批次跳过）
  - 详情：正文仅一条 .xlsx 附件链接 /module/download/downfile.jsp?...filename={md5}.xlsx
  - xlsx：19 列结构化——统一社会信用代码/相对人/决定书文号/案件名称/处罚类别/
    处罚事由/处罚依据/处罚结果/处罚机关 等；一行=一案
策略：翻页至日期 <2023-01-01 停；标题含（无）跳过；下载 xlsx → 按行展开 md；
      quality 门槛（facts>=30）就地判定，DEL 不写盘。
用法：python jx_xzcf_r7.py [--pages N] [--dry]
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, io, json, time, random, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from curl_cffi import requests as cr  # noqa: E402
import openpyxl  # noqa: E402

SITE = "https://jiangxi.chinatax.gov.cn"
SEARCH = SITE + "/module/xxgk/search.jsp?infotypeId=&vc_title=&vc_number=&area=XZCFXXGS&divid=div1576&jdid=26&currpage={page}"
DATE_FROM = "2023-01-01"
CAP = 6000  # r9 复跑：提量收 2023-01→2025-07 余量（原 2000 量控已解除）
DELAY = 1.5

LAWLIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary"))
OUTROOT = os.path.join(LAWLIB, "专题", "税务案例", "江西省", "行政处罚公示")
PROG = os.path.join(ROOT, "progress", "jx_xzcf_r7.jsonl")

ROW_RE = re.compile(
    r"<a href='([^']+)'[^>]*syh='([^']*)'[^>]*jg='([^']*)'[^>]*rq='([^']*)'[^>]*mc='([^']*)'", re.S)
_seen = {}
_mark_lock = None  # 主线程注入


def load_prog():
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                j = json.loads(line)
                _seen[j["k"]] = j
            except Exception:
                pass


def mark(k, st, **kw):
    if k in _seen:
        return False
    j = {"k": k, "st": st}
    j.update(kw)
    with _mark_lock:
        _seen[k] = j
        with open(PROG, "a", encoding="utf-8") as f:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    return True


def fetch_page(page):
    for attempt in range(3):
        time.sleep(DELAY + random.uniform(0, 0.8))
        try:
            r = cr.get(SEARCH.format(page=page), impersonate="chrome124", timeout=150,
                       headers={"Referer": SITE + "/col/col32618/index.html",
                                "X-Requested-With": "XMLHttpRequest",
                                "Accept-Language": "zh-CN,zh;q=0.9"})
            if r.status_code == 200 and "mc=" in r.text:
                return r.text
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def parse_rows(txt):
    out = []
    for m in ROW_RE.finditer(txt):
        href, syh, jg, rq, mc = (g.strip() for g in m.groups())
        if href.startswith("http://"):
            href = href.replace("http://", "https://", 1)
        out.append({"url": href.split("?")[0] + ("?xxgkhide=1" if "xxgkhide" in href else ""),
                    "xurl": href if "downfile" in href else None,
                    "syh": syh, "org": jg, "date": rq, "title": mc})
    return out


def get_detail_att(pageurl):
    """详情页 → xlsx 附件 url"""
    for attempt in range(3):
        time.sleep(0.8 + random.uniform(0, 0.5))
        try:
            r = cr.get(pageurl, impersonate="chrome124", timeout=150,
                       headers={"Referer": SITE + "/", "Accept-Language": "zh-CN,zh;q=0.9"})
            if r.status_code == 200:
                m = re.search(r'href="(/module/download/downfile\.jsp\?[^"]+\.(?:xlsx|xls|doc|docx|pdf))"', r.text, re.I)
                if m:
                    return SITE + m.group(1), None
                return None, "no-att"   # 正文型或无附件
        except Exception as e:
            err = type(e).__name__
        time.sleep(2)
    return None, "fetch-fail"


def download_xlsx(atturl):
    for attempt in range(3):
        time.sleep(0.8 + random.uniform(0, 0.4))
        try:
            r = cr.get(atturl, impersonate="chrome124", timeout=300,
                       headers={"Referer": SITE + "/", "Accept-Language": "zh-CN,zh;q=0.9"})
            if r.status_code == 200 and len(r.content) > 500:
                ct = (r.headers.get("Content-Type") or "").lower()
                if "html" in ct and b"<" in r.content[:200] and b"xml" not in r.content[:600]:
                    # 可能是错误页
                    head = r.content[:200]
                    if b"DOCTYPE html" in head or b"<html" in head:
                        return None, "html-shell"
                return r.content, None
        except Exception:
            pass
        time.sleep(2)
    return None, "dl-fail"


def _find_col(labels_list, aliases, exclude=()):
    """labels_list: [(row1, row2), ...]；alias 优先级驱动（外层循环 aliases）"""
    for a in aliases:
        for i, labels in enumerate(labels_list):
            joined = "|".join(str(x or "") for x in labels)
            if any(e in joined for e in exclude):
                continue
            for lab in labels:
                lab = str(lab or "").strip()
                if lab == a or (a in lab and len(lab) < len(a) + 14):
                    return i
    return None


def parse_xlsx_rows(content):
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
    except Exception:
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content), header=None, dtype=str)
            rows = df.values.tolist()
        except Exception:
            return None, "xlsx-parse-fail"
    if not rows:
        return None, "empty-sheet"
    # 两种表头：A 单行（萍乡稽查局 19 列）；B 两行合并（县区局 36 列）
    r1 = rows[0]
    r2 = rows[1] if len(rows) > 1 else [""] * len(r1)
    two_row = any(str(x or "").strip() in ("统一社会信用代码", "工商注册号", "组织机构代码") for x in r2)
    labels = list(zip(r1, r2 if two_row else [""] * len(r1)))
    data_start = 2 if two_row else 1

    def col(aliases, exclude=()):
        return _find_col(labels, aliases, exclude)

    mp = {
        "name": col(["行政相对人名称", "相对人名称"]),
        "xydm": col(["统一社会信用代码"], exclude=("机关", "来源")),
        "wsh": col(["行政处罚决定书文号", "决定书文号"]),
        "fr": col(["法定代表人姓名", "法定代表人"], exclude=("证件")),
        "ajmc": col(["案件名称"]),
        "lb": col(["处罚类别"]),
        "sy": col(["违法事实", "处罚事由", "违法行为类型"]),
        "yj": col(["处罚依据"]),
        "jg2": col(["处罚内容", "处罚结果"]),
        "fkje": col(["罚款金额"]),
        "czrq": col(["处罚决定日期", "作出处罚日期"]),
        "jg": col(["处罚机关"], exclude=("代码",)),
        "bz": col(["备注"]),
    }
    out = []
    for r in rows[data_start:]:
        if not r:
            continue
        row = {}
        for k, i in mp.items():
            v = ""
            if i is not None and i < len(r) and r[i] is not None:
                v = str(r[i]).strip()
                if v in ("None", "-", "无", "nan", "NaN"):
                    v = ""
            row[k] = v
        if not row["name"] and not row["wsh"]:
            continue
        if row["wsh"]:
            row["wsh"] = re.sub(r"\s+", "", row["wsh"])
        out.append(row)
    return out, mp


def norm_date(s):
    s = str(s).strip()
    m = re.match(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"(\d{4})[-/.](\d{1,2})$", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    return s[:10] if re.match(r"\d{4}-\d{2}-\d{2}", s) else ""


CITY_PREFIX_RE = re.compile(r"^【(.+?)】")


def city_of(org, title):
    m = CITY_PREFIX_RE.match(title)
    if m:
        return m.group(1)
    # 从机关名取市
    for c in ["南昌", "九江", "景德镇", "萍乡", "新余", "鹰潭", "赣州", "宜春", "上饶", "吉安", "抚州",
              "赣江新区"]:
        if c in org:
            return c + "市" if not c.endswith("新区") else c
    return "省局本级"


def facts_len(sy, jg2, fkje):
    """事实叙述长度：违法事实/事由 + 处罚内容/结果 + 罚款金额上下文。
    处罚依据（法条引用）不计入——与 quality_prune 的 facts 口径一致。"""
    segs = []
    if sy:
        segs.append(sy)
    if jg2:
        segs.append(jg2)
    if fkje and re.search(r"[\u4e00-\u9fff]", fkje):
        segs.append(fkje)
    return len(re.findall(r"[\u4e00-\u9fff]", " ".join(segs)))


def write_row_md(item, row, batch):
    date = norm_date(row.get("czrq")) or item["date"]
    title = f"{row.get('name', '')}行政处罚（{row.get('wsh') or item['syh']}）"
    org = row.get("jg") or ""
    if "税务局" not in org:
        org = item["org"] or org
    city = city_of(org, item["title"])
    facts = facts_len(row.get("sy", ""), row.get("jg2", ""), row.get("fkje", ""))
    if facts < 30:
        return None, f"facts<30({facts})"
    body = []
    if row.get("xydm"):
        body.append(f"- 行政相对人：{row['name']}（统一社会信用代码：{row['xydm']}）")
    elif row.get("name"):
        body.append(f"- 行政相对人：{row['name']}")
    if row.get("fr"):
        body.append(f"- 法定代表人：{row['fr']}")
    body.append(f"- 处罚决定书文号：{row.get('wsh') or item['syh']}")
    if row.get("ajmc"):
        body.append(f"- 案件名称：{row['ajmc']}")
    if date:
        body.append(f"- 作出处罚日期：{date}")
    body.append(f"- 处罚机关：{org}")
    if row.get("lb"):
        body.append(f"- 处罚类别：{row['lb']}")
    if row.get("fkje"):
        body.append(f"- 罚款金额（万元）：{row['fkje']}")
    body.append(f"- 公示批次：{item['title']}（{item['date']}，索引号 {item['syh']}）")
    md = "\n".join(body) + "\n\n"
    md += "## 违法事实与处罚事由\n\n" + (row.get("sy") or "（见处罚内容）") + "\n"
    md += "\n## 处罚依据\n\n" + (row.get("yj") or "（未列）") + "\n"
    md += "\n## 处罚内容\n\n" + (row.get("jg2") or "（未列）") + "\n"
    if row.get("bz"):
        md += "\n## 备注\n\n" + row["bz"] + "\n"
    md += f"\n> 数据来源：江西省税务局门户网站行政处罚信息公示附件（{batch}），原文链接 {item['url']}\n"
    out_dir = os.path.join(OUTROOT, city)
    os.makedirs(out_dir, exist_ok=True)
    import taxcase_scrape as t
    fn = f"{date}_{t.safe_filename(title)}.md"
    p = os.path.join(out_dir, fn)
    if os.path.exists(p):
        return "exists", ""
    fm = ("---\n"
          f'title: "{title}"\n'
          f'来源机关: "{org}"\n'
          '栏目: "行政处罚公示"\n'
          '地区: "江西省"\n'
          f"发布日期: {date or item['date']}\n"
          f'原文来源: "国家税务总局江西省税务局网站"\n'
          "抓取日期: 2026-10-11\n"
          f"原文链接: {item['url']}\n"
          "---\n\n")
    with open(p, "w", encoding="utf-8") as f:
        f.write(fm + md + "\n")
    return "done", ""


def process_item(it, stats, lock):
    """单条目：详情→附件→解析→写盘（线程安全：mark 内部 append 由锁保护）"""
    k = it["url"]
    att, err = get_detail_att(k)
    if not att:
        with lock:
            stats["fail"] += 1 if err == "fetch-fail" else 0
            if err != "fetch-fail":
                stats["no_att"] += 1
        mark(k, err or "no-att", title=it["title"], date=it["date"])
        return
    content, err = download_xlsx(att)
    if content is None:
        with lock:
            stats["fail"] += 1
        mark(k, err, title=it["title"], date=it["date"])
        return
    rows, header = parse_xlsx_rows(content)
    if rows is None:
        with lock:
            stats["fail"] += 1
        mark(k, header, title=it["title"], date=it["date"])
        return
    kept = deln = 0
    for row in rows:
        st, why = write_row_md(it, row, att.rsplit("/", 1)[-1][:40])
        if st == "done":
            kept += 1
        elif st is None:
            deln += 1
    with lock:
        stats["rows"] += len(rows)
        stats["kept"] += kept
        stats["del"] += deln
    mark(k, "ok", title=it["title"], date=it["date"], rows=len(rows), kept=kept, dels=deln)
    if rows:
        print(f"  {it['date']} {it['title'][:38]} rows={len(rows)} kept={kept} del={deln}", flush=True)


def main():
    global _mark_lock
    import threading
    from concurrent.futures import ThreadPoolExecutor
    _mark_lock = threading.Lock()
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=0, help="最多翻页数（0=不限直到日期越界）")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--workers", type=int, default=1,
                    help="并发详情线程数；默认 1（合规红线：单线程，审查修复自 4 降为 1）")
    args = ap.parse_args()
    load_prog()
    stats = {"pages": 0, "items": 0, "skip_wu": 0, "no_att": 0, "rows": 0, "kept": 0, "del": 0, "fail": 0}
    lock = threading.Lock()
    page = 1
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while True:
            if args.pages and page > args.pages:
                break
            if stats["kept"] >= CAP:
                print("cap reached", stats["kept"])
                break
            txt = fetch_page(page)
            if txt is None:
                print(f"page {page} FAILED", flush=True)
                break
            items = parse_rows(txt)
            stats["pages"] += 1
            if not items:
                print(f"page {page} empty -> stop", flush=True)
                break
            old_cnt = 0
            todos = []
            for it in items:
                k = it["url"]
                stats["items"] += 1
                if k in _seen:
                    continue
                if it["date"] and it["date"] < DATE_FROM:
                    old_cnt += 1
                    mark(k, "old", title=it["title"], date=it["date"])
                    continue
                if re.search(r"[（(]\s*(无|无内容|0)\s*[)）]\s*$", it["title"]) or "（无）" in it["title"]:
                    stats["skip_wu"] += 1
                    mark(k, "wu", title=it["title"], date=it["date"])
                    continue
                if args.dry:
                    print("DRY:", it["date"], it["title"][:60], flush=True)
                    mark(k, "dry", title=it["title"], date=it["date"])
                    continue
                todos.append(it)
            for it in todos:
                pool.submit(process_item, it, stats, lock)
            # 等本页完成
            pool.shutdown(wait=True)
            from concurrent.futures import ThreadPoolExecutor as _TP
            pool = _TP(max_workers=args.workers)
            print(f"== page {page}: cumulative kept={stats['kept']} rows={stats['rows']} wu={stats['skip_wu']}", flush=True)
            if old_cnt == len(items):
                print("whole page old -> stop", flush=True)
                break
            page += 1
    print("FINAL:", json.dumps(stats, ensure_ascii=False), "progress:", len(_seen))


if __name__ == "__main__":
    main()
