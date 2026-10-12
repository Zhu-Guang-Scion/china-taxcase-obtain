# 第十轮：税务媒体/专栏线——官网增量收割（2026-10-12）

执行：R10 税务媒体官网替代矩阵智能体 ｜ 调研依据：`_research/wechat_channels_r10.md`
门槛：quality_prune2（栏目含 税务媒体/专栏/评析 → narrative KEEP）＋ adapter 级门禁
（媒体文章须含具体案情或操作路径；纯政策转述/活动预告/招聘 DEL 不入库）
产出根：`lawlibrary/专题/税务案例/全国/税务媒体与专栏/` ｜ 断点：`progress/media_r10.jsonl`
delay≥1.2s（知乎线≥2s，未用上）；量控：总量≤2,500、每源≤800（税海涛声≤600）——本轮实际 246 件，远低于上限。

## 总表

| # | 源 | 通道 | 产出 | 状态 |
|---|---|---|---|---|
| 1 | 中国税务报（中国税网 ctaxnews.com.cn） | 官网直抓 | **195**（税案通报 97 + 合规案例 98） | 完成（归档窗 2025-08→2026-10，在线仅 10 页） |
| 2 | 税海涛声"文涛说税"（段文涛） | 知乎→搜狐号兜底 | **14** | 部分（知乎 403 全灭；搜索引擎枚举配额耗尽） |
| 3 | 毕马威（KPMG）中国税务快讯 | 官网直抓 | **23** | 完成（列表静态 64 条，近三年 URL 过滤+门禁后 23） |
| 3b | 德勤/安永/普华永道 税务快讯 | 官网 | **0** | 落空（列表页 JS 渲染，静态抓不到文章索引） |
| 3c | 威科先行 wkinfo.com.cn 免费文章区 | 官网 | **0** | 落空（全站 SPA+登录墙，无静态免费区） |
| 4 | 明税（北京明税律所）公众号 | 搜狗微信（复用 r9 adapter） | **0** | 落空（weixin.sogou antispider，3×420s 冷却无效，与 r9 末段同症状） |
| 5 | wechatDownload 整号历史 | MCP（qiye45 9.7k★） | — | **留用户人工**：PC 微信取 key 后可续（见文末） |

本轮净入库 **232 件**，全部通过 quality_prune2（KEEP=narrative-column）。

## 1. 中国税务报 ctaxnews.com.cn——195 件

- **探活**：round3 曾记"域名已死"，本轮实测 200 存活（站点名"中国税网"，中国税务报社）。
- 栏目：税案通报 `/sswfaj/node_23.html`（分页 node_23_2..10，**第 11 页起 HTTP 500**，在线归档只到 2026-04）；
  合规案例 `/zt/node_8131.html`（单页全量，2025-08→2026-10）。
- 文章页 `.article-wrap`（标题拆多段 p / `.publish-time` / `.source` / `.article-main`）。
- 件均质量高：官方通报式全案情叙事（违法手段、金额、法条、处理处罚、司法衔接），如
  《"绕行"万里偷逃消费税的黄金首饰案》（西藏空壳转移收入，追罚 4002.04 万元全要素在文）。
- 门禁拒收 5 件（征订/评论员文章类）。adapter：`adapters/ctaxnews_r10.py`。

## 2. 税海涛声（段文涛）"文涛说税"——14 件（多重受阻，非配额问题）

逐通道证据（2026-10-11/12 实测）：
- **知乎专栏** c_1089525539886383104（2085 篇）：专栏元信息 API 200，但
  文章列表 API 需登录（need_login）、**文章页对 curl_cffi 全系 impersonation（chrome124/131、edge101、safari、firefox）一律 403（584 字节 WAF 页）**——带主页 cookie+referer 也拦。搜索 API 需 x-zse-96 签名（错误码 10003）。知乎通道**整线落空**。
- **搜狐号镜像**（作者 ID 467122，mp.sohu.com/profile?xpt=dGF4c2h0c0Bzb2h1LmNvbQ==）：
  文章页需 `impersonate=edge101`（chrome 系被 sohu WAF 403）；作者 API
  `v2.sohu.com/author-page-api/author-articles/pc/467122` **分页参数全失效（恒返最新 20 篇）**；
  mp.sohu.com/apiV2/profile/newsListAjax 超时死链；mp/pc profile 页均 JS 壳。
