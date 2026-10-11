# 第五轮富信源调研：税务稽查/处罚案例（2026-10-10）

> 调研目标：为「只要富全文（含违法事实叙述+处理结果）」的税务案例库找新信源。
> 方式：curl_cffi chrome124 直连探测（同库内技术栈）+ playwright 会话内抓 XHR + GitHub API + WebSearch。
> 探测证据文件在 `_research/probe_r5/`（home_*.html / fj_ybcx.html / ln_sword.html / hn_search.html 等）。
> 凡写【实测】均为本轮直接验证。

---

## 1. 结论速览表

| 信源 | 富全文? | 墙? | 优先级 | 预估量（涉税） | 一句话 |
|---|---|---|---|---|---|
| **浙江政务服务网·行政处罚结果公开系统**（xzcf.zjzwfw.gov.cn） | **是**（详情页=决定书全文叙事，repo 样本 2.7KB/件） | **无**（API 裸奔，无验证码无签名） | **P0** | 省本级税务 6；市级+区县待查 areacode（全库含各执法领域，量大） | curl_cffi 直连实测通，可能补齐信用浙江 3,069 条索引的正文 |
| **福建 etax xxmh 处罚平台** | **是**（列表 API 自带 cfsy=处罚事由/cfyj=处罚依据字段） | 图片验证码（ddddocr 实测识别 OK） | **P0** | 全省处罚决定（待过码后看 total） | 同浙江剑法：ddddocr+重试即可规模化 |
| **安徽 16 市局频道·稽查查处通报** | **是**（全文叙事，实测样本 500+ 字案情） | 无 | **P1** | 每市频道数十条，估 300-800 | 大汉 CMS 直抓，当晚可收 |
| **辽宁 sword 行政执法公示平台**（etax.liaoning:8090） | 结构化（字段型，按山东经验含处罚内容） | 无（直连 200） | **P1** | 全省一般处罚结果+重大失信案件（山东同款平台 3,243 条） | IAB/有头会话内 fetch，同山东打法 |
| **天津·涉税信息公告（处罚公示日批次）** | 半富（表格含处罚事由字段，待逐条验证字数） | 无 | **P2** | 日批次，估千级 | 已库只有天津新闻，此栏未收 |
| 厦门 sbf 处罚平台 | 字段型（表头含处罚事由/依据） | 无 | P3（疑空库） | 实测 totalCount=0 | 同浙江 sword 空库情形，需浏览器会话终验 |
| 青岛 xxgk2019 | 未知 | **路径级瑞数**（首页 200，/xxgk2019/、/search/ 412） | P3 | - | 有头浏览器可过 |
| 河南 portal | **否**（实测搜索无处罚/失信数据） | 无 | 放弃 | 0 | 数据不在省局官网 |
| 湖北/重庆/陕西/宁波 主站+etax | - | 瑞数全站 | 排队 | - | 浏览器会话队列 |
| 湖南 主站 | - | 加速乐 MMB1 | 排队 | - | 但 **etax.hunan 200 无墙**（电子税务局壳） |
| openlaw.cn | - | **强制登录**（任何页跳 /login）【实测】 | 放弃 | - | 已实质关闭 |
| 信用中国 www.creditchina.gov.cn | - | 瑞数 412【实测】 | P3 | - | 搜索 API 旧端点也 412 |
| 信用河南 credit.henan.gov.cn | 索引型（文章搜索） | 无 | P3 | - | 处罚库在登录数据服务后 |
| GitHub/HF 现成数据集 | **不存在**（GitHub API 实测 total=0~6 且全不相关） | - | - | 0 | 唯一例外：浙江处罚爬虫 repo（下详） |
| 中国税务报 | 富（案例报道）但无公开官网存档（ctaxnews.com 域名已死【实测】） | - | P3 | - | App/tophub 聚合/公众号通道；转载有版权顾虑 |
| 人民法院案例库 rmfyalk.court.gov.cn | 精选富案例 | 无【实测 200】 | P3 | 涉税小几百 | 质高量小，适合评测集 |

---

## 2. 新富源详情（每源：入口/机制/探测证据）

