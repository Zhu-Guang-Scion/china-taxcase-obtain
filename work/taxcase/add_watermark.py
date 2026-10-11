# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""开源水印工具：给全部已提交文件加 Zhu-Guang-Scion 作者水印（幂等）。
- .py   : coding 行之后插入版权头；__author__/__copyright__ 插在模块 docstring
         之后（放在 docstring 前会让 __doc__ 失效 —— 审查修复）
- .json : 追加 _copyright 键（加载器只读已知键，安全）
- .md   : 文末追加署名分隔线（已含署名则跳过）
- LICENSE / README 单独处理
"""
import os, re, io, sys, json

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GH = "Zhu-Guang-Scion"
GHURL = "github.com/Zhu-Guang-Scion"
MARK = "CLAW-ZGS-2026"

PY_HDR = (
    "# ============================================================\n"
    f"# Copyright (c) 2026 {GH} <{GH}@users.noreply.github.com>\n"
    f"# China_Law 法规库与税务案例库工具链 · {GHURL} · 水印 {MARK}\n"
    "# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引\n"
    "# ============================================================\n"
)
PY_ATTR = f'__author__ = "{GH}"\n__copyright__ = "Copyright (c) 2026 {GH} ({GHURL}), MIT"\n'
MD_FOOT = (f"\n\n---\n\n> 记录与代码作者：{GH} · {GHURL} · {MARK} · MIT\n")
JSON_KEY = {"_copyright": f"(c) 2026 {GH} ({GHURL}), MIT, {MARK}"}


def _insert_after_docstring(src, block):
    """把 block（无换行的文本行）插到模块 docstring 之后（审查修复：
    __author__/__copyright__ 若放在 docstring 之前会让 __doc__ 失效）。
    无 docstring 时退化为插在文件头部注释区之后的 body 首行之前。"""
    import ast
    tree = ast.parse(src)
    lines = src.split("\n")
    if (tree.body and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        end = tree.body[0].end_lineno  # docstring 结束行（1-based）
        return "\n".join(lines[:end] + [block.rstrip("\n")] + lines[end:])
    return block + src


def wm_py(p):
    src = open(p, encoding="utf-8").read()
    if MARK in src:
        return False
    lines = src.split("\n")
    i = 0
    if lines and lines[0].startswith("#!"):
        i = 1
    # 跳过 coding 行与 docstring 前 3 行内的情况：只在 coding 行后插
    if i < len(lines) and re.match(r"# -\*- coding", lines[i]):
        i += 1
    # 已有 __author__ 的不重复加属性
    attr = "" if f"__author__" in src else PY_ATTR
    # 版权头放 coding 行后、docstring 前；
    # __author__/__copyright__ 属性放模块 docstring 之后（保住 __doc__）
    out = "\n".join(lines[:i]) + "\n" + PY_HDR + "\n".join(lines[i:])
    if attr:
        out = _insert_after_docstring(out, attr)
    open(p, "w", encoding="utf-8", newline="\n").write(out)
    return True


def wm_json(p):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(d, dict) or d.get("_copyright"):
        return False
    d["_copyright"] = JSON_KEY["_copyright"]
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return True


def wm_md(p):
    src = open(p, encoding="utf-8").read()
    if MARK in src or "Zhu-Guang-Scion" in src:
        return False
    open(p, "a", encoding="utf-8").write(MD_FOOT)
    return True


def main():
    import subprocess
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                           encoding="utf-8", cwd=ROOT).stdout.split("\n")
    n = {"py": 0, "json": 0, "md": 0}
    for rel in files:
        if not rel.strip():
            continue
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        try:
            if rel.endswith(".py"):
                n["py"] += wm_py(p)
            elif rel.endswith(".json"):
                n["json"] += wm_json(p)
            elif rel.endswith(".md") and rel not in ("README.md", "LICENSE"):
                n["md"] += wm_md(p)
        except Exception as e:
            print("ERR", rel, str(e)[:60])
    print(f"水印完成: py+{n['py']} json+{n['json']} md+{n['md']}")


if __name__ == "__main__":
    main()
