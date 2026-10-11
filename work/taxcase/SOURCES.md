# 税务案例库 · 抓取路径与经验（v8 汇总）

> 建库：2026-10-10/11 八轮完成 ｜ **终库 31,764 件纯 md（295MB），RICH 96.4%，31 省全覆盖**
> 本文档是 skill 的底稿。分省明细见 `work/taxcase/sources/*.md`。

## 〇l、第八轮（2026-10-11）：质量门禁 v2——二次清洗「处罚信息孤悬」

**用户裁决**：仍存在"只有一个处罚信息孤悬，没有翔实的案例经过和处罚结果"的文件。

### v1（30 字门槛）漏网的三种形态（本轮实测定位）
1. **法条+金额凑字数**：信用广东型——"根据《征管法》63 条…处罚款 418 万元"过 30 字门槛，但全文无案情经过
2. **分类模板句超 30 字**：云南/湖南/辽宁/江西 cfsy 普遍形态——"扣缴义务人不履行代扣代缴义务，应扣未扣、应收而不收税款，在账簿上不列或少列收入"（43 字 0 数字）＝换了说法的类别标签
3. **走逃户批量同文模板**：广西失信 97 条——同一句式只换公司名与日期（"具有偷税行为，不履行税收义务并脱离税务机关监管"）

### v2 门禁（quality_prune2.py，已固化 AGENT_BRIEF/skill）
- **处罚公示类双要素**：(a) 案情具体性=事实段≥30字 且（≥2数字+单位词[万元/份/倍/%…]）或（≥80字+数字+行为动词[开具/取得/隐匿/虚开/抵扣…]）；(b) 处罚结果要素（罚款/追缴/没收/移送/判处/停止办理/纳入…）。缺一不入库
- **失信类只查事实具体性**（栏目标题即结果语义；防误杀采集截断但有具体案情者）
- **叙事类（通报/判决/12366）不动**
- 结果：**删除 3,154 件**（留档 pruned_files_v2.json）——浙江 1,087 / 江西 729 / 福建失信告知书 247 / 辽宁 205 / 山东 123 / 四川 116 / 青岛 94 / 广西走逃模板 97 / 湖北 79 / 上海 73…

### 本轮踩坑记录（重要，进 skill）
1. **误杀教训**：初版把"结果要素"也套在失信类上，黑龙江 267 条被误判——实为**采集截断**（两列表格详情解析切掉处罚段，原文有）而非数据缺陷；修正为失信类豁免。**门禁误杀先查采集缺陷，别急着删**
2. **数字≠具体性**：日期数字会充数（广西走逃模板 32 个数字全在日期里）——单位词白名单必须排除纯日期（万?元/份/倍/%/税率/车/张/笔/条/人）
3. **"拟确定为失信主体"告知书**（福建莆田 247 条）是程序性文书非失信公布正文——正文在未提取的附件里，v1 放行、v2 事实具体性正确拦截
4. 次级通道（≥80字+数字+动词）实测偏宽（上海 73/74 仍删）——留用但标注谨慎
5. 清洗链：34,918 →（v2 删 3,154）→ **31,764 件 / RICH 96.4%**

## 〇k、第七轮总述（扩围+攻坚，16 省区 + 福建市局，+13,772 件）

| 组 | 件数 | 亮点 | 文档 |
|---|---|---|---|
| 冀晋蒙 | **+4,317** | 冀 1,907（瑞数墙走 HTTP 通道破，14 市处罚平台跨市去重）/ 晋 1,923（`commonRemote/extQuery` 6 市全收，太原471+大同397+晋城392…）/ 蒙 487（失信 WAS5 全量零失败） | sources/{hebei,shanxi,neimenggu}_r7.md |
| 豫赣琼 | **+2,193** | **河南翻案**（round5"官网无数据"推翻——真入口 wzjh.henan 汇联全站搜索 API，省站+19 市循环；洛阳稽查局把《税务处理决定书》全文发新闻栏）/ **江西 2,036**（xxgk 6,111 批次 .xlsx 按行展开=决定书级结构化 19/36 列表头；余 ~190 页断点）/ 琼 60（稽查省局派驻制无市局子站） | sources/{henan,jiangxi,hainan}_r7.md |
| 桂滇黔 | **+3,905** | 桂 1,064（失信 restSearch API 全收）/ 滇 1,429（失信 bulletin 495+pub 处罚 934 双源，余量改 MAX_PAGES 可续）/ 黔 1,412（失信 /irs/front/list 1,197+处罚 215；912 件短语型被门槛正确过滤） | sources/{guangxi,yunnan,guizhou}_r7.md |
| 甘宁青新 | **+972** | 宁 600（FieldForm LIKE 饱和枚举全量）/ 甘 181（处罚 900 条 4 字短语型门槛拦，湖南同形态）/ 青 150（TRS 云搜索行自带全文）/ 新 41（瑞数会话内 $.ajax 直调 IRS 检索 11 词并集） | sources/{gansu,ningxia,qinghai,xinjiang}_r7.md |
| 吉黑藏 | **+885** | 黑 454（nsrmc 模糊词并集饱和枚举 456 全量）/ 吉 415（全站瑞数有头会话内失信全量，分页懒扩展）/ 藏 16（预期体量） | sources/{heilongjiang,jilin,xizang}_r7.md |
| 福建市局（攻坚翻案） | **+1,500** | **主站与 9 市局子站全部无墙**（此前判死的只是 etax 平台）；TRS was5 契约 channelid=203958+classsql siteid+DOCTITLE= 直收 10 市（福/泉/莆各触顶 300），正文 cjk 中位 839 字；**厦门 https 软 404 但 http 正常** | sources/fujian_cities_r7.md |

