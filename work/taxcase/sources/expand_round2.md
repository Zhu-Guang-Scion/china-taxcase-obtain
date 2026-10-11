# 税务案例库扩源 round2 —— 新信源与机制记录

日期：2026-10-10 ｜ adapter：`adapters/gd_city_cases.py`、`adapters/national_12366.py`、`adapters/gd_random_inspection.py`
背景：round1 后广东省仅 42 件（见 guangdong.md），本轮定向扩市局子站 + 新类型信源。

## 一、广东省 21 市子站（guangdong.chinatax.gov.cn/gdsw/{城市代码}）

- 市频道入口：`/gdsw/{code}/{code}_index.shtml`（首页解析所得；20 市代码见 adapter CITIES 表，
  广州 gzsw、珠海 zhsw、汕头 stsw、佛山 fssw、韶关 sgsw、河源 hysw、惠州 hzsw、汕尾 swsw、
  东莞 dgsw、中山 zssw、江门 jmsw、阳江 yjsw、湛江 zjsw、茂名 mmsw、肇庆 zqsw、清远 qysw、
  潮州 czsw、揭阳 jysw、云浮 yfsw；深圳独立站已另抓）
- 每市栏目（TRS 同构）：通知公告 `{c}_tzgg`（广州为 `gzsw_tggg`）、工作动态/税务新闻 `{c}_swxw`、
  基层动态 `{c}_jcdt`、基层公告 `{c}_jcgg`（仅东莞/中山）、媒体视点 `{c}_mtbd`（仅茂名）、
  广州工作动态 `gzsw_gzdt`（列表页非 city_list/common_list 命名，get_channel_id 多模式回退）
- **机制与省站完全一致**：列表页内联 JS `channelId = "32hex"` →
  `/gdtaxejs/common/search/{channelId}?_pageSize=20&page={n}&_isAgg=true&_isJson=true&_template=index`
  返回 newest-first，`url` 为 `../../gdsw/...` 相对路径（基准=站点根）；
  翻到 `publishedTimeStr < 2023-01-01` 即停。`_rangeTimeGte` 参数无效（不过滤）。
- 标题过滤：TITLE_KW（处罚|查处|曝光|骗取|虚开|偷税|逃税|失信|违法|税案|以案|案例|复议|欠税|
  送达|强拍|变卖|抵税|稽查|移送|追缴）+ 排除词（采购/招标/培训/党建/目录清单/服务…）。
- 归类目录：`广东省/<市名>/{税案通报,行政处罚公示,文书送达公告,欠税公告,执法公告,重大税收违法失信公布,行政复议}/`
- **重大发现：东莞"稽查局税务文书送达公告"（东税稽公告〔20xx〕N号）量大（3 年 29+ 批，
  jcgg+tzgg 共 339 候选），正文几乎全部在 docx/doc 附件里**，页面正文仅一两行。
  adapter 已加附件抽取：docx→python-docx（含表格）、pdf→pymupdf；老 `.doc` 二进制无解析器，
  记为未提取。附件相对路径基准是**详情页所在目录**（`.../{hash}/files/{hash}.docx`，
  无 content_ 前缀），不是站点根。
- 各市真实产出差异极大：东莞独发稽查送达公告；佛山/惠州/珠海/广州的 tzgg 以行政通知为主，
  案件类只有零星几条（搜索证实属实，非漏抓）。

## 二、国家税务总局 12366 纳税服务平台（12366.chinatax.gov.cn）—— 问题解答库

- 入口：`/sscx/main`（知识搜索页，SPA）；数据接口（反向自 zsk_search.js）：
  - 列表 `POST /sscx/search`，form: `zlflag=2`（问题解答；1=税收法规、3=办税流程、5=表证单书）、
    `keywords=''`、`order=desc&sortField=ZLFBRQ`、`page`、`pagesize`（**服务端封顶 10**）。
    返回 `pageContent[].ZLNR` 仅 156 字预览。
  - 全文 `POST /sscx/toDetail`，form: `code={ZLCODE}&flag=2` → `bean.ZLNR` 全文（HTML 片段+实体）。
- 全库 totalRow=5027 条问答；2026-10-10 第三轮已**全量抓完**（5,019/5,027 入库，8 条服务端空内容死链），
  同时抓齐 zlflag=3 办税流程 196 件与 zlflag=5 表证单书 259 件 → 详见 `sources/12366_full.md`。
- 坑：pagesize 传 50 服务端只回 10；ZLNR 需 html.unescape + `<br/>`→换行；抓取 POST 需带
  Referer/Origin（12366 域），X-Requested-With 非必需。
- 价值：全国统一的税务实操问答（扣缴、优惠、申报），对 RAG 应对类能力是全新类型。

## 三、双随机/随机抽查公示（广东省站，search5 检索发现）

- 省站"行政执法公示平台"的**双随机抽查结果**是 TRS shtml 新闻页（与已知空壳 JSP 处罚列表不同源）：
  频道 `/gdsw/ssjygkgzdt/`（执法公开工作动态）、`/gdsw/SSJYGK/`（大写，市局公示多发此处）、
  `/gdsw/ssjgzdt/`、`/gdsw/gongzuoqingkuang001/`（年度"双随机"抽查情况和抽查结果公示）。
- 用 search5（POST /search5/search/s，siteCode=bm29190001）关键词：随机抽查/双随机 检索，
  2023+ 标题含"抽查"且非政策文件 → `广东省/<市名>/随机抽查公示/`（无市名归省级目录）。
- 2023-2026 每年省局+佛山+肇庆等市局公示均在（上海同类已有 8 件入库，广东本轮补齐）。

## 四、信用广东（credit.gd.gov.cn，即 creditchina.gd.gov.cn）—— **验证码墙，未抓取**

