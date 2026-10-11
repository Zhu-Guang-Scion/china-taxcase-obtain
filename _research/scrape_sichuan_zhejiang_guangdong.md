# 四川 / 浙江 / 广东三省税务局抓取攻坚预研报告

> 预研日期：2026-10-10。方式：GitHub API 检索（精确 star/活跃度）、npm 实装实测（rs-reverse）、
> 本机实测（ddddocr 识别浙江 sword 验证码、rs-reverse 生成四川瑞数 cookie、信用广东/信用四川接口复核）。
> 前置文档：`work/taxcase/sources/shandong.md`（四川部分）、`guangdong.md`、`expand_round2.md`、`zhejiang.md`、`browser_round2.md`。
> 标注 **[实测]** 的均为本次直接验证。

---

## 0. 本次预研的三个决定性新事实

1. **[实测] 四川的墙是瑞数（`$_ts`），不是网宿**。`tmp/sc_challenge_inline.js` 开头即
   `$_ts=window['$_ts']; $_ts.nsd=114459; $_ts.cd="..."`，响应头 `Server: ******`（瑞数惯用的掩码）、
   cookie `QDkE2SSrLpcXO/T` 双段式。山东才是网宿（`Server: wswaf`、`x-ws-request-id`、`$_ss`）。
   **两者的字节码 VM 结构同源**（LCG 常量同为 `0x3d3f*(x&0xFFFF)+0x269ec3`、字节码分发器同构），
   即网宿 wswaf 的挑战引擎是瑞数系引擎的贴牌/衍生——所以瑞数生态工具对两省都值得试。
   shandong.md 把四川标成"网宿 wswaf"是误判，应更正为"瑞数系"。
2. **[实测] 浙江 sword 平台的图片验证码可被 ddddocr 直接识别**。验证码为 60x20 JPEG、4 位小写字母数字
   （实测输出 `vthb / mnp5 / wpx5 / rup9 / qFve`，识别干净），接口 `download.sword?ctrl=CheckcodeUtil_getCheckcode`
   无 IP/频率墙、绑定 `LESB_SESSION` 会话。**浙江处罚公示平台从"放弃"变为"全自动可抓"**。
3. **[实测] rs-reverse 能还原四川挑战代码（62ms），但生成的 cookie 未通过该站校验**。
   `makecode -u https://sichuan.chinatax.gov.cn/` 成功产出内外层 VM 代码与 meta-content 解析；
   `makecookie` 生成 279 字符 cookie（811ms）后，用同 UA（Mac Chrome/131）+ curl_cffi chrome124 TLS
   回放 `/col/col2720/index.html` 仍 412。且该站**轮换挑战变体**（cookie 名在 `QDkE2SSrLpcXT /
   QDkEWSSrLpcXT / v2f86nPGWDKdT` 间轮换，约一半生成尝试直接报错需重试）。
   结论：纯算法路线对该站当前变体**差一层 basearr 适配**，不是死路，但今天不能开箱即用。

---

## 1. 结论速览表

按「稳定性 × 成本」排序；用户已确认耗时长可接受，故"人工一次性介入 + 长尾自动"类方案优先于"全自动但脆"类。

