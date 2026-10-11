#!/usr/bin/env python3
# ============================================================
# Copyright (c) 2026 Zhu-Guang-Scion <Zhu-Guang-Scion@users.noreply.github.com>
# China_Law 法规库与税务案例库工具链 · github.com/Zhu-Guang-Scion · 水印 CLAW-ZGS-2026
# MIT License（见仓库 LICENSE）；数据不入库，仅元数据索引
# ============================================================
"""docx XML 直抽回退：python-docx 拒收(content-type 非标)的 docx 用这里。

这类文件 zip 结构完整、word/document.xml 存在，但 [Content_Types].xml 声明的
主类型非标准（常见于官方库中 RTF/WordML 转存的 docx），python-docx 会抛
"is not a Word file" —— 直接按 XML 抽 <w:t> 文本即可。
"""
__author__ = "Zhu-Guang-Scion"
__copyright__ = "Copyright (c) 2026 Zhu-Guang-Scion (github.com/Zhu-Guang-Scion), MIT"
import html as _hl
import re
import zipfile

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_WT = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.S)
TIAO_HEAD = re.compile(r"^第[一二三四五六七八九十百千零\d]+条")


def docx_xml_fallback(path):
    try:
        z = zipfile.ZipFile(path)
        names = z.namelist()
        target = "word/document.xml" if "word/document.xml" in names else \
                 next((n for n in names if n.endswith("document.xml")), None)
        if not target:
            return ""
        xml = z.read(target).decode("utf-8", errors="replace")
        out = []
        for para in re.split(r"</w:p>", xml):
            t = _hl.unescape("".join(_WT.findall(para))).strip()
            t = _CTRL.sub("", t)
            if t:
                out.append(("**" + t + "**") if TIAO_HEAD.match(t) else t)
        return "\n\n".join(out)
    except Exception:
        return ""
