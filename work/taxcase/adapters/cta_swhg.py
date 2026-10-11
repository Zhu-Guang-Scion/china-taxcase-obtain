# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""总局「税务合规典型企业案例」专题抓取（JSON API 专用适配器）
接口：POST /getFileListByCodeId {codeId, channelId, page, size}（页面 swhg.html 内嵌）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import taxcase_scrape as t

API = "https://www.chinatax.gov.cn/getFileListByCodeId"
BODY = {"codeId": "c103110", "channelId": "ada319f627474aecbb95d68b274b5fc7"}
# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
OUT = os.path.join(REPO, "lawlibrary", "专题", "税务案例",
                           "国家税务总局", "税务合规典型企业案例")
JOB = "cta_swhg"
os.makedirs(OUT, exist_ok=True)


def fetch_page(page, size=10):
    from curl_cffi import requests as cr
    for attempt in range(3):
        wait = 2.5 + t.random.uniform(0, 1) - (time.time() - t._last_ts[0])
        if wait > 0:
            time.sleep(wait)
        try:
            r = cr.post(API, json=dict(BODY, page=page, size=size),
                        impersonate="chrome124", timeout=30,
                        headers={"Referer": "https://www.chinatax.gov.cn/chinatax/c103110/swhg.html"})
            t._last_ts[0] = time.time()
            if r.status_code == 200:
                return r.json()["results"]["data"]
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    return None


def main():
    done, prog_path = t.load_progress(JOB)
    total = None
    page = 1
    n_new = 0
    with open(prog_path, "a", encoding="utf-8") as prog:
        while True:
            data = fetch_page(page)
            if not data:
                print(f"page {page} failed, stop"); break
            total = data.get("total", 0)
            items = data.get("results", [])
            if not items:
                break
            for it in items:
                url = (it.get("redirectUrl") or it.get("url") or "").strip()
                title = re.sub(r"<[^>]+>", "", it.get("titleHtml") or it.get("subTitleHtml") or "")
                title = re.sub(r"\s+", " ", title).strip()
                dstr = (it.get("publishedTimeStr") or "")[:10]
                if not url or url in done:
                    continue
                r = t.polite_get(url, 2.2, referer="https://www.chinatax.gov.cn/")
                if r is None:
                    prog.write(json.dumps({"url": url, "ok": False, "err": "fetch"},
                                          ensure_ascii=False) + "\n"); prog.flush(); continue
                d = t.extract_detail(r.text, url, title, dstr)
                if not d or len(d["md"]) < 100:
                    prog.write(json.dumps({"url": url, "ok": False, "err": "parse"},
                                          ensure_ascii=False) + "\n"); prog.flush(); continue
                fname = t.safe_filename((d["date"] or dstr or "nodate") + "_" + (d["title"] or title)) + ".md"
                fm = ("---\n"
                      f"title: \"{(d['title'] or title).replace(chr(34), '')}\"\n"
                      "来源机关: \"国家税务总局\"\n"
                      "栏目: \"税务合规典型企业案例\"\n"
                      "地区: \"全国\"\n"
                      f"发布日期: {d['date'] or dstr}\n"
                      f"原文来源: \"{d['source_org']}\"\n"
                      f"抓取日期: {time.strftime('%Y-%m-%d')}\n"
                      f"原文链接: {url}\n"
                      "---\n\n")
                with open(os.path.join(OUT, fname), "w", encoding="utf-8", newline="\n") as f:
                    f.write(fm + d["md"] + "\n")
                prog.write(json.dumps({"url": url, "ok": True, "file": fname},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                n_new += 1
            if page * 10 >= (total or 0):
                break
            page += 1
    print(f"[{JOB}] DONE new={n_new} total_in_column={total}")


if __name__ == "__main__":
    main()
