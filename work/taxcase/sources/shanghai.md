# 上海市税务局（shanghai.chinatax.gov.cn）税务案例抓取记录

抓取日期：2026-10-10 ｜ adapter 目录：`work/taxcase/adapters/sh_*.py`

## 栏目总览

| # | 栏目 | 入口 URL | 抓取方式 | 件数 |
|---|------|----------|----------|------|
| 1 | 行政处罚公示（一般程序处罚结果） | https://shanghai.chinatax.gov.cn/newxbwz/gspt/xzcf/xzcf.jsp （信息公开栏目页 /xxgk/sgs/xzcf/） | JSON API（WebLogic .pfv） | 1102 |
| 2 | 税案通报（稽查案例曝光，来自税务新闻） | https://shanghai.chinatax.gov.cn/xwdt/swxw/ | TRS 静态列表 + 关键词过滤 | 46 |
| 3 | 稽查公布（随机抽查工作安排/结果公示） | https://shanghai.chinatax.gov.cn/xxgk/tzgg/ | TRS 静态列表 + 关键词过滤 | 8 |
| 4 | 文书送达公告（催报/催缴/限期缴纳等执法文书公告送达） | https://shanghai.chinatax.gov.cn/was5/web/search?channelid=198173&searchword=文书送达公告&orderby=-docreltime | 站内 was5 检索倒序翻页 | 562 |
| 5 | 重大税收违法失信主体信息 | https://shanghai.chinatax.gov.cn/newxbwz/tycx/TYCXzdsswfajgblCtrl-init.pfv | 不可枚举，放弃（见踩坑3） | 0 |
| 6 | 行政复议决定书 | （无公开栏目） | 站内检索仅11条且全为法规/办事指南，无决定书全文 | 0 |

## 各栏目技术细节

### 1. 行政处罚公示（sh_xzcf.py）——本站核心资产
- 入口页 `xzcf.jsp` 内的 ajax 接口：
  `POST /newxbwz/gspt/xzcf/YbcxcfCtrl-ybxzcfcx.pfv`
  form: `ajmc=&xzcfsx=一般程序处罚&xzxdrmc=&xzxdrdm=&cfjg=&gsptyzm=&yzmflag=1&curPage=N`
- **`yzmflag=1` 时接口不校验验证码**（验证码仅客户端 yzmFlag 开关控制，服务端不校验该值）；
  `yzmflag=0` 且验证码为空时返回 `{"gscode":"yzmsb"}`。
- 必须先 GET 一次 `xzcf.jsp` 拿 JSESSIONID，再 POST；10条/页，`pageCount=111, totalRecords=1102`。
- **`xzcfsx` 的合法值是下拉框里唯一的「一般程序处罚」**（不是页面 JS 里写的「处罚」，传错返回空结果集但 HTTP 200）。
- 返回 JSON 字段：决定书文号/案件名称/相对人/统一码/法人/作出处罚机关与日期/公示日期/违法事实(cfsy)/处罚依据(cfyj)/处罚结果(cfyjjg)/应缴罚款额(yjfkje)——**列表即全量字段，无需再抓详情页**（详情页 initNewView 只是把同一批字段回显）。
- 平台滚动窗口：最早记录 2023-10，无需翻旧。全部 1102 条 ≥2023-01-01，无早于阈值记录。

### 2/3. 税案通报 + 稽查公布（sh_swxw.py）
- TRS 静态列表：首页 `/xwdt/swxw/`，第N页 `index_{N-1}.html`；页数在页面 JS `pagecount = 39`。
- 列表条目：`<a class="info" href="./202609/t481644.html" title="…">` + `<span class="time">2026-09-29</span>`。
  通用 `t.parse_list_items` 的 URL 正则**匹配不了** `/YYYYMM/tNNNNNN.html` 与 `./相对路径`，adapter 自写解析（urljoin 后必须清 `/./` 段，否则 polite_get 直接失败）。
- 税案通报=税务新闻按标题关键词过滤（稽查|查处|偷税|逃税|骗取|虚开|曝光|违法|失信|欠税|拒不|追缴|处罚），34页即覆盖到2019年，date_from=2023-01-01 截断。
- 详情正文容器兼容 `t.extract_detail`；出现过1篇活动集锦走了兜底抓到页脚，已人工删除。

### 4. 文书送达公告（sh_wsgg.py）
- 上海16区局的催报公告/欠税催缴公告散在各区子站 `/xxxtax/tzgg/<子类>/YYYYMM/tNNNN.html`，
  没有统一聚合栏目，**用站内 was5 检索聚合**：
  `GET /was5/web/search?channelid=198173&searchword=文书送达公告&orderby=-docreltime&perpage=10&page=N`
- 结果条目：`<p class="list_title"><a href>` + `var docreltime='YYYY.MM.DD'`（script 写日期，不在纯文本里）。
- `orderby=-docreltime` 按发布时间倒序（页面顶部「按时间排序」按钮对应 form 字段 orderby）。
- 全库命中1264条；倒序翻页至 2023-01-01 前停，上限100页（量控1000件）。
- 详情正文含《限期缴纳税款通知书》全文+被送达人名单，兼具复议告知内容。

## 踩坑记录
1. **处罚查询平台的验证码是摆设**：`yzmflag=1` 直接过；但注意 `xzcfsx` 参数值必须是「一般程序处罚」，传页面初始 JS 里默认的「处罚」会得到空结果（不报错）。
2. **curl_cffi chrome124 指纹必须**：普通 requests 拿壳页，与本站 WebLogic(.pfv)/TRS 混合架构下尤其明显；POST 接口若不带 Referer+xhr 头会拿到空 body。
3. **重大税收违法失信主体平台被功能性下架**（页面 JS 注释「20240923 撤下其他查询方式」）：
   仅剩「条件查询+验证码」，且 `getxxsByYzm` 空验证码返回空集不报错；用已曝光处罚企业全名精确查询同样空集——
   既无法枚举也无法验证，判定该栏目不可抓（总局站与信用中国有同源数据，不属本省任务）。
4. **复议决定书无公开**：上海税务无行政复议决定书栏目，站内检索「行政复议决定书」仅11条（全是法规与办事指南）。
5. **上海文章 URL 形如 `/YYYYMM/tNNNNNN.html` 且列表用 `./` 相对链接**：通用解析器两头都不认（正则限定了 content*.shtml），adapter 需自写列表解析 + urljoin。
6. **首页/信息公开页导航里找不到任何案例栏目**：曝光类内容全在「新闻动态-税务新闻」里，靠关键词过滤而非栏目划分；行政执法数据在独立 JSP 平台（newxbwz/gspt）而非信息公开栏目页（/xxgk/sgs/xzcf/ 只挂了1篇目录文件+平台链接）。

## 数量与失败统计
- 行政处罚公示：1102 件（全量 1102/1102，0 失败，0 跳过；平台最早 2023-10）
- 税案通报：46 件（关键词命中47，人工剔除1篇页脚噪音）
- 稽查公布：8 件（关键词命中10，剔除1篇裁量基准访谈预告、1篇活动集锦）
- 文书送达公告：562 件（倒序翻页至整页早于2023-01-01停，覆盖2023-01-03至2026-10-09；
  含10件小样；部分检索命中因标题不含公告词被过滤≈5%/页；扫描件跳过 0——未遇 PDF 决定书类附件）
- 失信主体/复议决定书：0（原因见上）
- **md 总数：1718 件**（行政处罚公示1102 + 文书送达公告562 + 税案通报46 + 稽查公布8）
- 质检：0 噪音残留、0 重复内容、0 缺 front matter、0 过短(<400B)文件


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
