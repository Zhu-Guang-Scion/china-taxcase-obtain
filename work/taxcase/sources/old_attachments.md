# 老格式附件提取（.doc / .xlsx / .xls）实录

> 2026-10-10 第三轮补全。第一轮建库时 .doc 老二进制与 .xlsx 明细表被标「二进制格式未提取」，
> 本轮全量下载并提取回填。**零安装**：Word COM（pywin32 已有）+ openpyxl（已有）+ Excel COM。

## 结果

| 项 | 数 |
|---|---|
| 清点（待提取附件） | **101 个**（.doc 71 + .xlsx 29 + .xls 1），分布在 **85 个 md** |
| 下载 | 101/101（`taxcase_scrape.polite_get`，1.6s 限速，0 失败） |
| 提取成功 | **100**；失败 1（江苏连云港一 .doc 链接已死，返回 144B 脚本页） |
| 回写 | **84 个 md、100 个附件节**（69 md×1 节、14 md×2 节、1 md×3 节） |
| Word COM | 顺利：68 个 OLE .doc + 2 个**伪装成 .doc 的 RTF** 全部提出（Office 16.0） |

## 附件分布（本轮清点）

| 来源 | 站点 | 数量 | 内容 |
|---|---|---|---|
| 广东东莞·文书送达公告 | guangdong.chinatax.gov.cn | 82 | 《税务处理决定书》.doc + 发票明细表 .xlsx/.xls |
| 江苏·苏州工业园区处罚送达公告 | jiangsu.chinatax.gov.cn | 19 | 公告送达纳税人名单 .xlsx（downfile.jsp 通道） |

另有 405 个 .doc 链接第一轮已用 Word COM 提过（江苏 15 市局），本轮跳过。

## 真实文件类型（魔数 sniff，别信扩展名）

| 魔数 | 扩展名 | 实际 | 处理 | 数量 |
|---|---|---|---|---|
| OLE `D0CF11E0` | .doc | Word 97 老格式 | **Word COM** | 68 |
| `{tf` | .doc | **RTF** | Word COM 照样能开 | 2 |
| PK | .xlsx | xlsx | **openpyxl** | 29 |
| OLE | .xls | Excel 97 | **Excel COM**（`Excel.Application` UsedRange） | 1 |
| BOM+`<script>` | .doc | 死链错误页 | 记失败 | 1 |

## 方法要点（脚本在 `work/taxcase/tmp/old_att/`，断点 `progress/old_att.jsonl` + `old_att_write.jsonl`）

1. **清点**（inventory_scan.py）：全库 8,056 md 正则扫 `.doc|.xlsx|.xls` 链接；
   「已提取」判定 = 文中有 `## 附件（doc 全文）` 节且无「未提取」标记。
2. **下载**（download.py）：polite_get + 魔数落盘到 `tmp/old_att/files/`（提取完已删，md-only 库）。
3. **提取**（extract.py）：
   - Word COM：`Documents.Open(ReadOnly=True, ConfirmConversions=False, AddToRecentFiles=False)`，
     `Content.Text` + 逐表 `Table.Range.Text`，`\r/\x07/\x0b`→`\n`，3+ 连续空行折叠；>40 字才算成功。
   - openpyxl：`data_only=True` 逐 sheet → markdown 表（首行作表头），≤500 行×40 列，
     合并单元格列在 `> 合并单元格：A1:R1` 引注；单元格内 `|` 转义。
   - Excel COM（.xls）：`UsedRange.Value` 转 md 表，整数化浮点。
4. **回写**（writeback.py）：按附件在 md 内出现顺序文末追加
   `\n\n## 附件（doc|xlsx 全文）\n\n<内容>`（与江苏第一轮格式一致）；
   同步把「（附件 xxx 为二进制格式或无文本层，未提取）」改为「老格式附件已提取，全文见文末」。

## 坑

- **Excel COM 日期带时区**：UsedRange 出来是 `2019-09-11 00:00:00+00:00`，必须洗成 `2019-09-11`（首修 1 件 .xls 已回填干净版本）。
- **RTF 伪装 .doc**：魔数 sniff 是必须的，按扩展名分派会漏。
- **writeback 断点先跑 dry 会把进度写满**：dry 也写 progress jsonl，正式跑全被 skip——重跑前删断点文件。
- 东莞仍有 8 个 md 留有「未提取」标记，全是 **.docx 损坏 / .pdf 扫描件**（第一轮遗留，不在本轮范围）。
- 江苏 downfile.jsp 链接在正文是相对路径、front matter 里是绝对 URL——清点正则只匹配 http 即可全中。
- 大 xlsx（发票明细 498 行、10 万字符）也完整进了 md，表格限 500 行×40 列足够。

## 质检（5 件抽查全过）

东莞 236 号（doc 决定书 + xlsx 发票明细表 10 行，与正文金额 540,345.00 元对得上）；
苏州园区 2023-10-16（xlsx 纳税人名单）；东莞 42 号（.xls 发票明细 498 行，日期已洗干净）；
东莞 32 号（RTF 伪 doc）；东莞 11 号（1 md 3 节）。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
