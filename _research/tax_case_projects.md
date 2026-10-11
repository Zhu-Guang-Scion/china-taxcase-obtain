# 中国税务案例/文书数据集与抓取项目调研报告

> 调研日期：2026-10-10。调研方式：GitHub API 检索、HuggingFace（经 hf-mirror）API 检索、WebSearch（中英文）、对 chinatax.gov.cn 总局及省级站点的直接 HTTP 实测（curl，默认 UA）。
> 用途：为自建「税务案例库」（税案通报 / 处罚公示 / 重大税收违法失信 / 税务行政复议决定书 / 涉税裁判文书 → markdown → RAG/微调）提供经验参考。
> 标注约定：凡标注 **[实测]** 的结论均为本次直接验证，其余来自公开资料，可靠性以链接为准。

---

## 1. 结论速览

1. **公开市场上不存在"现成的中国税务案例爬虫"可以直接复用。** GitHub 上"税务×爬虫"合计仅 6 个仓库，最高 star 35（outerman/tax-policy-crawler，2019 年停更，且抓的是"政策"不是"案例"）。税务案例抓取基本是一片空白，需要自建。
2. **涉税裁判文书不需要自己爬。** 社区已有两份裁判文书网全量备份流通：macrodatas.cn 的 102G / 8500 万+ 文书全量包（cncases/cases 项目的数据源，BT 种子公开）和 amakerlife 的 94.3GB 磁力链备份。从全量包里按案由（税务行政管理、逃税罪、虚开增值税专用发票罪等）过滤，是最现实的涉税裁判文书获取路径。
3. **裁判文书网本身（wenshu.court.gov.cn）自 2021 年起持续收紧、2024 年起检索大幅受限，不要再投入逆向成本**——历史上它是瑞数 WAF（cookie `FSSBBIl1UgzbN7N80T`、参数 `MmEwMd`），社区逆向项目（476★）也已提示站点后来更换为 sojson 类加密；旧爬虫（sixs、Henryhaohao、Leon406 等）全部失效。
4. **国家税务总局官网（www.chinatax.gov.cn）对爬虫非常友好 [实测]**：无 robots.txt（404）、无 WAF、纯服务端渲染静态 HTML，且存在一个可直接翻页的列表接口 `/chinatax/manuscriptList/{栏目code}?page=N`。"税案通报"栏目即 `c102025`。**这是最容易落地的一块，应最先做。**
5. **省级税务局站点反爬分裂成两档 [实测]**：上海/江苏/广东/浙江/河南/深圳/辽宁/福建/安徽等裸 curl 即 200；北京/四川/陕西为瑞数（HTTP 412 + `$_ts` JS 挑战）、湖南为类加速乐挑战页（412 + `/MMB1_*.js`）、山东电子税务局（etax）也是瑞数。后者需 playwright 或放弃直连。
6. **HuggingFace 上没有任何中国税务专项数据集**；CAIL2018 为纯刑事案件（268 万份，202 罪名），不含税务行政案件。中文法律 SFT 数据集（DISC-Law-SFT、lawyer_llama_data 等）以法条问答为主，税是边角料。
7. **没有人整理过"各省税务局行政处罚公示入口汇总"清单**（awesome 法律资源清单里也没有税务条目）。各省公示入口分散在各自的"行政执法信息公示平台"，URL 无统一规律，需要逐省踩点。这本身就是本项目可以产出并开源的第一个成果。
8. **税务行政复议决定书是最稀缺的一类**：2023 年新复议法第 79 条才要求公开，网上散见于地方司法局专栏和商业数据库（CnOpenData 售卖），没有批量公开源。

---

## 2. GitHub 开源项目明细

### 2.1 税务方向（直接相关）

| 名称 | URL | 数据源 | 技术方案 | 规模/活跃度 | 可复用性 |
|---|---|---|---|---|---|
| outerman/tax-policy-crawler | https://github.com/outerman/tax-policy-crawler | 国税总局及税务机构网站的**税收政策/解读/条约**（非案例） | Scrapy + requests + BeautifulSoup + proxy_pool 代理池；动态 UA、禁 cookie、延迟下载、失败重试、并发、多种存储与排重 | 35★，2019-08 最后 push，**已停更** | 中。架构（scrapy+代理池+断点重试）可参考，但站点 2019 年后多次改版，选择器必失效 |
| gruam23/tax-policy | https://github.com/gruam23/tax-policy | 各地税务局网站（作者维护的多省爬虫脚本集合） | Python 脚本 | 0★，2025-12 push，**近期有维护** | 低-中。无文档无 star，但"多省税务局爬虫文件"的选点可参考 |
| chongli9230/Tax-website-crawler | https://github.com/chongli9230/Tax-website-crawler | 税务网站 | Python | 0★，2020-11 | 低 |
| No-bb-just-do-it/shuiwu | https://github.com/No-bb-just-do-it/shuiwu | 税务 | Python | 2★，2019-03 | 低 |
| chgxdfchgvj/HKKKKk、chgxdfchgvj/HK1 | https://github.com/chgxdfchgvj/HKKKKk | "税务局爬虫" | Python | 1★/0★，2026-08 push | 低（新但无名，未验证） |

