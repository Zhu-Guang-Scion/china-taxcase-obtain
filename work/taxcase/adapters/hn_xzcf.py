# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""湖南 税务行政一般程序处罚结果 收割器（验证码 + in-page XHR）
页面: /xzzfpenalty/20200325400599
接口: POST /xzzfpenaltygetdata  {page,limit,site_id,ajmc,mc,dm,cfjg,logincode,_csrf}
验证码: GET /kaptcha/getlogincode?rand （JPEG，XHR in-page 取 base64 → ddddocr）
响应: {code:1, count:N, data:[{jdswh,ajmc,cflb,cfsy,cfyj,xzxdrmc,xzxdrdm,fddbrxm,cfjg,cfjiguan,cfsxq}]}
产出: tmp/hn/xzcf_records.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json, random, string, base64, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pw_common import pw_open  # 审查修复：改自侦察脚本抽出的公共模块
from playwright.sync_api import sync_playwright
import ddddocr

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "tmp", "hn")
os.makedirs(OUT, exist_ok=True)
RECS = os.path.join(OUT, "xzcf_records.jsonl")
PROG = os.path.join(ROOT, "progress", "qd_hn_r6.jsonl")
OCR = ddddocr.DdddOcr(show_ad=False)

JS_CAPTCHA = r"""async () => {
  return await Promise.race([
    new Promise(resolve => {
      $.ajax({ type:'GET', url:'/kaptcha/getlogincode?r=' + Math.random(),
        timeout: 10000, xhrFields:{responseType:'arraybuffer'},
        success: (d, s, x) => {
          const buf = new Uint8Array(d); let bin='';
          for (let i=0;i<buf.length;i++) bin += String.fromCharCode(buf[i]);
          resolve({ok:true, b64: btoa(bin), ct: (x.getResponseHeader('content-type')||'')});
        },
        error: (x,s,e) => resolve({ok:false, err: x.status+' '+s}) });
    }),
    new Promise(r2 => setTimeout(()=>r2({ok:false, timeout:true}), 12000)) ]);
}"""

JS_QUERY = r"""async (args) => {
  const token = $('meta[name="_csrf"]').attr('content');
  const data = {page:args.page, limit:args.limit, site_id:args.site_id||'',
                ajmc:'', mc:'', dm:'', cfjg:'', logincode:args.code, _csrf:token};
  return await Promise.race([
    new Promise(resolve => {
      $.ajax({ type:'POST', url:'/xzzfpenaltygetdata', data:data, dataType:'json', timeout:25000,
        success: d => resolve({ok:d.code!=0, code:d.code, count:d.count||0, rows:d.data||[]}),
        error: (x,s,e) => resolve({ok:false, err:x.status+' '+s}) });
    }),
    new Promise(r2 => setTimeout(()=>r2({ok:false, timeout:true}), 30000)) ]);
}"""


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def mark(d):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")


class CapSolver:
    """验证码求解器：页面 img 原生加载（带会话）→ 元素截图 → ddddocr"""

    def __init__(self, pg):
        self.pg = pg

    def solve(self):
        try:
            el = self.pg.query_selector('#codeImgGm')
            if el is None:
                return ""
            self.pg.evaluate(
                "() => { const e=document.getElementById('codeImgGm'); if(e){e.src='/kaptcha/getlogincode?r='+Math.random();} }")
            time.sleep(2.2)
            shot = el.screenshot()
            code = OCR.classification(shot)
            code = re.sub(r"\s", "", code)
            return code if len(code) >= 3 else ""
        except Exception:
            return ""


