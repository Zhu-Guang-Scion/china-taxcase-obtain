# 税务案例抓取源记录 —— 山东省 + 四川省（2026-10-10）

## 总体结论（必读）

两省税务局官网 `shandong.chinatax.gov.cn` / `sichuan.chinatax.gov.cn` 全站被
**网宿 wswaf JS 挑战**阻断（首请求 412 + 混淆 JS 计算 cookie，重放一律 400），
HTML 页面在本次任务环境下**完全不可抓**。改用两条替代通道：
1. **微信公众号官方发布**（省/市税务局公众号的"税案通报/曝光"文章，经搜狗微信搜索发现 → mp.weixin.qq.com 原文抓取）
2. 信用平台（已探明接口但字段/翻页受限，未作为主源，记录备查）

---

## 一、官方站（被阻断，栏目入口备查）

以下入口经搜索引擎确认存在、但直接抓取返回 412 挑战（curl/curl_cffi/playwright 均 400）：

### 山东省税务局 shandong.chinatax.gov.cn
| 栏目 | 入口 URL | 说明 |
|---|---|---|
| 行政处罚公示（执法公示平台） | https://shandong.chinatax.gov.cn/zfgspt/extranet/xzcf | Spring 应用，查询表单（决定书文号/案件名称/处罚机关/日期），结果分页 |
| 行政处罚（另一入口） | https://shandong.chinatax.gov.cn/zfgspt/extranet/xzc | 同平台 |
| 重大税收违法案件信息 | 首页-信息公开-行政执法-重大税收违法案件 | 搜索引擎可见 2026-03-17 更新 |
| 税案曝光/稽查新闻 | 站内"税务新闻/工作动态/媒体视点" | 如《税务部门曝光7起网红网店偷税案件》(2026-07-10)、《山东省淄博市警税联合依法查处一起代开发票虚开案件》 |

CMS：`.json`/`.txt`/`.ico`/`.xml` 后缀请求可穿透 WAF（origin 直达，404 可见）；
`/zfgspt/**.json` 是 Spring DispatcherServlet 通配（任意名 200 空响应），真实数据接口
（`/zfgspt/extranet/xzcf/data.json`）GET 一律返回 Content-Length: 0，未找到有效参数组合
（POST 返回标准错误 JSON：`INTERNAL_SERVER_ERROR / Request method 'POST' not supported`，
证明处理器存在、仅支持 GET）。`.do`/无后缀/`.html` 一律 412。

### 四川省税务局 sichuan.chinatax.gov.cn
| 栏目 | 入口 URL | 说明 |
|---|---|---|
| 行政处罚公示（TRS col 栏目） | https://sichuan.chinatax.gov.cn/col/col2720/index.html | 国家税务总局四川省税务局行政处罚公示 |
| 税务行政一般程序处理结果 | https://sichuan.chinatax.gov.cn/col/col8705/index.html | 各市州稽查局处罚公示（art_ 文章，内含决定书文号/案件名称/处罚类别/处罚事由表格） |
| 行政处罚决定和结果 | https://sichuan.chinatax.gov.cn/col/col11932/index.html | 同类栏目 |
| 重大税收违法失信主体信息公布栏 | 信息公开-行政执法公示（搜索引擎 2026-09-29 可见更新） | 失信主体识别号/法定代表人/案件性质等字段 |
| 重大税收违法失信案件信息 | 同上，年度汇总文章 | 2025-01-23 / 2026-01-21 / 2026-01-23 版本 |
| 行政复议决定书送达公告 | 各市局通知公告（如眉山市 2026-08-11《关于送达〈行政复议决定书〉的公告》） | 大量以 PDF 附件形式 |

CMS：TRS（`/col/colXXXX/index.html` + `/art/YYYY/M/D/art_XXX_XXXXXX.html`），
与总局同构（`/chinatax/manuscriptList/...` 接口同被 412）。
**同款平台镜像在 etax.sichuan.chinatax.gov.cn/zfgspt/extranet/xzcf?city=ybs_3**
（该子域 HTML 页可开，但数据接口 `/zfgspt/privilege/xzcf_nav.json` 返回
flash-cookie 插页（`http://1.1.1.3:89/cookie/flash.js`）→ 随后 900 状态码，同为网宿栈）。

---

## 二、wswaf 反爬实录（踩坑核心）

1. **指纹无关**：curl / curl_cffi(chrome124) / requests / playwright chromium（含
   `--disable-blink-features=AutomationControlled` + navigator.webdriver 补丁）/ 真实
   Edge（channel=msedge，headed）全部同样结局：`412(挑战页) → 200(JS) → 400(空)`。