**结论：税务案例爬虫这一细分领域在 GitHub 上接近空白，没有任何一个项目覆盖"税案通报/处罚公示/失信公布"三类数据。**

### 2.2 裁判文书方向（可复用于涉税文书子库）

| 名称 | URL | 数据源 | 技术方案 | 规模/活跃度 | 可复用性 |
|---|---|---|---|---|---|
| cncases/cases | https://github.com/cncases/cases | **macrodatas.cn 的文书网全量包（8500 万+ 文书、102G，BT 种子 `810air.torrent` 公开）** | Rust：convert 入库（约 200G DB）→ 建索引（15.5G）→ 本地搜索服务；可选 vsearch + qdrant 向量检索；在线 demo caseopen.org | 1131★，2026-09 仍在 push，**活跃** | **高**。与其爬 wenshu，不如下它的 102G 全量包按案由过滤税务文书；其"入库→索引→(向量)检索"管线与本项目 RAG 需求同构 |
| amakerlife/wenshu.court.gov.cn-backup | https://github.com/amakerlife/wenshu.court.gov.cn-backup | 文书网全量数据备份（网上流传的 94.3GB 全量包） | 仅磁力链接：`magnet:?xt=urn:btih:afa29281baf8ab6a3f5b1e9b9b0799e120611db1` | 71★，2023-12 | 高（作为 cncases 数据源的备份渠道） |
| sml2h3/mmewmd_crack_for_wenshu | https://github.com/sml2h3/mmewmd_crack_for_wenshu | 文书网反爬挑战求解（历史瑞数：`params:MmEwMd`、`html:9DhefwqGPrzGxEp9hPaoag`、`cookie:FSSBBIl1UgzbN7N80T`） | JS 逆向 SDK，提供多语言调用方式 | 476★，2025-10 push | 低-中。README 自述文书网已更换免费 sojson 加密、瑞数算法已开源过时；主要价值是**反爬机制的档案记录** |
| sixs/wenshu_spider | https://github.com/sixs/wenshu_spider | 文书网 | Python | 351★，2018-2022 | 不可用（老接口全失效） |
| Henryhaohao/Wenshu_Spider | https://github.com/Henryhaohao/Wenshu_Spider | 文书网 | Scrapy | 206★，2018-2019 | 不可用 |
| Leon406/wenshukt | https://github.com/Leon406/wenshukt | 文书网 Android App 接口 | Java | 50★，2021 失效停更 | 不可用 |
| nciefeiniu/wenshu | https://github.com/nciefeiniu/wenshu | 文书网 cookie 获取 | HTML+JS | 51★，2020"已终结" | 不可用 |
| guoxw/wenshu- | https://github.com/guoxw/wenshu- | 文书网数据增量更新 | - | 42★，2020 | 不可用 |
| zhang17173/Event-Extraction | https://github.com/zhang17173/Event-Extraction | 裁判文书（事件抽取/判决预测） | Python NLP | 608★，2026-03 push | 中。若要做税务案例结构化（当事人/违法行为/处罚结果抽取），管线可参考 |
| liuhuanyong/LawCrimeMining | https://github.com/liuhuanyong/LawCrimeMining | 裁判文书与犯罪案例文本 | Python NLP | 365★，2018 停更 | 低 |

### 2.3 汇总清单与生态（间接相关）

