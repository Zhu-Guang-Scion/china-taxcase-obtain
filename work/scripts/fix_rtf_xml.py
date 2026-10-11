#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""用官方 API 替换 lawtext 镜像里的 RTF/WordML 格式文件为标准 docx/doc/pdf。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import io
import json
import os
import re
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flk_cookie  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
CAT = "地方法规"


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    return name.strip().rstrip(".")[:100] or "unnamed"


def sniff(c: bytes):
    """返回 (good, ext)。"""
    if c[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(c))
            if "word/document.xml" in z.namelist():
                return True, "docx"
        except Exception:
            pass
        return False, None
    if c[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return True, "doc"
    if c[:5] == b"%PDF-":
        return True, "pdf"
    return False, None


def main():
    payload = flk_cookie.refresh(quiet=True)
    s = flk_cookie.build_session(payload)
    dd = os.path.join(ROOT, "downloads", "flk", CAT)
    items = [json.loads(l) for l in
             open(os.path.join(ROOT, "lists", f"flk_{CAT}.jsonl"), encoding="utf-8")
             if l.strip()]
    pp = os.path.join(ROOT, "lists", f"flk_dl_progress_{CAT}.jsonl")
    latest = {}
    for l in open(pp, encoding="utf-8"):
        if l.strip():
            try:
                r = json.loads(l)
                latest[r["bbbs"]] = r
            except Exception:
                pass

    targets = []
    for it in items:
        r = latest.get(it["bbbs"])
        if not (r and r.get("ok")):
            continue
        fp = os.path.join(dd, r.get("file", ""))
        if not os.path.exists(fp):
            continue
        with open(fp, "rb") as fh:
            head = fh.read(16)
        if head.startswith(b"{\\rtf") or head.startswith(b"<?xml"):
            targets.append((it, r))
    print("RTF/XML targets:", len(targets))

    prog = open(pp, "a", encoding="utf-8")
    fixed = 0
    for it, r in targets:
        okf = False
        for fmt in ("docx", "pdf"):
            try:
                resp = s.get("https://flk.npc.gov.cn/law-search/download/pc",
                             params={"format": fmt, "bbbs": it["bbbs"]}, timeout=30)
                if "json" not in resp.headers.get("content-type", ""):
                    print("WAF BLOCK, abort")
                    sys.exit(2)
                url = (resp.json().get("data") or {}).get("url", "")
                if not url:
                    continue
                r2 = s.get(url, timeout=90)
                c = r2.content
                if len(c) < 2000:
                    continue
                good, ext = sniff(c)
                if not good:
                    print("  仍非标准格式:", fmt, c[:8], it["title"][:22])
                    continue
                name = sanitize(f"{it.get('flxz') or CAT}_{it['title']}_{it.get('gbrq','')}_有效")
                fp2 = os.path.join(dd, name + "." + ext)
                n = 1
                while os.path.exists(fp2) and os.path.getsize(fp2) > 2000 and n < 9:
                    fp2 = os.path.join(dd, f"{name}_{n}.{ext}")
                    n += 1
                with open(fp2, "wb") as f:
                    f.write(c)
                prog.write(json.dumps({"bbbs": it["bbbs"], "ok": True,
                                       "file": os.path.basename(fp2), "fmt": fmt,
                                       "bytes": len(c),
                                       "replaced_rtf_xml": True},
                                      ensure_ascii=False) + "\n")
                prog.flush()
                print("FIXED", os.path.basename(fp2)[-45:], len(c))
                fixed += 1
                okf = True
                break
            except SystemExit:
                raise
            except Exception as e:
                print("ERR", it["title"][:18], type(e).__name__)
        if not okf:
            print("  keep rtf/xml:", it["title"][:30])
        time.sleep(2.5)
    prog.close()
    print("fixed:", fixed)


if __name__ == "__main__":
    main()