| 省 | 推荐 | 方案 | 稳定性 | 成本/耗时 | 一句话 |
|---|---|---|---|---|---|
| **四川** | ★★★★★ | **桌面真实浏览器（playwright headed/Edge channel）过一次瑞数挑战 → CDP `Storage.getCookies` 导出全套 cookie → curl_cffi 全站 GET 抓 TRS col/art** | 高（北京同款瑞数已被本项目 playwright 有头会话通过；山东经验：GET 可用 cookie 复放） | 人工几分钟/次 + cookie 约 7 天有效，全量栏目 1-2 天 | 一次性人工换 7 天自动窗口 |
| 四川 | ★★★★ | 微信公众号通道扩量（qiye45/wechatDownload 整号导出，替代搜狗搜索的零散命中） | 高 | 半天（需 PC 微信客户端登录一次） | 官方号的税案通报是稳定镜像 |
| 四川 | ★★★ | sdenv 补环境跑原版挑战 JS（社区活跃，跑通后全自动续 cookie） | 中（需按站调环境指纹） | 2-5 天工程 | 备选，工程量大 |
| 四川 | ★★ | rs-reverse 纯算 cookie | 中低（该站变体未适配，需跟进社区 basearr 更新） | 半天试 + 等适配 | 62ms 还原成功，差临门一脚 |
| **浙江** | ★★★★★ | **sword 平台全自动：requests/curl_cffi + ddddocr 识别 CheckcodeUtil 验证码 → POST `ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg` 按 67 个 swjgDm 全量翻页** | 高（[实测]验证码可识别、平台无 WAF；识别错即换码重试） | 1-2 天（含 postData 逆向半天） | 验证码是纸老虎 |
| 浙江 | ★★★ | zjzwfw 双公示（`/zjservice/matter/punishment/index.do`，阿里 WAF）+ 信用浙江 creditzj.gov.cn 交叉 | 中 | 浏览器会话内探接口 1 天 | 归集了税务处罚，可交叉补漏 |
| 浙江 | ★★ | data.zjzwfw.gov.cn 开放数据平台申请官方接口 | 中（审批流程不可控） | 申请周期数周 | 正路但慢 |
| **广东** | ★★★★ | **信用广东 API + ddddocr `slide_match` 本地识别滑块缺口 + 轨迹模拟 → 换 VALIDATE_CODE_ID → `jsonArgs={"cf_cfjg":"like;税务"}` 过滤翻页**（全量 137,634 条中税务约上千条） | 中高（自建滑块，无行为指纹强校验的证据；每次过滤查询要重滑） | 2-3 天（滑块逆向 1 天 + 采集 1 天）；注意频率自律 | 技术可行，只做低频合规采集 |
| 广东 | ★★★ | gdzwfw.gov.cn 处罚公示 SPA 接口逆向（浏览器会话内抓 XHR） | 中（SPA 接口未探明；站点可直连 200） | 1 天探明 | expand_round2 的遗留项 |
| 广东 | ★★★ | 微信公众号扩量（同四川；广东税务/各市税务号） | 高 | 半天 | 已有 adapter，换发现源 |
| 三省 | ★★★ | 微信公众号整号导出通道（wechatDownload 9.7k★） | 高 | 每省半天 | 替代搜狗搜狗反爬 |

**明确不可行/不值得**：信用四川批量（服务端硬 cap 5 页）、信用中国国家站（同款 wswaf 412）、
全国统一处罚公示聚合平台（不存在）、浙江复议决定书（该省不公示，维持）、
`node:vm` 裸跑挑战 JS（已证 500 ops/s）、quickjs 跑挑战（纯解释器无 JIT，比 node:vm 更慢）。

---

## 2. 任务一：网宿 wswaf 挑战求解生态

### 2.1 结论：不存在 wswaf 专属开源求解器

- GitHub 搜索 `wswaf`：**total 0 仓库**[实测，GitHub API]。
- 中文网络搜索 "wswaf / 网宿 反爬 / $_ss 逆向"：无任何公开分析文章（网宿 WAAP 产品页、
  通用 WAF bypass 教程之外为零）[WebSearch]。
- 社区对网宿挑战的通行认知：与加速乐（知道创宇）同类"JS 挑战 → 算 cookie → 重放"，
  分析资料以 `acw_sc__v2`（知了智/阿里系）居多，网宿 `$_ss` 是空白区。

### 2.2 为什么瑞数生态可以覆盖 wswaf

**[实测]** 对比 `tmp/sd_challenge_vm.js`（网宿 `$_ss`）与 `tmp/sc_challenge_vm.js`（瑞数 `$_ts`）：