| 名称 | URL | 说明 | 活跃度 |
|---|---|---|---|
| pengxiao-song/awesome-chinese-legal-resources | https://github.com/pengxiao-song/awesome-chinese-legal-resources | 1004★ 的中文法律数据源汇总（官方/竞赛/开源/咨询网站）。**无任何税务专门条目** | 2023-06 停更 |
| lilialla/awesome-legal-ai-zh | https://github.com/lilialla/awesome-legal-ai-zh | 163★，200+ 个法律 AI 开源仓按场景分类、标注能否商用 | 2026-10 活跃 |
| hiddendevj/Crawler_Illegal_Cases_In_China | https://github.com/hiddendevj/Crawler_Illegal_Cases_In_China | **4738★，中国大陆爬虫开发者涉诉与违规案例库**（含判决与执法案例）。做政府站点抓取前的合规自查必读 | 2026-03 push |
| LawRefBook/Laws | https://github.com/LawRefBook/Laws | 法律法规 markdown 库（与本项目既有法规库定位相同，可互备） | 活跃 |
| DevnorsAI/devnors-data-python（及 devnors-data-mcp） | https://github.com/DevnorsAI/devnors-data-python | **商业数据 SDK**（554★，2026-09 活跃）：一个 API Key 走 `POST /v1/data/query` 查裁判文书（legal_cases）、法条、企业工商、税号开票等，按 token 计费 | 活跃。可作为补充数据源/对照源，注意商业许可 |

---

## 3. HuggingFace 数据集明细

（经 hf-mirror.com API 枚举 + WebSearch 交叉验证；本机无法直连 huggingface.co）

| 数据集 | id | 规模/内容 | 许可证 | 与税务案例的相关性 |
|---|---|---|---|---|
| CAIL2018（官方镜像） | `china-ai-law-challenge/cail2018`（另有 `polinaeterna/cail2018` 等） | 267 万+ 刑事文书（源自文书网 573 万文书筛选），202 罪名/183 法条；Small 版 19.6 万 | unknown（官方未标注） | **无关**：纯刑事案件，无行政案件、无税务案由。回答调研问题 2：CAIL 不含税务行政案件 |
| Lawyer LLaMA 训练数据 | `Skepsun/lawyer_llama_data` | 司法考试题 + 法律问答 SFT | apache-2.0 | 低。可用于税法问答对的构造范式参考 |
| DISC-Law-SFT | `ShengbinYue/DISC-Law-SFT` | 法律引用/司法考试/咨询 SFT 三类 | apache-2.0 | 低（865 下载/181 赞，质量口碑好） |
| LawBench | `RiverGrey/LawBench` 等多个镜像 | 20 项法律任务评测基准（含法条检索、类案检索） | 视镜像 | 低-中。评测框架可借鉴 |
| Chinese-Legal-Case-Classification | `gehits/Chinese-Legal-Case-Classification-Dataset` | 中文案件分类 | cc-by-nc-4.0（**禁商用**） | 低 |
| Refined-Chinese-Legal-Dataset | `zhjdong/Refined-Chinese-Legal-Dataset` | 法律文本精修 | cc-by-nc-sa-4.0 | 低 |
| 税务专项检索（"tax"） | — | 检索结果全部为美国州税矩阵、印度个税、加拿大税务判决等 | — | **无任何一个中国税务数据集** |

**回答调研问题 2：HuggingFace 上不存在中国税务案例数据集；CAIL 为刑事；中文法律数据集以法条/SFT 问答为主。** 自建库如果做好清洗与脱敏，本身就是可发布的稀缺资源（注意文书网数据的再分发合规风险，见第 7 节）。

---

## 4. 学术界与商业数据源

| 名称 | 出处/URL | 内容与规模 | 获取方式 |
|---|---|---|---|
| 锦天城《大数据下 1990-2024 年度全国税务行政诉讼案件实证分析》 | https://www.allbrightlaw.com （2025-12 律所研究报告） | 从裁判文书网/北大法宝筛得 **3909 份税务行政诉讼裁判文书**的实证统计（含筛选口径描述） | 报告免费，原始数据不附带；**筛选口径可复用** |
| 最高人民法院涉税典型案例（2025-11） | https://www.court.gov.cn | 危害税收征管犯罪典型案例一批（逃税/骗税/虚开） | 官网页直接可得，量小质高，适合做评测集 |
| CNOpenData 税收调查企业裁判文书数据 | https://www.cnopendata.com | 全国税收调查企业的裁判文书结构化数据（含案号/法院等），2008-2016 起年度更新 | **商业付费** |
| 国家基础学科公共科学数据中心 全量裁判文书数据集 | https://www.nbsdc.cn | 2023-08 前公开的全部刑/民裁判文书约 8000 万份 | 学术申请通道（面向科研机构） |
| macrodatas.cn 文书网全量包 | https://www.macrodatas.cn/article/1147471898 | 8500 万+ 文书 / 102G（即 cncases/cases 的数据源） | 站内获取 + 社区 BT 种子 |
| Liebman 等河南裁判文书数据集 | Columbia Law（Liebman 2020, "Mass Digitization of Chinese Court Decisions"） | 河南 105.9 万份文书 | 学术申请 |
| CSMAR / 北大法宝 / 威科先行 | 商业数据库 | 均有税务诉讼/处罚专题模块 | 机构订阅 |