## 〇i、第七轮（2026-10-11）：东北两省 + 西藏——失信栏富全文采集

| 地区 | 件数 | 主源与关键发现 | 文档 |
|---|---|---|---|
| 黑龙江省 | **+454** | **全站无墙**（curl_cffi 直连最快一省）。失信栏=山东系 jslib bulletin 挂件（zdss.html→ajaxfors.jsp, tablename=jcms_141），**nsrmc LIKE 模糊多词并集饱和枚举 456 条**（公司 426+非公司词补齐），忽略分页参数一次全量返回；详情 art_6410 两列表格富全文。处罚平台不存在（旧 etax 迁移新电子税局，zfgspt 温馨提示 404 页） | `sources/heilongjiang_r7.md` |
| 吉林省 | **+415** | **全站瑞数**（连 /art/ /module/ 都 412）→ 有头通过挑战+会话内 fetch。失信栏 col19972 分面查询：`/module/search/index.jsp` FieldForm GET，5 条/页，**分页窗口懒扩展须翻到无新增**（415 条全量）；详情 td.title_left 行式，富全文拆 2 段。坑：col 页 onload 自动 submit 有竞态→过挑战时家页改用旧 art 页。jsearch（页面 $.ajax）可用作探针；处罚类内容皆送达告知书（门槛必删）不投入 | `sources/jilin_r7.md` |
| 西藏自治区 | **+16** | 快探盒收口：**无失信栏、etax:8443 是跳转 :5100 的空壳**；唯一有效源=主站通知公告 col5513（dataproxy body 参数全在 POST，webid=1/unitid=13090）301 条中 16 件税案查处/曝光通稿（255–1541 汉字富全文，栏目=税案通报） | `sources/xizang_r7.md` |

本轮合计 **+885 件**（失信 869 + 税案通报 16），全部 quality_prune KEEP。

### 〇i.2、第七轮增量二（2026-10-11）：西南三省——零墙直连，失信栏三家全破

| 地区 | 件数 | 主源与关键发现 | 文档 |
|---|---|---|---|
| 广西壮族自治区 | **+1,064** | 全站 200 直连。失信栏 `/restSearch` API（channelid=290909，NF 年份枚举 2023-2026，pageSize=100，行自带 ZYWFSS 违法事实+XGFL_CFQK 处理处罚全文，100% 过门槛）；etax:8208 wings 平台 TCP 不通 | `sources/guangxi_r7.md` |
| 云南省 | **+495 +处罚量控 934** | 失信 bulletin JSP（`ajaxfors.jsp?tablename=jcms_41&title=&key=` **空参数必带否则 404**，一次返回全量 496 行；详情 begin/end 标记 **12/14 段两模板变体，事实恒在末段**）；处罚 `/pub/info/topic` 服务端渲染 241 页决定书级 11 列（ pageNumber 翻页） | `sources/yunnan_r7.md` |
| 贵州省 | **+1,197 +215** | `/irs/front/list` JSON API **https+Origin 硬条件**（http 返"系统错误"）；**同表双渠道** channelId=5735176 失信（行全文）/5793970 处罚——**字段语义随渠道变**（f_2022118461091 失信=名称/处罚=违法事实），处罚 80% 短语型被门槛正确过滤 | `sources/guizhou_r7.md` |

### 〇i.3、第七轮增量三（2026-10-11）：西北四省区——三省失信栏富全文，新疆唯一活源是站内检索

