# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""青岛 重大税收违法失信主体公布栏（WAS5 channelid=223090 直连版）
列表: GET /search/was5/web/search?channelid=223090&searchword=&page=N（10/页，共~514）
详情: /resourcedata/sswf2019/qy/YYYYMM/tYYYYMMDD_NNNNN.html
产出: tmp/qd/sswf_list.jsonl + tmp/qd/sswf_details/*.html
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json, argparse
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pw_common import pw_open  # 审查修复：改自侦察脚本抽出的公共模块
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "qd")
DETS = os.path.join(TMP, "sswf_details"); os.makedirs(DETS, exist_ok=True)
LIST_F = os.path.join(TMP, "sswf_list.jsonl")
PROG = os.path.join(ROOT, "progress", "qd_hn_r6.jsonl")
SITE = "https://qingdao.chinatax.gov.cn"

JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def fetch_in(pg, u, home=SITE + "/"):
    r = {"status": 0, "text": ""}
    for att in range(4):
        try:
            r = pg.evaluate(JS_FETCH, u)
        except Exception as e:
            log(f"  fetch exc {str(e)[:60]}")
            pw_open(pg, home); time.sleep(2); continue
        if r["status"] not in (412, 900) and not (len(r["text"]) < 3000 and "MMB1_" in r["text"]):
            return r
        pw_open(pg, home); time.sleep(2)
    return r


def parse_list(html):
    dets = re.findall(r'href=["\']([^"\']+)["\'][^>]*>\s*详细信息', html)
    m = re.search(r"(?:共|搜索到|找到|总计)[^0-9]{0,8}(\d+)", html)
    return (int(m.group(1)) if m else None), [urljoin(SITE + "/", d) for d in dets]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=80)
    args = ap.parse_args()
    done_urls = set()
    if os.path.exists(LIST_F):
        for ln in open(LIST_F, encoding="utf-8"):
            try:
                d = json.loads(ln)
                if d.get("file"):
                    done_urls.add(d["url"])
            except Exception:
                pass
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        state = {"pg": pg, "fails": 0}

        def F(u):
            """fetch 优先；连续失败转真实导航（IP 级 fetch 临时封禁时导航仍可用）"""
            for att in range(6):
                try:
                    r = state["pg"].evaluate(JS_FETCH, u)
                except Exception:
                    r = {"status": -1, "text": ""}
                if r["status"] not in (412, 900, -1) and not (len(r["text"]) < 3000 and "MMB1_" in r["text"]):
                    state["fails"] = 0
                    return r
                state["fails"] += 1
                log(f"  fetch bad (st={r['status']}), fails={state['fails']} -> try NAV")
                # 转导航模式
                try:
                    h = pw_open(state["pg"], u)
                    if len(h) > 2500 and "MMB1_" not in h[:2000]:
                        state["fails"] = 0
                        return {"status": 200, "text": h}
                except Exception as e:
                    log(f"  nav exc {str(e)[:60]}")
                time.sleep(8 + att * 6)
            return {"status": 0, "text": ""}

        all_urls = []
        total = None
        for pno in range(1, args.max_pages + 1):
            u = f"{SITE}/search/was5/web/search?channelid=223090&searchword="
            if pno > 1:
                u += f"&page={pno}"
            r = F(u)
            t2, dets = parse_list(r["text"])
            if t2:
                total = t2
            if not dets:
                log(f"p{pno}: no rows, stop (total={total})")
                break
            before = len(all_urls)
            all_urls.extend(dict.fromkeys(dets))
            log(f"p{pno}: rows={len(dets)} cum={len(all_urls)} total={total}")
            mark({"phase": "qd_sswf_list2", "page": pno, "rows": len(dets),
                  "cum": len(all_urls), "ts": time.strftime("%F %T")})
            if len(all_urls) == before:
                break
            time.sleep(1.4 + pno % 3 * 0.4)
        # 详情
        todo = [u for u in all_urls if u not in done_urls]
        log(f"details todo: {len(todo)} (already {len(done_urls)})")
        fw = open(LIST_F, "a", encoding="utf-8")
        n_ok = 0
        for i, u in enumerate(todo):
            r = F(u)
            if r["status"] == 200 and len(r["text"]) > 1000:
                key = re.sub(r"\W", "", u.split("gov.cn")[-1])[-40:] or str(i)
                fp = os.path.join(DETS, key + ".html")
                open(fp, "w", encoding="utf-8").write(r["text"])
                fw.write(json.dumps({"url": u, "file": fp}, ensure_ascii=False) + "\n")
                n_ok += 1
            else:
                fw.write(json.dumps({"url": u, "file": None, "st": r["status"]},
                                    ensure_ascii=False) + "\n")
            fw.flush()
            if (i + 1) % 25 == 0:
                log(f"  details {i+1}/{len(todo)} ok={n_ok}")
            time.sleep(1.2 + i % 3 * 0.4)
        fw.close()
        b.close()
    log(f"done: details ok={n_ok}")


if __name__ == "__main__":
    main()
