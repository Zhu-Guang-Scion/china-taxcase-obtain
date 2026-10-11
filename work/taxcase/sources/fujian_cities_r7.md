# 第七轮：福建 9 市局子站（+平潭+厦门）静态栏目采集

- 攻坚日期：2026-10-11 ｜ 脚本：`work/taxcase/adapters/fj_cities_r7.py` ｜ 断点：`work/taxcase/progress/fj_cities_r7.jsonl`
- 前置：`sources/fujian_etax.md`（etax xxmh 处罚平台终局判死：anji 点选验证码服务端部署缺陷，
  人机均不可过，0 条）。本轮换路市局子站静态栏目（安徽模式），**全站无墙，直连采集**。

## 0. 一句话结论

**市局子站全部在主站路径下（非子域名），TRS WCM + was5 检索接口全开放——
`DOCTITLE=` 标题子串检索直达处罚/处理决定书送达公告，且送达公告正文内嵌决定书全文
（"违法事实及证据/处罚决定"两节俱全），是富全文直收源。厦门独立站 https 软 404 回首页、
http 直连正常，sbf 平台确认空库，仅静态栏目有少量产出。**

## 1. 站点结构（实测）

- 主站 `fujian.chinatax.gov.cn`：curl_cffi chrome124 直连 200，无瑞数/网宿墙，无需有头浏览器。
- 9 市局子站=主站路径（首页底部"市局频道"导航），全部 200：
  福州 `/fzsswj/` 漳州 `/zzsswj/` 泉州 `/qzsswj/` 三明 `/smsswj/` 莆田 `/ptsswj/`
  南平 `/npsswj/` 龙岩 `/lysswj/` 宁德 `/ndsswj/` 平潭 `/pingtanswj/`
  （子域名 fzsw.fujian.chinatax.gov.cn 等 **不解析**，别走弯路）