| 地区 | 件数 | 主源与关键发现 | 文档 |
|---|---|---|---|
| 宁夏回族自治区 | **+600** | http 瑞数但 `/module/search/` 也带挑战（与甘肃相反）→全程浏览器。失信栏 col16187 FieldForm：**isQuery=1+空字段参数必须齐全**，vc_name LIKE 多词饱和 599 全量（行 7 列含日期，详情 begin/end 标记 15 字段富全文；`<$[信息标题]>` 残留须清洗）。zfgs:9443 wings 平台验证码 ddddocr 快速通过但**空条件/nsrmc/cfjg 四路查询全「没有数据」=空壳**（重庆:8888 同款） | `sources/ningxia_r7.md` |
| 甘肃省 | **+181** | 失信 col8350（TRS FieldForm）：**列表 /module/search/ 无挑战 curl 直连**（辽宁同款）181 页×1 条=181 主体；详情 /art/ 有瑞数走有头。处罚 col10735 决定书级 60 页×15 可查但**违法事由 4 字短语全不过门槛**（湖南 cfsy 形态）不收 | `sources/gansu_r7.md` |
| 青海省 | **+150** | **全站无墙**（https 证书不匹配 403，http 直连）。失信=TRS 云搜索 `/common/search/6279081b…`：**行自带 zywfss 违法事实+xgflyj 处理处罚全文**，114 全收；etax:7201 sword 平台 http 52/https 黑洞/有头同死 | `sources/qinghai_r7.md` |
| 新疆维吾尔自治区 | **+41** | /lslm/ 失信旧平台+etax zfgspt 双双「服务异常」判死；唯一活链路=IRS 智能检索：**UI 翻页点击会污染会话（后续关键词全 0），改会话内 $.ajax POST /irs/front/search**（瑞数自动附令牌，裸 fetch 缺 ahUfMqtu 必 1000）11 词并集 798→382→镜像去重 41 件市局稽查通报 | `sources/xinjiang_r7.md` |

本轮四省区合计 **+972 件**（失信 893 + 税案通报 79），全部 quality_prune KEEP。

## 〇j、第七轮·波二（2026-10-11 午）：豫赣琼三省——河南搜索API破局 + 江西xlsx附件展开

| 地区 | 件数 | 主源与关键发现 | 文档 |
|---|---|---|---|
| 江西省 | **+2,036** | 主站无失信栏；**xxgk 动态模块 `/module/xxgk/search.jsp?area=XZCFXXGS`（6,111 批次，直连无墙）→ 详情仅 .xlsx 附件 → 19/36 列两种表头的决定书级结构化数据按行展开**；facts≥30 门槛（事由+处罚内容计，法条不计）4,022 行收 2,003；量控 cap 停在 2025-07（余 2023-10→2025-07 约 190 页可续） | `sources/jiangxi_r7.md` |
| 河南省 | **+97** | round5"官网无数据"翻案：**真入口是 wzjh.henan 汇联全站搜索 API（`/search-api/open/api/external-new`，siteId 逐站循环 20 站）**；6 关键词枚举→详情门槛；**洛阳市稽查局把《税务处理决定书》全文发新闻栏（5,639 字，河南最富源 18 件）**；通知公告=纯图片送达公告（DEL）；信阳/周口/驻马店无查处通报（0 件） | `sources/henan_r7.md` |
| 海南省 | **+60** | 行政处罚栏=upgrading.html 升级空壳、搜索 q 参数失效、无市局子站（稽查省局派驻制）；唯一富源=**税务新闻 `/ssxc_1_2/`（72 页全量，一案两稿：总局体例通报+本地媒体揭秘稿）**，总局镜像按来源排除 22 条 | `sources/hainan_r7.md` |

本轮三省合计 **+2,193 件**，全部 quality_prune KEEP；manifest/structured/corpus 已重建（全库 34,721 行结构化）。

## 〇h、第六轮（2026-10-11 晨）：瑞数省会话队列——6 地全部完成会话建立

**打法（四川同款）**：有头 chromium（--disable-blink-features=AutomationControlled）自动过瑞数 → 会话内采集（fetch 失败即转真实导航 / 站内 $.ajax / 接口枚举）。质量门槛全程强制。

| 地区 | 件数 | 主源与关键发现 | 文档 |
|---|---|---|---|
| 湖南省 | **1,321** | 失信 `/hardcasegetdatanew` 全收 1,308（行自带违法事实全文）；无 sword 平台（etax 是 SPA 壳）；fetch 被钩死走站内 $.ajax+元素截图 ddddocr；处罚 800/2,681 收后仅 16 过门槛（cfsy 本身是 4 字分类短语，数据形态如此），余量被 CDN 会话级封禁（复跑入口留档） | `sources/qingdao_hunan_r6.md` |
| 重庆市 | **856** | 失信 API `/api/qeuryZdaj`（空条件拒查→按案件性质枚举 ajxz 1-9/a/b，pageSize=200）+ `queryZdajById` 全文 795；**真实路径前缀 `/cqtax/`**（直接路径全 404）；8888 处罚平台空壳 | `sources/hubei_chongqing_r6.md` |
| 青岛市 | **623** | 瑞数全站连首页都 412；有头一次过；**fetch ~80 次/会话配额，失败即转真实导航全程无阻**；失信真身 WAS5 channelid=223090（503）；:6883 处罚平台 545 收 98 过门槛 | `sources/qingdao_hunan_r6.md` |
| 湖北省 | **211** | 443 黑洞全程 http；失信 `/hbsw/xxgk/zdsswfal/` 167 全量（2020 后停更历史存量）；gspt 平台 5 条 10 字索引型 DEL | `sources/hubei_chongqing_r6.md` |
| 宁波市 | **273** | 瑞数五代（全 URL 带 m4oH8x2I 令牌，文章逐页 goto）；失信 13 区子栏 19 页；156 条涉税通知全 DEL（程序性送达名单——门槛有效） | `sources/shaanxi_ningbo_r6.md` |
| 陕西省 | **67** | 失信 TRS 检索四年枚举 167→67 唯一主体（全文）；zfgs:88 平台三层封锁（扭曲验证码+XHR 随机 412+验证码被刷返空白）放弃 | `sources/shaanxi_ningbo_r6.md` |