| 特征 | 山东（wswaf/`$_ss`） | 四川（瑞数/`$_ts`） |
|---|---|---|
| 内联变量 | `$_ss.nsd / $_ss.cd` | `$_ts.nsd / $_ts.cd` |
| VM 入口 | `function(_$_7,_$gR){var _$dL=0;...}` | `function(_$e9,_$hc){var _$_C=0;...}` |
| PRNG LCG | `_$fu=0x3d3f*(_$fu&0xFFFF)+0x269ec3` | `_$dI=0x3d3f*(_$dI&0xFFFF)+0x269ec3` |
| 字节码分发 | if-else 树 op0..op11 起 | 同构 |
| 字节码 loader | `[1,0,4,3,5,2,6,10,11,8,9,7]` | 同族 |

同一个引擎家族。瑞数工具链（第 3 节）对 wswaf 站点的适配成本 = 变量名映射（`$_ss`→`$_ts`）+
basearr 校准，山东站可作为副产物一并尝试。

### 2.3 离线执行挑战 JS 的"更快方案"（回答 quickjs/duck2dxx/真实 V8 问题）

| 方案 | 状态 | 结论 |
|---|---|---|
| node:vm + 手写 DOM shim | 本项目已试，~500 ops/s，>40min 未完成 | 死路。慢因：自生成 eval 无 JIT 缓存 + shim 命中解释执行慢路径 |
| **quickjs** | 纯解释器、无 JIT | **更慢，排除** |
| duck2dxx/dukstomp 类 | 无此成熟项目 | 不存在 |
| **rs-reverse（纯算法）** | 614★ BSD-3-Clause，2026-02 活跃 | **不执行 VM，直接静态还原算法生成 cookie**（毫秒级）。对四川 [实测] 还原成功但 cookie 未过校验（变体适配问题） |
| **sdenv（补环境）** | 810★ BSD-3-Clause，2025-12 活跃 | **真 V8（Node 20+，JIT 开）+ jsdom 全 DOM + sdenv-extend 环境指纹插件**，跑站点原版挑战 JS。作者声称固定随机数后"生成的 cookie 与浏览器一致"。这是"500 ops/s"问题的正解——之前慢不是 V8 慢，是 shim 生态不对 |
| 真浏览器中继（riverPass） | 236★ MIT | 不解题，让真浏览器替你发请求（见 3.3） |

---

## 3. 任务二：瑞数 412 挑战求解生态（2026-10 现状）

| 项目 | star | 活跃度 | 覆盖 | 对川站可用性 |
|---|---|---|---|---|
| **pysunday/rs-reverse** | 614 | 2026-02 push，issues 2 | 瑞数 VMP 纯算法（4/5/6 代通杀思路），npm 包即装即用 | [实测] makecode 成功/makecookie 生成但**未过验证**；该站变体轮换，等社区适配或自行补 basearr |
| **pysunday/sdenv** | 810 | 2025-12 push，Discussions 活跃 | 补环境框架（jsdom+环境插件），跑原版 JS | 未实测（需 node-gyp/VS C++ 编译 + docker 可用）；对"变体轮换"型站点比纯算稳（执行的就是站点自己的代码） |
| 0xAllenChen/spider_reverse | 927 | 2026-05 | 学习仓：TLS 指纹、瑞数（含 **DrissionPage 过瑞数 6** 案例）、加速乐、极验滑块 | 参考其"DrissionPage 过瑞数 6"章节——**国产浏览器自动化库过瑞数的现成范例** |
| wjlin0/riverPass | 236 | 2024-10（v1.0.2 稳定） | Go：本地代理 + WebSocket 把请求转发进**你自己开着的美化浏览器**执行 | 与本项目"桌面浏览器人工过 + CDP 导 cookie"同思路的自动化版；浏览器需常开 |
| netpr1s0ner/RuishuBypass | 113 | 2024-05 | 瑞数 bypass all | 未验证 |
| handbye/RSVmpBypass | 76 | 2025-04 | BurpSuite 插件（测试向） | 安全测试用，非采集向 |
| sml2h3/mmewmd_crack_for_wenshu | 476 | 停更（README 自认过时） | 历史瑞数（文书网 FSSBBIl1UgzbN7N80T 时代） | **不可用**——文书网已换 sojson；对现代瑞数 5/6 无效，仅档案价值 |
| xiaoweigege/botgate-RuiShu-Spider | 38 | 2024-08 | 单版本瑞数案例 | 参考价值 |

