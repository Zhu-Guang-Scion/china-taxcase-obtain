# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
黑龙江税务 —— 重大税收违法失信主体公布栏 收割（第七轮 R7）
============================================================
数据源（直连无墙，curl_cffi chrome124 即可）：
  挂件页: http://heilongjiang.chinatax.gov.cn/module/jslib/bulletin/zdss.html
          （山东系 jslib bulletin，iframe: bullentop.jsp 查询表单 + first.jsp 占位）
  数据接口: GET /module/jslib/bulletin/bullenrightfortop.jsp?nsrmc=<模糊词>...
            → 页内 jpage 配置 totalRecord + proxyUrl='ajaxfors.jsp'，tablename=jcms_141
  代理接口: GET ajaxfors.jsp?startrecord=1&endrecord=1000&perpage=1000
            &tablename=jcms_141&nsrmc=<模糊词>&（其余空）
            → 一次性返回全部命中行（dataStore=[ "<tr>...<a href='art_6410_ID.html'>详细信息" ]）
  枚举法：nsrmc 模糊匹配（LIKE），多词并集饱和即全量（实测 456 条：公司426+厂/店/部/合作社等补齐）
  详情页:  /art/YYYY/M/D/art_6410_<id>.html —— 两列 table（label td + value td），
           值内嵌 <!--<$[..]>begin/end--> 标记；「主要违法事实相关法律依据及税务处理处罚情况」为富全文
用法：
  python hlj_r7.py --probe        # 抓 2 条详情看解析
  python hlj_r7.py                # 全量收割（断点续抓 progress/hlj_sx_r7.jsonl）+ 质量门槛入库
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random, argparse, hashlib, warnings
warnings.filterwarnings("ignore")
from html import unescape
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402
from taxcase_scrape import safe_filename  # noqa: E402
from curl_cffi import requests as cr  # noqa: E402
from datetime import date

BASE = "http://heilongjiang.chinatax.gov.cn"
BULL = BASE + "/module/jslib/bulletin/"
AJAX = BULL + "ajaxfors.jsp"
PROG = os.path.join(ROOT, "progress", "hlj_sx_r7.jsonl")
URLS_CACHE = os.path.join(ROOT, "tmp", "r7", "hlj_sx_urls.json")
LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例", "黑龙江省"))
OUT = os.path.join(LIB, "重大税收违法失信公布")
TODAY = date.today().isoformat()
DELAY = 1.2

# 模糊枚举词（饱和实测：456 条全量）
TERMS = ["公司", "厂", "店", "部", "中心", "合作社", "市场", "站", "行", "社", "队",
         "宾馆", "超市", "经销", "运输", "尔滨", "大", "物流", "贸易", "建筑", "工程",
         "房地产", "服务", "汽车", "农"]

S = cr.Session()
S.headers.update({"Referer": BULL + "bullenrightfortop.jsp"})


def gw(url, tries=3):
    for i in range(tries):
        try:
            r = S.get(url, impersonate="chrome124", timeout=150)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        time.sleep(2 + i * 2)
    return None