**回答调研问题 3：学术界没有可直接下载的"涉税裁判文书数据集"，只有论文/报告附带的方法与规模描述（锦天城 3909 份最接近）；可下载的大规模替代品是 macrodatas 102G 全量包与 nbsdc 学术数据集，均需自行按税务案由过滤。**

---

## 5. chinatax.gov.cn 站群实测：结构、入口与反爬

### 5.1 国家税务总局主站 [实测]

- **robots.txt：不存在**（`/robots.txt` 返回 404）。无任何抓取禁令声明，但也没有授权声明。
- **无 WAF、无验证码、无需 cookie**：默认 curl UA 直接 200；响应头 `Access-Control-Allow-Origin: *`，走 CDN 缓存。
- **纯服务端渲染**：正文与列表都是静态 HTML + jQuery（无 React/Vue/NUXT），requests 即可抓，**不需要 playwright**。
- **栏目 URL 模式**（TRS CMS）：
  - 频道：`https://www.chinatax.gov.cn/chinatax/n810219/`（新闻发布）
  - **税案通报栏目**：`https://www.chinatax.gov.cn/chinatax/n810219/c102025/common_listwyc.html`
  - 文章正文：`/chinatax/n810219/c102025/c5252649/content.html`（`c+数字` 为文章 ID，全局唯一递增趋势，可做增量水位）
- **翻页接口（关键发现）**：首页"更多>>按钮调用 `serach_channel()`，实际是服务端渲染的列表端点：
  ```
  GET /chinatax/manuscriptList/c102025?_channelName=税案通报&_isAgg=0&_pageSize=20&_template=index&page=N
  ```
  裸 curl 直接返回 20 条/页的 HTML 列表 + `page=N` 分页参数 [实测]。`_isAgg=1` 可聚合子栏目。**这一条就是总局税案通报全量抓取的全部技术需求。**
- 政策法规库 `fgk.chinatax.gov.cn`：同样 curl 200、无 robots，与本项目的法规库重叠，可做交叉校验源。

### 5.2 省级税务局站点 WAF 实测（2026-10-10，默认 curl UA）

| 站点 | 状态 | WAF 判定 |
|---|---|---|
| www.chinatax.gov.cn（总局） | 200 | 无 |
| shanghai.chinatax.gov.cn | 200 | 无 |
| jiangsu.chinatax.gov.cn | 200 | 无 |
| guangdong.chinatax.gov.cn | 200 | 无 |
| zhejiang / henan / shenzhen / liaoning / fujian / anhui | 200 | 无 |
| **beijing.chinatax.gov.cn** | **412** | **瑞数**（页面含 `$_ts` / `$_ts.cd` 混淆 JS 挑战） |
| **sichuan.chinatax.gov.cn** | **412** | **瑞数** |
| **shaanxi.chinatax.gov.cn** | **412** | **瑞数** |
| **hunan.chinatax.gov.cn** | **412** | 类加速乐挑战（`/MMB1_<hash>/ZYbKRgIknL7izCT.js`） |
| **etax.shandong.chinatax.gov.cn**（山东电子税务局/失信公布栏所在） | **412** | **瑞数** |
| hubei.chinatax.gov.cn | 连接失败（本网络） | 未知 |

含义：约一半省份裸 requests 即可抓；瑞数省（北京/四川/陕西等）要么上 playwright（配合住宅 IP、低频），要么改走替代渠道（信用中国归集、该省政务服务网双公示镜像）。瑞数的 412 JS 挑战对无头浏览器也有指纹检测，逆向成本高，**不建议硬刚**。

### 5.3 各类税务案例数据的入口现状