**许可与风险**：rs-reverse/sdenv 均为 BSD-3-Clause 且带免责声明（"仅用于个人学习研究"）。
使用 = 对政府站点的反爬对抗，法律灰色（见第 8 节）；本项目用途（公开处罚公示的合规采集、低频、非商用研究）
风险可控，但必须自律频率并保留可撤回策略。

**能否用于四川 etax/省站**：省站主域 [实测] 瑞数；`etax.sichuan.chinatax.gov.cn`（zfgspt 镜像，
flash-cookie 插页 + 900 状态码，同为瑞数栈）同生态覆盖。北京站（同为瑞数）本项目已用
playwright 有头会话通过，**对川站尚未系统性尝试"有头+人工一次"**——这是优先级最高、成本最低的路线。

---

## 4. 任务三：滑块验证码自动化（信用广东，仅技术可行性研究）

### 4.1 现状复核 [实测]

- `POST credit.gd.gov.cn/gdcreditwebApi2/company/web/booleanQueryListByPageSimple` 仍可达（HTTP 200），
  无过滤返回 total=137,634 / totalPage=9,176，字段含 `cf_cfjg`（处罚机关）/`cf_xdr_mc`/`cf_nr`/`cf_wsh`/`cf_jdrq`。
- 第 1 页（最新 15 条）中税务记录 0 条——**无过滤的 5 页×50 条窗口对"税务"维度基本无产出**，
  jsonArgs 过滤（403→滑块）是唯一有效路径，与 expand_round2 结论一致。
- 滑块为**自建**（前端 `showValidateCode`，非极验/网易易盾/腾讯防水墙），签发 `VALIDATE_CODE_ID`
  约 1 分钟超时，带过滤查询/翻页>5 都要它。

### 4.2 生态与可行性

| 工具 | star | 活跃度 | 能力 |
|---|---|---|---|
| sml2h3/ddddocr 1.6.1 | 14,825 | 2026-03 | OCR + **`slide_match`（缺口偏移检测）/`slide_comparison`** [实测本机已装，API 存在] |
| chenwei-zhao/captcha-recognizer | 664 | 2026-08 | 单/多缺口滑块识别，pip 安装，可部署为本地 API |
| 81NewArk/AntiCAP | 661 | 2026-09 | 点选/滑块/算术/旋转/OCR 全家桶 + WebApi 版（372★） |

**技术可行性评估**（不实施）：
1. 自建滑块通常 = 背景图 + 缺口图两张图 → `ddddocr.slide_match(缺口, 背景)` 直接得 x 偏移；
   无公开证据表明信用广东滑块带行为轨迹熵校验（若只有位置校验，匀速轨迹即可过）。
2. 流程自动化：取图 → 识别 → 模拟轨迹 POST → 得 VALIDATE_CODE_ID → 1 分钟窗口内
   `jsonArgs={"cf_cfjg":"like;税务"}` + rows=50 连续翻页 → 过期重滑。税务量级上千 →
   约 20-60 次滑块求解，每次 2-4 秒，**半天到一天可完成全量**，配合 curl_cffi 复放。
3. 风险点：①若轨迹有服务端校验（学习人类加速度曲线即可绕，社区成熟）；②IP 频率（低频+夜间）；
   ③滑块图若为动态碎片需先逆 JS 拼图（未见证据）。
4. **合规红线**：这是对政府公示平台验证码机制的自动化。本报告只做可行性论证；
   实际执行需限频（≥3-5s/请求）、只在公开处罚公示范围、留撤回机制，并优先考虑
   "人工滑一次 + 抓紧 1 分钟窗口多翻页"的半自动形态。

---

## 5. 任务四：替代数据通道

### 5.1 四川