### 2.1 浙江政务服务网·行政处罚结果信息公开系统【P0，本轮最大发现】

- **入口**：`https://xzcf.zjzwfw.gov.cn/punishment/#/Punish`（Vue SPA，按部门筛选含"省税务局"）
- **列表 API（实测 curl_cffi 直连 200，无验证码、无签名、无墙）**：
  ```
  POST https://xzcf.zjzwfw.gov.cn/api-gateway/jpaas-punishment-server/open-api/punishment/searchPunishList
  Content-Type: multipart/form-data
  字段: xzcfws_code(文书号) / xzcfws_name(案件名) / bxzcf_name(被处罚对象) /
        begindate / enddate / bxzcf_type / deptId / areacode / pageNo / pageSize
  返回: data.punishList[] = {xzcfws_code, xzcfws_name, bxzcf_name, bxzcf_type,
        bxzcf_legalman, xzcf_date, orgnode, guid} + total/pageTotal
  ```
- **部门码（实测 searchPunishDeptList 返回）**：省税务局=`001003028`（本列表共 14 个省本级部门）
- **实测结果**：deptId=001003028、2015-01-01~2026-10-10 → **total=6**（省本级只办大案）；样本如"浙江丽水莲都中银富登村镇银行涉嫌虚假纳税申报案"。
- **市级/区县数据**：页面有"按地区"模式，但 12 位 areacode（330100000000）实测返回空——正确参数格式需在 playwright 会话里点一次"杭州市"抓包确认（本轮点击元素被隐藏下拉挡住，未捕获）。**这是采集前唯一待办**。
- **详情富文本证据**：GitHub repo `lizhendong1366-pixel/zhejiang-punishment-spider`（2026-06 活跃，★0）内 12 个样本 md，其中《嵊州市贺兴生鲜超市…案》含完整"主要违法事实+处罚种类、依据、内容+履行方式"约 2,700 字——即决定书摘要全文，**通过质量门槛（≥30 字违法事实叙述）无悬念**。该 repo 的 `fetch_all_12_cases.py` 为 playwright 全套可复用脚本。
- **详情端点**：本轮未捕获（点击列表行后未抓到 XHR，可能路由内渲染）——采集时用 playwright 会话抓一次即可。
- **战略意义**：库内信用浙江 3,069 条索引（esId 留存、详情被点击式验证码挡住）的正文很可能就在这个系统里——**同一上游、无验证码通道**。

### 2.2 福建 etax xxmh 处罚结果平台【P0】

- **入口页**：`https://etax.fujian.chinatax.gov.cn/xxmh/view/xzzf/xzzf_fj/ybcxcfjg.jsp?swjg_dm=13500000000`
  （主站 fujian.chinatax.gov.cn 200 无墙；ztree 目录在 `/zfxxgkzl/zfxxgkml/xzzf/` 页面内嵌 JS 里，含"行政许可/行政处罚/行政检查"三类，后两者指向 etax）
- **数据 API（实测）**：
  ```
  POST https://etax.fujian.chinatax.gov.cn/xxmh/xzzf/swxzybcxcfjg/querySwxzybcxcfjg.do
  data: ajmc / xzxdrdm / xzxdrmc / cfjg / page / swjg_dm=13500000000 / captcha=<图片码>
  返回 JSON: {count:"N-机关名", data[]: {jdswh, ajmc, cflb, cfsy(处罚事由), cfyj(处罚依据),
             xzxdrmc, xzxdrdm, fddbrmc, cfjg(处罚结果), cfjg2(处罚机关), cfrq2}}
  ```
- **验证码**：`GET /tycx-cjpt-web/cxptGz/builderCaptcha.do?t=<ts>` → 纯 PNG 图片（24KB）。**本机 ddddocr 实测识别成功**（样本输出 `76v4Ey`）。与浙江 sword 的 ck1 同档（预期 70-80% 过码率），完全可规模化。
- **未过码直查**返回 `{"errMsg":"验证码校验失败"}`（GBK）——API 契约清晰。
- **注意**：cfsy 字段长度需过码后抽样验证是否≥30 字（表头设计上是"处罚事由"整段）。
- **区县扩展**：swjg_dm 换区县局代码即可分片（JSP 页面同目录还有 xzxk_zyxzxkjg.jsp 许可结果）。