| 数据类别 | 入口 | 形态 |
|---|---|---|
| 税案通报 | 总局 `c102025` 栏目 + 各省局同名栏目 | 静态 HTML 新闻稿，量少质高，最易抓 |
| 行政处罚公示 | 各省"行政执法信息公示平台"（如山西 shanxi.chinatax.gov.cn、山东、吉林均有）；**无全国统一入口** | 多为 AJAX 分页 + 可逆向 JSON 接口；部分藏在瑞数站后面 |
| 重大税收违法失信案件公布 | 依据税务总局令第 54 号《重大税收违法失信主体信息公布管理办法》（2022-02-01 施行），省局门户"公布栏"发布（上海=纳税服务>公众查询>公布栏；山东在 etax 子域[瑞数]） | 查询系统形态（按地区/性质/年度/纳税人名称查），字段结构化程度高 |
| 税务行政复议决定书 | 2023 新《行政复议法》第 79 条要求公开；散见于省局"法定主动公开"栏目、地方司法局复议决定书专栏、全国行政复议服务平台（xzfy.moj.gov.cn，偏申请入口非文书库） | **碎片化，无批量源**；CnOpenData 商业售卖复议文书数据 |
| 涉税裁判文书 | 文书网（已受限）；替代：macrodatas 102G 全量包 / cncases / 94.3G 磁力备份 | 从全量包按案由过滤：税务行政管理（行政案由）、逃税罪、虚开增值税专用发票罪、骗取出口退税罪等 |
| 替代聚合源 | 信用中国（creditchina.gov.cn，双公示归集含税务处罚）、地方大数据平台（如 data.beijing.gov.cn 行政处罚数据集） | 接口比税务站规范，适合做瑞数省的旁路 |

**回答调研问题 5：未发现任何现成的"各省税务局行政处罚公示入口汇总"清单**（awesome-chinese-legal-resources 等清单中均无）。URL 规律仅限 `{省份拼音}.chinatax.gov.cn` 这一层，公示平台的具体路径各省各异，需逐省踩点建映射表——这份映射表本身就是可以沉淀并开源的中间产出。

---

## 6. 坑点清单（前人踩过 + 本次实测）

1. **裁判文书网是"技术和法律双高风险区"**：2021 年起要求登录+验证码、检索受限，2024 年起大规模下架/限流（amakerlife 仓库原话"24 年就关了"）；历史上用瑞数（cookie `FSSBBIl1UgzbN7N80T`），后传换 sojson 加密。所有 2018-2022 年的老爬虫（sixs/Henryhaohao/Leon406/nciefeiniu/guoxw）**全部失效**，不要在这些仓库上浪费时间为上策。
2. **瑞数 WAF 的 412 不是网络错误**：北京/四川/陕西/山东 etax 返回 412 + 一段 `$_ts` 混淆 JS，必须真实执行 JS 拿到动态 cookie 才能放行；对 headless 测试（无 webdriver 特征处理）也会二次拦截。湖南是另一套（MMB1 挑战 JS）。**这些省不要用 requests 硬试，直接归入 playwright 队列或旁路渠道。**
3. **总局站"看起来要 JS 其实不用"**：翻页按钮是 `onclick`，但底层 `/chinatax/manuscriptList/` 是服务端渲染端点，直接构造 URL 即可翻页；别急着上浏览器渲染。
4. **无 robots.txt ≠ 随便抓**：政府网站普遍无 robots 声明，合规边界要靠自律——参考 hiddendevj/Crawler_Illegal_Cases_In_China（4738★）里的真实判例：控制频率、避开高峰、只取公开信息、不绕过登录/付费墙、非商用研究用途、公布个人信息时做脱敏（失信公布栏含自然人姓名+身份证号部分位，入库前必须脱敏策略先行）。
5. **省站改版频繁、结构不统一**：2019 年的 tax-policy-crawler 选择器已全部过期；每省公示平台路径、参数命名各不相同，脚本要按省做适配器而不是统一模板。
6. **"重大税收违法失信"数据的个人信息密度高**：公布字段含法定代表人/财务负责人/直接责任人姓名与证件号（脱敏版），用于微调训练集时脱敏与授权评估要在建库之前完成，不能后补。
7. **数据许可陷阱**：HF 上中文法律数据集大量 cc-by-nc（禁商用）；CAIL 官方未标 license；文书网数据再分发在法律上处于灰色地带（最高法使用条款禁止批量爬取）——**用社区既有备份（BT 全量包）获取是一回事，再公开分发是另一回事**，对外发布自建库时建议只发布清洗脚本与元数据、不发布文书原文。
8. **编码坑**：本次实测中 Windows 下 Git Bash 的中文 URL 编码会静默失败（curl 貌似成功实则查空），写抓取脚本时统一在代码内做 percent-encode。
9. **etax 子域 ≠ 主站**：山东主站可直连，但失信公布栏在 etax.shandong 子域上且挂了瑞数；做入口映射时要精确到具体子域。
10. **复议决定书别指望批量**：公开是 2023 年后的新义务，各省执行进度不一，只能按省"法定主动公开"栏目零散采集 + 定期回访增量。