本轮合计 **+3,351 件**（失信主体全量 4,343 + 处罚/通报），全部 quality_prune KEEP。

## 〇g、第五轮总述（质量清理 + 行动前调研 + 通宵采集）

### 1. 质量清理（用户裁决：删无参考价值文件）
- **删除 6,722 件**（留档 `pruned_files.json`）：信用浙江索引型 3,069、上海催报催缴送达 562、信用广东纯金额告示 1,090、江苏无附件送达 499、欠税名单 48、其他程序性公告
- **判定规则固化**（`quality_prune.py`，已写入 AGENT_BRIEF 强制门槛）：违法事实/事由叙述 ≥30 中文字符才入库；催报催缴/欠税名单/索引列表一律不收；采集时就地判定 DEL 不入库
- 清理后全库 audit：RICH 94.3%

### 2. 行动前调研（`_research/rich_sources_round5.md`，10+ 省实测）
新落地：浙江政务网处罚 API（P0）/ 安徽 16 市（P1）/ 辽宁 sword+失信栏（P1）/ caseopen 判决书（部分）。判死：福建（anji 部署缺陷人机均不可过，〇f）、天津批次（4-13 字短语）、河南（官网无数据）、湖北/重庆/陕西/宁波（瑞数全站墙）、厦门（空库）、openlaw（强制登录）。

### 3. 通宵采集 +4,370 件（全部过质量门槛）
| 信源 | 件数 | 文档 |
|---|---|---|
| 裁判文书·税务行政管理 | 1,838（caseopen 首批全文，余量待 CF 宽限，`caseopen_harvest.py` 续跑） | 本文件〇g.4 |
| 浙江省·行政处罚公示 | 1,193（政务网 API 零验证码；6,302 全扫 19% 过门槛；与信用浙江索引 99.7% 对上） | `sources/zhejiang_zwfw.md` |
| 辽宁省 | 1,211（〇e） | `sources/liaoning_sword.md` |
| 安徽省·16 市 | 128（正文汉字中位 907 字） | `sources/anhui_tianjin_r5.md` |

### 4. caseopen 裁判文书链路（playwright 有头导航法，新增关键经验）
主页过 Anubis+CF → goto `/api/search?...&export=true`（limit 强制 2000 含全文）→ **稳定提取循环**（innerText→json.loads 重试至完整，挑战重导期间捕获异常重试）→ 单页 9.3MB/2,000 份全文约 48s。**当晚 CF 升级 Turnstile 交互挑战后自动浏览器不可过**（坐标点击/challenge iframe 均无效）——已存 2,000 份；剩余（税务行政管理余 2,885 + 逃税罪 2,634 + 虚开/骗税 2020后子集）待 CF 宽限窗口用 `caseopen_harvest.py` 续跑（断点在 `tmp/caseopen_progress.json`）。

## 〇f、第五轮增量·二（2026-10-11，福建攻坚）

| 项 | 结果 | 关键路径 |
|---|---|---|
| **福建·etax xxmh 处罚公示** | ❌ **0 条**（验证码不可过，判定服务端部署缺陷） | API 契约全破（querySwxzybcxcfjg.do form 字段/count 格式/翻页免码推断）+ sso 验证码全链路逆向（anji-plus 系 **SM4-ECB** pointJson，gmssl 与站点 sm4.js 逐字节一致；playwright 网络日志解密证明请求=浏览器请求）。但 clickWord check 对一切与图面一致的坐标一律 6111：12+ 轮求解（VLM 九宫格映射双重验证、4 坐标策略、Java2D 锚点模拟、有头真浏览器点击）全败；speech 分支 500、blockPuzzle 被强制 clickWord、旧图码后端已不认——迁移半成品形态。**人机均不可过**，复跑条件见文档第 8 节。`sources/fujian_etax.md` |

## 〇e、第五轮增量（2026-10-10/11，辽宁采集）

