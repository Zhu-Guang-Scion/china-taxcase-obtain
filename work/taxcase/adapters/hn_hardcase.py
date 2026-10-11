# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""湖南 重大税收违法失信主体公布栏 收割器
接口: POST /hardcasegetdatanew （页面 jQuery $.ajax，_csrf 从 meta 取）
  参数: type=0 type_value='' case_type=1 page=N limit=100 is_search=0 + 全空查询字段
  响应: {code:1, hardCasePage:{totalElements, content:[{id, content(全文), taxpayerName,
        taxpayerNumber, place, hardCaseType.typeName, showTime(ms), siteName, caseType...}]}}
产出: tmp/hn/hardcase_records.jsonl（断点 progress/qd_hn_r6.jsonl）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json, argparse
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pw_common import pw_open  # 审查修复：改自侦察脚本抽出的公共模块
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "tmp", "hn")
os.makedirs(OUT, exist_ok=True)
RECS = os.path.join(OUT, "hardcase_records.jsonl")
PROG = os.path.join(ROOT, "progress", "qd_hn_r6.jsonl")

JS = r"""async (args) => {
  const token = $('meta[name="_csrf"]').attr('content');
  const data = {type:0, type_value:'', case_type:args.case_type, page:args.page,
                limit:args.limit, is_search:0, _csrf:token,
                taxpayerName:'', taxpayerNumber:'', organizationalCode:'', place:'',
                legalName:'', legalIdCard:'', financeName:'', financeIdCard:'',
                personName:'', personIdCard:''};
  return await Promise.race([
    new Promise(resolve => {
      $.ajax({ type:'POST', url:'/hardcasegetdatanew', data:data, dataType:'json', timeout:15000,
        success: d => resolve({ok:d.code==1, total: d.hardCasePage? d.hardCasePage.totalElements:0,
              rows: d.hardCasePage&&d.hardCasePage.content? d.hardCasePage.content:[]}),
        error: (x,s,e) => resolve({ok:false, err:(x.status+' '+s)}) });
    }),
    new Promise(r2 => setTimeout(() => r2({ok:false, timeout:true}), 20000))
  ]);
}"""


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--case-type", type=int, default=1)
    args = ap.parse_args()
    done_ids = set()
    if os.path.exists(RECS):
        for ln in open(RECS, encoding="utf-8"):
            try:
                done_ids.add(json.loads(ln)["id"])
            except Exception:
                pass
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.dismiss())
        pw_open(pg, "https://hunan.chinatax.gov.cn/hardcase/20190408002097")
        time.sleep(2)
        # 探 total + limit 上限
        r = pg.evaluate(JS, {"page": 1, "limit": args.limit, "case_type": args.case_type})
        if not r.get("ok"):
            log(f"probe fail {r}"); sys.exit(1)
        total = r["total"]
        log(f"total={total} first page rows={len(r['rows'])}")
        fw = open(RECS, "a", encoding="utf-8")
        got = 0
        npages = (total + args.limit - 1) // args.limit
        for pn in range(1, npages + 1):
            if pn == 1:
                rows = r["rows"]
            else:
                for att in range(3):
                    r2 = pg.evaluate(JS, {"page": pn, "limit": args.limit,
                                          "case_type": args.case_type})
                    if r2.get("ok"):
                        rows = r2["rows"]
                        break
                    log(f"p{pn} retry {r2}")
                    time.sleep(3)
                    pw_open(pg, "https://hunan.chinatax.gov.cn/hardcase/20190408002097")
                else:
                    rows = []
            new = 0
            for rec in rows:
                if rec.get("id") in done_ids:
                    continue
                fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                done_ids.add(rec["id"])
                new += 1
                got += 1
            fw.flush()
            log(f"p{pn}/{npages}: rows={len(rows)} new={new} cum={len(done_ids)}")
            mark({"phase": "hn_hardcase_page", "page": pn, "rows": len(rows),
                  "new": new, "ts": time.strftime("%F %T")})
            if not rows:
                break
            time.sleep(1.6 + pn % 3 * 0.4)
        fw.close()
        b.close()
    log(f"done, unique={len(done_ids)}")


if __name__ == "__main__":
    main()
