# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""山西省税务局 行政执法公示平台·税务行政一般程序处罚结果 收割（R7，直连 curl_cffi）
发现链: 失信栏 topic zdsswf 的 extQuery 空（浙江剑同款 0 数据）→ 平台行政处罚栏
  /xzzfgsptWeb/web/list/11400-2661 省级"暂未产生执法信息" → 碎片
  /xzzfgsptWeb/xzcfweb/swxzybcfjg/<orgid>-2662 内注释真 API:
  POST /xzzfgsptWeb/commonRemote/extQuery?sqlid=swxzybcfjg&limit=100&lmdm=2662
       &orgid=<市orgid>&swjgdm=<orgid*1000000>&db=xzzf&page=N  body=start=(N-1)*100
  市级 orgid 11401-11406 有数据（太原471/大同397/阳泉161/长治291/晋城392/朔州211，
  晋中/运城/忻州/临汾/吕梁 0）
字段: JDSWH 决定书文号 / AJMC 案件名称 / CFLB 处罚类别 / CFSY 处罚事由 / CFYJ 处罚依据 /
  XZXDRMC 相对人名称 / XZXDRDM 代码 / FDDBRXM 法人 / CFJG 处罚结果 / CFSWJG 处罚机关 /
  CFRQ 处罚日期
输出: tmp/sx_r7/xzcf_records.jsonl；断点 progress/shanxi_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, random, hashlib, argparse
from curl_cffi import requests as cr

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.normpath(os.path.join(ROOT, "tmp", "sx_r7"))
os.makedirs(TMP, exist_ok=True)
PROG = os.path.join(ROOT, "progress", "shanxi_r7.jsonl")
B = "https://shanxi.chinatax.gov.cn"

CITY_ORGIDS = [11401, 11402, 11403, 11404, 11405, 11406, 11407, 11408, 11409, 11410, 11411]
CITY_NAMES = {11401: "太原市", 11402: "大同市", 11403: "阳泉市", 11404: "长治市",
              11405: "晋城市", 11406: "朔州市", 11407: "晋中市", 11408: "运城市",
              11409: "忻州市", 11410: "临汾市", 11411: "吕梁市"}


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


def run(per=100, max_pages=40):
    sess = cr.Session(impersonate="chrome124", timeout=300)
    sess.get(B + "/xzzfgsptWeb/web/list/11400-2661")
    H = {"Referer": B + "/xzzfgsptWeb/web/list/11400-2661",
         "X-Requested-With": "XMLHttpRequest"}
    out_path = os.path.join(TMP, "xzcf_records.jsonl")
    done_pages = load_done("xzcf_page")
    fw = open(out_path, "a", encoding="utf-8")
    grand = 0
    for orgid in CITY_ORGIDS:
        city = CITY_NAMES[orgid]
        swjgdm = f"{orgid}0000000"
        pg = 1
        city_n = 0
        while pg <= max_pages:
            pkey = f"{orgid}:{pg}"
            if pkey in done_pages:
                pg += 1
                continue
            u = (f"{B}/xzzfgsptWeb/commonRemote/extQuery?sqlid=swxzybcfjg"
                 f"&limit={per}&lmdm=2662&orgid={orgid}&swjgdm={swjgdm}&db=xzzf&page={pg}")
            ok = False
            for t in range(3):
                try:
                    r = sess.post(u, headers=H, data=f"start={(pg-1)*per}")
                    d = r.json()
                    ok = True
                    break
                except Exception as e:
                    log(f"  exc {type(e).__name__} {str(e)[:60]} retry {t}")
                    time.sleep(4 + 3 * t)
            if not ok:
                log(f"{city} p{pg} unreachable, stop city")
                break
            msg = d.get("message")
            if not isinstance(msg, dict):
                log(f"{city} p{pg} bad msg: {str(msg)[:80]}")
                break
            lst = msg.get("list") or []
            total = msg.get("totalRow")
            for rec in lst:
                rec["_orgid"] = orgid
                rec["_city"] = city
                fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
            city_n += len(lst)
            grand += len(lst)
            mark({"phase": "xzcf_page", "key": pkey, "ok": True, "n": len(lst),
                  "city": city, "total": total})
            log(f"{city} p{pg}: +{len(lst)} city_cum={city_n} total={total}")
            if not lst or city_n >= int(total or 0):
                break
            time.sleep(random.uniform(1.5, 2.5))
            pg += 1
    fw.close()
    log(f"DONE grand={grand} -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=40)
    args = ap.parse_args()
    run(max_pages=args.max_pages)
