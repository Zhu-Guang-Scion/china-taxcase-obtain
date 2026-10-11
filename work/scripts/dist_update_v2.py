# -*- coding: utf-8 -*-
"""把工作区的审查修复同步进 GitHub 分发仓库 china-law-obtain（v2 升级）。

- 水印：版权头插在 shebang/coding 行后；__author__/__copyright__ 插在模块
  docstring 之后（ast 定位 end_lineno，与 tax-case-obtain 修复规范一致）
- 可移植化：CHINALAW_ROOT 环境变量 + 脚本相对定位（dist 布局 scripts/ -> 仓库根，
  比工作区少一层 dirname）；保留 CHINA_LAW_WORK 作为 work 目录覆盖
- 从工作区移植 4 个 E:\\ 硬编码文件（REPO 层级 3->2 改写）
- LF 写盘（仓库 autocrlf=true，统一入库形态）
"""
import ast
import os
import re
import shutil

DIST = r"E:\ai_coding_xiangmu\china-law-obtain"
WORK = r"E:\ai_coding_xiangmu\China_Law\work\scripts"

WATERMARK_HDR = [
    "# ============================================================",
    "# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>",
    "# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026",
    "# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引",
    "# ============================================================",
]
AUTHOR_LINES = [
    '__author__ = "Zhu-Guang-Scion"',
    '__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"',
]

# 工作区(3层dirname) -> 分发(2层dirname) 的 REPO 块
WORK_REPO_BLOCK = """REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))"""
DIST_REPO_BLOCK = """REPO = os.environ.get(
    "CHINALAW_ROOT",
    os.path.normpath(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))"""

UNIFIED_ROOT = """REPO = os.environ.get("CHINALAW_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.environ.get("CHINA_LAW_WORK") or os.path.join(REPO, "work")"""


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def add_watermark(src):
    """水印插入；返回新文本。已含水印的跳过。"""
    if '__author__ = "Zhu-Guang-Scion"' in src:
        return src, False
    lines = src.split("\n")
    # 版权头位置：跳过 shebang 与 coding 声明行
    idx = 0
    while idx < len(lines) and (lines[idx].startswith("#!") or
                                lines[idx].startswith("# -*- coding")):
        idx += 1
    lines[idx:idx] = WATERMARK_HDR
    src2 = "\n".join(lines)
    # __author__ 插到模块 docstring 之后
    try:
        tree = ast.parse(src2)
        body = tree.body
        if body and isinstance(body[0], ast.Expr) and \
                isinstance(body[0].value, ast.Constant) and \
                isinstance(body[0].value.value, str):
            end = body[0].end_lineno  # docstring 结束行(1-based)
            out_lines = src2.split("\n")
            out_lines[end:end] = ["", *AUTHOR_LINES]
            src2 = "\n".join(out_lines)
        else:
            # 无 docstring：版权头后直插
            ins = idx + len(WATERMARK_HDR)
            out_lines = src2.split("\n")
            out_lines[ins:ins] = AUTHOR_LINES
            src2 = "\n".join(out_lines)
    except SyntaxError:
        return src, False
    return src2, True


def unify_paths(src, fname):
    """路径模式统一：返回(新文本, 是否改动)。"""
    changed = False

    # A 模式：ROOT = CHINA_LAW_WORK or cwd/work（含 abspath 包裹变体）
    pat_a = re.compile(
        r'^(?P<var>_?ROOT = )(?P<pre>os\.path\.abspath\()?'
        r'os\.environ\.get\("CHINA_LAW_WORK"\) or os\.path\.join\(os\.getcwd\(\), "work"\)'
        r'\)?$', re.M)
    m = pat_a.search(src)
    if m:
        var = "_ROOT" if m.group("var").startswith("_ROOT") else "ROOT"
        src = src[:m.start()] + UNIFIED_ROOT.replace("\nROOT =", f"\n{var} =") + src[m.end():]
        changed = True

    # B 模式：ROOT = join(dirname(__file__), "..")（1 层，dist 布局下指向仓库根，语义错位）
    pat_b = re.compile(
        r'^ROOT = os\.path\.(?:abspath\()?os\.path\.join\('
        r'os\.path\.dirname\(__file__\), "\.\."'
        r'\)\)?$', re.M)
    if pat_b.search(src) and "CHINALAW_ROOT" not in src:
        src = pat_b.sub(UNIFIED_ROOT, src, count=1)
        changed = True
    return src, changed


def port_from_work(fname):
    """从工作区移植（E:\\ 硬编码的 4 个文件），REPO 层级 3->2。"""
    src = read(os.path.join(WORK, fname))
    if WORK_REPO_BLOCK in src:
        src = src.replace(WORK_REPO_BLOCK, DIST_REPO_BLOCK)
    # fgk_search 的 sys.path 硬编码工作区版已修好（相对本文件），无需改
    return src


def main():
    scripts = sorted(f for f in os.listdir(os.path.join(DIST, "scripts"))
                     if f.endswith(".py"))
    stats = {"wm": [], "path": [], "ported": [], "skip": []}
    for fn in scripts:
        dp = os.path.join(DIST, "scripts", fn)
        orig = read(dp)

        if "E:\\ai_coding_xiangmu" in orig or "E:/ai_coding_xiangmu" in orig:
            src = port_from_work(fn)
            stats["ported"].append(fn)
        else:
            src = orig

        src, ch_path = unify_paths(src, fn)
        if ch_path:
            stats["path"].append(fn)
        src, ch_wm = add_watermark(src)
        if ch_wm:
            stats["wm"].append(fn)

        ast.parse(src)  # 语法校验，坏则抛异常
        if src != orig:
            write(dp, src)
        else:
            stats["skip"].append(fn)

    print("ported(E:\\修复):", stats["ported"])
    print("path(路径统一):", stats["path"])
    print("watermark:", len(stats["wm"]), "个")
    print("unchanged:", stats["skip"])


if __name__ == "__main__":
    main()
