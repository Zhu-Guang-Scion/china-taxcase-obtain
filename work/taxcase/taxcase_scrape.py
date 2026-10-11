# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""
税务案例通用抓取器 v1 (2026-10-10)
================================
针对税务系统 TRS CMS 同构站点（总局 www.chinatax.gov.cn + 各省 *.chinatax.gov.cn）。

列表两种模式：
  A. manuscriptList —— 总局栏目分页接口：
     {site}/chinatax/manuscriptList/{channel_code}?_isAgg=0&_pageSize=20&_template=index
       &_channelName={name}&_keyWH=wenhao&page={n}
  B. static_list —— 省局静态列表页，URL 模板含 {page} 占位（page从1起，
     第1页可用首页URL，其后 index_1.html/index_2.html… 按模板逐页拼）

详情页提取（多容器回退）：
  .article-content / #zoomcon / .TRS_Editor / #zoom / article / [id^=zoom]
标题： h2.article-subtitle > <title> > 列表title
日期： <PUBLISHTIME>yyyymmdd</PUBLISHTIME> 或 meta 或列表页日期

输出： 纯 markdown（YAML front matter + 正文），进度 jsonl 断点续抓，URL去重。
合规： 单线程、默认 2.5s+随机抖动间隔、失败重试3次退避。

用法：
  python taxcase_scrape.py job.json            # 跑一个任务
  python taxcase_scrape.py job.json --dry-run  # 只抓列表不抓详情
job.json 字段：
  job_id, site, list_mode(manuscriptList|static_list),
  channel_code, channel_name(上述A模式),
  list_url_template(上述B模式, 含{page}), first_page_url(可选),
  out_dir, region, source_name, category,
  max_pages, date_from(可选,早于则停), delay(可选秒)

约定（审查修复后）：
  - out_dir 支持相对路径：相对**当前工作目录（CWD）**解析（不是相对 job.json 或
    本文件），便于在仓库根执行 `python work/taxcase/taxcase_scrape.py <job.json>`；
    绝对路径行为不变。
  - static_list 未给 first_page_url 时，第一页 URL = 模板去掉 {page} 占位
    （{page}→""，如 ".../list{page}.html" 首页即 list.html）。若站点首页是
    index.html 而模板含 "_{page}"，务必显式给 first_page_url。
  - 日期比较前统一 _norm_date() 归一化（容忍 "/" "." 分隔与缺零填充）。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json, os, re, sys, time, random, hashlib, argparse
from datetime import date
from urllib.parse import urljoin, quote

from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

import requests

try:  # chinatax 主站对 python-requests 的 TLS 指纹返回无数据壳页，必须 chrome 指纹
    from curl_cffi import requests as cffi_requests
    _HAS_CFFI = True
except ImportError:
    _HAS_CFFI = False

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HERE = os.path.dirname(os.path.abspath(__file__))
PROG_DIR = os.path.join(HERE, "progress")
os.makedirs(PROG_DIR, exist_ok=True)

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
_last_ts = [0.0]


class Resp:
    __slots__ = ("status_code", "text", "content", "headers")

    def __init__(self, r):
        self.status_code = r.status_code
        self.content = r.content
        self.headers = dict(getattr(r, "headers", {}) or {})
        enc = ""
        try:
            enc = self.headers.get("Content-Type", "") or ""
        except Exception:
            pass
        m = re.search(r"charset=([\w-]+)", enc)
        if not m:  # 从 HTML meta 探测（省局常见 gbk）
            m2 = re.search(rb'charset=["\']?([\w-]+)', self.content[:2048])
            m = type("M", (), {"group": lambda s, i=0: m2.group(1).decode()})() if m2 else None
        r.encoding = m.group(1) if m else "utf-8"
        self.text = r.text


def polite_get(url, delay=2.5, referer=None, timeout=40, retries=3):
    """带全局限速+重试退避的 GET：优先 curl_cffi(chrome指纹)，回退 requests。"""
    for attempt in range(retries):
        wait = delay + random.uniform(0, 1.0) - (time.time() - _last_ts[0])
        if wait > 0:
            time.sleep(wait)
        try:
            h = {"Referer": referer} if referer else {}
            if _HAS_CFFI:
                r = cffi_requests.get(url, headers=h, timeout=timeout,
                                      impersonate="chrome124")
            else:
                r = _session.get(url, headers=h, timeout=timeout)
            _last_ts[0] = time.time()
            if r.status_code == 200:
                return Resp(r)
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(3 * (attempt + 1) + random.uniform(0, 2))
    return None


# ---------------- 列表解析 ----------------