机制已探明（供浏览器智能体接手）：
- 处罚列表 API：`POST https://credit.gd.gov.cn/gdcreditwebApi2/company/web/booleanQueryListByPageSimple`
  （request.js 里 proxyString=/gdcreditwebApi2/；需头 `Request-Client-Set: xygd-web`、`Accept: application/json`、
  Origin/Referer）
  form: `tableName=v_ztk_03_sgs_xzcf&page=1&rows=15&orderArgs=[{"cf_jdrq_sort":"desc"}]`
  （records=137,634，字段 cf_xdr_mc/cf_cfjg 处罚机关/cf_nr 处罚内容/cf_jdrq 决定日期/cf_wsh 文号）
- **403 规则（实测）**：①带 `jsonArgs` 过滤（如 `{"cf_cfjg":"like;税务"}`）一律 403；
  ②`page>5` 403；③rows>50 未验证（50 可用）。即无验证码最多拿 5 页×50 条未过滤数据。
- 带过滤的查询需要滑块验证码签发的 `VALIDATE_CODE_ID`（前端 showValidateCode，约 1 分钟超时后
  分页再 403），uuid 伪造无效。→ 归入「待浏览器智能体处理」。

## 五、广东政务服务网（www.gdzwfw.gov.cn）

首页静态可达（200），处罚公示为 SPA 无静态链接，未探明接口，时间盒内放弃 → 待浏览器智能体处理。

## 六、总局站既有类目核查

`国家税务总局/` 已有 税案通报 1144 + 税务合规典型企业案例 70（另一智能体已覆盖），
违法黑名单新闻稿/合规指引方向不重复投入。

## 产出统计（运行后回填）

（见文末「最终数字」）

## 六点五、其他省「稽查随机抽查公示」线索（本轮未抓，供后续轮次）

- 上海：shanghai.chinatax.gov.cn `/xxgk/tzgg`（2025年度随机抽查结果，随机抽取 1200 户先自查再检查）——上海目录已有 8 件同类，可核对是否漏 2025 年度件
- 四川：sichuan.chinatax.gov.cn 信息公开下设「双随机、一公开」「行政处罚决定和结果公示」专栏（结构化栏目，量大）
- 山东：shandong.chinatax.gov.cn「检查计划」栏目 + 各地市稽查局分散公示（烟台/枣庄/聊城等）
- 北京：beijing.chinatax.gov.cn「双随机一公开」专栏（2022-2024 计划与结果）
- 新疆：如 铁门关税务局稽查局 2025 随机抽查检查结果公示（xinjiang.chinatax.gov.cn）
- 贵州毕节等市局稽查局亦有同类公示

## 六点六、坑：并发保护

- MSYS(Git Bash) 下 `pgrep -f python脚本名` **找不到 Windows python 进程**，链式等待脚本会提前放行，
  造成同站双进程并发（本轮发生过一次，已 kill 重排）。同站任务排队必须以**日志标记文件**为握手信号。
- TaskStop 杀 bash 后其子 python 会继续跑完当前命令并可能执行下一行（孤儿进程），需 `wmic`+`taskkill //T` 清理。

## 待浏览器智能体处理

| 站点/入口 | 现象 | 已探明信息 |
|---|---|---|
| credit.gd.gov.cn 行政处罚列表 | jsonArgs 过滤 / page>5 → 403 滑块验证码墙 | API 见上节四；VALIDATE_CODE_ID 需滑块，1 分钟超时；无过滤可拿 250 条；按"处罚机关=税务"过滤后全省量级上千 |
| www.gdzwfw.gov.cn 行政处罚公示 | SPA 无静态链接 | 未探明接口 |
| 东莞/揭阳等送达公告 .doc 老格式 + .xlsx 明细附件 | python-docx 不支持 .doc；xlsx 未接 openpyxl | 73 个 md 内已留"未提取"标记与附件 URL；补齐可用 openpyxl(xlsx)+LibreOffice/antiword(.doc) 按附件 URL 回填 |

## 最终数字（2026-10-10 16:55 回填）

| 来源 | 目录 | 新增 md | 失败/跳过 |
|---|---|---|---|
| 广东省 19 市子站（pass1 全市 + pass2 东莞附件重试 + 广州补跑） | 广东省/<市名>/{税案通报,文书送达公告,欠税公告,执法公告,行政处罚公示,重大税收违法失信公布,行政复议} | **281** | pass1 46 件 docx 正文页失败，pass2 附件抽取后全部恢复；.doc 老格式 73 处未提取（见待浏览器） |
| 双随机/随机抽查公示（省站 search5 检索） | 广东省/{随机抽查公示,肇庆市/随机抽查公示,...} | **11** | 1 件 404 |
| 12366 问题解答库（最近 300 条，2025-05~2026-10 发布） | 全国/12366热点问答 | **300** | 0 |
| **合计新增** | | **592** | |

- 广东省目录：42 → **334**（全省 21 市全覆盖，东莞 111 / 揭阳 28 / 茂名 15 最多——
  东莞=稽查送达公告+欠税公告大户，揭阳=文书送达公告，其余市多为税案通报+欠税公告各若干）
- 全库由 4,221 增至 8,056（含其他智能体同窗口产出；本智能体贡献 +592）
- 栏目类型新增 4 类：12366热点问答（全国）、文书送达公告、欠税公告、随机抽查公示（广东省内）
- 增量重跑：`python adapters/gd_city_cases.py --city dg --budget 900`（progress jsonl 断点续抓，
  URL 与省轮 gd_cases.jsonl 互通去重）；`python adapters/national_12366.py --limit 300`；
  `python adapters/gd_random_inspection.py`


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