### 2.3 安徽 16 市局频道·稽查查处通报【P1，当晚可收】

- **结构**：主站 anhui.chinatax.gov.cn（大汉 CMS，200 无墙）→ 首页市局频道 col9471(合肥)~col9486(黄山)，每市频道下 `工作动态(col9492 等)/通知公告(col9489 等)`。
- **实测样本**（`/art/2026/8/10/art_9492_1320003.html`）：
  > "国家税务总局合肥市税务局第二稽查局依法查处长丰县三十头飞乐加油站偷税案件……经查，2021年至2023年，……通过第三方支付平台绑定企业员工私人账户收款等方式隐匿收入，进行虚假纳税申报，少缴增值税等税费169.58万元。2025年6月……依据《税收征收管理法》……"
  ——**典型税案通报级富文本**。
- **另含**：《税务检查通知书》送达公告（告示型，不入库）、《税务协助检查通知书》送达公告（同）。
- **无 jsearch**（实测 404）；处罚决定书平台未在 portal 发现（安徽处罚数据或也走信用安徽 credit.ah.gov.cn——该站 200 无墙，本轮未深挖其 API）。
- **量估**：16 市 × 工作动态近年条目，涉税查处类估 300-800 件。

### 2.4 辽宁 sword 行政执法公示平台【P1，山东同款】

- **入口**：主站 liaoning.chinatax.gov.cn（大汉 CMS 无墙）`/col/col7053/index.html` JS 跳转 →
  `https://etax.liaoning.chinatax.gov.cn:8090/sword?ctrl=XzzfgsptHomeCtrl_index`
  （支持 `&sxq=<市>` / `&yjcd=&ejcd=` 传区划进平台）
- **实测**：GET 200 无墙、无验证码（首页层面）；菜单含 **一般处罚结果 / 重大税收违法失信案件信息 / 行政许可结果**（HTML 内 `link_title` span 佐证）。
- **数据接口**：wings 框架会话型，本轮直接猜 endpoint 404——需浏览器会话内 fetch（同山东 `query_swxz_ybcx_cfjg.spring` 的 IAB 打法；山东同平台收获 3,243 条先例）。
- **重要旁证**：平台 JS 代码含 `if(paramsArrry.province == 'shenzhenshi')` 分支——**这是多省共用的 Xzzfgspt sword 平台**，逆向一次可复用到其他用同款平台的省份。

### 2.5 天津·涉税信息公告（处罚公示日批次）【P2】

- WebSearch 证实存在"涉税信息公告汇总"页：每日批次《国家税务总局天津市税务局 YYYY年MM月DD日税务行政处罚公示》，表格字段含 **处罚事由、处罚依据**（搜索快照原文）。
- 主站 200 无墙（自研 u_zlmViewMx.action 体系，库内已有天津 adapter）；栏目 URL 未定位到（首页 JS 渲染），采集时从首页导航进"涉税信息公告"即可。
- **风险**：处罚事由若是短语（"发票违法"）而非叙事，需按 quality_prune.decide() 过滤——收益可能打折，先试抓 3 日批次再定。

### 2.6 厦门 sbf 处罚平台【P3，疑空库】

- **入口**：`http://xiamen.chinatax.gov.cn/xmswcms/xzzfxxgspt/sjsy.html`（**必须 http**；https 会 302 回首页【实测】）；市局+8 区局子页。
- **数据 API（实测 200 无墙）**：`https://sbf.xiamen.chinatax.gov.cn:1080/dwfw/swxzybcxcfjg.do?swjgdm=13502000000`（查询端点 `swxzybcxcfjgQuerySj.do`；失信=`zdsswfsxajxx.do`；欠税=`qsgl.do`）
- 表头字段：决定书文号/案件名称/处罚类别/**处罚事由/处罚依据**/相对人/代码/法代/结果/机关/日期——字段齐全。
- **但**：市局与思明区局 totalCount 均为 **0**——与浙江 sword 空库同款情形。浏览器会话终验一次（带查询条件 POST）再定生死。

