#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""WAF 看护：定期探测 flk.npc.gov.cn 验证码是否解除；解除后自动慢速续下地方法规。

策略：
- 每 PROBE_INTERVAL 秒探测一次（playwright 刷 cookie + 单请求 download/pc）
- 连续 PASS_N 次 JSON 正常 → 启动 flk_download.py 地方法规 3 workers（慢速）
- 下载进程结束后回到探测循环
日志: work/logs/waf_watch.log
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flk_cookie  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG = os.path.join(ROOT, "logs", "waf_watch.log")
PROBE_INTERVAL = 20 * 60  # 20 分钟
PASS_N = 2  # 连续通过次数


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def probe():
    """返回 (ok, msg)。ok=API 返回 JSON。"""
    try:
        payload = flk_cookie.refresh(quiet=True)
    except Exception as e:
        return False, f"cookie refresh failed: {type(e).__name__}: {e}"
    s = flk_cookie.build_session(payload)
    bbbs = flk_cookie.get_test_bbbs() or "x"
    ok, msg = flk_cookie.test_session(s, bbbs)
    # test_session 用的是法律 bbbs；再测一个地方法规的更贴近实际
    items_path = os.path.join(ROOT, "lists", "flk_地方法规.jsonl")
    if os.path.exists(items_path):
        with open(items_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    it = json.loads(line)
                    ok2, msg2 = flk_cookie.test_session(s, it["bbbs"])
                    return ok2, msg2
    return ok, msg


def run_download():
    log("启动慢速下载: flk_download.py 地方法规 3")
    p = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "flk_download.py"),
         "地方法规", "3"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    tail = (p.stdout or "").strip().splitlines()[-5:]
    for t in tail:
        log(f"  dl| {t}")
    log(f"下载进程退出 code={p.returncode}")


def main():
    log("=== WAF 看护启动 ===")
    consecutive = 0
    while True:
        ok, msg = probe()
        log(f"探测: {'PASS' if ok else 'BLOCK'} ({msg[:80]})")
        if ok:
            consecutive += 1
            if consecutive >= PASS_N:
                run_download()
                consecutive = 0
                # 下载器退出后（可能又遇 WAF 或队列跑完），继续探测
        else:
            consecutive = 0
        time.sleep(PROBE_INTERVAL)


if __name__ == "__main__":
    main()
