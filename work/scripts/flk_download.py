#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""flk.npc.gov.cn 多线程批量下载器：现行有效法规官方 docx。

用法: python flk_download.py <category> [workers]
  category: 宪法/法律/行政法规/监察法规/地方法规/司法解释/all
断点续下：进度存 work/lists/flk_dl_progress_<category>.jsonl (bbbs -> 状态)
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import io
import json
import os
import random
import re
import sys
import threading
import time
import zipfile
from urllib.parse import unquote

import requests

BASE = "https://flk.npc.gov.cn"
ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
DL_ROOT = os.path.join(ROOT, "downloads", "flk")
PROGRESS_DIR = os.path.join(ROOT, "lists")
COOKIE_JSON = os.path.join(LISTS, "flk_cookies.json")
FRESH_SECONDS = 30 * 60  # cookie 文件 30 分钟内视为新鲜

SXX_MAP = {1: "已废止", 2: "已修改", 3: "有效", 4: "尚未生效"}

_print_lock = threading.Lock()
_cookie_lock = threading.Lock()
_pause_lock = threading.Lock()
_pace_lock = threading.Lock()
_pause_until = 0.0   # 熔断暂停截止时间戳
_pace_mult = 1.0     # 全局降速倍率（熔断时增大，持续成功时缓慢回落）
_last_refresh_ts = 0.0     # 上次 playwright 真实刷新时间
_last_refresh_ok = False   # 上次刷新后是否有成功请求（判断 cookie 是否已烧毁）


def log(msg):
    with _print_lock:
        print(msg, flush=True)


def pace_sleep(base_lo, base_hi):
    """按全局降速倍率 sleep。"""
    with _pace_lock:
        mult = _pace_mult
    time.sleep((base_lo + random.random() * (base_hi - base_lo)) * mult)


def pace_success():
    """持续成功时缓慢回落降速倍率。"""
    global _pace_mult
    with _pace_lock:
        _pace_mult = max(1.0, _pace_mult - 0.05)


def load_cookie_payload(max_age=FRESH_SECONDS):
    """读取 cookie 池文件；不存在/过期/损坏返回 None。max_age=None 不限时。"""
    if not os.path.exists(COOKIE_JSON):
        return None
    try:
        with open(COOKIE_JSON, encoding="utf-8") as f:
            payload = json.load(f)
        if max_age is not None and time.time() - payload.get("ts", 0) > max_age:
            return None
        return payload if payload.get("cookies") else None
    except Exception:
        return None


def apply_cookies(s, payload):
    if not payload:
        return
    ua = payload.get("ua")
    if ua:
        s.headers["User-Agent"] = ua
    for c in payload.get("cookies", []):
        try:
            s.cookies.set(c.get("name", ""), c.get("value", ""),
                          domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            pass


def refresh_cookie_file(reason=""):
    """用 playwright 刷新 cookie 池文件（多线程下单飞）。返回 payload 或 None。

    复用窗口较短(15s)，且若上次刷新后一直没有成功请求（cookie 已被 WAF 烧毁），
    则强制重新跑 playwright 而不是复用文件。
    """
    global _last_refresh_ts, _last_refresh_ok
    with _cookie_lock:
        now = time.time()
        p = load_cookie_payload(max_age=15)
        if p and _last_refresh_ok:
            return p
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import flk_cookie
            p = flk_cookie.refresh(quiet=True)
            _last_refresh_ts = now
            _last_refresh_ok = False
            n = len(p.get("cookies", []))
            log(f"[cookie] playwright 刷新成功 {n} 个 cookie {reason}")
            return p
        except Exception as e:
            log(f"[cookie] playwright 刷新失败 {reason}: {type(e).__name__}: {e}")
            return None


def mark_refresh_effective():
    """cookie 刷新后确有请求成功——允许后续短窗复用。"""
    global _last_refresh_ok
    with _cookie_lock:
        _last_refresh_ok = True


def circuit_break(seconds=600):
    """失败率突增时全局暂停并提升降速倍率。"""
    global _pause_until, _pace_mult
    with _pause_lock:
        _pause_until = max(_pause_until, time.time() + seconds)
    with _pace_lock:
        _pace_mult = min(6.0, _pace_mult + 1.0)
        m = _pace_mult
    log(f"[break] 失败率过高，全局暂停 {seconds}s，降速倍率 {m:.1f}")


def wait_if_paused():
    while True:
        with _pause_lock:
            if time.time() >= _pause_until:
                return
            remain = _pause_until - time.time()
        time.sleep(min(remain, 5))


class RollingFail:
    """滑动窗口失败率：最近 window 次尝试中失败占比。"""

    def __init__(self, window=40):
        self.lock = threading.Lock()
        self.window = window
        self.buf = []

    def record(self, ok):
        with self.lock:
            self.buf.append(bool(ok))
            if len(self.buf) > self.window:
                self.buf.pop(0)
            n = len(self.buf)
            if n >= 20:
                return sum(1 for x in self.buf if not x) / n
        return 0.0


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://flk.npc.gov.cn/",
        "Origin": "https://flk.npc.gov.cn",
        "Accept": "application/json, text/plain, */*",
    })
    payload = load_cookie_payload()
    if payload:
        apply_cookies(s, payload)
    else:
        refresh_cookie(s)
    return s