def _norm_date(s):
    """日期归一化为 YYYY-MM-DD（审查修复：容忍 "/" "." 分隔与缺零填充，
    避免字符串比较 "2025-6-3" vs "2025-10-01" 出错）。无法解析时尽量降级。"""
    if not s:
        return ""
    s = str(s).strip()
    m = re.match(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", s)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return s.replace("/", "-").replace(".", "-")


def parse_list_items(html, page_url):
    """从列表页提取 [(url,title,date)]，去重保序。

    兼容两种结构：
    - 静态列表页: <a href title="..."> + <span class="time">2026-09-28</span>
    - manuscriptList: <a href>标题文本</a> + <span>[2026-09-28]</span>（绝对URL）
    """
    soup = BeautifulSoup(html, "lxml")
    host = re.sub(r"^https?://", "", page_url).split("/")[0]
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("javascript", "#", "mailto")):
            continue
        if not re.search(r"(content[_0-9a-f]*\.s?html|/c\d+/[^/]+\.html)", href):
            continue
        url = urljoin(page_url, href)
        if host not in url:
            continue  # 跳过跨站导航
        text = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
        if len(text) < 8:
            continue
        date_s = ""
        scope = a.parent.get_text(" ", strip=True) if a.parent else text
        m = re.search(r"(\d{4}[-./]\d{1,2}[-./]\d{1,2})", scope[:300])
        if m:
            date_s = _norm_date(m.group(1))
        url_canon = url.split("#")[0]
        if url_canon in seen:
            continue
        seen.add(url_canon)
        items.append((url_canon, re.sub(r"\s+", " ", text), date_s))
    return items


def iter_list(job):
    """产出 (url,title,date) 流。"""
    if job["list_mode"] == "manuscriptList":
        base = (f"{job['site']}/chinatax/manuscriptList/{job['channel_code']}"
                f"?_isAgg=0&_pageSize=20&_template=index"
                f"&_channelName={quote(job['channel_name'])}&_keyWH=wenhao&page=")
        for page in range(1, int(job.get("max_pages", 10)) + 1):
            url = base + str(page)
            r = polite_get(url, job.get("delay", 2.5), referer=job["site"] + "/")
            if r is None:
                print(f"[list] page {page} fetch failed, stop"); return
            items = parse_list_items(r.text, url)
            if not items:
                print(f"[list] page {page} empty, stop"); return
            yield from items
            total = re.search(r"共(\d+)页", r.text)
            if total and page >= int(total.group(1)):
                return
    else:  # static_list
        tpl = job["list_url_template"]
        # 审查修复：旧默认值 tpl.replace("{page}", "index.html") 会拼出
        # index_index.html.html 之类的坏 URL。新约定：未给 first_page_url 时
        # 第一页 = 模板去掉 {page} 占位（{page}→""）；首页为独立 index.html 的
        # 站点必须在 job.json 里显式给 first_page_url。
        first = job.get("first_page_url") or tpl.replace("{page}", "")
        for page in range(1, int(job.get("max_pages", 10)) + 1):
            url = first if page == 1 else tpl.replace("{page}", str(page - 1))
            r = polite_get(url, job.get("delay", 2.5), referer=job["site"] + "/")
            if r is None:
                print(f"[list] page {page} fetch failed, stop"); return
            items = parse_list_items(r.text, url)
            if not items:
                print(f"[list] page {page} empty, stop"); return
            yield from items


# ---------------- 详情解析 ----------------

CONTENT_SELECTORS = [
    "div.article-content", "#zoomcon", "div.TRS_Editor", "#zoom",
    "div.article", "article", "div#content", "div.main-content",
    "div.ggwnr", "div.nr", "div.content",
]


def _abs_md_images(md, base_url):
    """markdown 内相对路径图片 → 绝对URL（md-only库不存图片，保留可解析链接）"""
    def repl(m):
        src = m.group(2).strip()
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        return "![%s](%s)" % (m.group(1), urljoin(base_url, src))
    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, md)


