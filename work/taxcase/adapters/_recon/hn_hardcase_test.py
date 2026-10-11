# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""湖南 hardcase 失信栏接口测试（带超时与 dialog 处理）"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import sys, os, re, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from pw_common import pw_open  # 审查修复：侦察脚本归档后从 adapters 取公共模块
from playwright.sync_api import sync_playwright

JS = r"""async (args) => {
  const token = $('meta[name="_csrf"]').attr('content');
  const data = {type:args.type, type_value:'', case_type:args.case_type, page:args.page,
                limit:args.limit, is_search:args.is_search, _csrf:token,
                taxpayerName:args.name, taxpayerNumber:'', organizationalCode:'', place:'',
                legalName:'', legalIdCard:'', financeName:'', financeIdCard:'',
                personName:'', personIdCard:''};
  return await Promise.race([
    new Promise(resolve => {
      $.ajax({ type:'POST', url:'/hardcasegetdatanew', data:data, dataType:'json', timeout:12000,
        success: d => resolve({ok:true, code:d.code,
              total: d.hardCasePage? d.hardCasePage.totalElements:null,
              n: d.hardCasePage&&d.hardCasePage.content? d.hardCasePage.content.length:0,
              first: d.hardCasePage&&d.hardCasePage.content&&d.hardCasePage.content[0]?
                     JSON.stringify(d.hardCasePage.content[0]).slice(0,1000):null,
              msg: d.msg||''}),
        error: (x,s,e) => resolve({ok:false, st:x.status, s:s, e:String(e)}) });
    }),
    new Promise(r2 => setTimeout(() => r2({ok:false, timeout:true}), 15000))
  ]);
}"""


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled", "--window-position=2400,100"])
        ctx = b.new_context(locale="zh-CN")
        pg = ctx.new_page()
        pg.on("dialog", lambda d: d.dismiss())
        events = []
        pg.on("response", lambda r: events.append("RESP " + str(r.status) + " " + r.url[:90])
              if "hardcaseget" in r.url else None)
        pg.on("requestfailed", lambda rq: events.append("FAIL " + rq.url[:90] + " " + str(rq.failure)))
        pw_open(pg, "https://hunan.chinatax.gov.cn/hardcase/20190408002097")
        time.sleep(2)
        for args in [
            {"type": 0, "type_value": "", "case_type": 1, "page": 1, "limit": 10,
             "is_search": 0, "name": ""},
            {"type": 0, "type_value": "", "case_type": 1, "page": 1, "limit": 10,
             "is_search": 1, "name": "公司"},
            {"type": 1, "type_value": "", "case_type": 1, "page": 1, "limit": 10,
             "is_search": 0, "name": ""},
        ]:
            events.clear()
            r = pg.evaluate(JS, args)
            print("ARGS", json.dumps(args, ensure_ascii=False)[:80])
            print("  ->", json.dumps(r, ensure_ascii=False)[:1000])
            print("  EV:", events[:6])
            time.sleep(2)
        b.close()


if __name__ == "__main__":
    main()