def query_page(pg, solver, page, limit=10, tries=30, st=None):
    net_fails = 0
    for att in range(tries):
        code = solver.solve()
        if not code:
            time.sleep(0.8)
            continue
        r = pg.evaluate(JS_QUERY, {"page": page, "limit": limit, "code": code})
        if r.get("ok"):
            return r
        if r.get("err") and "500" in str(r.get("err")):
            # 500 = 后端坏节点随机出现，立即换码重试（勿重开页面）
            time.sleep(1.2)
            continue
        if r.get("timeout") or r.get("err"):
            net_fails += 1
            log(f"  q err {r}, net_fails={net_fails}")
            if st is not None and net_fails >= 3:
                # 整 context 重置（CDN 按会话封 XHR）
                try:
                    st["ctx"].close()
                except Exception:
                    pass
                st["ctx"] = st["b"].new_context(locale="zh-CN")
                st["pg"] = st["ctx"].new_page()
                st["pg"].on("dialog", lambda d: d.dismiss())
                log("  [reset] new CONTEXT")
                pw_open(st["pg"], "https://hunan.chinatax.gov.cn/xzzfpenalty/20200325400599")
                time.sleep(2)
                st["solver"] = CapSolver(st["pg"])
                pg, solver = st["pg"], st["solver"]
                net_fails = 0
                continue
            time.sleep(6 + att * 2)
            pw_open(pg, "https://hunan.chinatax.gov.cn/xzzfpenalty/20200325400599")
            time.sleep(2)
            continue
        # code==0 验证码错误 → 换码重试
        time.sleep(0.4)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100)
    args = ap.parse_args()
    done = set()
    last_page = 0
    if os.path.exists(RECS):
        for ln in open(RECS, encoding="utf-8"):
            try:
                d = json.loads(ln)
                done.add(str(d.get("jdswh", "")) + "|" + str(d.get("cfsxq") or ""))
            except Exception:
                pass
    if os.path.exists(PROG):
        for ln in open(PROG, encoding="utf-8"):
            try:
                d = json.loads(ln)
                if d.get("phase") == "hn_xzcf_page":
                    last_page = max(last_page, d.get("page", 0))
            except Exception:
                pass
    log(f"[resume] done={len(done)} last_page={last_page}")
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.dismiss())
        st = {"b": b, "ctx": ctx, "pg": pg, "solver": None}
        pw_open(pg, "https://hunan.chinatax.gov.cn/xzzfpenalty/20200325400599")
        time.sleep(2)
        solver = CapSolver(pg)
        st["solver"] = solver
        # 预热等待（若此前被限流）
        warm = 75 if last_page else 0
        if warm:
            log(f"warm-up {warm}s (rate-limit cooldown)...")
            time.sleep(warm)
        r = None
        if last_page:
            # 断点续跑：直接查断点页
            rp = query_page(pg, solver, last_page, 100, tries=10)
            if rp and rp.get("ok"):
                r = rp; total = rp["count"]
                log(f"resume ok: count={total}")
        if r is None:
            for lim in (100, 50, 20, 10):
                rp = query_page(st["pg"], st["solver"], 1, lim, tries=8, st=st)
                if rp and rp.get("ok"):
                    args.limit = lim
                    r = rp
                    break
        if not r:
            log("probe failed"); sys.exit(1)
        total = r["count"] if r.get("count") else 2681
        log(f"probe ok: count={total} rows={len(r['rows'])}")
        if r["rows"]:
            log("sample: " + json.dumps(r["rows"][0], ensure_ascii=False)[:300])
        fw = open(RECS, "a", encoding="utf-8")
        got = 0
        npages = (total + args.limit - 1) // args.limit
        start = max(1, last_page) if last_page else 1
        log(f"resume from page {start} (done={len(done)})")
        first_rows = r["rows"]
        for pn in range(start, npages + 1):
            if pn == start:
                rows = first_rows
            else:
                rp = None
                for lim in (100, 50, 25, 10, 5):
                    rp = query_page(st["pg"], st["solver"], pn, lim, tries=8, st=st)
                    if rp is not None and rp.get("rows"):
                        if lim != 100:
                            log(f"p{pn}: fallback limit={lim} ok")
                        break
                    rp = None
                    time.sleep(3)
                if rp is None:
                    log(f"p{pn} FAIL after retries, stop")
                    break
                rows = rp["rows"]
            new = 0
            for rec in rows:
                k = str(rec.get("jdswh", "")) + "|" + str(rec.get("cfsxq") or "")
                if k in done or not k.strip("|"):
                    continue
                fw.write(json.dumps(rec, ensure_ascii=False) + "\n")
                done.add(k)
                new += 1
                got += 1
            fw.flush()
            log(f"p{pn}/{npages}: rows={len(rows)} new={new} cum={len(done)}")
            mark({"phase": "hn_xzcf_page", "page": pn, "rows": len(rows), "new": new,
                  "ts": time.strftime("%F %T")})
            time.sleep(3.0 + pn % 3 * 0.8)
        fw.close()
        b.close()
    log(f"done, unique={len(done)}")


if __name__ == "__main__":
    main()
