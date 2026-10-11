# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""OCR 补全：把税务案例库中跳过的扫描件 PDF 用 MinerU OCR 成文本，追加到对应 md。

- 目标1：江苏省/处罚决定书送达公告 + 行政复议公告送达 中 front matter 标 (scanned_img) 的附件
- 目标2：全库其他 md front matter「附件:」里的 PDF 链接（深圳/天津等），下载→文本层检查→扫描件才 OCR
- 断点：progress/js_ocr_scan.jsonl（按 pdf_url 幂等）
- 限速：polite_get 全局 2.5s；MinerU 每件后 sleep 5s；失败重试 2 次退避
- 401/403 → 立即终止（token 失效不空转）
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import re
import shutil
import subprocess
import sys
import time

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量（默认仓库根，按本文件位置定位）
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxcase_scrape as t  # noqa: E402  (polite_get)

LIB = os.path.join(REPO, "lawlibrary", "专题", "税务案例")
PROG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress", "js_ocr_scan.jsonl")
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", "ocr_dl")
# 可移植化（审查修复）：mineru CLI 支持环境变量 MINERU_CLI 覆盖，回退 PATH 查找
CLI = os.environ.get("MINERU_CLI", shutil.which("mineru-open-api") or "mineru-open-api")
TODAY = "2026-10-10"

CJK = re.compile(r"[\u4e00-\u9fff]")
ATT_LINE = re.compile(r"^\s+-\s+(\S+)(?:\s+\((\w+)\))?\s*$", re.M)
TIAO = re.compile(r"第[一二三四五六七八九十百千零\d]+条")
STRUCT = re.compile(r"(第[一二三四五六七八九十百千零\d]+条|决定|[〔\[]\d+[〕\]]\d*号|\d+号)")


def cjk_len(s):
    return len(CJK.findall(s or ""))


