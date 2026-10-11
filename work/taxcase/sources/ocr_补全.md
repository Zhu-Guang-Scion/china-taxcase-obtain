# OCR 补全（扫描件附件 → md 全文）

日期：2026-10-10　执行：ocr_fill.py（MinerU pipeline 模型，ch）

## 目标找回

原计划重新抓详情页找回江苏扫描件 URL；实际盘点发现 **front matter「附件:」字段已完整存档**（原抓取时 kind=scanned_img 的附件 URL 均在），无需重抓详情页，直接按 front matter 取数。

| 来源 | 扫描件附件数 | 说明 |
|---|---|---|
| 江苏省/处罚决定书送达公告 | 107 | 83 个 md，其中 14 个 md 含多附件（无锡梁溪 25 户为单 md 25 附件） |
| 江苏省/行政复议公告送达 | 2 | 泰州、无锡各 1 |
| 天津市/通知公告涉税案例 | 1 | front matter 无 kind 标记，下载后实测无文本层 |
| 深圳市/行政处罚公示 | 1 | 同上 |
| **合计** | **111** | 全部经 pymupdf 复核：<80 中文字符（实测均 0 字符） |

其余地区（广东/山东/浙江/上海/四川/北京）front matter 挂的是 zip/xlsx（非文本件），不在 OCR 范围；天津另一 md 附件为 zip，跳过。

## 结果

- **下载 111/111 成功，0 失败**
- **OCR 成功 111/111，0 质检不过**（质检：中文字数≥300 或含"第X条/决定/〔〕号"结构）
- **回写 md 87 个**，追加 `## 附件（扫描件 OCR 全文）` 共 111 节（多附件 md 逐附件分节，节首带附件名加粗行）；front matter 原文链接行后统一加 `OCR: mineru-pipeline 2026-10-10` 共 87 处
- OCR 文本量：合计约 **25.1 万**中文字符/数字（单件 250–60031 字）
- 临时 PDF 用后即删（tmp/ocr_dl/ 已清空，库保持 md-only）

## 例外与处置

| 情形 | 数量 | 处置 |
|---|---|---|
| 大文件上传超时（38–50MB，mineru CLI 内部 ~60s 上传超时，`context deadline exceeded`） | 2（2023-10-16 苏园稽 186 页/50MB；2026-08-26 淮安 60 页/38MB） | pymupdf 降到 110dpi 灰度 JPEG（12.3MB/3.2MB）后重传成功，OCR 60,031 / 15,965 字，质检通过；进度里记 `ok_downsampled` |
| MINERU_TOKEN（环境变量）失效 | 1 个 | 401 A0211 "user token expired"；改用 `E:\ai_coding_xiangmu\MinerU高并发脚本\config.json` 的 3 个 token（均有效，脚本内置轮换） |

## MinerU 用量与限流观察

- 调用次数：111 次成功 + 约 8 次重试/测试 ≈ 120 次，全部走 pipeline 模型
- 限流：每件间隔 ≥5s，**全程零 429/限流报错**；3 个 token 均未触频控（用量主要受单文件处理时间约束）
- 处理耗时：1–2 页决定书约 10–40s/件；186 页大件 101s
- 瓶颈不在限流而在**上传超时**：>20MB 文件即可能命中 CLI 内置 ~60s 上传超时，大扫描件需预降采样

## 进度与复跑

- 断点文件：`progress/js_ocr_scan.jsonl`（113 条记录，111 唯一 pdf_url，末态 109 ok + 2 ok_downsampled）
- 复跑 `python ocr_fill.py` 即断点续做（按 pdf_url 幂等，终态记录跳过）

## 遗留说明

- 处理期间有并行流程对本库 md 做了标签/要素增强并重建了 front matter（附件行的 `(scanned_img)` 标记被其去除）；已复核：87 个 md 的 111 个 OCR 节与 `OCR:` 标记行在重建后均完整保留，front matter 附件 URL 也未丢。
- 库内其余 front matter 附件为 xlsx/zip/rar（16 条 `(fail)`、6 条 `(binary)`），非文本扫描件，未纳入本次 OCR。
