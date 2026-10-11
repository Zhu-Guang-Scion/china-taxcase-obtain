# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""内蒙古税务局 重大税收违法失信主体公布栏 收割（R7，直连 curl_cffi）
列表: GET /was5/search?channelid=214090&searchword=&sortfield=-DOCRELTIME&perpage=100&page=N
      （总 487 条，10 列/行表：所属税务机关/纳税人名称/识别号/案件性质/详细信息）
详情: /nsfw/sscx/zdaj/<区>/<yyyymm>/tYYYYMMDD_NNNNN.html，[标签,值] 成对表格，
      含「主要违法事实相关法律依据及税务处理处罚情况」全文；meta PubDate。
输出: tmp/nmg/zdaj_meta.jsonl + zdaj_*.html；断点 progress/neimenggu_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, random, hashlib, argparse
from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.normpath(os.path.join(ROOT, "tmp", "nmg"))
os.makedirs(TMP, exist_ok=True)
PROG = os.path.join(ROOT, "progress", "neimenggu_r7.jsonl")
B = "https://neimenggu.chinatax.gov.cn"

# 案件性质 JS 映射（页面内联脚本原样转写）
def anj_map(anj):
    if anj == "虚开增值税专用发票（普通发票）案件":
        return "虚开增值税专用发票或者虚开用于骗取出口退税、抵扣税款的其他发票案件"
    if anj == "偷税案件(自然人)":
        return "私自印制、伪造、变造发票，非法制造发票防伪专用品，伪造发票监制章案件"
    if anj == "其他-违法情节严重、有较大社会影响":
        return "多种违法类型案件"
    if anj == "偷税案件（隐瞒销售收入）":
        return "走逃（失联)案件"
    return anj


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def load_done(phase):
    done = set()
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                d = json.loads(ln)
                if d.get("phase") == phase and d.get("ok"):
                    done.add(d.get("key"))
            except Exception:
                pass
    return done


def get(url, tries=4):
    for t in range(tries):
        try:
            r = cr.get(url, impersonate="chrome124", timeout=300,
                       headers={"Referer": B + "/nsfw/sscx/zdaj/"})
            if r.status_code == 200:
                return r.text
            log(f"  st={r.status_code} {url[:80]}")
        except Exception as e:
            log(f"  exc {type(e).__name__} {str(e)[:60]}")
        time.sleep(4 + 3 * t)
    return ""


def parse_rows(h):
    """安全解析：split <tr>，数据行含 详细信息 链接。
    单元格顺序: sbh(机关) / nsrmc(名称) / ahxz(识别号) / ssdq(案件性质+script) / fsnd(链接)"""
    out = []
    for tr in re.split(r"<tr", h):
        if "详细信息" not in tr or "href" not in tr:
            continue
        m = re.search(r'href="([^"]+)"', tr)
        if not m:
            continue
        det = m.group(1).replace("http://neimenggu.chinatax.gov.cn", "")
        det = det if det.startswith("http") else B + det
        cells = []
        for td in re.split(r"<td", tr)[1:]:
            anj = re.search(r"var anj\s*=\s*'([^']+)'", td)
            td2 = re.sub(r"<script.*?</script>", "", td, flags=re.S)
            txt = re.sub(r"<[^>]+>|\s+|&nbsp;", "", td2)
            txt = (anj.group(1) if anj else "") or txt
            cells.append(txt)
        if len(cells) < 5:
            continue
        out.append({"sw": cells[0], "name": cells[1], "nsrsbh": cells[2],
                    "anj": cells[3], "url": det})
    return out


def strip(s):
    return re.sub(r"<[^>]+>|\s+|&nbsp;", "", s or "")


def run_list(perpage=100, max_pages=10):
    done_pages = load_done("zdaj_page")
    rows = {}
    total = None
    for pg in range(1, max_pages + 1):
        if pg in done_pages:
            # 仍拉一遍拿 rows（断点文件不存行内容，缓存于 jsonl 由详情阶段负责）
            pass
        u = (f"{B}/was5/search?channelid=214090&searchword=&sortfield=-DOCRELTIME"
             f"&perpage={perpage}&page={pg}")
        h = get(u)
        if not h:
            log(f"p{pg} unreachable, stop")
            break
        m = re.search(r"共有(\d+)\s*条记录", h)
        if m and total is None:
            total = int(m.group(1))
            log(f"total={total}")
        found = 0
        for r in parse_rows(h):
            if r["url"] not in rows:
                rows[r["url"]] = r
                found += 1
        log(f"p{pg}: +{found} cum={len(rows)}")
        mark({"phase": "zdaj_page", "key": pg, "ok": True, "n": found})
        if not found:
            break
        time.sleep(random.uniform(1.8, 2.8))
    out = os.path.join(TMP, "zdaj_rows.json")
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"list done: {len(rows)} unique rows -> {out}")
    return rows


def run_details():
    rows = json.load(open(os.path.join(TMP, "zdaj_rows.json"), encoding="utf-8"))
    done = load_done("zdaj_art")
    todo = [(u, r) for u, r in rows.items() if u not in done]
    log(f"details todo {len(todo)} / {len(rows)}")
    meta_path = os.path.join(TMP, "zdaj_meta.jsonl")
    n_ok = n_fail = 0
    with open(meta_path, "a", encoding="utf-8") as mf:
        for i, (u, r) in enumerate(todo):
            key = hashlib.md5(u.encode()).hexdigest()[:12]
            h = get(u)
            if h and len(h) > 4000 and "纳税人名称" in h:
                fp = os.path.join(TMP, f"zdaj_{key}.html")
                open(fp, "w", encoding="utf-8").write(h)
                mf.write(json.dumps({**r, "key": key, "file": fp},
                                    ensure_ascii=False) + "\n")
                mark({"phase": "zdaj_art", "key": u, "ok": True})
                n_ok += 1
            else:
                mark({"phase": "zdaj_art", "key": u, "ok": False})
                n_fail += 1
                log(f"  FAIL {u[:90]}")
            if (i + 1) % 25 == 0:
                log(f"  {i+1}/{len(todo)} ok={n_ok} fail={n_fail}")
            time.sleep(random.uniform(1.8, 2.6))
    log(f"details done ok={n_ok} fail={n_fail}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", choices=["list", "det", "all"])
    args = ap.parse_args()
    if args.part in ("list", "all"):
        run_list()
    if args.part in ("det", "all"):
        run_details()
