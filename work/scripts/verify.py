#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""校验套件：数量对账 + 文件完整性 + 抽样内容校验 + 镜像交叉核验。

用法:
  python verify.py counts      # 各源数量对账
  python verify.py integrity   # 全部下载文件完整性(docx zip/pdf头/大小)
  python verify.py sample      # 抽样内容校验(标题匹配/条款计数/实质长度)
  python verify.py cross       # 镜像交叉核验(LawRefBook/HF parquet/lawtext)
  python verify.py manifest    # 生成最终 manifest (csv + json, 含sha256)
  python verify.py all
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import csv
import glob
import hashlib
import io
import json
import os
import random
import re
import sys
import zipfile
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
LISTS = os.path.join(ROOT, "lists")
FLK_DL = os.path.join(ROOT, "downloads", "flk")
GOV_DL = os.path.join(ROOT, "downloads", "gov")
VERIFY = os.path.join(ROOT, "verify")
MIRRORS = os.path.abspath(os.path.join(ROOT, "..", "mirrors"))
os.makedirs(VERIFY, exist_ok=True)

FLK_CATS = ["宪法", "法律", "行政法规", "监察法规", "地方法规", "司法解释"]
GOV_CATS = ["部门规章", "地方政府规章"]


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def load_progress(cat):
    """flk 进度: bbbs -> 最新记录"""
    recs = load_jsonl(os.path.join(LISTS, f"flk_dl_progress_{cat}.jsonl"))
    latest = {}
    for r in recs:
        latest[r["bbbs"]] = r
    return latest


def load_gov_progress(cat):
    recs = load_jsonl(os.path.join(LISTS, f"gov_dl_progress_{cat}.jsonl"))
    latest = {}
    for r in recs:
        latest[r["url"]] = r
    return latest


# ── 1. 数量对账 ─────────────────────────────────────────────
def stage_counts():
    report = {"flk": {}, "gov": {}}
    for cat in FLK_CATS:
        items = load_jsonl(os.path.join(LISTS, f"flk_{cat}.jsonl"))
        prog = load_progress(cat)
        ok_cnt = sum(1 for r in prog.values() if r.get("ok"))
        official = sum(1 for r in prog.values() if r.get("ok") and r.get("source") != "lawtext")
        mirror = ok_cnt - official
        files = len(glob.glob(os.path.join(FLK_DL, cat, "*.docx"))) + \
                len(glob.glob(os.path.join(FLK_DL, cat, "*.pdf")))
        report["flk"][cat] = {
            "清单条数": len(items),
            "进度ok": ok_cnt,
            "官方API下载": official,
            "镜像补齐": mirror,
            "磁盘文件数": files,
            "缺口": len(items) - ok_cnt,
        }
    for cat in GOV_CATS:
        items = load_jsonl(os.path.join(LISTS, f"gov_{cat}.jsonl"))
        prog = load_gov_progress(cat)
        ok_cnt = sum(1 for r in prog.values() if r.get("ok"))
        files = len(glob.glob(os.path.join(GOV_DL, cat, "*.docx")))
        report["gov"][cat] = {
            "清单条数": len(items),
            "进度ok": ok_cnt,
            "磁盘docx数": files,
            "缺口": len(items) - ok_cnt,
        }
    # 官方 aggregateData 对照
    agg_path = os.path.join(LISTS, "aggregateData.json")
    if os.path.exists(agg_path):
        agg = json.load(open(agg_path, encoding="utf-8"))
        report["官方aggregateData"] = agg
    else:
        try:
            import requests as rq
            s = rq.Session()
            s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            s.get("https://flk.npc.gov.cn/", timeout=15)
            j = s.get("https://flk.npc.gov.cn/law-search/index/aggregateData", timeout=15).json()
            counts = {c["key"]: c["count"] for c in j.get("data", {}).get("flflCount", [])}
            json.dump(counts, open(agg_path, "w", encoding="utf-8"), ensure_ascii=False)
            report["官方aggregateData"] = counts
        except Exception as e:
            report["官方aggregateData"] = f"获取失败: {e}"
    out = os.path.join(VERIFY, "counts_report.json")
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {out}")
    return report


# ── 2. 文件完整性 ───────────────────────────────────────────
def check_docx(path):
    try:
        size = os.path.getsize(path)
        if size < 2000:
            return "太小"
        with zipfile.ZipFile(path) as z:
            if "word/document.xml" not in z.namelist():
                return "缺document.xml"
            xml = z.read("word/document.xml")
            if len(xml) < 500:
                return "document.xml过小"
        return "ok"
    except zipfile.BadZipFile:
        return "坏zip"
    except Exception as e:
        return f"异常:{type(e).__name__}"


