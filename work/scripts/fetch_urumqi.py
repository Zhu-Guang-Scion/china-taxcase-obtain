
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gov_download as gd


def main():
    # 审查修复：加 main 守卫 —— 原先 import 即启动浏览器抓取
    item2 = None
    for line in open('work/lists/gov_地方政府规章.jsonl', encoding='utf-8'):
        it = json.loads(line)
        if 'urumqi' in it['url']:
            item2 = it; break

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, channel='msedge')
        ctx = b.new_context(ignore_https_errors=True)
        pg = ctx.new_page()
        try:
            pg.goto(item2['url'].replace('http://', 'https://'), timeout=60000, wait_until='domcontentloaded')
            pg.wait_for_timeout(3000)
            html = pg.content()
        except Exception as e:
            print('goto err:', type(e).__name__, str(e)[:120])
            html = ''
        b.close()

    body = gd.extract_body(html) or gd.extract_body_generic(html)
    blocks = gd.body_to_blocks(body) if body else []
    cjk = sum(1 for _, t in blocks for ch in t if '\u4e00' <= ch <= '\u9fff')
    print('blocks:', len(blocks), 'cjk:', cjk)
    if cjk > 300:
        out_dir = 'work/downloads/gov/地方政府规章'
        base = gd.sanitize("%s_%s_%s" % (item2['cat'], item2['title'], item2.get('date', '')))
        gd.make_docx(item2['title'], blocks, item2, os.path.join(out_dir, base + '.docx'))
        sz = os.path.getsize(os.path.join(out_dir, base + '.docx'))
        with open(os.path.join(out_dir, base + '.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        print('docx:', sz)
        with open('work/lists/gov_dl_progress_地方政府规章.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'url': item2['url'], 'ok': True, 'file': base + '.docx', 'bytes': sz, 'source': 'playwright_edge'}, ensure_ascii=False) + '\n')
        print('OK 修复完成')



if __name__ == "__main__":
    main()
