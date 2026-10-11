# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
江苏税务（大汉 hanweb CMS）adapter
================================
栏目列表结构：
  - 列表页 /col/col{cid}/index.html 内嵌 <script type="text/xml"><datastore>
    <recordset><record><![CDATA[<li><a title=.. href=..>..</a><span>date</span></li>]]></record>
  - 翻页接口（POST）:
    /module/web/jpage/dataproxy.jsp?startrecord={start}&endrecord={end}&perpage=15
    form: col=1&appid=1&webid=18&path=/&columnid={cid}&sourceContentType=1
          &unitid={uid}&webname=..&permissiontype=0
  - unitid 从列表页 nextgroup 链接里提取

用法（驱动脚本 import）：
  from js_hanweb import HanwebCol
  hc = HanwebCol(col_id, date_from='2023-01-01')
  for url,title,date in hc.iter(max_pages=50): ...

详情页用 taxcase_scrape.extract_detail，标题优先用列表页 title 属性
（页面 <title> 带"网站 栏目名"前缀）。
附件：PDF 用 pymupdf 提取文本层（无文本层计为扫描件跳过）；
      docx 用 python-docx；旧 .doc 二进制无法解析时仅保留链接并计数。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import io
import os
import re
import sys
import time
import random

# 可移植化（审查修复）：sys.path 按本文件位置动态定位 work/taxcase，支持 CHINALAW_ROOT 覆盖
_TAXCASE_DIR = os.environ.get(
    "CHINALAW_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
sys.path.insert(0, _TAXCASE_DIR)
import taxcase_scrape as t  # noqa: E402

from curl_cffi import requests as cffi_requests  # noqa: E402

SITE = "https://jiangsu.chinatax.gov.cn"
DATAPROXY = SITE + "/module/web/jpage/dataproxy.jsp"

RECORD_RE = re.compile(
    r'<li><a[^>]*title="([^"]*)"[^>]*href="([^"]+)"[^>]*>.*?<span>([\d-]{8,10})</span>',
    re.S)


def _norm_date(s):
    return s.replace(".", "-").replace("/", "-") if s else ""


def parse_hanweb_records(text):
    """从列表页或 dataproxy 响应中抽取 [(url,title,date)]"""
    items, seen = [], set()
    for m in RECORD_RE.finditer(text):
        title, href, ds = m.group(1).strip(), m.group(2).strip(), _norm_date(m.group(3))
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = SITE + href
        if "jiangsu.chinatax.gov.cn" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        items.append((href.split("#")[0], re.sub(r"\s+", " ", title), ds))
    return items


class HanwebCol:
    def __init__(self, col_id, delay=2.5):
        self.col_id = col_id
        self.delay = delay
        self.unitid = None
        self.total = 0

    def _load_first_page(self):
        url = f"{SITE}/col/col{self.col_id}/index.html"
        r = t.polite_get(url, self.delay, referer=SITE + "/")
        if r is None:
            raise RuntimeError(f"col {self.col_id} first page failed")
        m = re.search(r"columnid=(\d+)&unitid=(\d+)", r.text)
        if m:
            self.unitid = m.group(2)
        mt = re.search(r"totalRecord:(\d+)", r.text)
        if mt:
            self.total = int(mt.group(1))
        return parse_hanweb_records(r.text)

    def _dataproxy(self, page, perpage=15):
        start = (page - 1) * perpage + 1
        end = page * perpage
        u = f"{DATAPROXY}?startrecord={start}&endrecord={end}&perpage={perpage}"
        data = {
            "col": "1", "appid": "1", "webid": "18", "path": "/",
            "columnid": str(self.col_id), "sourceContentType": "1",
            "unitid": self.unitid or "",
            "webname": "国家税务总局江苏省税务局网站", "permissiontype": "0",
        }
        for attempt in range(3):
            wait = self.delay + random.uniform(0, 1.0)
            time.sleep(wait)
            try:
                r = cffi_requests.post(
                    u, data=data, impersonate="chrome124", timeout=40,
                    headers={"Referer": f"{SITE}/col/col{self.col_id}/index.html",
                             "X-Requested-With": "XMLHttpRequest"})
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass
            time.sleep(3 * (attempt + 1))
        return None

    def iter(self, max_pages=50):
        """产出 (url,title,date)。
        注意：专题模板首页可能内嵌 3×15 条（多 tab），与 dataproxy 的 15/页
        错位 —— 因此第 1 页也走 dataproxy，保证与 totalRecord 口径一致。"""
        first = self._load_first_page()  # 仅用于提取 unitid/total
        if self.total and self.total <= 15:
            yield from first
            return
        seen = set()
        for page in range(1, max_pages + 1):
            txt = self._dataproxy(page, 15)
            if txt is None:
                print(f"[col{self.col_id}] dataproxy page {page} failed, stop")
                return
            items = parse_hanweb_records(txt)
            if not items:
                return
            new = 0
            for it in items:
                if it[0] in seen:
                    continue
                seen.add(it[0])
                new += 1
                yield it
            if new == 0:  # 整页重复 → 到尾
                return


# ---------------- 详情 + 附件 ----------------

def clean_title(list_title, detail_title):
    """优先列表页 title；退回详情页 <title> 并去掉站点/栏目前缀。"""
    if list_title and len(list_title) >= 8:
        return list_title
    s = detail_title or ""
    s = re.sub(r"^国家税务总局江苏省税务局网站\s*", "", s)
    s = re.sub(r"^[^：:]{2,12}[　\s]+", "", s, count=1) if s.startswith("国家税务总局江苏省") else s
    return s.strip()


def extract_attachment_text(url, referer):
    """下载附件并提取文本。返回 (text, kind)
    kind: pdf/docx/doc/scanned_img/binary/fail"""
    r = t.polite_get(url, 2.5, referer=referer)
    if r is None or not r.content:
        return "", "fail"
    head = r.content[:8]
    try:
        if head.startswith(b"%PDF"):
            import pymupdf
            with pymupdf.open(stream=r.content, filetype="pdf") as doc:
                parts = [p.get_text() for p in doc]
            txt = "\n".join(parts).strip()
            if len(txt) < 80:  # 无文本层 → 扫描件
                return "", "scanned_img"
            return txt, "pdf"
        if head.startswith(b"PK"):
            import docx as _docx
            d = _docx.Document(io.BytesIO(r.content))
            parts = [p.text for p in d.paragraphs]
            for tb in d.tables:
                for row in tb.rows:
                    parts.append("\t".join(c.text for c in row.cells))
            return "\n".join(parts).strip(), "docx"
        if head.startswith(b"\xd0\xcf\x11\xe0"):
            return _doc_via_word_com(r.content), "doc"
    except Exception:
        return "", "fail"
    return "", "binary"


_word_app = None


def _get_word():
    global _word_app
    if _word_app is None:
        import win32com.client
        _word_app = win32com.client.Dispatch("Word.Application")
        _word_app.Visible = False
        try:
            _word_app.DisplayAlerts = 0
        except Exception:
            pass
    return _word_app


def _doc_via_word_com(content):
    """旧版 .doc 用本机 Word COM 提取（Windows 环境）。失败返回空串。"""
    import tempfile
    import os
    import pythoncom
    pythoncom.CoInitialize()
    path = ""
    try:
        fd, path = tempfile.mkstemp(suffix=".doc")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(content)
        word = _get_word()
        doc = word.Documents.Open(path, ReadOnly=True, ConfirmConversions=False,
                                  AddToRecentFiles=False)
        txt = doc.Content.Text or ""
        doc.Close(False)
        txt = txt.replace("\r", "\n").replace("\x07", "\n").replace("\x0b", "\n")
        txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
        return txt if len(txt) > 80 else ""
    except Exception:
        return ""
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


def quit_word():
    global _word_app
    if _word_app is not None:
        try:
            _word_app.Quit()
        except Exception:
            pass
        _word_app = None


def build_md(url, list_title, list_date, source_name, region, category):
    """抓详情页 + 附件 → front matter dict 或 None。"""
    r = t.polite_get(url, 2.5, referer=SITE + "/")
    if r is None:
        return None
    d = t.extract_detail(r.text, url, list_title, list_date)
    if not d or len(d["md"]) < 60:
        return None
    title = clean_title(list_title, d["title"])
    date = d["date"] or list_date or ""
    md = d["md"]
    # 清理附件图标等内联图片
    md = re.sub(r"!\[\]\([^)]*icons/[a-z]+\.png\)", "", md)
    md = re.sub(r"!\[\]\([^)]*/picture/[^)]*\)", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()

    att_info = []
    for a in d["attachments"]:
        kind_txt, kind = extract_attachment_text(a, url)
        att_info.append({"url": a, "text": kind_txt, "kind": kind})
        if kind in ("pdf", "docx", "doc") and kind_txt:
            pass  # appended below

    parts = [md]
    for ai in att_info:
        if ai["text"]:
            parts.append(f"\n\n## 附件（{ai['kind']} 全文）\n\n{ai['text'].strip()}")
    body = "".join(parts)

    fm = {
        "title": title, "date": date, "source_org": d.get("source_org", ""),
        "md": body, "attachments": att_info, "url": url,
    }
    return fm
