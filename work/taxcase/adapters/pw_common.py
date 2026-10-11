# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""playwright 有头过墙的公共工具（审查修复：从 qd_hn_recon.py 抽出，
生产 adapter 不再依赖侦察脚本 —— qd_hn_recon.py 已移入 _recon/ 归档）。

依赖 qd/hn 站点通用的「瑞数/JS 挑战等待」逻辑：
  pw_open(page, url) —— goto 后轮询 page.content() 直到正文长度达标且无
  $_ts=window 挑战壳，返回最终 html（超时返回最后一次内容）。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import re
import time


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def body_text_len(html):
    m = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    body = m.group(1) if m else ""
    return len(re.sub(r"\s", "", re.sub(r"<[^>]+>", "", body)))


def pw_open(page, url, tries=4):
    last = ""
    for attempt in range(tries):
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            for _ in range(40):
                time.sleep(1)
                html = page.content()
                last = html
                if body_text_len(html) > 300 and "$_ts=window" not in html[:3000]:
                    return html
        except Exception as e:
            log(f"  pw_open exc {type(e).__name__}: {str(e)[:90]}")
            time.sleep(3)
    return last