def extract_detail(html, url, fallback_title="", fallback_date=""):
    soup = BeautifulSoup(html, "lxml")
    title = ""
    h = soup.select_one("h2.article-subtitle") or soup.select_one("h1")
    if h:
        title = h.get_text(" ", strip=True)
    if not title:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else fallback_title
    title = re.sub(r"\s+", " ", title)

    pub = ""
    m = re.search(r"<PUBLISHTIME>\s*([0-9-]{8,10})\s*</PUBLISHTIME>", html)
    if m:
        pub = m.group(1).replace(".", "-")
    if not pub:
        m = re.search(r'([12]\d{3}-\d{1,2}-\d{1,2})', soup.get_text(" ")[:3000])
        pub = m.group(1) if m else (fallback_date or "")
    src_org = ""
    m = re.search(r"来源[：:]\s*([^<\s]{2,30})", html)
    if m:
        src_org = m.group(1)

    body = None
    for sel in CONTENT_SELECTORS:
        node = soup.select_one(sel)
        if node:
            text = node.get_text("\n", strip=True)
            if len(text) >= 120:
                body = node; break
    if body is None:
        # 兜底：全文档 p 块拼正文
        ps = [p for p in soup.find_all("p")
              if len(p.get_text(strip=True)) >= 15]
        if ps:
            wrap = soup.new_tag("div")
            for p in ps:
                wrap.append(p.extract())
            body = wrap
    if body is None:
        return None

    # 清噪音
    for tag in body.select("script,style,.shareIcon,.fontsize,.print,"
                           "applet,iframe,form,.pagination,#page_div"):
        tag.decompose()
    # 附件链接保留
    attach = []
    for a in body.find_all("a", href=True):
        if re.search(r"\.(pdf|docx?|xlsx?|zip|rar)$", a["href"], re.I):
            attach.append(urljoin(url, a["href"]))
    md = MarkdownConverter(heading_style="ATX", bullets="-").convert_soup(body)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = md.replace("\\\\*\\*", "**")
    md = _abs_md_images(md, url)
    # 去掉行内残留的空白转义
    return {"title": title, "date": pub, "source_org": src_org,
            "md": md, "attachments": attach}


# ---------------- 落盘 ----------------

def safe_filename(title, limit=80):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", title)
    s = re.sub(r"\s+", "", s)
    s = s.strip("_. ")
    return s[:limit] or "untitled"


def load_progress(job_id):
    path = os.path.join(PROG_DIR, job_id + ".jsonl")
    done = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("ok"):
                        done.add(rec["url"])
                except json.JSONDecodeError:
                    pass
    return done, path


def run_job(job, dry_run=False):
    out_dir = job["out_dir"]
    if not os.path.isabs(out_dir):  # 审查修复：相对 out_dir 相对 CWD 解析（见模块 docstring）
        out_dir = os.path.normpath(os.path.join(os.getcwd(), out_dir))
    os.makedirs(out_dir, exist_ok=True)
    done, prog_path = load_progress(job["job_id"])
    date_from = _norm_date(job.get("date_from", ""))
    delay = job.get("delay", 2.5)
    n_new = n_skip = n_old = 0
    stop_old = False
    with open(prog_path, "a", encoding="utf-8") as prog:
        for url, title, ldate in iter_list(job):
            if stop_old:
                break
            ldate = _norm_date(ldate)  # 审查修复：比较前归一化
            if ldate and date_from and ldate < date_from:
                n_old += 1
                if n_old >= 20:  # 连续20条早于阈值，视为翻到旧区
                    stop_old = True
                continue
            if url in done:
                n_skip += 1
                continue
            if dry_run:
                print(f"[dry] {ldate} {title[:50]} {url}")
                n_new += 1
                continue
            r = polite_get(url, delay, referer=job["site"] + "/")
            if r is None:
                prog.write(json.dumps({"url": url, "ok": False,
                                       "err": "fetch"}, ensure_ascii=False) + "\n")
                continue
            d = extract_detail(r.text, url, title, ldate)
            if not d or len(d["md"]) < 100:
                prog.write(json.dumps({"url": url, "ok": False,
                                       "err": "parse"}, ensure_ascii=False) + "\n")
                prog.flush()
                continue
            fname = safe_filename((d["date"] or "nodate") + "_" + d["title"]) + ".md"
            fpath = os.path.join(out_dir, fname)
            fm = ("---\n"
                  f"title: \"{d['title'].replace(chr(34), '')}\"\n"
                  f"来源机关: \"{job['source_name']}\"\n"
                  f"栏目: \"{job['category']}\"\n"
                  f"地区: \"{job['region']}\"\n"
                  f"发布日期: {d['date'] or ''}\n"
                  f"原文来源: \"{d['source_org']}\"\n"
                  f"抓取日期: {date.today().isoformat()}\n"
                  f"原文链接: {url}\n")
            if d["attachments"]:
                fm += "附件:\n" + "\n".join(f"  - {a}" for a in d["attachments"]) + "\n"
            fm += "---\n\n"
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(fm + d["md"] + "\n")
            prog.write(json.dumps({"url": url, "ok": True, "file": fname,
                                   "title": d["title"], "date": d["date"]},
                                  ensure_ascii=False) + "\n")
            prog.flush()
            n_new += 1
            if n_new % 20 == 0:
                print(f"[{job['job_id']}] new={n_new} skip={n_skip}")
    print(f"[{job['job_id']}] DONE new={n_new} skip={n_skip} old_skipped={n_old}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with open(args.job, encoding="utf-8") as f:
        job = json.load(f)
    run_job(job, args.dry_run)


if __name__ == "__main__":
    main()