| 通道 | 状态 [实测] | 评价 |
|---|---|---|
| 信用中国(四川) credit.sc.gov.cn | 接口活：`punishmentListdata.phtml?viewId=json&page=N&kw=&captchaToken=`，**服务端硬 cap `totalpage=5`**（真实 totalpage_xs=9579 页暴露在响应里）；kw=税务局触发 FreeMarker 报错（kw 只匹配相对人名称）；无日期参数（页面 JS 只有 page/kw/captchaToken 三个参数） | **批量不可行，最多抽样 25-45 条**。别再投入 |
| 四川市州独立子站 | `chengdu.chinatax.gov.cn` / `luzhou.chinatax.gov.cn` DNS 不存在（000） | **无独立子站**，市州公示全在主站 col8705 栏目内（瑞数墙后） |
| 四川政务服务网 sczwfw | 未探明 | 低优先：处罚双公示归集通常同源信用四川，cap 大概率同款 |
| 总局站聚合 | 总局 manuscriptList 可用（另一智能体已覆盖税案通报 c102025） | 总局只发全国性大案，不含川内全部处罚明细 |
| 微信公众号 | 已有 adapter（搜狗→mp） | 见第 6 节扩量 |

### 5.2 浙江

| 通道 | 状态 | 评价 |
|---|---|---|
| **sword 处罚公示平台（:16002）** | **[实测] 验证码 ddddocr 可识别**；平台本身无 WAF（curl 直连 200）；IAB 打不开是因为非标端口网络层失败，**桌面浏览器/requests 都可达** | **首选。全量=67 个机关代码 × 分页，全自动**。唯一逆向工作是 wings postData JSON 结构（用 playwright 抓一次真实请求即可复放） |
| 浙江政务服务网双公示 | `www.zjzwfw.gov.cn/zjservice/matter/punishment/index.do` 存在（律所尽调通用入口）；主站挂**阿里 WAF**（302 + alicdn antidomxss/interfaceacting JS [实测]） | 需浏览器会话探 XHR；数据与省信用平台同源，做交叉补漏 |
| 信用浙江 creditzj.gov.cn | 本网络不可达（连接失败，站点本身大概率活着） | 换网络后可试，双公示归集口 |
| data.zjzwfw.gov.cn 开放平台 | 在线（官方开放数据/接口申请制） | 正路：申请"行政处罚"数据集接口，审批数周 |
| 浙江税务公众号 | 现有 adapter 可复用 | 税案通报镜像 |
| 复议决定书 | 站内检索 0 条（zhejiang.md 已证不公示） | 维持无源结论 |

### 5.3 广东

| 通道 | 状态 | 评价 |
|---|---|---|
| 信用广东 credit.gd.gov.cn | API 活 [实测]（137,634 条），过滤需滑块 | 见第 4 节，主攻方向 |
| 广东政务服务网 gdzwfw.gov.cn | 主站 curl 200 [实测]；处罚公示 SPA 接口未探明；GitHub 仅 jon2180/gdzwfw-crawler（4★，2021，办事目录非处罚） | 1 天浏览器探 XHR；skyDuanXianBing/gov-affair-kg-qa 证明 gdzwfw 后端接口可批量（157 万事项），处罚公示同栈概率高 |
| 信用中国（全国） | 同款 wswaf 412（shandong.md 已证） | 不可行；其按处罚机关检索若走通也依赖同一滑块生态 |
| 广东省数据开放平台 data.gd.gov.cn | 本网络不可达（000） | 未验证；开放平台通常有行政处罚数据集，换网络可查 |
| 12366/总局聚合 | 12366 为问答库（已抓 300 条）；无全国处罚明细聚合（WebSearch 确认无统一平台/批量下载） | 总局每年"重大税收违法失信案件"为新闻稿形式，量小，已被总局站覆盖 |

---

## 6. 任务五：微信公众号通道扩展

**生态剧变（2026-07）**：wechat-article-exporter（13,044★）**官方停维护**——其依赖的微信公众平台上游
核心接口被官方关闭，"免客户端一键同步"路线死亡（其 issue #200 明确"无法通过修改代码绕过"）。
存活路线全部依赖 **PC 微信客户端/微信内置浏览器取密钥**：

