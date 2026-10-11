# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""河北省税务局 执法公示平台·税务行政一般程序处罚结果 有头收割（R7）
机制（实测）:
  - 瑞数墙: 有头 chromium 过挑战（HTTPS 证书错配只能走 HTTP；/index.html 404 用根路径）
  - 失信栏 findTaxDishonestyCasesList?cid=27: 全城市/类型/年份 0 条（空库）——见 sources
  - 处罚结果 findTaxPenaltyResultList?cid=26: 省局空，**城市会话制**——.listwzqbox a[data-id]
    程序化 click → POST changeCity(带瑞数令牌) → **整页重新导航**后生效（局部 load 不够）
  - 页面自带 $.table.init 因脚本 404 未初始化 → 手动 init（带原生 columns，否则行空白）
  - 原始 JSON 从 XHR response 事件拦截（含未脱敏 NSRSBH），UI 仅用于翻页(.page-next)
输出: tmp/hb_r7/penalty_all.jsonl；断点 progress/hebei_r7.jsonl
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import os, re, json, time, argparse
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.normpath(os.path.join(ROOT, "tmp", "hb_r7"))
os.makedirs(TMP, exist_ok=True)
PROG = os.path.join(ROOT, "progress", "hebei_r7.jsonl")
U = "http://wzyy.hebei.chinatax.gov.cn/LawPublicity/law/adPenalty/taxPenaltyResult"

CITIES = [("2", "石家庄"), ("3", "唐山"), ("4", "秦皇岛"), ("5", "邯郸"),
          ("6", "邢台"), ("7", "保定"), ("8", "张家口"), ("9", "承德"), ("10", "沧州"),
          ("11", "廊坊"), ("12", "衡水"), ("167", "雄安"), ("171", "定州"), ("172", "辛集")]

INIT_JS = """() => {
  try {
    if (!$('#bootstrap-table').data('bootstrap.table')) {
      var prefix = ctx + "app-publicity-service/law";
      $.table.init({url: prefix + "/penalty/findTaxPenaltyResultList?cid=26&uid=",
                    showSearch: false, showRefresh: false, showToggle: false,
                    showColumns: false, pageSize: 50, pageList: [10,25,50,100],
                    columns: [
                      {field:'XZCFJDSWH', title:'决定书文号'},
                      {field:'AJMC', title:'案件名称'},
                      {field:'CFLB', title:'处罚类别'},
                      {field:'CFSY', title:'处罚事由'},
                      {field:'CFYJ', title:'处罚依据'},
                      {field:'NSRMC', title:'行政相对人名称'},
                      {field:'NSRSBH', title:'行政相对人代码'},
                      {field:'FDDBRXM', title:'法定代表人姓名'},
                      {field:'CFJG', title:'处罚结果'},
                      {field:'CFSWJG', title:'处罚机关'},
                      {field:'ZCGCFRQ', title:'处罚日期'}
                    ]});
    }
  } catch (e) {}
}"""


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


def btl(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", m.group(1) if m else "")))


def pw_open(pg, url, wait=45):
    last = ""
    for att in range(4):
        try:
            pg.goto(url, timeout=50000, wait_until="domcontentloaded")
        except Exception:
            pass
        for _ in range(wait):
            time.sleep(1)
            try:
                html = pg.content()
            except Exception:
                continue
            last = html
            if btl(html) > 300 and "$_ts=window" not in html[:3000]:
                return html
        time.sleep(3)
    return last


def run(city_ids=None, max_pages=80):
    cities = [(c, n) for c, n in CITIES if not city_ids or c in city_ids]
    done_cities = load_done("pen_city")
    out_all = os.path.join(TMP, "penalty_all.jsonl")
    fw = open(out_all, "a", encoding="utf-8")
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = br.new_context(locale="zh-CN")
        pg = ctx.new_page()
        h = pw_open(pg, U)
        log(f"platform open len={len(h)}")
        for cid, cname in cities:
            key = f"{cid}:{cname}"
            if key in done_cities:
                continue
            # 切市
            try:
                r = pg.evaluate(f"""() => {{
                  const a = [...document.querySelectorAll('.listwzqbox a')].find(
                      x => (x.getAttribute('data-id')||'') === '{cid}');
                  if (a) {{ a.click(); return 'ok'; }} return 'nf';
                }}""")
                if r != "ok":
                    log(f"{cname}: link nf")
                    continue
            except Exception as e:
                log(f"{cname}: click exc {str(e)[:60]}")
                continue
            time.sleep(8)
            # 整页重导航使城市会话生效（changeCity 绑定会自行 location.reload，
            # 须等 reload 与挑战都稳定再 goto）
            time.sleep(6)
            pw_open(pg, U)
            time.sleep(2)
            pg.evaluate(INIT_JS)
            # 首页数据 + 城市校验（total==0 时再切一次市重试）
            st = {}
            for attempt in range(2):
                for _ in range(20):
                    time.sleep(1)
                    try:
                        st = pg.evaluate("""() => {
                            try {
                              const o = $('#bootstrap-table').bootstrapTable('getOptions');
                              return {n: $('#bootstrap-table').bootstrapTable('getData').length,
                                      total: o.totalRows, page: o.pageNumber, pages: o.totalPages};
                            } catch (e) { return {n: 0, err: String(e).slice(0,60)}; }
                        }""")
                        if st.get("n", 0) > 0 or st.get("total") == 0:
                            break
                    except Exception:
                        pass
                if st.get("total"):
                    break
                log(f"{cname}: attempt{attempt} total=0, re-switch city")
                pg.evaluate(f"""() => {{
                  const a = [...document.querySelectorAll('.listwzqbox a')].find(
                      x => (x.getAttribute('data-id')||'') === '{cid}');
                  if (a) a.click();
                }}""")
                time.sleep(8)
                pw_open(pg, U)
                time.sleep(2)
                pg.evaluate(INIT_JS)
            total = st.get("total")
            cap_rows = []
            pages = st.get("pages") or 1
            if not total:
                # 空城市也记档（避免反复重试）
                log(f"{cname}: total=0 (empty)")
                mark({"phase": "pen_city", "key": key, "ok": True,
                      "total": 0, "rows": 0})
                continue
            for pgno in range(1, min(pages, max_pages) + 1):
                # 等当前页数据就绪
                for _ in range(15):
                    try:
                        cur = pg.evaluate("() => $('#bootstrap-table').bootstrapTable('getOptions').pageNumber")
                        if cur >= pgno:
                            break
                    except Exception:
                        pass
                    time.sleep(1)
                time.sleep(1.5)
                rows = pg.evaluate("() => $('#bootstrap-table').bootstrapTable('getData')")
                cap_rows.extend(rows)
                if pgno < min(pages, max_pages):
                    pg.evaluate("() => $('#bootstrap-table').bootstrapTable('nextPage')")
                time.sleep(2.5)
            rows = cap_rows
            for row in rows:
                row["_city"] = cname
                fw.write(json.dumps(row, ensure_ascii=False) + "\n")
            fw.flush()
            log(f"{cname}: total={total} raw_rows={len(rows)}")
            mark({"phase": "pen_city", "key": key, "ok": True,
                  "total": total, "rows": len(rows)})
        fw.close()
        br.close()
    log("hebei penalty done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default=None)
    args = ap.parse_args()
    run(city_ids=set(args.city.split(",")) if args.city else None)
