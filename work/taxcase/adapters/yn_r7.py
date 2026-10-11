# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""云南 r7：重大税收违法失信案件信息公布栏 全量收割（496 主体）。
列表： GET /bulletin/ajaxfors.jsp?tablename=jcms_41&title=&key= → dataStore 数组（全量行）
行： 地区/纳税人名称/识别号/案件性质/详情URL(art_8101_*.html)
详情： <!--X begin-->value<!--end--> 12 段（名称/地区/识别号/组织机构/地址/法人/…/违法事实+处理处罚）
质量门槛： quality_prune.decide 就地判定。
断点： progress/yunnan_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from curl_cffi import requests as cr
from quality_prune import decide

BASE = "https://yunnan.chinatax.gov.cn"
LIST_URL = BASE + "/bulletin/ajaxfors.jsp?tablename=jcms_41&title=&key="
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "..", "..", "lawlibrary", "专题", "税务案例",
                                    "云南省", "重大税收违法失信公布"))
PROG = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "progress", "yunnan_r7.jsonl"))
os.makedirs(OUT, exist_ok=True)
TODAY = "2026-10-11"
H = {"Referer": BASE + "/bulletin/bullenrightfortop.jsp"}


def safe_fn(s, maxlen=70):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s).strip("_. ")
    return s[:maxlen] or "untitled"


def get(url, timeout=60):
    r = cr.get(url, impersonate="chrome124", timeout=timeout, headers=H)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}")
    return r.content.decode("utf-8", errors="replace")


def parse_rows(list_html):
    """dataStore 行：地区|名称|识别号|案件性质|详情URL"""
    rows = []
    for m in re.finditer(r"<tr class='rlbbox'>(.*?)</tr>", list_html, re.S):
        seg = m.group(1)
        cells = re.findall(r"<(?:div|span)[^>]*>(.*?)</(?:div|span)>", seg, re.S)
        cells = [re.sub(r"<[^>]+>|\s+", "", c).strip() for c in cells]
        link = re.search(r"href='([^']+)'", seg)
        # 过滤表头
        if not link or not cells or cells[0] in ("所属地区",):
            continue
        rows.append({"region": cells[0] if cells else "", "name": cells[1] if len(cells) > 1 else "",
                     "nsrsbh": cells[2] if len(cells) > 2 else "",
                     "ajxz": cells[3] if len(cells) > 3 else "", "url": link.group(1)})
    return rows


def parse_detail(html):
    segs = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
            for s in re.findall(r"begin-->(.*?)end-->", html, re.S)]
    # 模板两变体：12 段（标准）与 14 段（多“公布日期/公布依据”两字段）——末段恒为违法事实
    return segs


def main():
    done = set()
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass
    lh = get(LIST_URL)
    rows = parse_rows(lh)
    print("list rows:", len(rows), flush=True)
    n_ok = n_del = n_err = 0
    for r_ in rows:
        url = r_["url"]
        key = url.rsplit("/", 1)[-1]
        if key in done:
            continue
        time.sleep(1.6 + random.uniform(0, 0.9))
        try:
            dh = get(url)
        except Exception as e:
            n_err += 1
            print("ERR", url, repr(e)[:80], flush=True)
            time.sleep(4)
            try:
                dh = get(url)
            except Exception:
                continue
        segs = parse_detail(dh)
        if len(segs) < 12:
            # 结构异常（字段缺失页留待人工）
            n_err += 1
            with open(PROG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "st": "bad", "segs": len(segs)}, ensure_ascii=False) + "\n")
            done.add(key)
            continue
        fact = segs[-1]
        if len(fact) < 20:
            # 源站事实字段为空（begin/end 间无内容）：按失信门槛不入库
            n_del += 1
            with open(PROG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "st": "del", "why": "empty-facts-on-source",
                                    "fl": len(re.findall(r"[\u4e00-\u9fff]", fact))},
                                   ensure_ascii=False) + "\n")
            done.add(key)
            continue
        segs[11] = fact  # 兼容 14 段变体
        name = segs[0] or r_["name"]
        title = f"{name}（重大税收违法失信主体）"
        m = re.search(r"/art/(\d{4})/(\d{1,2})/(\d{1,2})/", url)
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else TODAY
        body = f"# {title}\n\n"
        body += f"- **纳税人名称**：{name}\n"
        body += f"- **纳税人识别号**：{segs[2] or r_['nsrsbh']}\n"
        if segs[4]:
            body += f"- **注册地址**：{segs[4]}\n"
        body += f"- **案件性质**：{r_['ajxz'] or segs[10]}\n"
        body += f"- **公示机关/地区**：{segs[1] or r_['region']}\n"
        if segs[5]:
            body += f"- **法定代表人**：{segs[5]}\n"
        body += f"\n## 主要违法事实及相关处理处罚\n\n{segs[11]}\n"
        verdict, fl, why = decide("重大税收违法失信公布", "云南省", body)
        if verdict == "DEL":
            n_del += 1
            with open(PROG, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "st": "del", "why": why, "fl": fl},
                                   ensure_ascii=False) + "\n")
            done.add(key)
            continue
        fm = ("---\n"
              f'title: "{safe_fn(title, 80)}"\n'
              '来源机关: "国家税务总局云南省税务局"\n'
              '栏目: "重大税收违法失信公布"\n'
              '地区: "云南省"\n'
              f"发布日期: {date}\n"
              '原文来源: "云南省税务局重大税收违法失信案件信息公布栏"\n'
              f"抓取日期: {TODAY}\n"
              f"原文链接: {url}\n"
              "---\n\n")
        fn = f"{date}_{safe_fn(title)}.md"
        p = os.path.join(OUT, fn)
        k = 1
        while os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                if f"原文链接: {url}" in f.read():
                    p = None
                    break
            k += 1
            p = os.path.join(OUT, f"{date}_{safe_fn(title)}_{k}.md")
        if p is None:
            continue
        with open(p, "w", encoding="utf-8") as f:
            f.write(fm + body)
        n_ok += 1
        done.add(key)
        with open(PROG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "st": "ok", "f": os.path.basename(p)},
                               ensure_ascii=False) + "\n")
    print(f"FINISHED ok={n_ok} del={n_del} err={n_err}")


if __name__ == "__main__":
    main()
