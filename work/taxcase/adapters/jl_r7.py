# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
吉林税务 —— 重大税收违法失信主体公布栏 收割（第七轮 R7）
==========================================================
站点 jilin.chinatax.gov.cn 全站瑞数(412/$_ts)：cookie 复放不可行（四川结论），
唯一路径=有头 chromium 过挑战 → 会话内 page.evaluate(fetch)。
注意：col19972 页 onload 自动提交表单有竞态，过墙用稳定 art 页作家。

数据链路（实测）：
  栏目页: /col/col19972/index.html —— 分面查询（地区 field_1136 / 性质 field_1137 /
          年度 field_1138 / 纳税人名称 field_1113 等），#FormSearchTest GET 提交
  列表接口: GET /module/search/index.jsp?<FieldForm 参数>&currpage=N
          5条/页；**分页窗口懒扩展**（页码到尾显示的 maxpage 会从 11→21→…增长，
          必须翻到空页/无新增为止，以新增为 0 停）
  详情页: /art/YYYY/M/D/art_19972_<id>.html —— table.zdwf，行式
          <td class="title_left">LABEL</td><td>值（内嵌 <$[..]>begin/end 标记）</td>
          关键行：纳税人名称/纳税人识别号或社会信用代码/注册地址/法定代表人…/
          主体违法性质/主要违法事实相关法律依据及税务处理处罚情况（富全文）
用法： python jl_r7.py --probe   # 前 3 条详情解析
       python jl_r7.py           # 全量（断点 progress/jl_sx_r7.jsonl）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random, argparse, hashlib, warnings
warnings.filterwarnings("ignore")
from urllib.parse import quote
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from quality_prune import decide  # noqa: E402
from taxcase_scrape import safe_filename  # noqa: E402

SITE = "http://jilin.chinatax.gov.cn"
FIELD = ("field_1113:1:1,field_1114:1:1,field_1115:1:1,field_1116:1:1,"
         "field_1117:1:1,field_1120:1:1,field_1123:1:1,field_1126:1:1,"
         "field_1136:0:1,field_1137:0:1,field_1138:0:1")
SEL = "1113,1114,1115,1116,1117,1120,1123,1126,1136,1137,1138"
QURL = (SITE + "/module/search/index.jsp?"
        "field_1136_large=&field_1136_small=&field_1137_large=&field_1137_small="
        "&field_1138_large=&field_1138_small=&field_1113=&field_1114=&field_1115="
        "&field_1116=&field_1117=&field_1120=&field_1123=&field_1126="
        f"&strSelectID={SEL}&i_columnid=19972&field={quote(FIELD, safe='')}"
        "&initKind=FieldForm&type=1,1,1,1,1,1,1,1,1,1,1&currentplace=&splitflag=&fullpath=0"
        "&currpage={}")
# 过墙稳定页（col19972 有 onload 自动 submit 竞态）
HOME_ART = SITE + "/art/2021/10/27/art_19712_434017.html"

PROG = os.path.join(ROOT, "progress", "jl_sx_r7.jsonl")
LISTS = os.path.join(ROOT, "tmp", "r7")
LIB = os.path.normpath(os.path.join(ROOT, "..", "..", "lawlibrary", "专题", "税务案例", "吉林省"))
OUT = os.path.join(LIB, "重大税收违法失信公布")
TODAY = date.today().isoformat()
DELAY = (1.4, 2.4)

JS_FETCH = """async (u) => {
  const r = await fetch(u, {credentials:'include'});
  const buf = await r.arrayBuffer();
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('\\uFFFD')) { try { text = new TextDecoder('gbk').decode(buf); } catch(e){} }
  return {status: r.status, text: text};
}"""


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def polite():
    time.sleep(random.uniform(*DELAY))


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def pw_open(page, url, tries=3):
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=50000, wait_until="domcontentloaded")
            for _ in range(40):
                time.sleep(1)
                html = page.content()
                last = html
                if body_text_len(html) > 100 and "$_ts=window" not in html[:3000]:
                    return html
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:80]}")
            time.sleep(3)
    return last


def is_challenge(text, status):
    if status in (412, 900):
        return True
    return "$_ts=window" in text[:3000] or "$_ts.layouts" in text[:3000]


def fetch_in(page, url, tries=4):
    for attempt in range(tries):
        try:
            r = page.evaluate(JS_FETCH, url)
            if not is_challenge(r["text"], r["status"]):
                return r
            log(f"  fetch challenged st={r['status']} len={len(r['text'])}, reopen #{attempt}")
        except Exception as e:
            log(f"  fetch exc {type(e).__name__}: {str(e)[:70]}")
        pw_open(page, HOME_ART)
        time.sleep(2)
    return {"status": 0, "text": ""}


TR_RE = re.compile(
    r'<td class="title_left"[^>]*>\s*(.*?)</td>\s*<td[^>]*>(.*?)</td>', re.S)


