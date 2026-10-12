# -*- coding: utf-8 -*-
"""LLM 语义审查预分桶器（R11）
按「时效风险 × 实质性风险」规则从全库筛出需 LLM 甄别的文件，切成批次 JSONL。
桶规则（放宽以覆盖用户关切）：
  A 批复/函件/答复：date < 2021-01-01（老函件适用性存疑——多批废止清理）
  B 12366 问答/流程/表单：date < 2019-01-01（个税改革/营改增前口径）
  C 媒体/专栏/课程书籍/国际税收案例/风险提示：全部（机械宣传风险）
  D 案例类（处罚/失信/通报/合规）：date < 2018-01-01（历史口径标注审）
  E 裁判文书：全部 2012-2021 停更时代（历史口径标注审，删意极低）
每条目：{path, region, column, date, title, excerpt(front matter 后正文前 1300 字)}
"""
import os, re, json, sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", "lawlibrary", "专题/税务案例"))
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_review")
os.makedirs(OUT_DIR, exist_ok=True)
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def fm_get(fml, key):
    m = re.search(rf"^{key}:\s*\"?([^\"\n]*)\"?", fml, re.M)
    return m.group(1).strip() if m else ""


def bucket_of(column, date):
    has = lambda *ks: any(k in column for k in ks)
    if has("批复", "税函", "答复"):
        return "A" if date and date < "2021-01-01" else None
    if "12366" in column:
        return "B" if date and date < "2019-01-01" else None
    if has("媒体", "专栏", "课程与书籍", "国际税收", "风险提示", "评析"):
        return "C"
    if has("裁判文书"):
        return "E"
    # D：案例类老文件
    if date and date < "2018-01-01":
        return "D"
    return None


def main():
    entries = []
    for dp, _, fs in os.walk(ROOT):
        for fn in sorted(fs):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            txt = open(p, encoding="utf-8").read()
            m = FM_RE.match(txt)
            if not m:
                continue
            fml = m.group(1)
            col, reg = fm_get(fml, "栏目"), fm_get(fml, "地区")
            date = fm_get(fml, "发布日期") or fm_get(fml, "判决日期") or ""
            date = date[:10]
            b = bucket_of(col, date)
            if not b:
                continue
            body = txt[m.end():]
            excerpt = re.sub(r"\s+", " ", body)[:1300]
            entries.append({"bucket": b, "path": os.path.relpath(p, ROOT),
                            "region": reg, "column": col, "date": date,
                            "title": fm_get(fml, "title")[:80], "excerpt": excerpt})
    # 排序分批：桶内按路径稳定排序，每批 400
    entries.sort(key=lambda e: (e["bucket"], e["path"]))
    BATCH = 400
    n = 0
    for i in range(0, len(entries), BATCH):
        n += 1
        with open(os.path.join(OUT_DIR, f"batch_{n:02d}.jsonl"), "w", encoding="utf-8") as f:
            for e in entries[i:i + BATCH]:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    from collections import Counter
    c = Counter(e["bucket"] for e in entries)
    print(f"待审总数 {len(entries)} | 批次 {n} | 桶分布 {dict(sorted(c.items()))}")
    print("A=批复函件<2021  B=12366<2019  C=媒体课程全量  D=案例<2018  E=裁判文书全量")


if __name__ == "__main__":
    main()
