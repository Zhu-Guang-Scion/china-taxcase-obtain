# 江苏省税务局（jiangsu.chinatax.gov.cn）税务案例抓取记录

- 抓取日期：2026-10-10
- CMS：大汉 hanweb（列表页 `/col/col{id}/index.html`，文章页 `/art/2026/9/28/art_{colid}_{artid}.html`）
- 通用组件：`work/taxcase/adapters/js_hanweb.py`（HanwebCol + 附件提取）、`js_run.py`（驱动）

## 站点结构与翻页规律（大汉 jpage）

列表数据不在 HTML 的 `<a>` 标签里，而是内嵌在 `<script type="text/xml"><datastore>` 的
CDATA record 中；首页约 15 条（专题模板可能 3×15 条多 tab）。翻页接口（POST）：

```
POST /module/web/jpage/dataproxy.jsp?startrecord={(page-1)*15+1}&endrecord={page*15}&perpage=15
form: col=1&appid=1&webid=18&path=/&columnid={cid}&sourceContentType=1
      &unitid={uid}&webname=国家税务总局江苏省税务局网站&permissiontype=0
```

- `unitid` 从列表页 nextgroup 链接 `dataproxy.jsp?page=1&webid=18&...&columnid=X&unitid=Y` 提取。
- 响应为 XML：`<datastore><totalrecord>N</totalrecord><recordset><record><![CDATA[<li><a title=.. href=..><span>date</span>]]>`。
- **坑：专题模板（如 col24019 税案通报）首页内嵌 3×15 条与 dataproxy 的 15/页错位，
  第 1 页也必须走 dataproxy 才能与 totalRecord 口径一致**（否则出现整页重复）。
- 站内搜索 JSON 接口（发现栏目利器）：
  `POST /jsearchfront/interfaces/search.do`，form `q=<关键词>&websiteid=320000000000000&tpl=22&p=<页>&searchid=21`，
  返回结构化 JSON（含 title/url/column/content 全文）。

## 栏目清单与抓取结果

### 1. 税案通报（省局，优先级1）
- 入口：https://jiangsu.chinatax.gov.cn/col/col24019/index.html （"合规经营 诚信纳税"专题下）
- totalRecord=67，栏目 2025-02 才开设，全部在近三年窗口内 → 全量抓取
- 产出目录：`lawlibrary/专题/税务案例/江苏省/税案通报/`，**67 件**（多为新闻通报+案件剖析）
- 无附件（纯图文）

### 2. 处罚决定书送达公告（优先级2：处罚/处理决定书全文在附件）
- 来源：14 个市局"通知公告"栏目 + 2 个区县聚合栏 + 省局通知公告
- 各市真实栏目 id（市局频道页链接的 通知公告 col 会 JS 302 到真实 col）：
  - 南京区县聚合 col8433（南京本市 col9161 只有领导接访表！）
  - 无锡 col9193、无锡区县聚合 col8507
  - 徐州 col9223、常州 col9280、苏州 col9363、南通 col9432、连云港 col9508、
    淮安 col9566、盐城 col9530、扬州 col9479、镇江 col9426、泰州 col9386、
    宿迁 col9335、苏州工业园区 col9287
- 过滤规则（标题）：含 `行政处罚|处罚决定|处理决定` 或（含`稽查`且含`送达公告|公告送达|文书送达`）
- 附件：PDF（pymupdf 提取文本层）/ docx（python-docx）/ 旧 .doc（本机 Word COM 提取，全文质量好）；
  无文本层扫描 PDF 跳过并计数
- 产出目录：`lawlibrary/专题/税务案例/江苏省/处罚决定书送达公告/`

### 3. 行政复议公告送达（优先级4）
- 同上来源，标题含 `复议`（江苏的复议决定书多以"公告送达"形式发布，正文短、决定书在 PDF 附件）
- 产出目录：`lawlibrary/专题/税务案例/江苏省/行政复议公告送达/`

### 4. 重大税收违法失信主体（优先级3）——**被验证码拦截，放弃**
- 官方入口：https://jiangsu.chinatax.gov.cn/col/col9709/index.html
  → 跳 `/module/jslib/bulletin3/lpindex.html`（企业）/ `npindex.html`（自然人）查询系统
- 查询强制：至少一个检索条件 + 图片验证码（`lpverifycode.jsp`，服务端校验，
  空 rand 返回"验证码错误"）→ 无法批量枚举，按简报放弃并记录
- 市局通知公告栏中标题含"失信"的个别公布会被第 2 类过滤顺带捕获

### 5. 行政处罚案件信息查询（etax 查询系统）——**单户查询，不可批量**
- https://etax.jiangsu.chinatax.gov.cn:8443/tsyw/view/dfts/xzcfxx
- 前端 JS（fggspt/js/XZ_punish.js）要求"行政相对人代码必填"（layui 表格 POST
  `{http}/SgscxController/queryXzcf`），默认不加载列表 → 无法全量枚举，放弃

### 未抓取（记录）
- 非正常户公告 col14949（56 条，月度名单式，案例价值低）
- 行政检查 col23776 / "双随机一公开" col7674（检查计划类，非案例）
- 行政执法公示平台 /fggspt/main.html（壳，数据在 etax 查询接口）

## 踩坑记录

1. **TLS 指纹**：与总局一致，python-requests 拿壳页，全部走 curl_cffi chrome124（polite_get）。
2. **大汉列表解析**：t.parse_list_items 对大汉 CDATA record 无效（在 script 文本里），
   自写 RECORD_RE 正则解析。
3. **专题页 3×15 错位**：见上，第 1 页也走 dataproxy。
4. **附件是决定书全文的载体**：公告正文只有 3-5 行，`/module/download/downfile.jsp?filename=<md5>.pdf|doc`
   才是内容；旧 .doc 用 Word COM（win32com）提取成功率高， loose 二进制解码会产出乱码必须禁用。
5. **扫描件 PDF 无文本层**（复议决定书多见）：pymupdf 提取 <80 字符即判扫描件跳过计数。
6. **市局频道栏目是"频道页"非真实栏**：`/col/col9002/index.html` 这类是 JS 跳转壳，
   真实栏要跟 `location.href` 一跳；南京本市直发栏（col9161）只有接访表，
   真实处罚送达在区县聚合栏 col8433。
7. **编码**：全站 utf-8，无需 GBK 处理。

## 抓取量汇总（正式，2026-10-10）

| 栏目 | 来源栏目 | 件数 |
|---|---|---|
| 税案通报 | col24019（全量 2025-02 起） | 67 |
| 处罚决定书送达公告 | 14 市局通知公告 + 南京区县 col8433 + 无锡区县 col8507 + 省局 col8274（近三年，每市增量封顶，栏目硬上限 1000） | 736 |
| 行政复议公告送达 | 同上（标题含"复议"） | 3 |
| **合计** | | **896**（含同名冲突按 artid 后缀补抓的 90 件） |

- 附件提取（front matter 附件字段统计）：PDF 全文 153、旧 .doc 全文（Word COM）321、
  docx 全文 37；扫描件 PDF（无文本层）跳过 106；下载失败 32、无法解析二进制 7。
- 失败/错误：详情页解析失败 0；附件下载失败已逐条记录在文件 front matter。
- 已知瑕疵：同名同日泛化标题（"税务文书送达公告"）产生 59 组文件名冲突、90 件被覆盖，
  已全部按 URL artid 后缀补抓回库（文件名尾部 `_\d+` 即补抓件）。
- 噪音清理：删 2 件"启用行政复议专用章"行政事务公告。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