def check_pdf(path):
    try:
        size = os.path.getsize(path)
        if size < 5000:
            return "太小"
        with open(path, "rb") as f:
            head = f.read(5)
        if head != b"%PDF-":
            return "非PDF头"
        return "ok"
    except Exception as e:
        return f"异常:{type(e).__name__}"


def stage_integrity():
    result = {}
    total_bad = 0
    for base, cats in [(FLK_DL, FLK_CATS), (GOV_DL, GOV_CATS)]:
        for cat in cats:
            d = os.path.join(base, cat)
            files = sorted(glob.glob(os.path.join(d, "*.docx")) + glob.glob(os.path.join(d, "*.pdf")))
            stats = Counter()
            bad_examples = []
            for fp in files:
                r = check_pdf(fp) if fp.endswith(".pdf") else check_docx(fp)
                stats[r] += 1
                if r != "ok":
                    total_bad += 1
                    if len(bad_examples) < 10:
                        bad_examples.append({"file": os.path.basename(fp), "问题": r})
            result[f"{base.endswith('flk') and 'flk' or 'gov'}/{cat}"] = {
                "文件数": len(files),
                **dict(stats),
                "坏例": bad_examples,
            }
    out = os.path.join(VERIFY, "integrity_report.json")
    json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != '坏例'} for k, v in result.items()},
                     ensure_ascii=False, indent=2))
    print(f"损坏文件总数: {total_bad} -> {out}")
    return result


# ── 3. 抽样内容校验 ─────────────────────────────────────────
def docx_text(path, max_chars=200000):
    from docx import Document
    try:
        doc = Document(path)
        parts = []
        for p in doc.paragraphs:
            parts.append(p.text)
            if sum(len(x) for x in parts) > max_chars:
                break
        return "\n".join(parts)
    except Exception:
        # 回退: 直接读 xml
        try:
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
                return re.sub(r"<[^>]+>", "", xml)
        except Exception:
            return ""


def norm_title(t):
    t = re.sub(r'[《》〈〉\s（）()\-—_",.。·、:：;；!！?？]', "", t or "")
    return t


TIAO_RE = re.compile(r"第([一二三四五六七八九十百千零\d]+)条")


def cn_num_to_int(s):
    mapping = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
               "八": 8, "九": 9}
    if s.isdigit():
        return int(s)
    # 简易中文数字转换（支持到千）
    total, num, sect = 0, 0, 0
    unit_map = {"十": 10, "百": 100, "千": 1000}
    for ch in s:
        if ch in mapping:
            num = mapping[ch]
        elif ch in unit_map:
            u = unit_map[ch]
            if num == 0:
                num = 1
            sect += num * u
            num = 0
        else:
            return None
    return total + sect + num


def stage_sample(n_per_cat=40):
    random.seed(20261008)
    result = {}
    all_pass = 0
    all_total = 0
    for base, cats, kind in [(FLK_DL, FLK_CATS, "flk"), (GOV_DL, GOV_CATS, "gov")]:
        for cat in cats:
            d = os.path.join(base, cat)
            files = sorted(glob.glob(os.path.join(d, "*.docx")))
            if not files:
                result[f"{kind}/{cat}"] = {"抽样": 0}
                continue
            sample = random.sample(files, min(n_per_cat, len(files)))
            checks = []
            for fp in sample:
                fn = os.path.basename(fp)
                text = docx_text(fp)
                title_part = norm_title(fn.split("_")[1] if "_" in fn else fn)
                tnorm = norm_title(text[:3000])
                title_hit = title_part[:20] in tnorm if title_part else False
                tiaos = TIAO_RE.findall(text)
                max_tiao = max((cn_num_to_int(t) or 0 for t in tiaos), default=0)
                tiao_count = len(tiaos)
                cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
                ok = (title_hit and cjk >= 150 and (tiao_count >= 1 or cjk >= 600)) or \
                     (tiao_count >= 20 and cjk >= 1000)
                checks.append({"file": fn, "标题命中": title_hit, "正文字数": cjk,
                               "条数": tiao_count, "最大条号": max_tiao, "通过": ok})
                all_total += 1
                all_pass += 1 if ok else 0
            passed = sum(1 for c in checks if c["通过"])
            result[f"{kind}/{cat}"] = {
                "抽样": len(checks), "通过": passed,
                "通过率": f"{passed/len(checks)*100:.0f}%",
                "不通过明细": [c for c in checks if not c["通过"]][:8],
            }
    summary = {"总抽样": all_total, "总通过": all_pass,
               "总通过率": f"{all_pass/max(all_total,1)*100:.1f}%"}
    out = os.path.join(VERIFY, "sample_report.json")
    json.dump({"summary": summary, "detail": result}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))
    for k, v in result.items():
        print(f"  {k}: {v.get('抽样',0)} 抽样, 通过 {v.get('通过',0)} ({v.get('通过率','-')})")
    print(f"-> {out}")
    return {"summary": summary, "detail": result}


