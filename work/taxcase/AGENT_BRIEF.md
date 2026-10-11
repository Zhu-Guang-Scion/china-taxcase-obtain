# 税务案例分省抓取 —— 子智能体工作简报（必读）

## 项目背景
- 项目根：`E:\ai_coding_xiangmu\China_Law`（Windows，Git Bash 环境）
- 已建成法规库 `lawlibrary/`（27,795件）。现新建**税务案例库**：只存 md（不要保留 html/pdf/docx 原件），用于 RAG + 微调训练。
- 通用抓取库已写好：`work/taxcase/taxcase_scrape.py` —— **只 import 复用，不要原地修改**（总局任务正在后台使用它）。需要定制就复制到 `work/taxcase/adapters/` 改。

## 可复用组件（import taxcase_scrape as t）
- `t.polite_get(url, delay=2.5, referer=None)` —— 全局限速 GET。**内置 curl_cffi chrome124 指纹**（关键：税务系统站点对 python-requests 的 TLS 指纹返回无数据壳页/拦截，普通 requests 拿不到内容！curl 命令行和 curl_cffi 都能过）
- `t.parse_list_items(html, page_url)` —— BS4 通用列表解析 → [(url,title,date)]，兼容两种结构
- `t.extract_detail(html, url, fallback_title, fallback_date)` → dict(title/date/source_org/md/attachments)，多容器回退（.article-content/#zoomcon/.TRS_Editor/…），markdownify 转换
- `t.safe_filename(title)` —— Windows 安全文件名
- 进度断点模式：job_id 唯一即可，progress jsonl 写 `work/taxcase/progress/<job_id>.jsonl`

## job.json 跑法（静态列表页最常见）
```json
{
  "job_id": "gd_xzcf",
  "site": "https://guangdong.chinatax.gov.cn",
  "list_mode": "static_list",
  "list_url_template": "https://guangdong.chinatax.gov.cn/gdsw/xxx/index_{page}.html",
  "first_page_url": "https://guangdong.chinatax.gov.cn/gdsw/xxx/",
  "out_dir": "E:/ai_coding_xiangmu/China_Law/lawlibrary/专题/税务案例/广东省/行政处罚公示",
  "region": "广东省", "source_name": "国家税务总局广东省税务局",
  "category": "行政处罚公示",
  "max_pages": 40, "date_from": "2023-01-01", "delay": 2.5
}
```
总局系（www.chinatax.gov.cn 同构 TRS CMS）用 `list_mode=manuscriptList` + channel_code。
注意 static_list 模板约定：第1页用 first_page_url，其后用 `index_{page-1}.html`（即 page=2 → index_1.html）。各省分页命名可能不同（index_1.html / list_gz.php?currentPage=1 等），**先手动确认分页 URL 规律再写模板**；不符就写 adapter 自行翻页。

## 输出规范（严格遵守）
1. md 文件 front matter（由 job 机制自动生成，adapter 手写时保持一致）：
```yaml
---
title: "…"
来源机关: "国家税务总局XX税务局"
栏目: "行政处罚公示"
地区: "XX省"
发布日期: 2026-03-15
原文来源: "…"（页面"来源"字段，无则留空）
抓取日期: 2026-10-10
原文链接: <url>
---
```
2. 正文必须是干净案情/处罚内容：无导航、无页眉页脚、无"打印/分享/字号"、无访问量。脚本已处理；发现残留噪音要在 adapter 补清洗。
3. 文件名：`{发布日期}_{标题安全化}.md`。
4. 只写自己省份目录：`lawlibrary/专题/税务案例/<省名>/<栏目>/`，不要动其他目录。

## 采集内容优先级（每省按此找栏目）
1. **税案通报/曝光台/典型案例/稽查公布**（省局新闻类，质量最高）
2. **行政处罚公示/行政处罚决定书**（全文最有价值）
3. **重大税收违法失信案件（主体）公布**
4. **行政复议决定书/文书公告送达**（争议应对核心素材；多为 PDF 附件——有文本层的用 pymupdf 提取转 md，扫描件跳过并计数）
5. 通知公告栏里混着的零散处罚公示（标题含"行政处罚""处罚决定"）

## 量控与合规
- `date_from=2023-01-01`（近三年），单栏目 max_pages≤50、产出≤1000 件即可停（宁精勿滥，官方通报类可全量）
- 单线程，delay≥2.5s+抖动（polite_get 已内置），禁止并发高频请求
- 站点打不开/被拦：换 chrome 指纹重试 → 记录到 source 文档后放弃该栏目，不要死磕

## 已知坑（总局实测）
- TLS 指纹识别：requests 拿到 27KB 壳页（无数据），curl/curl_cffi 拿到 30KB 完整页。**一切抓取走 polite_get**
- 编码：省局常见 GBK（polite_get 已做 meta 探测）
- JS 渲染列表：先找页面背后的 JSON 接口（F12 风格猜测：/manuscriptList/、interface/*.json、getPageData 等）；实在不行可用 playwright（已安装 chromium）——`from playwright.sync_api import sync_playwright`
- 江苏/浙江系可能是大汉 CMS（URL 形如 `/art/2026/9/28/art_23636_13381.html`，列表页形如 `/art/23636/list.html` 或 `col/col23636/index.html`）

## 交付物（除 md 库外，必须写）
`work/taxcase/sources/<省拼音>.md`，内容：
- 每个栏目：入口 URL、列表翻页规律、页面结构（CMS 类型）、数据接口（如有）
- 抓取量（件数）、失败量、跳过的扫描件数
- 踩坑记录（反爬/编码/结构特殊点）
此文件将汇总进项目经验文档，务必写实。

## 质量门槛（2026-10-10 用户裁决，第五轮起强制）
**只收有具体案情的内容**：违法事实/事由叙述 ≥30 中文字符（如"通过个人账户收取培训费未入账，少缴增值税103万元"），
不要纯告示型记录（只有 文号+法条+罚款金额 / 催报催缴送达名单 / 欠税名单 / 索引型列表字段）。
采集时若数据源只提供元数据（如信用平台列表接口），要么找到详情全文再入库，要么放弃该源——
入库前用 work/taxcase/quality_prune.py 的 decide() 判定，DEL 的不入库。

## 质量门槛 v2（2026-10-11 用户二次裁决，取代 v1 的 30 字门槛）
v1 漏网的三种形态：①法条+罚款金额凑字数（信用广东型）②分类模板句超 30 字（"未按期申报/虚开发票"类短语，云南/湖南/辽宁 cfsy 普遍形态）③同一句式只换公司名的走逃户模板（广西失信批量同文）。
**v2 判定（work/taxcase/quality_prune2.py，采集时强制）**：
- 处罚公示类：双要素——(a) 案情具体性：事实段 ≥30 字且（≥2 数字+单位词[万元/份/倍/%…]），或 ≥80 字且含数字+行为动词（开具/取得/隐匿/虚开/抵扣…）；(b) 处罚结果要素（罚款/追缴/没收/移送/判处…）。缺一不入库。
- 失信类：栏目标题即结果语义，只查事实具体性（防误杀采集截断但有具体案情者）。
- 叙事类（通报/判决/案例/12366）保持保留。
- 已知陷阱：黑龙江两列表格详情解析会切尾（有具体案情但缺处罚段）——修复采集而非删数据。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