| 项 | 结果 | 关键路径 |
|---|---|---|
| **辽宁·sword 处罚公示** | ✅ **+216 件**（全省 213 机关 5,537 条，量控收 5,000，quality 门槛后入库） | etax.liaoning:8090 wings/sword 平台**有数据**（山东同款平台各省中唯一；浙江空库）。requests+浏览器 UA 直连 `POST /ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg`（swjgDm 逗号拼接 213 码一次查、rows=200 有效、**验证码服务端强制但 ddddocr 过码率~75%**，每 POST 消费一码；默认 UA 403）。wfsd 事由字段普遍短语（4.3% 过 30 字门槛，long-but-thin-facts 规则救回部分）。adapter `ln_sword.py`+`ln_sword_md.py` |
| **辽宁·主站失信公布栏** | ✅ **+995 件**（col1030 总量 ≈1,990，上限收 1,000，99.5% 过门槛，事实叙述中位 74 字） | 真源不在平台（gssxDm=19 披露页 213 机关仅 2 条无叙述）而在主站 `/module/search/index.jsp?i_columnid=5883`（10 条/页，currpage 超界钳尾页）+ art 详情 `<!--<$[label]>begin/end-->` 标记解析。col1030 路径级大汉 JS 挑战已**纯 python 求解**（decode_lmcl 三轮字节变换解 LMCL 令牌，必须作 query 首参重放，通过后种 UqZBpD3n3iXPAw1X cookie）。adapter `ln_sx.py`。`sources/liaoning_sword.md` |

## 〇d、第四轮增量（2026-10-10 深夜，网络环境变更对照实验：新 IP 下两省通过）

| 项 | 结果 | 关键路径 |
|---|---|---|
| **信用广东** | ✅ **+1,846 件**（含处罚内容全文：法条+罚款金额） | **网络环境变更（手机热点新 IP）后的对照实验：验证了访问受限（403）与出口 IP 信誉相关**：同一滑块算法（tianai CONCAT 纯算法）新 IP 下 check 5/5、过滤查询 200。流程=gen→check→VALIDATE_CODE_ID→`jsonArgs={"cf_cfjg":"like;税务"}`翻页（每码约翻 10 页/分钟级过期，403 即重解，全程 20 次解码收 38 页）。`tmp/gdslider/gd_harvest_cc3.py` 可复跑 |
| **信用浙江** | ✅ **+3,069 件**（索引型：文号/相对人/信用代码/日期/机关全映射） | **浙江税务处罚数据的真实去向**：省税务局 sword 平台空库，数据在**信用浙江**（credit.zj.gov.cn 双公示）。列表 API 直连无验证码：`POST https://xyxx.zjzwfw.gov.cn/router/api/p/creditXygsGetXzcfList` body `{"entity":{"wsh":"税",...},"current":N,"size":≤100}` → wsh 含"税"过滤 total=3069。详情端点 `creditXygsGetXzcfDetail` 被**点击式汉字验证码**单次门禁（captchCode 单次消费，7 种识别方案 ~1/8 过码率不可规模化）——详情暂缺，md 标注"详情未取"留 esId 回补。`sources/zhejiang_credit.md` |
| **curl_cffi timeout 量纲坑** | 重要 | 本机 curl_cffi 0.16.3 的 `timeout=N` 实际按 **N×100ms** 解析（25→2.5s）——移动热点高延迟下全部假超时；修正为传 N×10。已固化进 gd_harvest_cc3.py |

## 〇c、第三轮增量（2026-10-10 晚，恢复续跑后）

| 项 | 结果 | 关键路径（详见对应 sources/ 文档） |
|---|---|---|
| **12366 全库** | **+5,474 件**（问题解答 5,019/5,027 + 办税流程 196/196 + 表证单书 259/274） | 双 worker 并行 55 分钟；zlflag=1 税收法规跳过（法规库已覆盖）；8 件死链核实。`sources/12366_full.md` |
| **四川** | **+2,002 件**（行政处罚公示 1,000（etax 决定书级）+ 重大税收违法失信公布 1,000） | 有头 chromium 轮询过瑞数 → 会话内 evaluate 抓 etax `query_swxz_ybcx_cfjg.spring`（fetch+TextDecoder）与主站 jsearch（必须页面自身 jQuery $.ajax，裸 fetch 415）；cookie 复放死路与北京结论一致。**栏目更正：col2720 空壳、col8705/11932 已 404，真数据在 etax 平台**。`sources/sichuan_river.md`，adapter `sc_river.py` |
| **浙江 sword** | 终局闭环：**平台空库**（验证码 100% 流程打通、13 组实验确证无数据；浙江处罚真实形态是 col13226 新闻通报 52 件已入库） | 验证码 ddddocr 过码率 70-80%（关键：URL 参数是 `&t=<随机32位>&id=ck1` 非 ckcodeId）。`sources/zhejiang_sword.md` |
| **信用广东滑块** | 定格：滑块本体 **100% 已求解**（tianai CONCAT 型纯算法 5/5；非缺口型，ddddocr 无用）但查询网关带 VALIDATE_CODE_ID 仍 403（疑 IP 临时风控/轨迹分级）；**采集脚本就绪** `tmp/gdslider/gd_harvest_cc.py`，隔夜重试一条命令全量 | `sources/credit_gd_slider.md`（含三假设与分辨实验设计） |