# ── 4. 镜像交叉核验 ─────────────────────────────────────────
def stage_cross(sample_n=60):
    random.seed(20261008)
    out = {}

    # 4a. LawRefBook: 国家级法律/行政法规 md 条数 vs 我们 docx 条数
    lrb = os.path.join(MIRRORS, "Laws")
    if os.path.isdir(lrb):
        md_files = glob.glob(os.path.join(lrb, "**", "*.md"), recursive=True)
        out["LawRefBook"] = {"md总数": len(md_files)}
        # 用文件名匹配我们的法律/行政法规样本
        our_files = glob.glob(os.path.join(FLK_DL, "法律", "*.docx")) + \
                    glob.glob(os.path.join(FLK_DL, "行政法规", "*.docx"))
        random.shuffle(our_files)
        matched, tiao_equal, tiao_diff = 0, 0, []
        for fp in our_files[:sample_n]:
            fn = os.path.basename(fp)
            title = fn.split("_")[1] if "_" in fn else fn
            core = re.sub(r"（.*?）|\(.*?\)", "", title)
            hits = [m for m in md_files if core[:18] in os.path.basename(m)]
            if not hits:
                continue
            matched += 1
            md = open(hits[0], encoding="utf-8").read()
            md_tiao = TIAO_RE.findall(md)
            our_text = docx_text(fp)
            our_tiao = TIAO_RE.findall(our_text)
            md_max = max((cn_num_to_int(t) or 0 for t in md_tiao), default=0)
            our_max = max((cn_num_to_int(t) or 0 for t in our_tiao), default=0)
            if md_max and our_max and abs(md_max - our_max) <= 1:
                tiao_equal += 1
            else:
                tiao_diff.append({"file": fn, "md条": md_max, "docx条": our_max})
        out["LawRefBook"]["匹配样本"] = matched
        out["LawRefBook"]["条数一致"] = tiao_equal
        out["LawRefBook"]["条数差异例"] = tiao_diff[:10]
    else:
        out["LawRefBook"] = "未clone"

    # 4b. HF parquet: 标题集合对比（2023-09快照 vs 我们2026-10清单，只看法律/行政法规）
    pq = os.path.join(MIRRORS, "law_full.parquet")
    if os.path.exists(pq):
        import pandas as pd
        df = pd.read_parquet(pq)
        for cat, hf_types in [("法律", ["法律", "法律解释", "有关法律问题和重大问题的决定"]),
                              ("行政法规", ["行政法规"])]:
            ours = {norm_title(r["title"]) for r in load_jsonl(os.path.join(LISTS, f"flk_{cat}.jsonl"))}
            hf_eff = set(df[(df["type"].isin(hf_types)) & (df["status"] == "有效")]["title"].map(norm_title))
            both = ours & hf_eff
            only_ours = ours - hf_eff
            only_hf = hf_eff - ours
            out[f"HF对比_{cat}"] = {
                "我们有效": len(ours), "HF有效(2023-09)": len(hf_eff),
                "交集": len(both), "仅我们有(2023后有/口径差)": len(only_ours),
                "仅HF有(可能已废止/替换)": len(only_hf),
                "仅HF例": sorted(only_hf)[:8],
            }
    else:
        out["HF对比"] = "parquet 未下载"

    # 4c. lawtext regulations md: bbbs 覆盖率（针对地方法规清单）
    regs = os.path.join(MIRRORS, "regulations", "content")
    if os.path.isdir(regs):
        md_ids = {os.path.splitext(os.path.basename(p))[0]
                  for p in glob.glob(os.path.join(regs, "**", "*.md"), recursive=True)}
        items = load_jsonl(os.path.join(LISTS, "flk_地方法规.jsonl"))
        hit = sum(1 for it in items if it["bbbs"] in md_ids)
        out["lawtext_regulations覆盖"] = {
            "镜像md总数": len(md_ids), "我们地方法规清单": len(items),
            "bbbs命中": hit, "覆盖率": f"{hit/len(items)*100:.1f}%",
        }
    else:
        out["lawtext_regulations覆盖"] = "未clone"

    json.dump(out, open(os.path.join(VERIFY, "cross_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


# ── 5. manifest ─────────────────────────────────────────────
def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def stage_manifest():
    rows = []
    for cat in FLK_CATS:
        items = load_jsonl(os.path.join(LISTS, f"flk_{cat}.jsonl"))
        prog = load_progress(cat)
        # 文件索引: bbbs 不在文件名里，按 file 字段从进度取
        by_file = {}
        for r in prog.values():
            if r.get("ok") and r.get("file"):
                by_file[r["file"]] = r
        d = os.path.join(FLK_DL, cat)
        disk = {os.path.basename(p): p for p in
                glob.glob(os.path.join(d, "*.docx")) + glob.glob(os.path.join(d, "*.pdf"))}
        for it in items:
            bbbs = it["bbbs"]
            r = prog.get(bbbs, {})
            fp = disk.get(r.get("file", "")) if r.get("file") else None
            if not fp:
                # 兜底: 尝试按命名规则找
                guess = re.sub(r'[\\/:*?"<>|]', "_",
                               f"{it.get('flxz') or cat}_{it['title']}_{it.get('gbrq','')}_有效") + ".docx"
                fp = disk.get(guess)
            status = "已下载"
            src = r.get("source", "官方API" if r.get("ok") else "")
            size = sha = ""
            if fp and os.path.exists(fp):
                size = os.path.getsize(fp)
                sha = sha256_file(fp)
            elif r.get("ok"):
                status = "进度ok但文件缺失"
            else:
                status = f"未下载:{r.get('error','未尝试')[:60]}"
            rows.append({
                "库": "国家法律法规数据库", "类别": cat, "标题": it["title"],
                "公布日期": it.get("gbrq", ""), "施行日期": it.get("sxrq", ""),
                "制定机关": it.get("zdjgName", ""), "bbbs": bbbs,
                "时效性": "有效", "状态": status, "来源": src,
                "文件": os.path.basename(fp) if fp else "",
                "大小": size, "sha256": sha,
                "官方链接": f"https://flk.npc.gov.cn/detail?id={bbbs}",
            })
    for cat in GOV_CATS:
        items = load_jsonl(os.path.join(LISTS, f"gov_{cat}.jsonl"))
        prog = load_gov_progress(cat)
        d = os.path.join(GOV_DL, cat)
        disk = {os.path.basename(p): p for p in glob.glob(os.path.join(d, "*.docx"))}
        for it in items:
            r = prog.get(it["url"], {})
            fp = disk.get(r.get("file", "")) if r.get("file") else None
            status = "已下载" if (fp and os.path.exists(fp)) else (
                f"未下载:{r.get('error','未尝试')[:60]}" if not r.get("ok") else "进度ok但文件缺失")
            size = sha = ""
            if fp and os.path.exists(fp):
                size = os.path.getsize(fp)
                sha = sha256_file(fp)
            rows.append({
                "库": "国家规章库", "类别": cat, "标题": it["title"],
                "公布日期": it.get("date", ""), "施行日期": "",
                "制定机关": it.get("org", ""), "bbbs": "",
                "时效性": "有效(规章库仅收录现行)", "状态": status,
                "来源": "gov.cn详情页HTML转docx",
                "文件": os.path.basename(fp) if fp else "",
                "大小": size, "sha256": sha,
                "官方链接": it["url"],
            })
    csv_path = os.path.join(VERIFY, "manifest.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    stats = Counter(r["状态"].split(":")[0] for r in rows)
    summary = {"总条目": len(rows), **dict(stats)}
    json.dump({"summary": summary},
              open(os.path.join(VERIFY, "manifest_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False))
    print(f"-> {csv_path}")
    return summary


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("counts", "all"):
        stage_counts()
    if stage in ("integrity", "all"):
        stage_integrity()
    if stage in ("sample", "all"):
        stage_sample()
    if stage in ("cross", "all"):
        stage_cross()
    if stage in ("manifest", "all"):
        stage_manifest()


if __name__ == "__main__":
    main()