def load_progress():
    done, lines = {}, []
    if os.path.exists(PROG):
        with open(PROG, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                lines.append(rec)
                if rec.get("pdf_url"):
                    done[rec["pdf_url"]] = rec
    return done, lines


def append_progress(rec):
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------- 目标盘点 ----------------

def parse_md(path):
    """返回 (front_matter_text, attachments[(url, kind)], url, body)"""
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", txt, re.S)
    if not m:
        return "", [], "", txt
    fm, body = m.group(1), m.group(2)
    url = ""
    mu = re.search(r"^原文链接:\s*(\S+)", fm, re.M)
    if mu:
        url = mu.group(1).strip()
    atts = [(u.strip(), k or "") for u, k in ATT_LINE.findall(fm)]
    return fm, atts, url, body


def collect_targets():
    """[(md_path, page_url, pdf_url, kind, need_ocr_hint)]"""
    targets = []
    for root, _dirs, files in os.walk(LIB):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(root, fn)
            try:
                _fm, atts, url, _body = parse_md(p)
            except Exception:
                continue
            for aurl, kind in atts:
                low = aurl.lower()
                if not (".pdf" in low or "downfile.jsp" in low):
                    continue
                is_js = "jiangsu.chinatax.gov.cn" in aurl
                # 江苏：仅这两个目录的 scanned_img 才 OCR（其他 pdf 已提过文本）
                if is_js and kind == "scanned_img":
                    targets.append((p, url, aurl, kind, True))
                elif is_js:
                    continue  # 江苏 pdf/其他 kind：原抓取已处理或非文本件
                else:
                    # 其他地区：无 kind 标记，下载后按文本层判断
                    targets.append((p, url, aurl, kind, False))
    return targets


# ---------------- 下载 + 文本层 ----------------

def download_and_check(pdf_url, referer):
    """返回 (status, pdf_bytes_or_None, cjk_in_textlayer)"""
    r = t.polite_get(pdf_url, 2.5, referer=referer or None)
    if r is None or not getattr(r, "content", b""):
        return "download_fail", None, 0
    content = r.content
    if not content[:5].startswith(b"%PDF"):
        # downfile.jsp 可能返回错误页
        if content[:200].lstrip().lower().startswith(b"<!doctype") or b"<html" in content[:300].lower():
            return "download_fail", None, 0
        return "not_pdf", None, 0
    import pymupdf
    try:
        with pymupdf.open(stream=content, filetype="pdf") as doc:
            txt = "\n".join(pg.get_text() for pg in doc).strip()
    except Exception:
        return "pdf_broken", None, 0
    return "ok", content, cjk_len(txt)


# ---------------- MinerU ----------------

class TokenDead(Exception):
    """所有 token 都失效"""


def load_tokens():
    """env MINERU_TOKEN(S) + 可选 MINERU_TOKEN_CONFIG 指向的 config.json tokens，去重保序。

    可移植化（审查修复）：仓库外 config.json 不再硬编码 —— MINERU_TOKEN_CONFIG 为空
    （或文件不存在）时只用 MINERU_TOKEN / MINERU_TOKENS 环境变量。
    """
    toks = [x.strip() for x in os.environ.get("MINERU_TOKEN", "").split(",") if x.strip()]
    toks += [x.strip() for x in os.environ.get("MINERU_TOKENS", "").split(",") if x.strip()]
    cfg_path = os.environ.get("MINERU_TOKEN_CONFIG", "")
    if cfg_path:
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            for x in cfg.get("tokens", []):
                x = x.strip()
                if x and x not in toks:
                    toks.append(x)
        except Exception:
            pass
    # 去重保序
    seen, out = set(), []
    for x in toks:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


TOKENS = load_tokens()
_tok_idx = [0]
_dead_tokens = set()


def run_mineru(pdf_path, out_dir, seq):
    """用当前 token 跑一次；401/403 抛 TokenDead（调用方换 token 重试）。"""
    if _tok_idx[0] >= len(TOKENS):
        raise TokenDead("no live token")
    token = TOKENS[_tok_idx[0]]
    env = dict(os.environ)
    env["MINERU_TOKEN"] = token
    r = subprocess.run(
        [CLI, "extract", pdf_path, "-o", out_dir, "-f", "md",
         "--model", "pipeline", "--language", "ch"],
        capture_output=True, timeout=1200, env=env)
    blob = ((r.stdout or b"") + b"\n" + (r.stderr or b"")).decode("utf-8", errors="replace")
    if re.search(r"\b(40[13])\b", blob) or "unauthorized" in blob.lower() or "token" in blob.lower():
        raise TokenDead(blob[-200:])
    md = os.path.join(out_dir, os.path.splitext(os.path.basename(pdf_path))[0] + ".md")
    if os.path.exists(md):
        return open(md, encoding="utf-8").read()
    raise RuntimeError(blob[-200:] or "no output md")


def next_token():
    """换下一个 token。返回 False = 全部失效。"""
    _dead_tokens.add(TOKENS[_tok_idx[0]])
    for i, tk in enumerate(TOKENS):
        if tk not in _dead_tokens:
            _tok_idx[0] = i
            return True
    return False


def clean_ocr_text(raw):
    """去掉 MinerU md 的图片引用/空标题行，压掉多余空行。"""
    lines = []
    for ln in raw.splitlines():
        s = ln.rstrip()
        if not s.strip():
            if lines and lines[-1].strip():
                lines.append("")
            continue
        if re.match(r"^!\[.*\]\(.*\)$", s.strip()):
            continue
        lines.append(s)
    txt = "\n".join(lines).strip()
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt


def qc(txt):
    c = cjk_len(txt)
    return (c >= 300) or bool(TIAO.search(txt)) or bool(STRUCT.search(txt)), c


# ---------------- md 回写 ----------------

OCR_MARK = "OCR: mineru-pipeline " + TODAY


def att_name(body, pdf_url):
    """从正文附件链接里找显示名。"""
    tail = pdf_url.split("/")[-1].split("?")[0]
    m = re.search(r"\[([^\]]{2,80})\]\([^)]*" + re.escape(tail) + r"\)", body)
    if m:
        return m.group(1).strip()
    return ""


def write_back(md_path, ocr_text, name):
    txt = open(md_path, encoding="utf-8").read()
    m = re.match(r"^(---\n.*?\n---\n)(.*)$", txt, re.S)
    if not m:
        print(f"  !! front matter 解析失败: {md_path}")
        return False
    fm, body = m.group(1), m.group(2)
    changed = False
    if OCR_MARK not in fm:
        fm2 = re.sub(r"(^原文链接:\s*\S+\s*$)", r"\1\n" + OCR_MARK, fm, count=1, flags=re.M)
        if fm2 != fm:
            fm = fm2
            changed = True
    if name and txt.count("## 附件（扫描件 OCR 全文）") >= 1:
        header = f"\n\n## 附件（扫描件 OCR 全文）\n\n**（{name}）**\n\n"
    elif name and "## 附件（扫描件 OCR 全文）" in body:
        header = f"\n\n## 附件（扫描件 OCR 全文）\n\n**（{name}）**\n\n"
    else:
        header = "\n\n## 附件（扫描件 OCR 全文）\n\n"
    new_body = body.rstrip() + header + ocr_text.strip() + "\n"
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(fm + new_body)
    return True


# ---------------- 主流程 ----------------

def main():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(os.path.dirname(PROG), exist_ok=True)
    targets = collect_targets()
    multi = {}
    for md, _u, purl, _k, _h in targets:
        multi[md] = multi.get(md, 0) + 1
    n_multi = sum(1 for v in multi.values() if v > 1)
    print(f"目标附件 {len(targets)} 个，涉及 md {len(multi)} 个（多附件 md {n_multi} 个）", flush=True)

    done, _ = load_progress()
    stats = {"ok": 0, "not_scanned": 0, "download_fail": 0, "ocr_fail": 0,
             "qc_fail": 0, "skipped_resumed": 0, "not_pdf": 0, "pdf_broken": 0}
    seq = 0
    t0 = time.time()
    for md_path, page_url, pdf_url, kind, hint in targets:
        prev = done.get(pdf_url)
        if prev and (prev.get("ocr_done") or prev.get("status") in ("not_scanned", "not_pdf")):
            stats["skipped_resumed"] += 1
            continue
        seq += 1
        short = os.path.basename(md_path)[:40]
        status, content, cjk_tl = download_and_check(pdf_url, page_url)
        if status != "ok":
            stats[status if status in stats else "download_fail"] += 1
            append_progress({"url": page_url, "pdf_url": pdf_url, "scanned": None,
                             "ocr_done": False, "status": status, "ts": time.strftime("%H:%M:%S")})
            print(f"[{seq}] {status}: {pdf_url[:90]}", flush=True)
            continue
        if cjk_tl >= 80:  # 有文本层，非扫描件
            stats["not_scanned"] += 1
            append_progress({"url": page_url, "pdf_url": pdf_url, "scanned": False,
                             "ocr_done": False, "status": "not_scanned", "textlayer_cjk": cjk_tl,
                             "ts": time.strftime("%H:%M:%S")})
            print(f"[{seq}] 有文本层({cjk_tl}字)跳过: {short}", flush=True)
            continue
        # 扫描件 → MinerU
        run_dir = os.path.join(TMP, f"run{seq}")
        os.makedirs(run_dir, exist_ok=True)
        clean_pdf = os.path.join(run_dir, f"ocr{seq:04d}.pdf")
        with open(clean_pdf, "wb") as f:
            f.write(content)
        raw, ok, err = "", False, ""
        for attempt in range(4):  # 含 token 轮换的重试
            try:
                raw = run_mineru(clean_pdf, run_dir, seq)
                ok = True
                break
            except TokenDead as e:
                if next_token():
                    print(f"  token 失效，切换到 #{_tok_idx[0]}", flush=True)
                    continue
                print(f"!! 全部 MINERU_TOKEN 失效，终止: {str(e)[:120]}", flush=True)
                shutil.rmtree(run_dir, ignore_errors=True)
                append_progress({"url": page_url, "pdf_url": pdf_url, "scanned": True,
                                 "ocr_done": False, "status": "token_dead",
                                 "ts": time.strftime("%H:%M:%S")})
                with open(os.path.join(os.path.dirname(PROG), "ocr_summary.json"), "w", encoding="utf-8") as f:
                    json.dump({"stats": stats, "token_dead": True, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False)
                return 2
            except Exception as e:
                err = str(e)[:150]
                print(f"  retry{attempt}: {err[:100]}", flush=True)
                time.sleep(10 * (attempt + 1))
        if not ok:
            stats["ocr_fail"] += 1
            append_progress({"url": page_url, "pdf_url": pdf_url, "scanned": True,
                             "ocr_done": False, "status": "ocr_fail", "error": err,
                             "ts": time.strftime("%H:%M:%S")})
            shutil.rmtree(run_dir, ignore_errors=True)
            print(f"[{seq}] OCR失败: {short} | {err[:80]}", flush=True)
            time.sleep(5)
            continue
        text = clean_ocr_text(raw)
        passed, c = qc(text)
        if not passed:
            stats["qc_fail"] += 1
            append_progress({"url": page_url, "pdf_url": pdf_url, "scanned": True,
                             "ocr_done": False, "status": "qc_fail", "ocr_cjk": c,
                             "ts": time.strftime("%H:%M:%S")})
            shutil.rmtree(run_dir, ignore_errors=True)
            print(f"[{seq}] 质检不过({c}字): {short}", flush=True)
            time.sleep(5)
            continue
        _fm, _atts, _u, body = parse_md(md_path)
        name = att_name(body, pdf_url)
        wrote = write_back(md_path, text, name if multi.get(md_path, 1) > 1 else "")
        stats["ok" if wrote else "ocr_fail"] += 1
        append_progress({"url": page_url, "pdf_url": pdf_url, "scanned": True,
                         "ocr_done": True, "status": "ok", "ocr_cjk": c, "name": name,
                         "md": os.path.relpath(md_path, LIB), "ts": time.strftime("%H:%M:%S")})
        shutil.rmtree(run_dir, ignore_errors=True)
        el = time.time() - t0
        print(f"[{seq}] OK {c}字 {el/60:.0f}min: {short}", flush=True)
        time.sleep(5)  # MinerU 限速
    print("DONE " + json.dumps(stats, ensure_ascii=False), flush=True)
    with open(os.path.join(os.path.dirname(PROG), "ocr_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"stats": stats, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
