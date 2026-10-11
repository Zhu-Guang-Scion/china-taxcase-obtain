#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""补充下载仍现行有效的早期批次应用指南（2017批3项 + 2019批4项），并登记不可得项。"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import gov_download as gd

# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量
REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
OUT_DIR = os.path.join(REPO, "work", "downloads", "standards", "执业准则")
LIST_OUT = os.path.join(REPO, "work", "lists", "standards_执业准则.jsonl")

B2017 = "https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201703/t20170320_60608.html"
B2019 = "https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201904/t20190410_60613.html"

# 仍现行（未被2021/2022/2023批次取代）的早期批次指南
EXTRA = [
    # (pdf url, full title, guide year, batch notice url, note)
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201703/W020210421541525183910.pdf",
     "《中国注册会计师审计准则第1331号——首次审计业务涉及的期初余额》应用指南", "2017", B2017,
     "会协〔2017〕11号批次，未被后续批次取代，仍现行"),
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201703/W020210421541525199522.pdf",
     "《中国注册会计师审计准则第1332号——期后事项》应用指南", "2017", B2017,
     "会协〔2017〕11号批次，未被后续批次取代，仍现行"),
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201703/W020210421541525221072.pdf",
     "《中国注册会计师审计准则第1511号——比较信息：对应数据和比较财务报表》应用指南", "2017", B2017,
     "会协〔2017〕11号批次，未被后续批次取代，仍现行"),
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201904/W020210421541566910688.pdf",
     "《中国注册会计师审计准则第1153号——前任注册会计师和后任注册会计师的沟通》应用指南", "2019", B2019,
     "会协〔2019〕13号批次，未被后续批次取代，仍现行"),
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201904/W020210421541566957063.pdf",
     "《中国注册会计师审计准则第1221号——计划和执行审计工作时的重要性》应用指南", "2019", B2019,
     "会协〔2019〕13号批次，未被后续批次取代，仍现行"),
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201904/W020210421541567056172.pdf",
     "《中国注册会计师审计准则第1502号——在审计报告中发表非无保留意见》应用指南", "2019", B2019,
     "会协〔2019〕13号批次，未被后续批次取代，仍现行"),
    ("https://www.cicpa.org.cn/ztzl1/Professional_standards/Professional_guidelines/yifabu/201904/W020210421541567063997.pdf",
     "《中国注册会计师审计准则第1503号——在审计报告中增加强调事项段和其他事项段》应用指南", "2019", B2019,
     "会协〔2019〕13号批次，未被后续批次取代，仍现行"),
]

NOTE_ONLY = [
    {"title": "《中国注册会计师审计准则第1612号——银行间函证程序》应用指南",
     "url": "", "note": "源自会协〔2010〕94号38项应用指南批次，未被后续批次废止但原文附件未在中注协现行网站留存，官网应用指南栏目现为空，无法取得"},
    {"title": "《中国注册会计师审计准则第1613号——与银行监管机构的关系》应用指南",
     "url": "", "note": "源自会协〔2010〕94号批次，官网未留存附件，无法取得"},
    {"title": "《中国注册会计师审计准则第1632号——衍生金融工具的审计》应用指南",
     "url": "", "note": "源自会协〔2010〕94号批次，官网未留存附件，无法取得"},
    {"title": "《中国注册会计师其他鉴证业务准则第3101号——历史财务信息审计或审阅以外的鉴证业务》应用指南",
     "url": "", "note": "源自会协〔2010〕94号批次，官网未留存附件，无法取得"},
]


def main():
    s = gd.make_session()
    recs = []
    for url, title, year, src, note in EXTRA:
        m = re.search(r"第(\d+)号", title)
        fname = gd.sanitize(f"执业准则_应用指南_审计准则第{m.group(1)}号_{year}.pdf")
        fp = os.path.join(OUT_DIR, fname)
        rec = {"title": title.strip("《》"), "doc_no": "", "date": year, "url": url,
               "file": fname, "source": src, "cat": "应用指南", "series": "审计准则",
               "no": f"第{m.group(1)}号", "note": note, "status": ""}
        if os.path.exists(fp) and os.path.getsize(fp) > 10000:
            rec["status"] = "ok"
        else:
            for attempt in range(4):
                try:
                    r = s.get(url, timeout=90)
                    if r.status_code == 200 and b"%PDF" in r.content[:1024] and len(r.content) > 50000:
                        with open(fp, "wb") as f:
                            f.write(r.content)
                        rec["status"] = "ok"
                        rec["bytes"] = len(r.content)
                        break
                    raise RuntimeError(f"http {r.status_code} len={len(r.content)}")
                except Exception as e:
                    rec["error"] = str(e)
                    time.sleep(1.5 * (attempt + 1) + random.random())
            if rec["status"] != "ok":
                rec["status"] = "fail"
        print(f"[{rec['status']}] {fname}")
        time.sleep(0.6 + random.random() * 0.4)
        recs.append(rec)
    for n in NOTE_ONLY:
        recs.append({"title": n["title"], "doc_no": "", "date": "", "url": n["url"],
                     "file": "", "source": "cicpa.org.cn", "cat": "应用指南",
                     "series": "审计准则", "no": "", "note": n["note"],
                     "status": "not_found"})
    with open(LIST_OUT, "a", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("appended", len(recs))


if __name__ == "__main__":
    main()
