# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
辽宁税务 —— 重大税收违法失信主体公布栏 抓取器
================================================
数据源：辽宁省税务局主站 大汉 CMS
  栏目页: http://liaoning.chinatax.gov.cn/col/col1030/index.html（路径级 JS 挑战，
          playwright 有头可过；/module/search/ 与 /art/ 路径无挑战，requests 直连）
  列表接口: GET /module/search/index.jsp?field=a:1:1,b:1:1&i_columnid=5883&a=&b=&currpage=N
            （10条/页，currpage 超界钳到最后页；共约 199 页 ≈ 1,992 条）
  详情页:  /art/YYYY/M/D/art_5883_<id>.html（字段以 <!--begin-->xxx<!--end--> 标记包裹）
  字段: 纳税人名称/识别号/注册地址/法定代表人(姓别证件)/案件性质/主要违法事实/法律依据及处理处罚
用法：
  python ln_sx.py --probe     # 探页数
  python ln_sx.py             # 正式抓取（断点续抓，上限 MAX）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random, argparse, warnings
warnings.filterwarnings("ignore")
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROG = os.path.join(ROOT, "progress", "ln_sx.jsonl")
BASE = "http://liaoning.chinatax.gov.cn"
SEARCH = (BASE + "/module/search/index.jsp?field=a%3A1%3A1%2Cb%3A1%3A1"
          "&i_columnid=5883&a=&b=&currpage={}")
MAX = 1000
DELAY = 1.6

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA,
                  "Referer": BASE + "/col/col1030/index.html"})

_CH_HEX = re.compile(r'new Array\(\),\w+="((?:\\x[0-9a-fA-F]{2})+)"')
_CH_AG = re.compile(r'[;}]\w+\((\d+),')


def is_challenge(text):
    return ("new Array()" in text and "eval(" in text and len(text) < 2500)


def decode_lmcl(text):
    """解码大汉 CMS 路径级 JS 挑战 → 重定向 query 的 LMCL 令牌"""
    m = _CH_HEX.search(text)
    if not m:
        return None
    hexstr = m.group(1)
    s = "".join(chr(int(hexstr[i + 2:i + 4], 16)) for i in range(0, len(hexstr), 4))
    ag = int(_CH_AG.search(text).group(1))
    a = [ord(c) for c in s]
    i = 4
    while i <= 35:
        a[i] = (a[i] + a[i + 1]) & 0xFF
        a[i] = ((a[i] << 7) & 0xFF) | (a[i] >> 1)
        i += 1
    i = 1
    while True:
        a[i] = (a[i] + a[i + 1]) & 0xFF
        a[i] = (~a[i]) & 0xFF
        a[i] = a[i] ^ 13
        i += 1
        if i > 40:
            break
    i = 37
    while True:
        if i < 3:
            break
        a[i] = ((a[i] ^ 182) + 35) & 0xFF
        i -= 1
    out = "".join(chr(a[i] ^ ag) for i in range(1, len(a) - 1) if i % 7)
    m2 = re.search(r"LMCL=(\w+)", out)
    return m2.group(1) if m2 else None


def get(url, tries=4):
    """带挑战处理的 GET：挑战页解码 LMCL 令牌（作为 query 首参）重放，
    通过后服务端种 UqZBpD3n3iXPAw1X cookie，同会话后续请求免挑战"""
    r = None
    for i in range(tries):
        r = S.get(url, timeout=30)
        if not is_challenge(r.text):
            return r
        lmcl = decode_lmcl(r.text)
        if not lmcl:
            return r
        if "?" in url:
            base, q = url.split("?", 1)
            q = re.sub(r"(?:&)?LMCL=\w+", "", q)  # 防重复堆积
        else:
            base, q = url, ""
        url = f"{base}?LMCL={lmcl}&{q}".rstrip("&?")
        time.sleep(1.0)
    return r