def looks_like_waf(resp=None, exc=None):
    """判断失败是否为 WAF JS 挑战（返回了 HTML 而非 JSON）。"""
    if exc is not None and type(exc).__name__ == "JSONDecodeError":
        return True
    if resp is not None and "json" not in (resp.headers.get("content-type") or ""):
        return True
    return False


def refresh_cookie(s):
    """轻量会话刷新：优先复用 cookie 池文件，否则 GET 首页。"""
    payload = load_cookie_payload(max_age=120)
    if payload:
        apply_cookies(s, payload)
        return True
    for i in range(5):
        try:
            r = s.get(BASE + "/", timeout=20)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2 + 2 * i)
    return False


def valid_docx(content: bytes) -> bool:
    if not content or len(content) < 2000:
        return False
    try:
        z = zipfile.ZipFile(io.BytesIO(content))
        return "word/document.xml" in z.namelist()
    except Exception:
        return False


def looks_like_legacy_doc(content: bytes) -> bool:
    """OLE2 复合文档魔数（老 .doc）。"""
    return content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def decide_ext(content: bytes, url: str, fmt: str):
    """返回 (ok, ext)。docx 请求可能实际给 .doc。"""
    if fmt == "docx":
        if valid_docx(content):
            return True, "docx"
        if looks_like_legacy_doc(content) or url.lower().split("?")[0].endswith(".doc"):
            return True, "doc"
        return False, "docx"
    return True, "pdf"


def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name.strip().rstrip(".")[:100] or "unnamed"


class Progress:
    """线程安全 JSONL 进度：bbbs -> {ok, file, error}"""

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            rec = json.loads(line)
                            self.data[rec["bbbs"]] = rec
                        except Exception:
                            continue
        self._count = 0

    def mark(self, bbbs, **kv):
        with self.lock:
            rec = {"bbbs": bbbs}
            rec.update(kv)
            self.data[bbbs] = rec
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def done_ok(self, bbbs):
        with self.lock:
            r = self.data.get(bbbs)
            return bool(r and r.get("ok"))


