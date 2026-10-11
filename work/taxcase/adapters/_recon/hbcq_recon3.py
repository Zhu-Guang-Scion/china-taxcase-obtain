# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""重庆 zdwfajcx 失信查询页活体侦察：dump goPage 源码、点查询、抓 XHR。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.path.join(ROOT, "tmp", "hb_cq")

URL = "http://chongqing.chinatax.gov.cn/xxgkxt/pages/qywh/zdwfajcx.html"


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def main():
    from playwright.sync_api import sync_playwright
    xhr = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = browser.new_context(locale="zh-CN")
        page = ctx.new_page()
        page.on("request", lambda r: xhr.append(
            {"m": r.method, "u": r.url[:250], "pt": (r.post_data or "")[:400]})
            if r.resource_type in ("xhr", "fetch") else None)
        page.on("response", lambda rp: xhr.append(
            {"m": "RESP", "u": rp.url[:250], "st": rp.status,
             "ct": (rp.headers or {}).get("content-type", "")[:40]})
            if rp.request.resource_type in ("xhr", "fetch") else None)

        print("goto ...", flush=True)
        page.goto(URL, timeout=70000, wait_until="domcontentloaded")
        for _ in range(45):
            time.sleep(1)
            if body_text_len(page.content()) > 300:
                break
        time.sleep(3)

        # 1) goPage 源码与相关全局
        info = page.evaluate("""() => {
          const out = {fns:{}, ajaxUrls:[], selFilter:[]};
          for (const n of ['goPage','submitForm','queryData','loadData','search','doQuery']) {
            try { if (typeof window[n] === 'function') out.fns[n] = window[n].toString().slice(0,1500); } catch(e){}
          }
          // 找 jQuery ajax 预设 (ajaxSetup) 与 document 上明文 url
          const html = document.documentElement.outerHTML;
          for (const m of html.matchAll(/['"](\\/[^'"]*(?:do|action|query|spring|servlet)[^'"]*)['"]/g)) {
            out.ajaxUrls.push(m[1]);
          }
          // 查询区 select options 前5
          document.querySelectorAll('select').forEach((s,i)=>{
            const opts=[...s.options].slice(0,4).map(o=>o.value);
            out.selFilter.push({i, name:s.name, id:s.id, opts});
          });
          return out;
        }""")
        print(json.dumps(info, ensure_ascii=False, indent=1)[:4000], flush=True)

        # 2) 点击查询类按钮（表单区域的，非站搜）
        clicked = page.evaluate("""() => {
          const cands = [...document.querySelectorAll('a,button,input[type=button],input[type=submit],span')].filter(e=>{
            const t=(e.textContent||e.value||'').trim();
            return t==='查询' || t==='搜 索' || t==='搜索';
          });
          const seen=new Set(); const hits=[];
          for (const e of cands) {
            const key=(e.className||'')+'|'+(e.id||'');
            if (seen.has(key)) continue; seen.add(key);
            hits.push({tag:e.tagName, cls:e.className, id:e.id, txt:(e.textContent||'').trim().slice(0,10)});
          }
          return hits;
        }""")
        print("query buttons:", json.dumps(clicked, ensure_ascii=False), flush=True)
        for btn in clicked[:3]:
            try:
                n0 = len(xhr)
                page.evaluate("""(b) => {
                  const els=[...document.querySelectorAll(b.tag)];
                  const e=els.find(x=>((x.textContent||x.value||'').trim()===(b.txt))&&(x.className===b.cls));
                  if (e) e.click();
                }""", btn)
                time.sleep(6)
                print(f"clicked {btn}; new xhr={len(xhr)-n0}", flush=True)
            except Exception as e:
                print("click exc:", str(e)[:80], flush=True)

        time.sleep(2)
        # 3) 渲染后表格行
        rows = page.evaluate("""() => {
          const trs=[...document.querySelectorAll('tr')];
          return trs.map(tr=>[...tr.children].map(td=>(td.textContent||'').trim().slice(0,40)))
                    .filter(r=>r.length>3 && r.some(c=>c));
        }""")
        print("rendered rows:", len(rows), flush=True)
        for r in rows[:6]:
            print("  ", " | ".join(r)[:150], flush=True)

        json.dump(xhr, open(os.path.join(TMP, "cq_zdwf_xhr.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        open(os.path.join(TMP, "cq_zdwf_rendered.html"), "w", encoding="utf-8").write(page.content())
        print("saved", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