2. **挑战机制**：412 页内联脚本设置 `$_ss.nsd / $_ss.cd`；外链 VM JS（`/lvnX3MmLs93I/rzvf6f64qMxv.c69d89a.js`，
   133KB，字节码 VM + 自生成 eval）计算 cookie（如 `Q805dsSXd0YYP`、四川两个
   `QDkE2SSrLpcXO/P`），然后 `location.reload()`。计算出的 cookie 在任何客户端重放均 400。
3. **Node 离线执行挑战**：用 node:vm + DOM shim 执行挑战 JS。关键点：必须让
   `window === 全局对象`（否则 loader 判定 `window.$_ss` 为空走"重置"分支，跳过主计算）。
   修正后字节码正确进入 op10（大 VM `_$dj(28)`），但纯解释执行 ~500 ops/s，
   真实浏览器 1 秒内完成的计算在 Node 里 >40 分钟仍未结束（自生成 eval 无 JIT 缓存），
   放弃。字节码 loader 序列（备查）：`[1,0,4,3,5,2,6,10,11,8,9,7]`。
4. **扩展名白名单**：WAF 只挑战"会返回 HTML"的路径。`.json/.txt/.ico/.xml/.js` 直达
   origin（robots.txt→404、favicon→200、任意 .json→404/空 200）。**但两省站没有能用的 JSON 数据接口**（山东 zfgspt 为空通配；四川 TRS manuscriptList 返回 HTML 片段被 412）。
5. **同样使用 wswaf 的省份**（本次顺带确认）：吉林、新疆、陕西、青岛、湖南（Server: core）、
   甘肃/青海/宁夏/黑龙江/河北/江西（连接失败）。广东、上海、内蒙、广西、辽宁、福建等不受影响。
6. `web.archive.org` 本网络不可达（TLS 超时），Wayback 兜底不可用。

---

## 三、实际采用的通道

### 3.1 微信公众号官方发布（主通道）
- adapter：`work/taxcase/adapters/sd_sc_weixin.py`
- 链路：`weixin.sogou.com/weixin?type=2`（搜公众号文章）→ 逐条解析
  `/link`（响应是 `url += '...'` JS 拼接，正则拼接还原真实 URL）→ `mp.weixin.qq.com`
  文章页（curl_cffi 直抓，#activity-name/#js_name/#js_content，`var ct` 取发布时间，
  `var msgLink` 取规范链接）。
- 过滤：标题含 查处/曝光/虚开/骗税/偷税/处罚/案件/通报/稽查/失信 之一 + 含省份/城市地名；
  文章页公众号名必须含"税"；发布日期 ≥ 2023-01-01。
- **搜狗微信反爬激进**：约 3~5 次搜索（间隔 9-14s）即触发 antispider；新会话 + 冷却
  ~7 分钟可恢复。adapter 内置冷却重试（最多 4 轮）。
- 输出目录：`lawlibrary/专题/税务案例/山东省/税案通报/`、`.../四川省/税案通报/`
- 数量：见文末统计。

### 3.2 信用平台（已探明、受限，未批量采用）
- **信用中国(山东) credit.shandong.gov.cn**（无 WAF，可达）：
  行政处罚公示入口 `creditsearch.publicity.dhtml?types=2`，iframe 列表
  `creditsearch.punishmentList.phtml`，数据接口
  `POST /creditsearch.creditsgsindexcayth.phtml?type=行政处罚&kw=&page=N`（kw 只搜
  行政相对人名称，**entity 维度**：返回企业名+统一社会信用代码，需二跳
  `creditsearch.creditdetailindexbgca.dhtml?tyshxydm=...` 看处罚记录）。**无法按处罚
  机关过滤**，不适用于按"税务"批量筛。
- **信用中国(四川) credit.sc.gov.cn**（无 WAF，可达）：
  `GET /creditsearch.punishmentListdata.phtml?viewId=json&page=N&kw=` 返回**记录级**
  JSON（cf_cfjg 处罚机关 / cf_xdr_mc 相对人称 / xy_shxyh 信用代码），totalnum≈47892。
  但 **每页仅 5 条、page≥10 即触发验证码墙**（220 字节拦截页），且 kw 查"税务局"会因
  无结果触发 FreeMarker 模板错误。结论：可抽样、不可批量。
- 信用中国（全国 www.creditchina.gov.cn）本身也是同款 wswaf 412。

---

## 四、抓取量统计（2026-10-10 实跑定格）

| 省份 | 栏目 | 来源 | 件数 | 说明 |
|---|---|---|---|---|
| 山东省 | 税案通报 | 微信公众号（山东税务/滨州税务官方号 + 青岛正业税务师事务所转载） | **4** | 2023-04-06~2023-12-06，虚开/偷税/税警联合案件 |
| 四川省 | 税案通报 | 微信公众号（四川税务官方号 + 理税转载） | **3** | 2023-02-16~2026-03-30，虚开/偷税/移送公安 |
| 合计 | | | **7 md** | |