def enumerate_urls():
    if os.path.exists(URLS_CACHE):
        return json.load(open(URLS_CACHE, encoding="utf-8"))
    allrows = {}
    for term in TERMS:
        u = (f"{AJAX}?startrecord=1&endrecord=1000&perpage=1000&tablename=jcms_141"
             f"&nsrmc={quote(term)}&nsrsbh=&zcdz=&zzjgdm=&fddbrmc=&fddbrsfzhm="
             f"&cwfzrmc=&cwfzrsfzhm=")
        txt = gw(u)
        if not txt:
            print(f"[enum] {term} FAIL")
            continue
        rows = re.findall(r"href='(https?://heilongjiang\.chinatax\.gov\.cn"
                          r"/art/\d+/\d+/\d+/art_6410_(\d+)\.html)'", txt)
        for url, _ in rows:
            allrows[url] = 1
        print(f"[enum] {term}: links={len(rows)} cum={len(allrows)}", flush=True)
        time.sleep(1.0)
    out = sorted(allrows)
    os.makedirs(os.path.dirname(URLS_CACHE), exist_ok=True)
    json.dump(out, open(URLS_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return out


ROW_RE = re.compile(
    r"bgcolor=[\"']#f4fcff[\"'][^>]*>\s*([^<]{2,60})</td>\s*<td[^>]*>(.*?)</td>", re.S)


def parse_art(html):
    """两列表格：label td（bgcolor#f4fcff）+ value td（剥标签、去 begin/end 标记）"""
    fields = {}
    for m in ROW_RE.finditer(html):
        label = re.sub(r"\s+", "", m.group(1))
        v = m.group(2)
        v = re.sub(r"<!--<\$\[[^\]]*\]>begin-->|<!--<\$\[[^\]]*\]>end-->", " ", v)
        v = re.sub(r"<br\s*/?>", "\n", v)
        v = re.sub(r"<[^>]+>", " ", v)
        v = unescape(v)
        v = re.sub(r"[ \t]+", " ", v).strip()
        fields.setdefault(label, v)
    rec = {}
    rec["nsrmc"] = fields.get("纳税人名称", "")
    rec["nsrsbh"] = fields.get("纳税人识别号或社会信用代码", "")
    rec["zcdz"] = fields.get("注册地址", "")
    rec["fddbr"] = fields.get("法定代表人或者负责人姓名、性别及身份证号码（或者其他证件号码）",
                              "").replace("法定代表人：", "法定代表人：")
    rec["ajxz"] = fields.get("案件性质", "")
    rec["wfsd"] = fields.get("主要违法事实相关法律依据及税务处理处罚情况", "")
    if not rec["wfsd"]:
        rec["wfsd"] = fields.get("主要违法事实", "")
    rec["fzry"] = fields.get("负有直接责任的财务人员姓名、性别及身份证号码（或者其他证件号码）", "")
    rec["wfqr_fddbr"] = fields.get("违法期间法人代表或者负责人姓名、性别及身份证号码（或者其他证件号码）", "")
    return rec


def load_done():
    done = {}
    if os.path.exists(PROG):
        for line in open(PROG, encoding="utf-8"):
            try:
                r = json.loads(line)
                if r.get("ok"):
                    done[r["key"]] = r
            except json.JSONDecodeError:
                pass
    return done


def write_md(rec, art_url, art_date):
    nsrmc = rec.get("nsrmc") or f"失信主体_{art_url.rsplit('_', 1)[-1].split('.')[0]}"
    title = nsrmc
    lines = ["# " + title + "（重大税收违法失信主体）", ""]
    rows = [("纳税人名称", rec.get("nsrmc")),
            ("纳税人识别号或统一社会信用代码", rec.get("nsrsbh")),
            ("注册地址", rec.get("zcdz")),
            ("法定代表人（负责人）", rec.get("fddbr")),
            ("案件性质", rec.get("ajxz"))]
    for k, v in rows:
        if v:
            lines.append(f"- **{k}**：{v}")
    lines += ["", "## 主要违法事实及相关法律依据、税务处理处罚情况", "",
              rec.get("wfsd") or "（未公示）"]
    if rec.get("fzry") and rec["fzry"] not in ("", "无", "-"):
        lines += ["", "负有直接责任的财务人员：" + rec["fzry"]]
    body = "\n".join(lines) + "\n"
    verdict, fl, why = decide("重大税收违法失信公布", "黑龙江省", body)
    if verdict != "KEEP":
        return None, why, fl
    fn = f"{art_date or 'nodate'}_{safe_filename(title)}.md"
    path = os.path.join(OUT, fn)
    if os.path.exists(path):
        return "exists", why, fl
    key = art_url.rsplit("_", 1)[-1].split(".")[0]
    fm = ("---\n"
          f"title: \"{title.replace(chr(34), '')}\"\n"
          "来源机关: \"国家税务总局黑龙江省税务局\"\n"
          "栏目: \"重大税收违法失信公布\"\n"
          "地区: \"黑龙江省\"\n"
          f"发布日期: {art_date or 'nodate'}\n"
          "原文来源: \"黑龙江省税务局重大税收违法失信主体信息公布栏\"\n"
          f"抓取日期: {TODAY}\n"
          f"原文链接: {art_url}\n"
          f"记录KEY: {hashlib.md5(('hljsx' + key).encode()).hexdigest().upper()}\n"
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body)
    return "KEEP", why, fl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    urls = enumerate_urls()
    print(f"[urls] total={len(urls)}")
    done = load_done()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    if args.probe:
        for u in urls[:2]:
            h = gw(u)
            print(json.dumps(parse_art(h), ensure_ascii=False)[:500])
            print("---")
        return
    fout = open(PROG, "a", encoding="utf-8")
    stats = {"keep": 0, "del": 0, "exists": 0, "fail": 0}
    reasons = {}
    for i, u in enumerate(urls):
        m = re.search(r"/art/(\d+)/(\d+)/(\d+)/art_6410_(\d+)\.html", u)
        art_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
        key = m.group(4) if m else str(i)
        if key in done:
            stats["exists"] += 1
            continue
        time.sleep(DELAY + random.uniform(0, 0.5))
        h = gw(u)
        if not h:
            stats["fail"] += 1
            fout.write(json.dumps({"ok": 0, "key": key, "url": u}, ensure_ascii=False) + "\n")
            fout.flush()
            continue
        rec = parse_art(h)
        rec["url"] = u
        rec["fbrq"] = art_date
        verdict, why, fl = write_md(rec, u, art_date)
        fout.write(json.dumps({"ok": 1, "key": key, "verdict": verdict,
                               "why": why, "rec": rec}, ensure_ascii=False) + "\n")
        fout.flush()
        done[key] = 1
        if verdict == "KEEP":
            stats["keep"] += 1
        elif verdict == "exists":
            stats["exists"] += 1
        else:
            stats["del"] += 1
            reasons[why] = reasons.get(why, 0) + 1
        if (i + 1) % 25 == 0:
            print(f"[{i+1}/{len(urls)}] {stats}", flush=True)
    fout.close()
    print("[done]", stats, "del_reasons:", reasons)


if __name__ == "__main__":
    main()