| 项目 | star | 活跃度 | 机制 | 评价 |
|---|---|---|---|---|
| **qiye45/wechatDownload** | 9,715 | **2026-10-07（本周）** | 复制任一文章链接→微信内置浏览器打开→自动抓 key→**整号历史文章批量下载**（md/pdf/docx/csv，含评论/合集/图片音视频），免装证书，支持 MCP 调用 | **首选**。机制与本项目 IAB 手法同源；各省税务官方号=处罚公告稳定镜像 |
| rachelos/we-mp-rss | 4,874 | 2026-10-10（当日） | docker 自托管，公众号→RSS/Markdown/PDF，定时增量更新 | 适合长期订阅增量，配合 wechatDownload 补历史 |
| striver-ing/wechat-spider | 2,973 | 2026-08 | 微信 PC 客户端 hook，文章/阅读量/评论 | 备选 |
| wnma3mz/wechat_articles_spider | 3,482 | 2024-04 停更 | mitmproxy 抓包微信客户端 | API 老化，不推荐 |
| lqqyt2423/wechat_spider | 1,590 | 2026-08 | 历史文章链接枚举 | 备选 |
| wechat-article/wechat-article-exporter | 13,044 | **2026-07-30 停维护** | 公众平台临时素材接口 | **已死**，勿投入 |
| tmwgsicp/wechat-download-api | 1,161 | 2026-07 | 整号导出 API（7 种格式） | 备选 |

落地：PC 微信登录一次 → wechatDownload 导出"四川税务/四川税务教育/成都税务/浙江税务/广东税务/
深圳税务"等官方号全历史 → 标题关键词过滤（复用 sd_sc_weixin.py 的过滤规则）→ 入库。
相比搜狗搜索（3-5 次即 antispider、只能搜到近期/热门），整号导出**无损、无反爬**。

---

## 7. 分省落地方案（步骤概要）

### 7.1 四川（推荐：有头浏览器通过挑战 + cookie 复用）

1. `playwright` `channel="msedge"`/`chrome` **有头**打开 `https://sichuan.chinatax.gov.cn/`，
   等挑战自转（必要时人工点一下）；若二次挑战死循环，清 cookie 重开或换网络出口。
2. 通过挑战后 CDP `Storage.getCookies`（或 `context.cookies()`）导出全部 `Q*` cookie（注意 httpOnly）。
3. curl_cffi(chrome124) 带 cookie 抓 TRS：`/col/col2720|col8705|col11932/index.html` 与
   `index_N.html` 列表 → `/art/YYYY/M/D/art_*.html` 详情（决定书文号表格已在页面内）。
   参考山东经验：**GET 可复放，若遇 POST 接口失效则回到浏览器内 fetch**。
4. cookie 失效（约 7 天或提前）时重复第 1 步；抓取间隔 ≥2s，全站 3 栏目+失信公布+复议送达公告
   约 1-2 天跑完。
5. 兜底并行：wechatDownload 导出四川税务矩阵公众号。
6. 若有头也过不了（出口 IP 受限）：a) 更换网络环境做对照（住宅/4G 热点，验证受限是否与出口 IP 相关）；b) 上 sdenv（docker 版先
   `sdenv check https://sichuan.chinatax.gov.cn/` 验证适用性）；c) riverPass 中继常开浏览器。

### 7.2 浙江（推荐：sword 平台 + ddddocr 全自动）

1. playwright（有头或无头均可，平台无 WAF）打开
   `http://zhejiang.chinatax.gov.cn:16002/sword?ctrl=XzzfgsptHomeCtrl_index`，
   在查询页发一次真实查询，抓下 `ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg` 的完整
   postData JSON 结构与验证码字段名（wingsCheckCode.js 显示验证码是普通具名 input）。
2. 复放脚本：每机关代码（67 个 swjgDm）新会话 → GET `download.sword?ctrl=CheckcodeUtil_getCheckcode`
   （拿 LESB_SESSION）→ ddddocr 识别 → POST 查询；`flag=1`（验证码错）则换码重试（实测识别质量
   预计 70-90% 通过率，重试 2-3 次内必过）→ 分页至尽。