---

## 3. 分省探测一览（本轮 11 目标全部实测）

| 省/市 | 主站状态 | 墙 | CMS/机制 | 处罚/失信栏目结论 |
|---|---|---|---|---|
| 河南 | 200 / 66KB | 无 | 自研（`/2026/09-30/142184.html`） | **官网无数据**【实测】：站内搜索 API（`wzjh.henan.chinatax.gov.cn/search-api/open/api/external-new`，siteId=4500180001）查"行政处罚/处罚决定书/失信主体/稽查"全部只返回政策文件与采购公告；etax.henan 连接超时。→ 数据在信用河南（文章搜索无处罚库，数据服务需登录）或根本只走内网 |
| 湖北 | http 412 / 2.3KB | **瑞数**（`$_ts`+cookie 挑战【实测】） | - | 全站墙（etax.hubei 亦 412） |
| 湖南 | 412 / 246B | **加速乐**（`/MMB1_*.js`【实测】） | - | 主站墙；**etax.hunan.chinatax.gov.cn 200 无墙**（6.9KB 电子税务局 JS 壳，公示模块需会话验证——湖南的潜在突破口） |
| 福建 | 200 / 178KB | 无 | TRS+etax xxmh 平台 | **见 2.2，P0** |
| 安徽 | 200 / 52KB | 无 | 大汉 CMS | **见 2.3，P1** |
| 重庆 | **202** / 2.5KB | **瑞数**【实测】 | - | 全站墙（etax.chongqing 亦瑞数） |
| 辽宁 | 200 / 48KB | 无 | 大汉 CMS + sword 平台 | **见 2.4，P1** |
| 陕西 | 412 / 2.7KB | **瑞数**【实测】 | - | 全站墙 |
| 宁波 | 412 / 6.8KB | **瑞数**【实测】 | - | 全站墙（etax.ningbo 亦 412） |
| 青岛 | 200 / 123KB | **路径级瑞数**：`/xxgk2019/`、`/search/was5/...` 均 412【实测】 | TRS+was5 | 有 was5 检索（同上海通道）；需有头会话过瑞数后走 was5 |
| 厦门 | 200 / 104KB | 无 | 自研 xmswcms + sbf 数据平台 | **见 2.6，P3** |

**重大税收违法失信专栏专项**（豫鄂湘皖闽渝）：
- 河南：portal 无【实测】；福建：ztree 无失信节点（厦门平台有 zdsswfsxajxx.do 端点但空）；安徽：portal 未见（仅查处新闻）；
- 湖北/湖南/重庆：主站被墙无法验证，进浏览器会话队列后按"省局首页→信息公开→失信公布"路径找；
- **对照**：四川模式（主站 col20038 jsearch，1,290 条）只适用于主站可直连省份；重庆/陕西/宁波/湖北这批瑞数省，失信数据多半同样在墙内，统一走"有头 playwright 会话内抓"（库内已有北京/四川两例成功打法）。

---

## 4. GitHub / 公开数据集（实测 GitHub API + WebSearch）

- **GitHub 无任何"税务处罚决定书"数据集/爬虫**【实测，多组查询 total=0~6 且全不相关】（与既有结论一致）。
- **唯一可用发现**：`lizhendong1366-pixel/zhejiang-punishment-spider`（★0，2026-06 push）——浙江省政务服务网行政处罚爬虫（playwright）+ 12 个脱敏样本 md + 完整脚本集。直接复用其选择器思路（见 2.1）。
- HuggingFace：无中国税务数据集（lawyer_llama/DISC-Law/CAIL 均法条问答或刑事，税是边角料）——与 v1 调研一致，无需重跑。
- CnOpenData/马克数据（macrodatas.cn 已重构为 SPA，站点存活）：仍是商业付费/已下架，无免费样本变化。
- **结论不变**：自建库即稀缺资产。

## 5. 稽查案例类内容源（非决定书但富案情）