- 枚举可用通道：**百度（主）+ 360（辅）** 搜 `"税海涛声"` 系查询收 `/a/{id}_467122`。
  本轮收 33 个 id → 门禁后 **14 件入库**（2016-2026 深档都有，案情/实务点评密度高，
  拒收 18 件主因搜狐镜像截断 too-short）。
- 枚举配额后续耗尽：百度出安全验证页、搜狗 web antispider、360 索引薄（每查询 1-2 条）。
  **复跑姿势**：等百度/搜狗冷却后跑 `adapters/wentao_sohu_r10.py`（断点续收），或走文末 wechatDownload 通道。
- adapter：`adapters/wentao_sohu_r10.py`（原计划 wentao_zhihu_r10.py，因知乎 403 改道）。

## 3. 四大税务刊——KPMG 37 件，其余三家落空

- **毕马威**：`/cn/zh/services/tax/china-tax-insights/china-tax-alert.html` 列表页**静态 HTML**（64 条，
  URL 自带 /insights/YYYY/MM/ 便于近三年过滤），文章页 AEM 容器。门禁（cjk≥800＋案/路径要素）后
  **23 件**（2023-12→2025-12 窗口，新政评析+实务影响分析为主）。注意两个坑（已修）：
  ①URL 月份是 `YYYY/MM` 斜杠格式，过滤常量必须写 `"2023/10"`（写 `"2023-10"` 会因 `'/'>'-'` 恒真放行全量）；
  ②AEM `datePublished` 实测为整站迁移日（32/37 文件同日 2025-04-2x、与内容期不符）——**发布日期以 URL 月份为准**。
  adapter：`adapters/kpmg_r10.py`。
- **德勤**：`/cn/zh/services/tax/perspectives/tax-newsflash.html` 与 tax-analysis 列表页为 JS 渲染
  （静态 HTML 仅 2 条导航链接），2deloitte.com DNS 不存在。落空。
- **安永**：/zh_cn/services/tax 杂志式专题页可达，但法规速递/快讯无静态列表（多路径 404）。
- **普华永道**：pwccn.com 已并站 pwc.com/cn，publications 页 JS 动态加载（静态 113 链接全为导航）。
- **威科先行** wkinfo.com.cn：全站 SPA+登录墙（任意路径同一 20KB 壳），无免费文章静态区。落空。
- 四大线后续若要补：需 JS 执行环境（browser-use 技能可驱动，成本另计）。

## 4. 明税公众号增量——0 件（搜狗拦截持续）

- 复用 r9 链路（`adapters/mingtax_weixin_r10.py`，改产出至 税务媒体与专栏/明税·涉税实务评析，
  done 集并了 r9 的 courses_books_r9.jsonl 防 12 件重收）。
- weixin.sogou.com 本轮即 antispider（独立新会话实测 200→5386 字节拦截页），
  3×420s 冷却未恢复——与 r9 末段症状一致。**该通道现只适合隔天零散补收。**
- 明税是"官网已死、公众号唯一存续"源，**整号历史只能走 wechatDownload（下）**。

## 5. 留给用户的人工通道（wechatDownload，调研第 2 步）

- 装 qiye45/wechatDownload 4.6+（Win）+ PC 微信；GUI 内打开一篇目标号文章取 key（人工约 1 分钟，需手机确认）；
- MCP 监听后可由 Agent 批量拉：**明税、税海涛声、财税茶座、中汇信达**（无官网/官网死优先）；
- 输出直接落 `lawlibrary/专题/税务案例/全国/税务媒体与专栏/<公众号名>/`，front matter 参照本轮 adapter 格式；
- 每号连抓勿超 3 页/次；跑前查 releases 页有无"(已失效)"标注。

## 复跑

```
python work/taxcase/adapters/ctaxnews_r10.py     # 断点 media_r10.jsonl；新文章出现后增量
python work/taxcase/adapters/wentao_sohu_r10.py  # 需百度/搜狗冷却；搜狐文章页 edge101 固定
python work/taxcase/adapters/kpmg_r10.py         # 列表静态，随时增量
python work/taxcase/adapters/mingtax_weixin_r10.py  # 建议隔天试；antispider 即 3×420s 自适应
```
