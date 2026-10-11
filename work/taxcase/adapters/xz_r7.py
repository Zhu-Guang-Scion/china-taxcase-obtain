# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
西藏税务 —— 税案通报/曝光新闻 收割（第七轮 R7，30分钟快探盒）
================================================================
探测结论（2026-10-11）：
  - 无重大税收违法失信主体公布栏（主站无该栏目；/module/jslib/bulletin/zdss.html 404）
  - 无 etax 处罚平台（etax.xizang:8443/sword 仅 SPA 壳并跳转 :5100 新电子税务局，
    ajax.sword 数据端点不存在——湖南式空壳）
  - 可用源=主站 通知公告 col5513（TRAP: hanweb/大汉 col 页 + dataproxy.jsp，
    unitid=13090 webid=1）：total 301 条中 16 条为税案查处/曝光通报（信源#4 新闻过滤）
用法： python xz_r7.py
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random, hashlib, warnings
warnings.filterwarnings("ignore")
from urllib.parse import quote
from datetime import date
from html import unescape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402
from taxcase_scrape import safe_filename  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402

S = "https://xizang.chinatax.gov.cn"
PROG = os.path.join(ROOT, "progress", "xz_news_r7.jsonl")
LISTS = os.path.join(ROOT, "tmp", "r7")
LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例", "西藏自治区"))
OUT = os.path.join(LIB, "税案通报")
TODAY = date.today().isoformat()

CASE = re.compile(r"查处|曝光|偷税|虚开|骗取|骗享|骗税|黑中介")
EXCL = re.compile(r"廉政|欠税的公告|信用修复|约束制度|惩戒机制|撤销|反馈通道|意见$")
DATE_RE = re.compile(r"(20\d{2})[-./年](\d{1,2})[-./月](\d{1,2})")


def sess():
    s = cr.Session()
    s.headers.update({"Referer": S + "/"})
    return s


def fetch_list(s):
    body = ("col=1&appid=1&webid=1&path=%2F&columnid=5513&sourceContentType=1"
            "&unitid=13090&webname=" + quote(quote("国家税务总局西藏自治区税务局", safe=""), safe="")
            + "&permissiontype=0&startrecord=1&endrecord=400&perpage=400")
    r = s.post(S + "/module/web/jpage/dataproxy.jsp", data=body,
               impersonate="chrome124", timeout=150,
               headers={"Content-Type": "application/x-www-form-urlencoded"})
    items = []
    for rm in re.finditer(r"<record>(.*?)</record>", r.text, re.S):
        seg = rm.group(1)
        a = re.search(r"href=['\"]?([^'\"\s>]+)", seg)
        tm = re.search(r"title=['\"]([^'\"]+)", seg)
        am = re.search(r">([^<>]{5,120})</a>", seg)
        dm = re.search(r"(20\d{2}-\d{2}-\d{2})", seg)
        if not a:
            continue
        url = a.group(1)
        if url.startswith("/"):
            url = S + url
        title = (tm.group(1) if tm else (am.group(1) if am else "")).strip()
        items.append({"url": url, "title": title, "date": dm.group(1) if dm else ""})
        keep = [i for i in items if CASE.search(i["title"]) and not EXCL.search(i["title"])]
    # 日期：dataproxy 只有 MM-DD，完整日期直接取 art URL 路径（TRS 发布日期）
    for i in keep:
        dm = re.search(r"/art/(\d+)/(\d+)/(\d+)/art_", i["url"])
        if dm:
            i["date"] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
    return items, keep


def parse_art(html):
    """正文在 begin-->/end--> 标记对内：取 CJK 字符最多的段（标题段极短，正文段最长）"""
    best = ""
    for m in re.finditer(r"begin-->(.*?)end-->", html, re.S):
        seg = m.group(1)
        seg2 = re.sub(r"<script.*?</script>", " ", seg, flags=re.S)
        seg2 = re.sub(r"<br\s*/?>", "\n", seg2)
        seg2 = re.sub(r"</p>", "\n", seg2)
        seg2 = re.sub(r"<[^>]+>", " ", seg2)
        seg2 = unescape(seg2)
        seg2 = re.sub(r"[ \t]+", " ", seg2)
        seg2 = re.sub(r"\n\s*\n+", "\n\n", seg2).strip()
        if len(re.findall(r"[\u4e00-\u9fff]", seg2)) > len(re.findall(r"[\u4e00-\u9fff]", best)):
            best = seg2
    return best


def load_done():
    done = set()
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r.get("ok"):
                    done.add(r["key"])
            except json.JSONDecodeError:
                pass
    return done


def main():
    s = sess()
    items, keep = fetch_list(s)
    print(f"[list] total={len(items)} case_keep={len(keep)}")
    json.dump(keep, open(os.path.join(LISTS, "xz_case_items.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    done = load_done()
    fout = open(PROG, "a", encoding="utf-8")
    stats = {"keep": 0, "del": 0, "exists": 0, "fail": 0}
    for it in keep:
        key = it["url"].rsplit("_", 1)[-1].split(".")[0]
        if key in done:
            stats["exists"] += 1
            continue
        try:
            r = s.get(it["url"], impersonate="chrome124", timeout=150)
        except Exception as e:
            print("fail", it["url"], str(e)[:60])
            stats["fail"] += 1
            fout.write(json.dumps({"ok": 0, "key": key, "url": it["url"]},
                                  ensure_ascii=False) + "\n")
            continue
        body = parse_art(r.text)
        cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
        title = it["title"]
        lines = ["# " + title, "", f"- **发布日期**：{it['date']}",
                 f"- **来源**：国家税务总局西藏自治区税务局（通知公告）", "",
                 "## 案情通报", "", body]
        mdtxt = "\n".join(lines) + "\n"
        verdict, fl, why = decide("税案通报", "西藏自治区", mdtxt)
        if verdict != "KEEP":
            stats["del"] += 1
            print("  DEL:", title[:40], why, "cjk=", cjk)
            fout.write(json.dumps({"ok": 1, "key": key, "verdict": None, "why": why,
                                   "url": it["url"]}, ensure_ascii=False) + "\n")
            continue
        fn = f"{it['date'] or 'nodate'}_{safe_filename(title)[:60]}.md"
        path = os.path.join(OUT, fn)
        fm = ("---\n"
              f"title: \"{title.replace(chr(34), '')}\"\n"
              "来源机关: \"国家税务总局西藏自治区税务局\"\n"
              "栏目: \"税案通报\"\n"
              "地区: \"西藏自治区\"\n"
              f"发布日期: {it['date'] or 'nodate'}\n"
              "原文来源: \"西藏自治区税务局网站通知公告（税案查处/曝光通报）\"\n"
              f"抓取日期: {TODAY}\n"
              f"原文链接: {it['url']}\n"
              f"记录KEY: {hashlib.md5(('xz' + key).encode()).hexdigest().upper()}\n"
              "---\n\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(fm + mdtxt)
        stats["keep"] += 1
        fout.write(json.dumps({"ok": 1, "key": key, "verdict": "KEEP",
                               "url": it["url"], "cjk": cjk},
                              ensure_ascii=False) + "\n")
        print("  KEEP:", it["date"], title[:44], "cjk=", cjk)
        time.sleep(1.2 + random.uniform(0, 0.5))
    fout.close()
    print("[done]", stats)


if __name__ == "__main__":
    main()