3. 输出处罚结果结构化字段 + 决定文书号；转 md 入库（zj_news_cases.py 同款骨架）。
4. 增量：每周重跑（数据量按机关数百条/机关，全量一次数小时）。

### 7.3 广东（推荐：信用广东 + 半自动滑块）

1. 浏览器登录 credit.gd.gov.cn 手动过一次滑块，抓 `showValidateCode` 相关 XHR：
   取图接口、校验接口、轨迹参数结构、VALIDATE_CODE_ID 回传字段。
2. 脚本：curl_cffi 取图 → `ddddocr.slide_match` 求缺口 x → 按抓包轨迹模板生成位移序列 →
   提交拿 VALIDATE_CODE_ID → 立即 `booleanQueryListByPageSimple` +
   `jsonArgs={"cf_cfjg":"like;税务"}` rows=50 连续翻页（1 分钟窗口内尽量多翻）→ 过期重滑。
3. 全量税务记录（估千级）当天完成；限频 ≥3-5s，夜间执行；**优先半自动（人工滑、机器翻页）起步**，
   确认无轨迹校验后再全自动。
4. 并行：gdzwfw SPA 探接口（1 天）+ wechatDownload 广东税务号矩阵。

---

## 8. 风险与合规提示

1. **反爬对抗的法律灰色**：瑞数/wswaf 挑战求解、滑块自动识别属于"绕过技术措施"，参照
   hiddendevj/Crawler_Illegal_Cases_In_China（4,738★）判例，风险点在**大批量、高频、干扰业务、
   转售数据**；公开行政处罚公示的低频合规采集（政府公开信息、非商用研究、脱敏入库）历来风险低，
   但应保持：≥2-5s 间隔、夜间执行、UA 不伪装成官方爬虫、随时可停。
2. **个人信息密度**：失信主体/处罚公示含自然人姓名+证件号脱敏位，入库沿用项目脱敏策略。
3. **工具许可**：rs-reverse/sdenv（BSD-3）、ddddocr/captcha-recognizer/AntiCAP（MIT）可内部使用；
   wechatDownload 无 license（默认版权保留，内部研究使用）；we-mp-rss NOASSERTION。
4. **微信通道**：PC 客户端取 key 属于微信使用条款边缘，账号有被限风险——用非核心小号登录。

---

## 9. 附：本次核实的关键仓库清单

| 仓库 | star | 活跃 | 用途 |
|---|---|---|---|
| https://github.com/pysunday/rs-reverse | 614 | 2026-02 | 瑞数纯算 cookie（npm `rs-reverse`） |
| https://github.com/pysunday/sdenv | 810 | 2025-12 | 瑞数补环境框架（docker/npm） |
| https://github.com/0xAllenChen/spider_reverse | 927 | 2026-05 | 瑞数/加速乐/滑块案例集（含 DrissionPage 过瑞数 6） |
| https://github.com/wjlin0/riverPass | 236 | 2024-10 | 浏览器中继代理过瑞数 |
| https://github.com/sml2h3/ddddocr | 14,825 | 2026-03 | OCR + 滑块缺口 slide_match |
| https://github.com/chenwei-zhao/captcha-recognizer | 664 | 2026-08 | 滑块识别 pip/API |
| https://github.com/81NewArk/AntiCAP | 661 | 2026-09 | 多类型验证码识别 |
| https://github.com/qiye45/wechatDownload | 9,715 | 2026-10 | 微信公众号整号导出（IAB 取 key） |
| https://github.com/rachelos/we-mp-rss | 4,874 | 2026-10 | 公众号 RSS/Markdown 增量订阅 |
| https://github.com/wechat-article/wechat-article-exporter | 13,044 | **已停** | 上游接口已关，勿用 |
| https://github.com/sml2h3/mmewmd_crack_for_wenshu | 476 | 已停 | 历史瑞数档案 |

实测产物：`work/taxcase/tmp/zj_cap_0..2.jpg`（浙江验证码样本）、`$TEMP/rsrev_test/`（rs-reverse
对川站的 makecode/makecookie 输出，含 `output/makecode/` 内外层 VM 还原代码）。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