## 〇b、第二轮增量（2026-10-10 下午）

| 项 | 结果 | 关键路径 |
|---|---|---|
| 山东·行政处罚公示 | **+3,243 件**（决定书级结构化数据） | IAB 内置浏览器自动过网宿 wswaf → 页面内 fetch `POST /zfgspt/extranet/shgs/query_swxz_ybcx_cfjg.spring`（**验证码纯前端校验，数据接口不验**）→ 40 页×100 条采集，KEY 去重（服务端 total 虚高 3933→实 3243）→ JSON→md。详见 sources/browser_round2.md |
| 四川（浏览器） | 失败（wswaf 第二轮挑战 webview 不执行） | 维持微信公众号通道；路线=桌面 Chrome 人工过+CDP cookie |
| 裁判文书 caseopen.org | **研判完成，不下载 102G**（种子仅到 2021；涉税子集仅 5.6 万件占 0.04%） | 改走 caseopen 在线 API（`cause:`+`year:` 字段查询，`/api/search?export=true` limit 强制 2000 含全文）；IAB 内大数据搬不出来（CF 拦 fetch + webview 搬运超时），全量需桌面 Chrome。实测计数：税务行政管理 4,723（2021 后仅 310）/逃税罪 2,634/虚开增专 40,896/骗税 41,879。报告 `_research/wenshu_value_assessment.md` |
| OCR 补全 | 江苏 106 扫描件+全库 PDF 附件 → MinerU pipeline OCR 追加「## 附件（扫描件 OCR 全文）」（子智能体执行） | MINERU_TOKEN 环境变量；CLI 同法规库 mineru_upgrade.py 用法 |
| 案例要素结构化 | **全部 md 附 标签/要素 front matter + `taxcase_structured.jsonl`** | `work/taxcase/structure_extract.py`（规则版：税种 22 词典/违法类型 14 类正则/行业 12 类/法条/罚款倍数/涉案金额/移送司法/程序类型） |
| 扩源（广东重点） | 信用广东/21 市局子站/12366 等（子智能体执行，产出见 sources/expand_round2.md） | |

## 〇、建库结果总览（2026-10-10 定格）

| 地区 | 栏目 | 件数 | 采集通道 |
|---|---|---|---|
| 国家税务总局 | 税案通报 | 1144 | manuscriptList 接口全量（2021-08→2026-09，0失败） |
| 国家税务总局 | 税务合规典型企业案例 | 70 | /getFileListByCodeId JSON 接口全量 |
| 上海市 | 行政处罚公示 | 1102 | JSP 平台 yzmflag=1 绕验证码，列表 JSON 即全字段 |
| 上海市 | 文书送达公告 | 562 | was5 检索聚合 16 区局 |
| 上海市 | 税案通报+稽查公布 | 46+8 | 税务新闻过滤 |
| 江苏省 | 处罚决定书送达公告 | 826 | 15 个市局大汉CMS栏，**附件全文提取**（PDF 153 + 旧.doc Word COM 321 + docx 37；扫描件跳过 106） |
| 江苏省 | 税案通报+行政复议送达 | 67+3 | col24019 全量 + 标题含"复议" |
| 深圳市 | 税案通报+行政处罚公示 | 80+3 | 开普云 SaaS search5 接口（zs.kaipuyun.cn），覆盖市局+7区局 |
| 北京市 | 行政处罚公示+税案通报 | 61+40 | 瑞数墙破法：有头 playwright 过挑战后 page.evaluate(fetch) 调 servlet |
| 天津市 | 税案通报+通知公告案例 | 43+6 | POST 表单翻页（u_zlmViewMx.action） |
| 广东省 | 税案通报（以案释法+稽查新闻） | 42 | gdtaxejs JSON 列表接口 + search5 关键词枚举 |
| 浙江省 | 税案通报 | 52 | 大汉CMS dataproxy.jsp POST 翻页 |
| 财政部 | 会计信息质量/财会监督检查公告 | 46 | 监督评价局栏目全量 11 页 |
| 最高检 | 涉税典型案例/指导性案例/公益诉讼 | 7 | 栏目枚举+标题过滤（354+1059+63批扫完） |
| 最高法 | 危害税收征管犯罪典型案例 | 2 | 站内搜索补获（栏目漏收） |
| 证监会 | 涉税行政处罚 | 4 | 处罚 channel JSON 接口扫近2年240件人工复核 |
| 山东省 | 税案通报 | 4 | 微信公众号（官网被 wswaf 拦） |
| 四川省 | 税案通报 | 3 | 同上 |
| **合计** | | **4,221** | manifest.csv + taxcase_corpus.jsonl（微调语料） |

