# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
辽宁税务 —— sword 行政执法公示平台·一般处罚结果 抓取器
========================================================
数据源：国家税务总局辽宁省税务局行政执法信息公示平台（wings/sword 框架）
  入口页: https://etax.liaoning.chinatax.gov.cn:8090/sword?ctrl=XzzfgsptHomeCtrl_index
  查询页: /sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg&sxq=liaoningsheng&swjgDm=<code>
  数据接口: POST /ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg
    postData=<urlencoded JSON>（表单编码单字段，尾部 +）
    字段: ajmc/nsrsbh/nsrmc/cfjg/yxqq/yxqz/swjgDm(逗号分隔多机关)/rows/
          ckcode(验证码)/ckcodeId=ck1；翻页加 pageNum（首响应 bizParams 回传亦可）
  验证码: GET /download.sword?ctrl=CheckcodeUtil_getCheckcode&t=<32随机>&id=ck1
          （参数名是 id 不是 ckcodeId；每次 POST 消费一个码，ddddocr 过码率~75%）
  会话: GSPT_SESSION cookie（python requests + 浏览器 UA 即可，默认 UA 403）
机关代码：213 个（辽宁省 193 + 大连市 20），来源 tmp/ln/ln_swjgdm_all.json
用法：
  python ln_sword.py --probe      # 探总数
  python ln_sword.py              # 正式抓取（断点续抓，量控 MAX_REC）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random, string, argparse, warnings
from datetime import date
warnings.filterwarnings("ignore")
import requests
import ddddocr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CODES_FILE = os.path.join(ROOT, "tmp", "ln", "ln_swjgdm_all.json")
PROG = os.path.join(ROOT, "progress", "ln_sword.jsonl")
BASE = "https://etax.liaoning.chinatax.gov.cn:8090"
CTRL = "XzzfgsptXzcfCtrl_getSwxzybcxcfjg"
INIT_URL = BASE + "/sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg&sxq=liaoningsheng&swjgDm=12100000000"
MAX_REC = 5000          # 量控
ROWS = 200              # 每页条数（实测 200 有效）
DELAY = 1.8             # 页间延时（秒）
CAP_RETRY = 12          # 每次请求验证码重试上限

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

S = requests.Session()
S.verify = False
S.headers.update({"User-Agent": UA})
OCR = ddddocr.DdddOcr(show_ad=False)


def init_session():
    r = S.get(INIT_URL, timeout=30)
    return r.status_code == 200


def fresh_captcha():
    t = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    rc = S.get(BASE + f"/download.sword?ctrl=CheckcodeUtil_getCheckcode&t={t}&id=ck1",
               timeout=30)
    if rc.status_code != 200 or len(rc.content) < 200:
        return ""
    return OCR.classification(rc.content)


def build_postdata(swjg, page=None, rows=ROWS, yxqq="", yxqz=""):
    data = [{"name": "ajmc", "value": "", "sword": "attr"},
            {"name": "nsrsbh", "value": "", "sword": "attr"},
            {"name": "nsrmc", "value": "", "sword": "attr"},
            {"name": "cfjg", "value": "", "sword": "attr"},
            {"name": "yxqq", "value": yxqq, "sword": "attr"},
            {"name": "yxqz", "value": yxqz, "sword": "attr"},
            {"name": "swjgDm", "value": swjg, "sword": "attr"},
            {"name": "rows", "value": str(rows), "sword": "attr"}]
    if page:
        data.append({"name": "pageNum", "value": str(page), "sword": "attr"})
    data.append({"name": "ckcodeId", "value": "ck1", "sword": "attr"})
    return {"tid": "", "ctrl": CTRL, "data": data, "bindParam": True}


def post_query(biz):
    postdata = __import__("urllib.parse", fromlist=["quote"]).quote(
        json.dumps(biz, ensure_ascii=False)) + "+"
    r = S.post(BASE + "/ajax.sword?ctrl=" + CTRL,
               data="postData=" + postdata,
               headers={"Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                        "Origin": BASE, "Referer": INIT_URL},
               timeout=90)
    return r


def query_page(swjg, page=None, rows=ROWS, yxqq="", yxqz=""):
    """带验证码重试的一页查询；返回 (grid_dict|None, last_resp_text)"""
    last = ""
    for att in range(CAP_RETRY):
        code = fresh_captcha()
        if not code:
            time.sleep(1.0)
            continue
        biz = build_postdata(swjg, page, rows, yxqq, yxqz)
        biz["data"].append({"name": "ckcode", "value": code, "sword": "attr"})
        r = post_query(biz)
        last = r.text
        if r.status_code != 200:
            time.sleep(2.0)
            continue
        if "验证码不正确" in r.text or "浏览器超时" in r.text:
            time.sleep(0.5)
            continue
        if "exception" in r.text[:200]:
            return None, last
        try:
            d = json.loads(r.text)
        except Exception:
            time.sleep(1.0)
            continue
        for item in d.get("data", []):
            if item.get("sword") == "SwordGrid":
                return item, last
        # flag=1 且非验证码问题（如"未查询到结果"）
        return None, last
    return None, last


def load_done():
    done = set()
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("ok"):
                        done.add(rec["key"])
                except json.JSONDecodeError:
                    pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--max", type=int, default=MAX_REC)
    args = ap.parse_args()

    codes = json.load(open(CODES_FILE, encoding="utf-8"))["codes"]
    allstr = ",".join(codes.keys())
    print(f"[ln_sword] codes={len(codes)} session init...")
    if not init_session():
        print("init failed"); sys.exit(1)

    g, raw = query_page(allstr)
    if not g:
        print("probe failed:", raw[:200]); sys.exit(1)
    total = g.get("totalRows", 0)
    npages = (total + ROWS - 1) // ROWS
    print(f"[probe] totalRows={total} pageNum={g.get('pageNum')} rows={len(g['trs'])}")
    if args.probe:
        return

    done = load_done()
    print(f"[resume] existing={len(done)}")
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    fout = open(PROG, "a", encoding="utf-8")

    nnew = 0
    for pg in range(1, npages + 1):
        if len(done) >= args.max:
            print(f"[cap] reached {args.max} records, stop"); break
        if pg == 1 and g:
            grid = g
        else:
            time.sleep(DELAY + random.uniform(0, 0.8))
            grid, raw = query_page(allstr, page=pg)
            if grid is None:
                print(f"[p{pg}] no grid: {raw[:120]}")
                # 未查询到结果等终态——重试一次后跳页
                time.sleep(DELAY)
                grid, raw = query_page(allstr, page=pg)
                if grid is None:
                    print(f"[p{pg}] skip"); continue
        trs = grid.get("trs", [])
        page_new = 0
        for tr in trs:
            tds = {k: v.get("value", "") for k, v in tr["tds"].items()}
            key = tds.get("uuid", "") or tds.get("swxzcfjdsuuid", "")
            if not key or key in done:
                continue
            fout.write(json.dumps({"ok": 1, "key": key, "rec": tds},
                                  ensure_ascii=False) + "\n")
            done.add(key)
            page_new += 1
            nnew += 1
            if len(done) >= args.max:
                break
        fout.flush()
        print(f"[p{pg}/{npages}] rows={len(trs)} new={page_new} total={len(done)} "
              f"(server total={total})", flush=True)
    fout.close()
    print(f"[done] new={nnew} total={len(done)}")


if __name__ == "__main__":
    main()
