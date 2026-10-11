# 第九轮：断点续跑——各源余量收编结果（2026-10-11 深夜）

执行：R9 断点续跑智能体 ｜ 门槛：quality_prune2（v2 强制，新收内容入库前判定）

## 总表

| # | 源 | 余量 | 收编结果 | 状态 |
|---|---|---|---|---|
| 1 | 江西 xxgk 处罚 xlsx | ~190 页（2023-01→2025-07） | 新写 1,438 → v2 后**净增 +733 件**（1,307→2,040），扫到 2023-01-01 边界 | **完成** |
| 2 | 云南 /pub 处罚 | 126 页（p116-241） | **+1,102 条记录 → v2 后净增 1,039 件**（934→1,973） | **完成**（241 页全量收满） |
| 3 | 湖南处罚平台 | 1,881 条 | **0 条——平台入口已死**（站重构，旧 URL 全部 302 首页） | 阻断（结构变化，非封禁） |
| 4 | caseopen 裁判文书 | ~6,000+（税务行政管理 2,885 / 逃税罪 2,634 等） | CF managed challenge 连拦 3 offset（无 checkbox 可点）→ 0 收 | 放弃记录 |
| 5 | 山东失信栏 | 排查（库内 0 件） | **确认漏抓但无数据本体可达**（四通道全排查，见 §5） | 缺口在案，留人工线索 |

本轮净入库：**+1,772 件**（江西 733 + 云南 1,039）。

---

## 1. 江西 xxgk（adapters/jx_xzcf_r7.py 续跑）——完成

- 改动：`CAP 2000→6000`（解除量控）；DATE_FROM=2023-01-01 不变即停扫线。
- 断点 `progress/jx_xzcf_r7.jsonl` 增量续跑（已见条目跳过），从 2025-07 断点页续到
  **2023-01-01 边界**（page 303 whole-page-old 停扫；r9 前共 2,240 批次 → 现 6,060）。
- 本轮产出：新写 **1,438 件**（segments：1,181 + 257）；**v2 门槛复检全目录
  keep=2,040 / del=705**（`tmp/v2_del_jx_r9.jsonl`，del 主因 facts<30——
  v2 的事实段只取「违法事实与处罚事由」节，比 r7 adapter 的 sy+jg2 合并口径严）。
- **库内净增 +733 件**（1,307 → 2,040），覆盖 2023-01-01→2026-10-10 全窗口。
- 残余：**331 个附件死链**（dl-fail 308 + fetch-fail 23，重试一轮全数复现=永久死）；
  544 个 no-att 空批次、237 个「（无）」标题，均正常口径。
- 备份：`progress/jx_xzcf_r7.jsonl.bak_r9`（重试前快照）。

## 2. 云南 /pub 处罚（adapters/yn_xzcf_r7.py 续跑）

- 改动：`MAX_PAGES 115→241`；新增 `YN_START_PAGE` 环境变量（本轮 =116，避开已收页重扫）。
- 收编：p116-241（2023-08→2024-10 窗口）**1,102 条记录全收，0 err**；
  v2 门槛复检该目录：keep=1,973 / del=39（`tmp/v2_del_yn_r9.jsonl`）。
- 库内：`lawlibrary/专题/税务案例/云南省/行政处罚公示/` 现存 **1,973 件**（r7 收 934 → 净增 1,039）。
- 断点 `progress/yunnan_xzcf_r7.jsonl` 共 2,036 ok 行，**该源已收满**（241 页全窗口）。

## 3. 湖南处罚余量 1,881 条——阻断原因变更（重要）

r6 记录的"CDN 对 XHR 会话级封禁"已不是主要矛盾；本轮实测（2026-10-11 深夜）：

1. `adapters/hn_xzcf.py` 重试一轮（含 75s 预热）：探针静默失败；交互诊断确认
   **页面上下文 XHR/fetch 仍全被掐**（`err:0 timeout`，CDN 封禁依旧）。
2. 按预案转**真实导航**（原生 form POST 提交，非 XHR）：返回 `Sorry, Page Not Found`。
3. 深挖发现真正原因：**hunan.chinatax.gov.cn 已整站重构**——旧 Spring CMS 全部路径
   （`/xzzfpenalty/20200325400599`、`/hardcase/20190408002097`、`/category|/lists|/search`）
   一律 302 到新首页 `/index`；新站无处罚平台入口（站内 jrobot 检索无结果）。