---

## 7. 对本项目的建议（优先级排序）

1. **P0 总局税案通报（1-2 天可完成全量）**：直接用 `/chinatax/manuscriptList/c102025?_pageSize=20&page=N` 翻页抓列表 + `content.html` 正文，requests + trafilatura（或自写 TRS 正文抽取）转 markdown。以文章 `c+ID` 做增量水位。无反爬，成本最低，先跑通整条"抓取→清洗→markdown→入库"管线。
2. **P0 涉税裁判文书走"全量包过滤"而非爬虫**：获取 macrodatas 102G 包（cncases 仓库内 `810air.torrent`）或 94.3G 磁力备份，按案由关键词（税务行政管理/逃税罪/虚开增值税专用发票用于骗取出口退税罪等）+ 文书类型（行政判决书/裁定书）过滤出涉税子集，再转 markdown。磁盘预算 ≥320G（参考 cncases：原始 102G + 库 200G + 索引 15G）。
3. **P1 省局分档并行**：先做"裸 curl 档"（沪/苏/粤/浙/豫/深/辽/闽/皖……）的处罚公示与失信公布栏；瑞数档（京/川/陕/湘/鲁 etax）统一走 playwright + 低频 + 断点续抓，或改走信用中国双公示数据旁路。**首先产出并维护一份《省局公示入口映射表》（省份/栏目/URL/反爬档位/接口形态），这既是工程资产也是社区稀缺品。**
4. **P1 税务行政复议决定书**：按省局"法定主动公开"栏目 + 地方司法局专栏做定期增量扫描；接受其碎片化现实，作为库的"长尾"层。
5. **P2 结构化与 RAG**：参考 cncases 的"convert → index → vsearch(qdrant) 向量检索"分层；对处罚公示做字段结构化（当事人/违法事实/处罚依据/处罚结果/日期），可参考 zhang17173/Event-Extraction 的事件抽取管线。最高法 2025-11 涉税典型案例（量小）留作评测集。
6. **合规基建先于扩量**：入库前完成（a）个人信息脱敏字段清单，（b）抓取频率与时段策略，（c）对照 Crawler_Illegal_Cases_In_China 的自查，（d）对外发布策略：只发脚本/元数据/清洗后统计，不发文书原文全文。
7. **可选补充**：DevnorsAI SDK（裁判文书/法条 API，按 token 计费）可作小规模对照/补漏源；CAIL2018 与 DISC-Law-SFT 等数据集可作微调阶段的通用法律底料，与自建税务案例混训。

---

## 8. 主要参考链接

- cncases/cases：https://github.com/cncases/cases （demo https://caseopen.org/ ）
- 文书网 94.3G 磁力备份：https://github.com/amakerlife/wenshu.court.gov.cn-backup
- 瑞数 MmEwMd 求解档案：https://github.com/sml2h3/mmewmd_crack_for_wenshu
- outerman/tax-policy-crawler：https://github.com/outerman/tax-policy-crawler
- awesome 中文法律资源：https://github.com/pengxiao-song/awesome-chinese-legal-resources
- 爬虫涉诉案例库：https://github.com/hiddendevj/Crawler_Illegal_Cases_In_China
- CAIL2018（HF）：https://hf-mirror.com/datasets/china-ai-law-challenge/cail2018
- CAIL 官方：https://github.com/thunlp/CAIL 、http://cail.cipsc.org.cn/
- DISC-Law-SFT：https://hf-mirror.com/datasets/ShengbinYue/DISC-Law-SFT
- lawyer_llama_data：https://hf-mirror.com/datasets/Skepsun/lawyer_llama_data
- 锦天城税务行政诉讼实证（3909 份）：https://www.allbrightlaw.com
- CNOpenData：https://www.cnopendata.com ；nbsdc：https://www.nbsdc.cn
- macrodatas 全量包说明：https://www.macrodatas.cn/article/1147471898
- 总局税案通报栏目：https://www.chinatax.gov.cn/chinatax/n810219/c102025/common_listwyc.html
- 《重大税收违法失信主体信息公布管理办法》（税务总局令第 54 号）：https://fgk.chinatax.gov.cn
- DevnorsAI SDK：https://github.com/DevnorsAI/devnors-data-python

> 免责说明：本报告仅为技术调研记录。各数据源的权利归属与使用边界以其官方声明为准；对政府网站与裁判文书数据的采集和再利用，请自行完成合规评估。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
