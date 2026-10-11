#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""用 playwright headless chromium 访问 flk.npc.gov.cn，收集 WAF(wzws) cookie。

用法:
  python flk_cookie.py            # 刷新 cookie 并写入 work/lists/flk_cookies.json
  python flk_cookie.py --test     # 刷新后立即用 requests 验证 download/pc 返回 JSON
  python flk_cookie.py --check    # 只检查现有 cookie 是否有效(不刷新)
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import sys
import time

import requests

BASE = "https://flk.npc.gov.cn"
ROOT = os.path.join(os.path.dirname(__file__), "..")
COOKIE_PATH = os.path.abspath(os.path.join(ROOT, "lists", "flk_cookies.json"))
FRESH_SECONDS = 30 * 60  # 30 分钟内视为新鲜

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def fetch_cookies_via_playwright(timeout_s=60):
    """新开一个浏览器实例（不复用全局），返回 cookies list + 最终 UA。

    注意：WAF 平静期首页不挑战，cookies 可能为空列表——这是正常情况，
    空 cookie 一样能过（普通 requests 即可）。
    """
    from playwright.sync_api import sync_playwright

    ua_used = UA
    # 启动选项按序尝试：自带 chromium → 系统 Edge → 系统 Chrome
    launch_opts = [
        {"headless": True, "args": ["--disable-blink-features=AutomationControlled",
                                    "--no-sandbox"]},
        {"headless": True, "channel": "msedge",
         "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]},
        {"headless": True, "channel": "chrome",
         "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]},
    ]
    last_err = None
    for opts in launch_opts:
        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(**opts)
                ctx = browser.new_context(
                    user_agent=UA,
                    locale="zh-CN",
                    viewport={"width": 1366, "height": 768},
                )
                page = ctx.new_page()
                page.goto(BASE + "/", wait_until="domcontentloaded",
                          timeout=timeout_s * 1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:
                    pass
                time.sleep(6)
                try:
                    cur = page.url
                    if "flk.npc.gov.cn" in cur and cur.rstrip("/") != BASE:
                        page.goto(BASE + "/", wait_until="domcontentloaded",
                                  timeout=30000)
                        time.sleep(4)
                except Exception:
                    pass
                cookies = ctx.cookies()
                return cookies, ua_used
        except Exception as e:
            last_err = e
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
    if last_err is not None:
        raise last_err
    return [], ua_used


def save_cookies(cookies, ua):
    payload = {
        "ts": time.time(),
        "ua": ua,
        "cookies": cookies,
    }
    os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
    tmp = COOKIE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, COOKIE_PATH)
    return payload


def load_cookies(max_age=FRESH_SECONDS):
    """读取 cookie 文件；不存在/过期/损坏返回 None。max_age=None 表示不限时长。"""
    if not os.path.exists(COOKIE_PATH):
        return None
    try:
        with open(COOKIE_PATH, encoding="utf-8") as f:
            payload = json.load(f)
        if max_age is not None and time.time() - payload.get("ts", 0) > max_age:
            return None
        if not payload.get("cookies"):
            return None
        return payload
    except Exception:
        return None


def build_session(payload):
    """按 cookie 文件构造 requests Session。payload 为 None 时建普通会话。"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (payload or {}).get("ua") or UA,
        "Referer": BASE + "/",
        "Origin": BASE,
        "Accept": "application/json, text/plain, */*",
    })
    for c in (payload or {}).get("cookies", []):
        s.cookies.set(c.get("name", ""), c.get("value", ""),
                      domain=c.get("domain", ""),
                      path=c.get("path", "/"))
    return s


def test_session(s, bbbs):
    """用 download/pc 验证 session：返回 (ok, err_msg)。"""
    try:
        r = s.get(BASE + "/law-search/download/pc",
                  params={"format": "docx", "bbbs": bbbs}, timeout=30)
        ct = r.headers.get("content-type", "")
        if "json" not in ct:
            return False, f"ct={ct} body[:120]={r.text[:120]!r}"
        j = r.json()
        return bool(j.get("data")), f"code={j.get('code')}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def get_test_bbbs():
    """从法律清单里取第一个 bbbs 作测试。"""
    list_path = os.path.join(ROOT, "lists", "flk_法律.jsonl")
    if os.path.exists(list_path):
        with open(list_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    return json.loads(line)["bbbs"]
    return ""


def refresh(quiet=False):
    """刷新并保存 cookie，返回 payload。"""
    cookies, ua = fetch_cookies_via_playwright()
    payload = save_cookies(cookies, ua)
    if not quiet:
        names = [c["name"] for c in cookies]
        print(f"[flk_cookie] 已保存 {len(cookies)} 个 cookie: {names}")
    return payload


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--check":
        payload = load_cookies(max_age=None)
        if not payload:
            print("[flk_cookie] 无 cookie 文件")
            sys.exit(2)
        s = build_session(payload)
        ok, msg = test_session(s, get_test_bbbs())
        age = int(time.time() - payload.get("ts", 0))
        print(f"[flk_cookie] cookie 年龄 {age}s, 验证 {'通过' if ok else '失败'}: {msg}")
        sys.exit(0 if ok else 1)
    payload = refresh()
    if mode == "--test":
        s = build_session(payload)
        ok, msg = test_session(s, get_test_bbbs())
        print(f"[flk_cookie] 刷新后验证 {'通过' if ok else '失败'}: {msg}")
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