- 厦门计划单列市独立站 `xiamen.chinatax.gov.cn`（xmdscms templt engine 自研 CMS）：
  - **https 任何路径（含 robots.txt、文章页）都返回 104384B 首页软 404**；
  - **http:// 直连正常**（文章页 `/xmswcms/content/S\d+.html`、栏目页均 200）；
  - `sbf.xiamen.chinatax.gov.cn:1080`（行政执法公示平台 iframe 数据源，/dwfw/*.do）：
    重大税收违法失信主体信息 `zdsswfsxajxx.do` 返回"记录数:0"——**空库确认**（与此前 sbf 判空一致）；
  - 栏目静态翻页：`pages/index.html, index2.html, index3.html…`（第 1 页无数字后缀）。

## 2. 主站 TRS was5 检索契约（本轮核心成果）

```
GET https://fujian.chinatax.gov.cn/was5/web/search
    ?channelid=203958                       # 检索根栏目（全子站通用，勿用栏目chnlid）
    &templet=advsch.jsp
    &sortfield=-docreltime                  # 时间倒序（默认 -docorderpri,-docreltime 混排）
    &classsql= siteid={48..56}              # 子站id：福州48 漳州49 泉州50 三明51 莆田52
                                            #         南平53 龙岩54 宁德55 平潭56
    &searchword=DOCTITLE=处罚决定书          # 标题子串精准检索（大小写不敏感）
    &prepage=50&page={n}
返回: {"count":"N","pagenum":"M","docs":[{title,title2,url,chnldocurl,time,docid,
        content(节选),channelname,…}]}
```

- 响应**非严格 JSON**（内嵌单引号串 + 字段间 `\r\n`），按文档块 `{"title"` 切分后逐字段正则解析；
  `title` 带检索高亮 `<font color=#FF0000>`，取 `title2`（干净）。
- **可用**：`DOCTITLE=关键字`（标题子串）、`searchword=关键字`（全文）、组合 `classsql siteid + searchword`。
- **不可用**（服务端报错/空）：`DOCTITLE=a OR DOCTITLE=b`、`AND DOCRELTIME>=…`、classsql 日期条件、
  `doctitle like '%x%'`（classsql 字段语法）——多词就分多次查询，日期客户端过滤。
- 前端列表页（avalon `list_pagebar`，model.list/wasdoc 模块）就是打这个接口；`index_N.html`
  静态翻页不存在（回软 404 电子税务局 SPA 壳）。channelid 各站不同值（如福州 203958）但
  203958 对全部 siteid 通用。

## 3. 栏目与内容形态

- 各子站相关栏目：`tzgg`(通知公告) / `xjtzgg`(县局通知公告) / `xxgk/gsgg`(税务公告) /
  `xxgk/wsgg`(文书公告·莆田) / `xxgk/sjxxgk/qtgg`(其他公告)——**决定书送达公告散布在
  这些栏目，按标题检索跨栏目采集，不必逐栏目翻**。
- **内容形态（关键）**：送达公告页 = 公告头（无法送达+法条）+ **决定书全文内嵌**
  （违法事实及证据 / 处罚决定 / 罚款金额 / 复议诉讼权利），无附件也已是富全文；
  少数带 pdf/doc 附件。
- 失信类：`《税务事项通知书（重大税收违法失信主体确定适用）》送达公告`（进入失信认定程序，
  常内嵌处理决定书）+ `涉税服务严重失信主体情况公告`（月度公式化，多空表）。
- 欠税公告等在 etax xxmh 平台（判死）——子站首页只放链接。

## 4. 抓取策略（fj_cities_r7.py）

每子站 4 组检索（均 `sortfield=-docreltime`，prepage=50）：
| 组 | searchword | 入库栏目 | 时窗 |
|---|---|---|---|
| Q1 | `DOCTITLE=处罚决定书` | 行政处罚决定 | 全时段 |
| Q2 | `DOCTITLE=处理决定书` | 行政处罚决定（URL 去重） | 全时段 |
| Q3 | `DOCTITLE=重大税收违法` | 重大税收违法失信公布 | 全时段 |
| Q4 | `DOCTITLE=虚开/偷税/查处/曝光/骗取/骗税/税案/追缴` | 税案通报 | ≥2023-01-01 |

- 厦门：`pages/indexN.html` 静态翻页（通知公告52页/税务要闻120页/外媒体头60页），
  标题关键词过滤后 http 抓详情。
- 双门槛：适配器 gate（cjk≥200 + 案情叙述 + 处罚要素）→ `quality_prune.decide()`，DEL 不入库。
- 量控：每市 ≤300、全省 ≤2,000（含厦门）。
- 附件链接（pdf/doc 等）追加到文末"附件:"节。

## 5. 坑

1. 子站是**路径不是子域名**——fzsw.fujian.chinatax.gov.cn 不解析，从首页 footer"市局频道"拿路径。
2. 厦门 **https 全站软 404 回首页**（连 robots.txt 都回 104384B 首页），必须 http:// 直连；
   等长 104384 的"首页"有多个变体，比对内容不能只看长度。
3. was5 组合布尔与日期过滤一律报错；`channelid` 必须用检索根栏目 203958，用栏目自身
   chnlid 会 404。
4. TRS 返回非严格 JSON，`"title2":"…","url":"…"` 之间有 `\r\n`，连续正则会跨文档误吞。
5. 同一送达公告会在"处罚决定书"与"处理决定书"两组检索重复命中（标题双书名号），
   progress 按 URL 去重；同日同标题不同 docid 是双栏目发布，文件名冲突按 exists 跳过。
6. 决定书（简易）针对个体户小案（罚款几十元）但全文结构完整，按普通件收录。

## 6. 抓取量汇总（2026-10-11 完成，两段跑批+断点续跑一次）

| 市 | 行政处罚决定 | 重大税收违法失信公布 | 税案通报 | 小计 |
|---|---|---|---|---|
| 福州 | 300 | 0（触顶未跑 Q3/Q4） | 0 | **300**（量控触顶） |
| 漳州 | 1 | 0 | 3 | **4**（源本就薄：DOCTITLE=处罚决定书 全库 0 条） |
| 泉州 | 300 | 0（触顶） | 0 | **300**（量控触顶） |
| 三明 | 150 | 5 | 3 | **158**（检索穷尽） |
| 莆田 | 85 | 215 | 0（触顶） | **300**（量控触顶） |
| 南平 | 143 | 1 | 8 | **152**（检索穷尽，Q4 87 条早于 2023 跳过） |
| 龙岩 | 0 | 1 | 8 | **9**（决定书标题检索 0 命中，仅新闻） |
| 宁德 | 72 | 31 | 9 | **112**（检索穷尽） |
| 平潭 | 79 | 0 | 6 | **85**（检索穷尽） |
| 厦门 | 0 | 0 | 80 | **80**（sbf 空库；静态栏目新闻） |
| **合计** | 1130 | 253 | 117 | **1,500** |

- progress 记录 3,423 条（含 skip-kw/rejected/old/exists/cap）；质量审计：
  **1,500 件全部 KEEP（quality_prune.decide 0 DEL）**，正文 cjk min=222 / 中位=839 / p10=611。
- 触顶三市（福州/泉州/莆田）的 Q3/Q4 未跑——按每市 ≤300 量控让路 Q1/Q2 决定书全文；
  如需补失信/新闻，删 progress 里对应市记录重跑即可（断点按 URL 粒度）。
- 富样本：宁德"陈幼平《税务行政处罚决定书》送达"（决定书全文内嵌，个人承包工程取得
  3 家材料商 5 份虚开发票 38.78 万元事实俱全）；莆田"重大税收违法失信主体告知适用"
  通知书 215 件（附件"拟公布的失信信息"全文内嵌：基本情况+违法事实+处理情况）。

## 7. 复跑条件

- was5 契约不变即可随时增量续跑（progress 断点）；`DOCTITLE=` 可换任意标题词扩展
  （如 `DOCTITLE=税务事项通知书` 可捞催报/核定类，本库口径不需要）。
- 若厦门 https 修复，栏目页可直接 https 抓；sbf 若出数据走 `/dwfw/*.do` 表单（当前空库）。
- etax xxmh 处罚平台的判死条件不变（见 fujian_etax.md 第 8 节）。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