def worker(idx, queue_list, progress, stats, stop_event, rolling):
    s = make_session()
    req_count = 0
    requeued = {}  # bbbs -> 次数（WAF 失败放回队列，最多 4 次）
    while not stop_event.is_set():
        wait_if_paused()
        try:
            item = queue_list.pop(0)
        except IndexError:
            break
        bbbs = item["bbbs"]
        cat = item["cat"]
        out_dir = os.path.join(DL_ROOT, cat)
        os.makedirs(out_dir, exist_ok=True)
        status = SXX_MAP.get(item.get("sxx"), "未知")
        base_name = sanitize(f"{item.get('flxz') or cat}_{item['title']}_{item.get('gbrq','')}_{status}")
        fpath_docx = os.path.join(out_dir, base_name + ".docx")

        # 已有有效文件则跳过
        if os.path.exists(fpath_docx) and os.path.getsize(fpath_docx) > 2000:
            progress.mark(bbbs, ok=True, file=os.path.basename(fpath_docx), skipped=True)
            with stats["lock"]:
                stats["skip"] += 1
            rolling.record(True)
            continue

        ok = False
        err = ""
        waf_hit = False
        for fmt in ("docx", "pdf"):
            try:
                if req_count >= 120:
                    refresh_cookie(s)
                    req_count = 0
                r = s.get(BASE + "/law-search/download/pc",
                          params={"format": fmt, "bbbs": bbbs}, timeout=30)
                req_count += 1
                if r.status_code != 200:
                    waf_hit = waf_hit or looks_like_waf(resp=r)
                    refresh_cookie(s)
                    raise RuntimeError(f"http {r.status_code}")
                waf_hit = waf_hit or looks_like_waf(resp=r)
                j = r.json()
                url = (j.get("data") or {}).get("url", "")
                if not url:
                    err = f"no url fmt={fmt}"
                    continue
                fpath = fpath_docx if fmt == "docx" else fpath_docx[:-5] + ".pdf"
                r2 = s.get(url, timeout=90)
                if r2.status_code != 200 or len(r2.content) < 2000:
                    err = f"oss http {r2.status_code} len {len(r2.content)}"
                    continue
                good, ext = decide_ext(r2.content, url, fmt)
                if not good:
                    err = f"invalid docx len {len(r2.content)}"
                    continue
                if ext != "pdf":
                    fpath = fpath_docx[:-5] + "." + ext
                with open(fpath, "wb") as f:
                    f.write(r2.content)
                progress.mark(bbbs, ok=True, file=os.path.basename(fpath), fmt=fmt,
                              bytes=len(r2.content))
                ok = True
                mark_refresh_effective()
                with stats["lock"]:
                    stats["ok"] += 1
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                waf_hit = waf_hit or looks_like_waf(exc=e)
                refresh_cookie(s)

        # WAF 挑战：刷新 cookie 池文件后立即重试一次
        if not ok and waf_hit:
            payload = refresh_cookie_file(reason=f"bbbs={bbbs}")
            if payload:
                s = make_session()  # 用新 cookie 重建会话
                req_count = 0
                for fmt in ("docx", "pdf"):
                    try:
                        r = s.get(BASE + "/law-search/download/pc",
                                  params={"format": fmt, "bbbs": bbbs}, timeout=30)
                        req_count += 1
                        if r.status_code != 200:
                            raise RuntimeError(f"http {r.status_code}")
                        j = r.json()
                        url = (j.get("data") or {}).get("url", "")
                        if not url:
                            err = f"no url fmt={fmt} (retry)"
                            continue
                        fpath = fpath_docx if fmt == "docx" else fpath_docx[:-5] + ".pdf"
                        r2 = s.get(url, timeout=90)
                        if r2.status_code != 200 or len(r2.content) < 2000:
                            err = f"oss http {r2.status_code} len {len(r2.content)} (retry)"
                            continue
                        good, ext = decide_ext(r2.content, url, fmt)
                        if not good:
                            err = f"invalid docx len {len(r2.content)} (retry)"
                            continue
                        if ext != "pdf":
                            fpath = fpath_docx[:-5] + "." + ext
                        with open(fpath, "wb") as f:
                            f.write(r2.content)
                        progress.mark(bbbs, ok=True, file=os.path.basename(fpath),
                                      fmt=fmt, bytes=len(r2.content), retried=True)
                        ok = True
                        mark_refresh_effective()
                        with stats["lock"]:
                            stats["ok"] += 1
                        break
                    except Exception as e:
                        err = f"{type(e).__name__}: {e} (retry)"

        if not ok and waf_hit:
            # WAF 期失败：放回队列稍后再试（而非标记失败），最多 4 轮
            n = requeued.get(bbbs, 0)
            if n < 4:
                requeued[bbbs] = n + 1
                queue_list.append(item)
                with stats["lock"]:
                    stats["waf_requeue"] += 1
                pace_sleep(2.0, 5.0)
                continue

        if not ok:
            progress.mark(bbbs, ok=False, error=err)
            with stats["lock"]:
                stats["fail"] += 1
        rate = rolling.record(ok)
        if rate > 0.2:
            circuit_break(600)
        elif ok:
            pace_success()
        with stats["lock"]:
            stats["done"] += 1
            d, o, f_, sk = stats["done"], stats["ok"], stats["fail"], stats["skip"]
        if d % 50 == 0:
            wr = stats.get("waf_requeue", 0)
            log(f"[{stats['cat']}] 进度 {d}/{stats['total']} 成功{o} 跳过{sk} 失败{f_} WAF重排{wr}")
        pace_sleep(0.3, 0.8)


def run_category(cat, workers=4, pace_init=1.0):
    global _pace_mult
    _pace_mult = float(pace_init)
    list_path = os.path.join(LISTS, f"flk_{cat}.jsonl")
    items = []
    with open(list_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    progress = Progress(os.path.join(PROGRESS_DIR, f"flk_dl_progress_{cat}.jsonl"))

    queue_list = []
    for it in items:
        if progress.done_ok(it["bbbs"]):
            continue
        queue_list.append(it)
    log(f"[{cat}] 总 {len(items)}，已完成 {len(items)-len(queue_list)}，待下 {len(queue_list)}")

    stats = {"lock": threading.Lock(), "ok": 0, "fail": 0, "skip": 0, "done": 0,
             "waf_requeue": 0, "total": len(items), "cat": cat}
    rolling = RollingFail(window=40)
    stop_event = threading.Event()
    threads = []
    for i in range(workers):
        t = threading.Thread(target=worker, args=(i, queue_list, progress, stats, stop_event, rolling), daemon=True)
        t.start()
        time.sleep(1.2)  # 错开启动
        threads.append(t)
    for t in threads:
        t.join()
    log(f"[{cat}] 结束: 成功{stats['ok']} 跳过{stats['skip']} 失败{stats['fail']} / 共{stats['total']}")


def main():
    cat = sys.argv[1] if len(sys.argv) > 1 else "all"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    pace = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    cats = ["宪法", "法律", "行政法规", "监察法规", "地方法规", "司法解释"] if cat == "all" else [cat]
    for c in cats:
        run_category(c, workers=workers, pace_init=pace)


if __name__ == "__main__":
    main()