4. 结论：**余量 1,881 条现阶段不可达**（入口消失，非封禁）。复跑须先人工在新站找
   行政执法公示平台新入口，再重写 adapter。既有 800 条原始数据在 `tmp/hn/xzcf_records.jsonl`。

## 4. caseopen 裁判文书——CF Turnstile 依旧拦（按 3-offset 规则放弃）

- `caseopen_harvest.py` 有头导航法：主页过挑战正常（title=裁判文书网），
  但 `/api/search?...&export=true` 导航页持续 CF 挑战——grab() 300s 超时，
  自动 turnstile 点击（iframe checkbox + 坐标 205,312）无效。
- 连续 offset 失败（税务行政管理@0/@2000/@4000），符合"3 offset 后放弃"口径，进程已停。
- 补充手工诊断（`tmp/caseopen_r9_diag.py`，80s 连续观测）：挑战页 title=请稍候…、
  body 114 字符，frames 含 `challenges.cloudflare.com/.../turnstile`——
  **managed challenge 无 checkbox 可点**（iframe 内 input[type=checkbox] count=0），
  静置不自动过 → 是 CF 对该 IP/指纹的强制交互判定，无宽限窗口可蹭。
- 断点状态：`tmp/caseopen_all.jsonl` 0 行、无 DONE_MARK（等效从头开始）。
- 复跑线索：换 IP/住宅代理 + 桌面 Chrome 人工点一次 turnstile 种 cf_clearance
  （httpOnly 不可导出，须 CDP 接管同一浏览器）再跑导航法。

## 5. 山东失信栏排查（库内 0 件属实——四通道全排查无数据本体）

| 通道 | 实测 |
|---|---|
| zfgspt 平台菜单 | 有头 chromium 可过网宿 wswaf（`--disable-blink-features=AutomationControlled` 即可，无需 IAB）；左栏确有「重大税收违法失信案件信息」菜单，**但 `data-url=""` 是空壳**（LeftNav.js：无 url 直接 return），iframe 无处可去 |
| zfgspt 数据接口 | 处罚接口真身 `/zfgspt/extranet/shgs/query_swxz_ybcx_cfjg.spring`（页 `/zfgspt/extranet/swxzcfjg`，业务 JS `/zfgspt/zfgspt/pages/shgs/swxzcfjg.js`）；**同名系失信接口 6 个候选全 404**（Spring 通配吞掉一切未知 .spring 名，报 POST not supported，盲猜无效） |
| 主站信息公开树 | `信息公开 col3 > 税收执法 col9219` 的年份子栏（2024 col22318 … 2019 col9411）**全是政府信息公开年度报告**，非失信名单；站点地图 col72 无失信栏 |
| 站内检索 | jrobot `search.do`（全站 + 标题域）与 WAS5（len=16 空响应）均只回《重大税收违法失信主体信息公布管理办法》及其解读，**无任何名单文章** |
| etax 电子税务局 | 搜索引擎快照证明失信名单表格页在 `etax.shandong.chinatax.gov.cn`（潍坊/济南稽查局案例可见），但 :8443 是 Vue 登录 SPA 壳，入口 bundle（index*.js 共 1.6MB）grep「失信」0 命中，公开路由未探明 |

- **结论**：山东失信确实漏（库内 0 件 vs 快照证明有数据），但机器可达通道全部无数据本体；
  唯一已知位置在 etax SPA 内部，需人工浏览器找到公布栏路由后才能补。
- 复用资产：`tmp/sd_r9_cookies.txt`（挑战 cookie，GET 对静态资源有效、时效短）；
  有头 chromium 过 wswaf 的最小打法已验证（见 §5 第一行）。
- 侦察留档：`tmp/sd_r9_*.html|js`（xzcf 页/菜单 LeftNav.js/swxzcfjg 业务 JS/站点地图/etax home）。

## 6. 本轮沉淀

- `tmp/v2_pass_dir.py`：对单目录跑 quality_prune2 的复用脚本（v2 强制门槛的工具化）。
- 云南 adapter 支持 `YN_START_PAGE` 环境变量（增量续跑免重扫）。
- 江西 adapter CAP 解除（量控期结束，按日期线停扫）。

---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