def parse_art(html):
    from html import unescape
    fields = {}
    for m in TR_RE.finditer(html):
        label = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", m.group(1)))
        v = m.group(2)
        v = re.sub(r"<!--<\$\[[^\]]*\]>begin-->|<!--<\$\[[^\]]*\]>end-->", " ", v)
        v = re.sub(r"<script.*?</script>", " ", v, flags=re.S)
        v = re.sub(r"<br\s*/?>", "\n", v)
        v = re.sub(r"<[^>]+>", " ", v)
        v = unescape(v)
        v = re.sub(r"[ \t]+", " ", v).strip(" ，,")
        if label and label not in fields:
            fields[label] = v.strip()
    rec = {}
    rec["nsrmc"] = fields.get("纳税人名称", "")
    rec["nsrsbh"] = fields.get("纳税人识别号或社会信用代码", "")
    rec["zcdz"] = fields.get("注册地址", "")
    rec["fddbr"] = fields.get("法定代表人或者负责人姓名、性别及身份证号码（或者其他证件号码）", "")
    rec["ajxz"] = fields.get("主体违法性质", "") or fields.get("案件性质", "")
    rec["wfsd"] = fields.get("主要违法事实相关法律依据及税务处理处罚情况", "")
    if not rec["wfsd"]:
        rec["wfsd"] = fields.get("主要违法事实", "")
    rec["fzry"] = fields.get("负有直接责任的财务人员姓名、性别及身份证号码（或者其他证件号码）", "")
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
    nsrmc = rec.get("nsrmc") or ("失信主体_" + art_url.rsplit("_", 1)[-1].split(".")[0])
    title = nsrmc
    lines = ["# " + title + "（重大税收违法失信主体）", ""]
    rows = [("纳税人名称", rec.get("nsrmc")),
            ("纳税人识别号或统一社会信用代码", rec.get("nsrsbh")),
            ("注册地址", rec.get("zcdz")),
            ("法定代表人（负责人）", rec.get("fddbr")),
            ("主体违法性质", rec.get("ajxz"))]
    for k, v in rows:
        if v:
            lines.append(f"- **{k}**：{v}")
    lines += ["", "## 主要违法事实及相关法律依据、税务处理处罚情况", "",
              rec.get("wfsd") or "（未公示）"]
    if rec.get("fzry") and rec["fzry"] not in ("", "无", "-"):
        lines += ["", "负有直接责任的财务人员：" + rec["fzry"]]
    body = "\n".join(lines) + "\n"
    verdict, fl, why = decide("重大税收违法失信公布", "吉林省", body)
    if verdict != "KEEP":
        return None, why, fl
    key = art_url.rsplit("_", 1)[-1].split(".")[0]
    fn = f"{art_date or 'nodate'}_{safe_filename(title)}.md"
    path = os.path.join(OUT, fn)
    if os.path.exists(path):
        return "exists", why, fl
    fm = ("---\n"
          f"title: \"{title.replace(chr(34), '')}\"\n"
          "来源机关: \"国家税务总局吉林省税务局\"\n"
          "栏目: \"重大税收违法失信公布\"\n"
          "地区: \"吉林省\"\n"
          f"发布日期: {art_date or 'nodate'}\n"
          "原文来源: \"吉林省税务局重大税收违法失信主体公布栏\"\n"
          f"抓取日期: {TODAY}\n"
          f"原文链接: {art_url}\n"
          f"记录KEY: {hashlib.md5(('jlsx' + key).encode()).hexdigest().upper()}\n"
          "---\n\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + body)
    return "KEEP", why, fl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LISTS, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2000,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        log("open stable art page (challenge)...")
        pw_open(page, HOME_ART)
        log("ready")

        # ---- 枚举列表（翻到无新增；分页窗口懒扩展）----
        arts = {}
        pg = 1
        empty_streak = 0
        while pg <= 200:
            r = fetch_in(page, QURL.format(pg))
            found = re.findall(r'href="(\.\./\.\./art/\d+/\d+/\d+/art_19972_\d+\.html)"', r["text"])
            new = 0
            for a in found:
                if a not in arts:
                    arts[a] = 1
                    new += 1
            pages = [int(x) for x in re.findall(r'currpage=(\d+)', r["text"])]
            mp = max(pages) if pages else 0
            if new == 0:
                empty_streak += 1
                log(f"[list p{pg}] new=0 cum={len(arts)} maxpage={mp} streak={empty_streak}")
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0
                log(f"[list p{pg}] +{new} cum={len(arts)} maxpage={mp}")
            pg += 1
            polite()
        urls = [a.replace("../../", SITE + "/") for a in sorted(arts)]
        json.dump(urls, open(os.path.join(LISTS, "jl_sx_arts_all.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=0)
        log(f"list total={len(urls)}")

        # ---- 详情 ----
        done = load_done()
        os.makedirs(os.path.dirname(PROG), exist_ok=True)
        fout = open(PROG, "a", encoding="utf-8")
        stats = {"keep": 0, "del": 0, "exists": 0, "fail": 0}
        reasons = {}
        n = 0
        for u in urls:
            m = re.search(r"/art/(\d+)/(\d+)/(\d+)/art_19972_(\d+)\.html", u)
            if not m:
                continue
            art_date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            key = m.group(4)
            n += 1
            if key in done:
                stats["exists"] += 1
                continue
            r = fetch_in(page, u)
            if r["status"] != 200 or len(r["text"]) < 800:
                stats["fail"] += 1
                fout.write(json.dumps({"ok": 0, "key": key, "url": u},
                                      ensure_ascii=False) + "\n")
                fout.flush()
                polite()
                continue
            rec = parse_art(r["text"])
            rec["url"] = u
            rec["fbrq"] = art_date
            verdict, why, fl = write_md(rec, u, art_date)
            fout.write(json.dumps({"ok": 1, "key": key, "verdict": verdict, "why": why,
                                   "rec": rec}, ensure_ascii=False) + "\n")
            fout.flush()
            done[key] = 1
            if verdict == "KEEP":
                stats["keep"] += 1
            elif verdict == "exists":
                stats["exists"] += 1
            else:
                stats["del"] += 1
                reasons[why] = reasons.get(why, 0) + 1
            if n % 10 == 0:
                log(f"  details {n}/{len(urls)} {stats}")
            polite()
        fout.close()
        log(f"done: {stats} del_reasons={reasons}")
        browser.close()


if __name__ == "__main__":
    main()