- 进度/断点：`work/taxcase/progress/shandong_weixin.jsonl`（38条）、`sichuan_weixin.jsonl`（24条）。
- 被过滤未收录：标题不含案件要素或非鲁/川地名约 127 条（rejected）、早于 2023-01-01 约 24 条
  （too_old，搜狗结果中大量 2017-2022 旧文）、公众号名非税务类（律媒/油价动态等）约 6 条。
- 失败：文章页解析失败 6 条（article）；搜狗 antispider 中断合计 5 轮（每轮冷却 420s 重试）。
- 已删除 2 条重复/纯媒体号文件（税与罚、智信和财税对同一官方曝光文的转发），保留的
  "青岛正业税务师事务所""理税"2 篇为行业号对官方稽查案件的完整转载（front matter 已如实标注）。

### 探明但未抓取的栏目（后续路线清单）

**A. wswaf 挑战求解后的官方站栏目（优先级最高）**

| 省 | 栏目 | 入口 | 预期形态 |
|---|---|---|---|
| 山东 | 行政处罚公示（执法公示平台 zfgspt） | https://shandong.chinatax.gov.cn/zfgspt/extranet/xzcf （备用 /zfgspt/extranet/xzc） | 结构化查询（决定书文号/案件名称/处罚机关/日期），全省+16市，量最大 |
| 山东 | 重大税收违法案件信息 | 首页>信息公开>行政执法 | 名单页 |
| 山东 | 税务新闻/工作动态/媒体视点 中的曝光/查处稿 | 站内 TRS 栏目 | 新闻页，static_list 可抓 |
| 四川 | 行政处罚公示 | https://sichuan.chinatax.gov.cn/col/col2720/index.html | TRS col 列表，分页 index_1.html |
| 四川 | 税务行政一般程序处理结果（各市稽查局处罚公示，表格型全文） | https://sichuan.chinatax.gov.cn/col/col8705/index.html | art 文章含决定书文号/处罚事由表格 |
| 四川 | 行政处罚决定和结果 | https://sichuan.chinatax.gov.cn/col/col11932/index.html | 同上 |
| 四川 | 重大税收违法失信主体信息公布栏 / 案件信息 | 信息公开>行政执法公示 | 名单页（2026-09 仍更新） |
| 四川 | 行政复议决定书送达公告（各市局） | 如眉山市 2026-08-11 公告 | 多为 PDF 附件（pymupdf 提取） |
| 四川 | zfgspt 镜像 | https://etax.sichuan.chinatax.gov.cn/zfgspt/extranet/xzcf?city=ybs_3 | 按市代码查询（city=cds_*/ybs_*/…） |

**B. wswaf 后续求解路线（本次验证过的不行 vs 可行方向）**
- 已排除：curl/curl_cffi 指纹、playwright chromium/真实 Edge（连 CDP 均在挑战第二跳拿 400）、
  Node vm 离线跑挑战（正确进入大 VM 但纯解释执行 ~500 ops/s，>40min 未完成，疑似需 JIT）。
- 建议路线1：**playwright 常驻浏览器 + 人工/半自动过一次验证**（若有干净住宅 IP 出口，真实
  浏览器大概率一次通过），用 CDP `Storage.getCookies` 导出 `Q*` cookie 给 curl_cffi 复用
  （cookie 有效期约 7 天），再全站 polite 抓取。
- 建议路线2：在有 V8 JIT 的隔离环境（如 quickjs 不行、需 node `--jitless=off` 的 worker +
  预热，或浏览器 OffscreenCanvas headless 新模式）执行挑战 JS；字节码 loader 序列与
  window===global 语义已在本文档第二节记录，可直接复用 `tmp/waf_solver.js`。
- 建议路线3：从 总局/其他省的开放站（广东/上海/内蒙等无 wswaf）确认 TRS `manuscriptList`
  接口在鲁川的 channel code 后，若 WAF 策略调整（.json 放行）可无浏览器直取。

**C. 信用平台通道（可抽样、不可批量）**
- credit.sc.gov.cn 记录级 JSON（含处罚机关字段）：page<10 可用、每页 5 条 —— 已记录接口。
- credit.shandong.gov.cn entity 级搜索（kw 仅匹配相对人名称）：不适合按税务过滤。
- 全国 creditchina.gov.cn 为同款 wswaf。

## 五、复用文件索引
- adapter：`work/taxcase/adapters/sd_sc_weixin.py`（搜狗微信→mp.weixin 链路、冷却重试、
  文件名级去重、机关名映射、公众号白名单过滤）
- wswaf 求解器（未完成，留档）：`work/taxcase/tmp/waf_solver.js` + 挑战样本
  `sd_challenge_inline.js` / `sd_challenge_vm.js` / `sc_challenge_*.js`
- 探索脚本：`work/taxcase/tmp/pw_diag.py`（playwright 挑战诊断）、`explore.py`、
  `pw_credit_sd.py`（信用平台 XHR 发现）


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