| 源 | 状态【实测】 | 可得性 | 合规 |
|---|---|---|---|
| 中国税务报 | **ctaxnews.com 域名已死**（HugeDomains 售卖页）；官方入口=ctax.org.cn「中国税务网」（GBK，其"税案通报"栏目 `/satb/` 是总局镜像，库内已有 1,144 条） | 电子报无公开归档；内容在 App + tophub.today 聚合 + 微信公众号 | 报纸内容转载有版权风险；公众号通道（wechatDownload）已建，仅收官方号转发 |
| 各省"稽查案例/查处"新闻专栏 | 安徽模式最优（2.3）；鲁川已被 wswaf/瑞数挡（公众号通道已收 4+3 条） | 直抓可行省份：皖（+可能闽辽同类栏目） | 政府网站公开信息，同库内现有口径 |
| 税务总局《税务稽查》杂志 | 无公开网络版目录（搜索未见官方站点），纸质/内网 | 放弃 | - |
| 财经媒体深度稽查报道（锦天城/Lexology/知乎专栏等） | 散见，量小 | 建议仅作线索源定位官方通报，不直接入库 | 版权清晰风险 |

## 6. caseopen.org 之外的裁判文书镜像（涉税行政）

| 站点 | 本轮实测 | 结论 |
|---|---|---|
| openlaw.cn | 任何路径 → 302 `/login`（标题"用户登录"） | **实质关闭**，老爬虫（sml2h3/openlawClawer，2017）彻底失效 |
| 马克数据网 macrodatas.cn | 200（重构 SPA） | 文书源已下架（v4 结论维持） |
| 威科先行 law.wkinfo.com.cn | 200（AI 壳页） | 机构付费 |
| 法信 faxin.cn | 200 / 114KB | 付费 |
| 人民法院案例库 rmfyalk.court.gov.cn | **200 无墙** | 最高法审核精选案例，涉税量小，适合做评测集；留 P3 |
| 信用中国 creditchina.gov.cn | **412 瑞数**【实测】（旧 API catalogSearchHome.do 亦 412） | 全国聚合通道被墙；河南/安徽省站可直连但数据库在登录后 |

→ **涉税裁判文书的既定路线不变**：caseopen.org 在线 API（export=true 含全文）或 102G 兜底，`_research/wenshu_value_assessment.md` 已研判。

---

## 7. 推荐执行顺序（夜间采集优先级）

1. **浙江 xzcf 系统**（零墙零码，纯 API）：playwright 会话点一次"按地区→杭州市"抓 areacode 正确格式与详情端点 → curl_cffi 全量采集（税务部门全层级）。若市级数据在，这同时解决信用浙江 3,069 条索引的正文回填。**预期新增：千级富全文**。
2. **福建 etax xxmh**：ddddocr 过码循环（复用浙江 sword 脚本模式，验证码同为图片型），分 swjg_dm 逐局采集。入库前抽 20 条验 cfsy 字数过 quality_prune。
3. **安徽 16 市局频道**：静态大汉 CMS，taxcase_scrape.py 直接写 16 个 static_list job，当晚完成。
4. **辽宁 sword**：IAB/有头浏览器会话内 fetch（山东先例），一般处罚结果+重大失信两栏。
5. **天津处罚公示日批次**：试抓 3 日批次验"处罚事由"字数，过门槛再全量。
6. **浏览器会话队列**（瑞数省）：湖北/重庆/陕西/宁波/青岛 + 湖南 etax 子域——按"夜间/低频/分批"节奏，手法复用四川 sc_river.py。
7. **放弃项**：河南 portal、openlaw、GitHub/HF 数据集、中国税务报官网存档。

## 8. 本轮探测留下的资产

- `_research/probe_r5/`：全部实测 HTML/JS 样本（各省首页、fj_ybcx 平台页+验证码样本、ln_sword 平台页、hn_search 等）
- 可直接复用的 API 契约：浙江 searchPunishList（multipart 字段全录）、福建 querySwxzybcxcfjg.do（字段表全录）、厦门 sbf 端点族、河南 wzjh 搜索 API（用于证伪）
- zhejiang-punishment-spider repo 的 playwright 选择器集（GitHub raw 可取）


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