## 一、数据源与入口（实测）

| 源 | 入口 | 列表机制 | 详情结构 | 状态 |
|---|---|---|---|---|
| 总局·税案通报 | https://www.chinatax.gov.cn/chinatax/n810219/c102025/common_listwyc.html | TRS CMS。首页静态 20 条；分页走 `POST GET /chinatax/manuscriptList/c102025?_isAgg=0&_pageSize=20&_template=index&_channelName=税案通报&_keyWH=wenhao&page=N`（共58页≈1160件，覆盖2021-08至今） | `/c{id}/content.html`；正文 `div.article-content#zoomcon`；标题 `h2.article-subtitle`；日期 `<PUBLISHTIME>` | 全量抓取 |
| 总局·税务合规典型企业案例 | https://www.chinatax.gov.cn/chinatax/c103110/swhg.html | 专题页 JS 渲染，数据接口 `POST /getFileListByCodeId` body=`{codeId:"c103110", channelId:"ada319f627474aecbb95d68b274b5fc7", page, size}`，返回 `results.data.results[]`（含 url/titleHtml/publishedTimeStr），共70件 | 同上 content.html | 全量抓取 |
| 各省税务局 | `<省拼音>.chinatax.gov.cn` | 各省异构：总局系TRS（manuscriptList 或静态 index_N.html）、大汉CMS（`/art/2026/9/28/art_23636_13381.html`，列表 `/art/<col>/list.html`）、查询系统 | 见分省 sources/*.md | 6省+2市并行抓取 |
| 两高/财政部/证监会 | 见 sources/lianggao.md | 各异 | 各异 | 抓取中 |

## 二、关键技术结论（必读，全部实测）

1. **TLS 指纹反爬（最大坑）**：chinatax.gov.cn 主站对 python-requests 的 TLS 指纹返回"无数据壳页"（27KB，有分页链接但无条目），curl 命令行和 **curl_cffi（impersonate="chrome124"）** 均可拿到完整页（30KB）。→ 一切抓取必须走 `curl_cffi`（`pip install curl_cffi`）。壳页与完整页大小差约 2.7KB，可用条目数判断。
2. **编码**：省局常见 GBK。响应头无 charset 时要从 HTML meta 探测（taxcase_scrape.Resp 已内置）。
3. **列表两形态**（同属总局 TRS 系）：
   - 静态列表页：`<a href title="..."> + <span class="time">2026-09-28</span>`
   - manuscriptList 接口页：`<a href>标题文本</a> + <span>[2026-09-28]</span>`，URL 是绝对 http://
   → `parse_list_items` 用 BS4 通用解析兼容两者；过滤条件 `content[_0-9a-f]*.s?html|/c\d+/...html` + 同 host。
4. **专题页 JSON API**：总局专题（如 swhg.html）正文区 `#boxshow` 由 `POST /getFileListByCodeId` 填充，body 结构与 channelId 在页面内嵌 `<script>` 里（`getData(1)` 函数）。返回路径 `results.data.results[]`。
5. **详情提取**：容器优先级 `.article-content → #zoomcon → .TRS_Editor → #zoom → article → ...`，正文≥120字才采纳，否则 p 块兜底。噪音清理：script/style/分享/字号/打印/分页。
6. **图片处理（md-only 库）**：不保存图片文件，正文里相对路径图片改写为绝对 URL（`_abs_md_images`），保留可溯源链接。
7. **限速合规**：单线程 + `delay≥2.2s + 0-1s 抖动`（polite_get 全局令牌），无 robots.txt 但保持礼貌频率；1160 件约 60 分钟。
8. **断点续抓**：`progress/<job_id>.jsonl` append-only，最新为准，重跑自动跳过 ok 项。
9. **PDF 附件**（复议决定书常见）：有文本层用 pymupdf 提取转 md；扫描件跳过并计数（MinerU OCR 可后续升级，参考法规库 mineru_upgrade.py）。

## 三、目录与产出规范

```
lawlibrary/专题/税务案例/
├── manifest.csv              # build_manifest.py 生成（地区/栏目/标题/日期/文件/链接/字数）
├── taxcase_corpus.jsonl      # 微调语料（id/meta/text，正文去 front matter）
├── 国家税务总局/{税案通报,税务合规典型企业案例}/
├── <省或市>/<栏目>/
└── {最高人民检察院,最高人民法院,财政部,证监会}/<主题>/
```

front matter 统一字段：`title / 来源机关 / 栏目 / 地区 / 发布日期 / 原文来源 / 抓取日期 / 原文链接`（附件链接可选）。
文件名：`{发布日期}_{标题安全化}.md`（Windows 非法字符清洗，≤80字）。

## 四、分省机制速查（详单见 sources/*.md）

| 站点 | CMS/机制 | 列表翻页 | 详情/数据接口 | 反爬 |
|---|---|---|---|---|
| 总局 www | TRS | `GET /chinatax/manuscriptList/{code}?...&page=N` | 静态 content.html | TLS指纹（curl_cffi 过） |
| 总局专题页 | 自研 | `POST /getFileListByCodeId` (JSON) | 同上 | 同上 |
| 上海 | TRS+JSP平台 | 处罚：`POST /newxbwz/gspt/xzcf/YbcxcfCtrl-ybxzcfcx.pfv`（yzmflag=1）；公告：was5 检索 `orderby=-docreltime` | 列表 JSON 即全字段 | 无 |
| 江苏 | 大汉CMS | `POST /module/web/jpage/dataproxy.jsp?startrecord=..&endrecord=..`（unitid 从列表页 nextgroup 取） | 附件 `/module/download/downfile.jsp?filename=<md5>.pdf/doc`；搜索 `/jsearchfront/interfaces/search.do` | 无（TLS指纹同坑） |
| 深圳 | TRS | 静态 `common_list_N.shtml`；搜索走开普云 `POST https://zs.kaipuyun.cn/search5/search/s`（siteCode=bm29360001） | 详情 URL 无 content_ 前缀（`/YYYYMM/hash.shtml`），通用正则匹配不到 | 无 |
| 广东 | TRS | `GET /gdtaxejs/common/search/{channelId}?_pageSize=20&page=N&_isJson=true`（channelId 在列表页内联 JS）；搜索 `POST /search5/search/s` | 相对 URL 基准是**站点根** | 无 |
| 浙江 | 大汉CMS | 同江苏 dataproxy（窗口15实际返回46条，须按URL去重） | meta ArticleTitle/ContentSource/Maketime | 处罚公示收敛到 :16002 验证码平台（放弃） |
| 北京 | TRS+瑞数 | 列表静态；处罚数据 servlet `POST /bjsat/xzzf/SwxzybcxcfjgServlet?page=N` | **有头 playwright 过瑞数 → page.evaluate(fetch) 调 servlet → JSON** | 瑞数412（无头也被识别，cookie 复用不稳） |
| 天津 | 自研 | `POST /u_zlmViewMx.action`（fjdm/lmdm/page 表单） | meta ArticleTitle/PubDate | 无 |
| 山东/四川 | — | 官网全被网宿 wswaf（412→JS→400，疑IP信誉） | 替代通道：微信公众号（搜狗微信→mp.weixin.qq.com 原文） | wswaf；后续路线=更换网络环境+真浏览器人工完成一次挑战，CDP 导出 Q* cookie（约7天有效）给 curl_cffi |
| 最高检 | TRS | 静态 `index_N.shtml`（无 index_1！createPageHTML 末参数=总条数） | 死链302回首页（title==首页判别） | 无 |
| 财政部 | 自研 | 静态分页 | 详情 URL 必须带月份目录 `/jianchagonggao/YYYYMM/t....htm` | 无 |
| 证监会 | 自研 | `searchList/{channel}__render.js` 揭示的 JSON 接口 | 决定书同名须正文解析文号+当事人 | 无 |

## 五、量控与增量策略

- 近三年优先（date_from=2023-01-01）；官方通报类栏目全量。
- 单栏目 cap 50 页 / 1000 件（处罚公示类量大，宁精勿滥）。
- 增量更新：重跑 job（断点自动跳过，只抓新列表页出现的新 URL）；建议每月一次。
- 去重：原文链接为唯一键（build_manifest.py --prune 可物理去重）。

## 六、坑点与未决

- **省站反爬两档（预研实测14省）**：沪/苏/粤/浙/豫/深/辽/闽/皖裸 curl 可抓；**京/川/陕为瑞数（HTTP 412 + $_ts JS 挑战）、湖南类加速乐、山东 etax 亦瑞数** → 需 playwright 真浏览器或放弃直连（分省 agent 已被告知不死磕）。
- **裁判文书不要自爬**：wenshu.court.gov.cn 2024 年起检索大幅受限（历史瑞数→sojson）。正确路径：下载社区全量包（cncases/cases 项目，102G/8500万+文书，BT `810air.torrent`；备份磁力链 amakerlife 仓库）按案由过滤「税务行政管理/逃税罪/虚开增值税专用发票罪」。当前 md-only 库未纳入，留作后续专项。
- GitHub 无现成税务案例爬虫（最相关 35★ 2019 停更）；HuggingFace 无中国税务数据集；CAIL2018 纯刑事不含税务行政——**自建库本身即稀缺资产**，对外只开源脚本与元数据、不发文书原文。
- 税务行政复议决定书最稀缺（2023 新复议法才要求公开），散见地方专栏——各省 agent 重点找。
- 信用中国涉税处罚未纳入本批（查询系统型，量大，留作交叉验证源）。
- 详细调研见 `_research/tax_case_projects.md`（项目明细+坑点）与 `_research/baidu_netdisk_api.md`（网盘通道）。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
