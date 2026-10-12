# -*- coding: utf-8 -*-
"""R11 处置器：应用子智能体 verdicts
- DEL → 移入隔离区 work/taxcase/llm_quarantine/<relpath>（可回滚，非物理删除）
- TAG → front matter「抓取日期」行后插「时效提示: 历史口径（<reason>）」
- KEEP → 不动；缺 verdict 的条目按 KEEP 处理并记录
用法： python llm_review_apply.py [--dry]
"""
import os, re, json, argparse, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "lawlibrary", "专题", "税务案例"))
REV_DIR = os.path.join(HERE, "llm_review")
QUAR = os.path.join(HERE, "llm_quarantine")
LOG = os.path.join(HERE, "llm_review", "apply_log.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    verdicts = {}
    for fn in sorted(os.listdir(REV_DIR)):
        if fn.startswith("verdicts_") and fn.endswith(".jsonl"):
            for line in open(os.path.join(REV_DIR, fn), encoding="utf-8"):
                try:
                    v = json.loads(line)
                    verdicts[v["path"]] = (v.get("verdict", "KEEP"), v.get("reason", ""))
                except json.JSONDecodeError:
                    pass
    # 批次全集（含缺 verdict 条目）
    all_paths = set()
    for fn in sorted(os.listdir(REV_DIR)):
        if fn.startswith("batch_") and fn.endswith(".jsonl"):
            for line in open(os.path.join(REV_DIR, fn), encoding="utf-8"):
                try:
                    all_paths.add(json.loads(line)["path"])
                except json.JSONDecodeError:
                    pass
    from collections import Counter
    cnt = Counter()
    log = open(LOG, "a", encoding="utf-8")
    for rel in sorted(all_paths):
        p = os.path.join(ROOT, rel)
        v, reason = verdicts.get(rel, ("KEEP", "无verdict按KEEP"))
        cnt[v] += 1
        if v == "DEL":
            if args.dry:
                continue
            dst = os.path.join(QUAR, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(p, dst)
        elif v == "TAG":
            if args.dry:
                continue
            txt = open(p, encoding="utf-8").read()
            if "时效提示:" in txt[:2000]:
                continue
            new = txt.replace("抓取日期:", f"时效提示: 历史口径（{reason[:40]}）\n抓取日期:", 1)
            if new == txt:  # 无抓取日期行则在原文链接行后插
                new = txt.replace("原文链接:", f"时效提示: 历史口径（{reason[:40]}）\n原文链接:", 1)
            open(p, "w", encoding="utf-8", newline="\n").write(new)
        log.write(json.dumps({"path": rel, "verdict": v, "reason": reason},
                             ensure_ascii=False) + "\n")
    log.close()
    print(f"处置 {sum(cnt.values())} 件：{dict(cnt)}  （DEL 已隔离至 llm_quarantine/，可回滚）")


if __name__ == "__main__":
    main()