def list_page(cp):
    r = get(SEARCH.format(cp))
    if r.status_code != 200:
        return []
    # art links with date path
    out = []
    for m in re.finditer(r'(?:\.\./)*(/art/(\d+)/(\d+)/(\d+)/art_5883_(\d+)\.html)', r.text):
        path, y, mo, d, aid = m.groups()
        out.append({"id": aid, "url": BASE + path, "date": f"{y}-{int(mo):02d}-{int(d):02d}"})
    return out


def art_detail(url):
    r = get(url)
    r.encoding = "utf-8"
    if r.status_code != 200:
        return None
    return r.text


def parse_art(html):
    """按大汉 CMS 字段标记 <!--<$[label]>begin-->VAL<!--<$[..]>end--> 提字段"""
    fields = {}
    for m in re.finditer(r"<!--<\$\[([^\]]+)\]>begin-->(.*?)<!--<\$\[[^\]]+\]>end-->", html, re.S):
        label = m.group(1).strip()
        v = re.sub(r"<[^>]+>", " ", m.group(2))
        v = re.sub(r"\s+", " ", v).strip()
        fields.setdefault(label, v)
    rec = {}
    rec["nsrmc"] = fields.get("纳税人名称", "")
    rec["nsrsbh"] = fields.get("纳税人识别号", "")
    rec["zcdz"] = fields.get("注册地址", "")
    rec["fddbr"] = fields.get("法定代表人或负责人姓名", "").replace("法定代表人：", "").strip()
    rec["fddbr_xb"] = fields.get("性别", "")
    rec["fddbr_zj"] = fields.get("法定代表人或者负责人证件号码", "")
    rec["ajxz"] = fields.get("案件性质", "")
    rec["wfsd"] = fields.get("主要违法事实", "")
    rec["cfyj_cl"] = fields.get("相关法律依据及税务处理处罚情况", "")
    # 发布日期：art URL 路径为准（由调用方填 fbrq），页面 meta 兜底
    m = re.search(r"name=['\"]UpdateTime['\"]\s+content=['\"]([\d\- :]+)", html)
    rec["fbsj"] = m.group(1)[:10] if m else ""
    return rec


def load_done():
    done = {}
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("ok"):
                        done[r["key"]] = r
                except json.JSONDecodeError:
                    pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--max", type=int, default=MAX)
    args = ap.parse_args()
    p1 = list_page(1)
    print(f"[probe] p1 arts={len(p1)}")
    if args.probe:
        for it in p1[:3]:
            h = art_detail(it["url"])
            time.sleep(0.5)
            print(json.dumps(parse_art(h), ensure_ascii=False)[:400])
        return
    done = load_done()
    print(f"[resume] existing={len(done)}")
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    fout = open(PROG, "a", encoding="utf-8")
    pg = 1
    empty_streak = 0
    while len(done) < args.max and pg <= 200:
        items = list_page(pg)
        if not items:
            empty_streak += 1
            print(f"[p{pg}] empty ({empty_streak})", flush=True)
            if empty_streak >= 4:
                print("[abort] 4 consecutive empty pages"); break
            time.sleep(3.0)
            continue
        empty_streak = 0
        new = 0
        for it in items:
            if it["id"] in done or len(done) >= args.max:
                continue
            time.sleep(DELAY + random.uniform(0, 0.6))
            try:
                h = art_detail(it["url"])
            except Exception as e:
                print(f"[art {it['id']}] err: {e}")
                h = None
            if not h:
                fout.write(json.dumps({"ok": 0, "key": it["id"], "url": it["url"]},
                                      ensure_ascii=False) + "\n")
                continue
            rec = parse_art(h)
            rec["url"] = it["url"]
            rec["fbrq"] = it["date"]
            fout.write(json.dumps({"ok": 1, "key": it["id"], "rec": rec},
                                  ensure_ascii=False) + "\n")
            done[it["id"]] = 1
            new += 1
        fout.flush()
        print(f"[p{pg}] new={new} total={len(done)}", flush=True)
        pg += 1
        time.sleep(DELAY + random.uniform(0, 0.6))
    fout.close()
    print(f"[done] total={len(done)}")


if __name__ == "__main__":
    main()
