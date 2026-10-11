# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""青岛 税案通报/稽查查处新闻 —— WAS5 全站检索收割
接口: GET /search/was5/web/search?channelid=296952&searchword=KW&page=N（会话内 fetch）
选择: 标题严格关键词（查处|曝光|虚开|骗税|偷税|逃避缴纳税款|追缴|稽查局），2023-01-01 起
产出: tmp/qd/news_arts.jsonl + 详情 tmp/qd/news_pages/*.html
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json, argparse
from urllib.parse import quote
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pw_common import pw_open  # 审查修复：改自侦察脚本抽出的公共模块
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "qd")
PAGES = os.path.join(TMP, "news_pages"); os.makedirs(PAGES, exist_ok=True)
ARTS = os.path.join(TMP, "news_arts.jsonl")
PROG = os.path.join(ROOT, "progress", "qd_hn_r6.jsonl")
SITE = "https://qingdao.chinatax.gov.cn"

JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""

KWS = ["查处", "偷逃", "追缴税款", "少缴", "曝光台", "涉税违法", "案件公布",
       "虚开", "骗取出口退税", "逃避缴纳税款"]
TITLE_RE = re.compile(r"查处|曝光|虚开|骗税|骗取|偷税|偷逃|逃避缴纳税款|追缴|重大税收违法|失信|少缴|违法")
BAD_RE = re.compile(r"送达公告|催缴|催报|文书公告|招聘|采购|招标")
DATE_FROM = "2023-01-01"
MAX_PAGES_PER_KW = 12


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def fetch_in(pg, u, home=SITE + "/"):
    for att in range(3):
        try:
            r = pg.evaluate(JS_FETCH, u)
        except Exception as e:
            log(f"  fetch exc {str(e)[:60]}")
            pw_open(pg, home); time.sleep(2); continue
        if r["status"] not in (412, 900) and not (len(r["text"]) < 3000 and "MMB1_" in r["text"]):
            return r
        pw_open(pg, home); time.sleep(2)
    return r


def parse_hits(html):
    """WAS5 结果 → [(url,title,date)]"""
    out = []
    for m in re.finditer(
            r'href=["\']([^"\']+/t\d{8}_\d+\.s?html)["\'][^>]*>([^<]{6,90})<', html):
        u, t = m.group(1), m.group(2).strip()
        seg = html[m.end():m.end() + 400]
        dm = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", seg)
        d = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}" if dm else ""
        out.append((u, t, d))
    return out


def main():
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    seen = {}
    if os.path.exists(ARTS):
        for ln in open(ARTS, encoding="utf-8"):
            try:
                d = json.loads(ln)
                seen[d["url"]] = d
            except Exception:
                pass
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        state = {"pg": pg, "fails": 0}

        def F(u):
            """fetch 优先；失败转真实导航"""
            for att in range(5):
                try:
                    r = state["pg"].evaluate(JS_FETCH, u)
                except Exception:
                    r = {"status": -1, "text": ""}
                if r["status"] not in (412, 900, -1) and not (len(r["text"]) < 3000 and "MMB1_" in r["text"]):
                    state["fails"] = 0
                    return r
                state["fails"] += 1
                log(f"  fetch bad (st={r['status']}), fails={state['fails']} -> try NAV")
                try:
                    h = pw_open(state["pg"], u)
                    if len(h) > 2500 and "MMB1_" not in h[:2000]:
                        state["fails"] = 0
                        return {"status": 200, "text": h}
                except Exception as e:
                    log(f"  nav exc {str(e)[:60]}")
                time.sleep(6 + att * 5)
            return {"status": 0, "text": ""}

        for kw in KWS:
            total = None
            for pno in range(1, MAX_PAGES_PER_KW + 1):
                u = (f"{SITE}/search/was5/web/search?channelid=296952"
                     f"&searchword={quote(kw)}" + (f"&page={pno}" if pno > 1 else ""))
                r = F(u)
                hits = parse_hits(r["text"])
                m = re.search(r"(?:共|搜索到|找到)[^0-9]{0,6}(\d+)[^0-9]{0,4}(?:条|篇)", r["text"])
                if m:
                    total = m.group(1)
                new_kw = 0
                for uu, tt, dd in hits:
                    if uu not in seen:
                        seen[uu] = {"url": uu, "title": tt, "date": dd, "kw": kw}
                        new_kw += 1
                log(f"[{kw}] p{pno}: hits={len(hits)} new={new_kw} (total={total}, cum={len(seen)})")
                if not hits or new_kw == 0:
                    break
                time.sleep(1.6 + pno % 2)
        # 落盘列表
        with open(ARTS, "w", encoding="utf-8") as f:
            for d in seen.values():
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        # 详情
        todo = [d for d in seen.values()
                if (not d["date"] or d["date"] >= DATE_FROM)
                and TITLE_RE.search(d["title"]) and not BAD_RE.search(d["title"])]
        log(f"details todo (title-filtered): {len(todo)} / {len(seen)}")
        n_ok = 0
        for i, d in enumerate(todo):
            r = F(d["url"])
            if r["status"] == 200 and len(r["text"]) > 1500:
                key = re.sub(r"\W", "", d["url"].split("gov.cn")[-1])[-40:] or str(i)
                fp = os.path.join(PAGES, key + ".html")
                open(fp, "w", encoding="utf-8").write(r["text"])
                d["file"] = fp
                n_ok += 1
            else:
                d["file"] = None
            if (i + 1) % 20 == 0:
                log(f"  details {i+1}/{len(todo)} ok={n_ok}")
                with open(ARTS, "w", encoding="utf-8") as f:
                    for dd in seen.values():
                        f.write(json.dumps(dd, ensure_ascii=False) + "\n")
            time.sleep(1.5 + i % 3 * 0.4)
        with open(ARTS, "w", encoding="utf-8") as f:
            for dd in seen.values():
                f.write(json.dumps(dd, ensure_ascii=False) + "\n")
        b.close()
    log(f"done details ok={n_ok}")


if __name__ == "__main__":
    main()
