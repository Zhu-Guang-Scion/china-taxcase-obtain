# R10 · 税务批复/函件/官方答复 采集（fgk + 税屋）

> 第十轮新栏目「税务批复与函件」。调研：`_research/pifu_sources_r10.md`（probe 样本在
> `_research/probe_r10/`）。adapter：`adapters/pifu_r10.py`（fgk API）、
> `adapters/shui5_r10.py`（税屋 playwright 过 WAF）。断点：`progress/pifu_r10.jsonl`
> （fgk/shui5 共用，src 字段区分）；列表缓存 `pifu_r10.fgk_items.json` /
> `pifu_r10.shui5_items.json` / `pifu_r10.shui5_prov_items.json`。
> 入库：`lawlibrary/专题/税务案例/全国/税务批复与函件/`。

## 1. 信源一：总局政策法规库 fgk.chinatax.gov.cn（官方权威，无墙）

- **列表**：`GET https://www.chinatax.gov.cn/search5/search/s?siteCode=bm29000002
  &searchWord={词}&type=&pageSize=10&pageNum={n}&orderBy=5&column=政策法规`
  （TRS search5 JSON；**服务端每页封顶 10 条**，pageSize 传 20 也只回 10；pageNum 从 0）。
  关键词为全文匹配噪音大，必须按 `govDoc.docType` 白名单二次过滤：
  `国税函/国税函发/国税函字/税总函/税总办函/税函`（公告/令/国函/财税/国税发 全剔除）。
  实测 totals：批复 471｜国税函 333｜税总函 22｜税函 3 → 函类去重后 **530 件**。
- **建议提案答复**：官网栏 `/chinatax/n810214/c102374/c102387/` 首页仅 22 条直出、
  `index_1.html` 404（无翻页）；历史项经 search5 检索 `号建议的答复`(84)+`提案答复`(40)
  按 URL 前缀 `/c102387/` 过滤得 **124 件**。
- **详情**：fgk `content.html` 正文在 `<div class="arc_cont">`（TextContentDuanLuo 段）；
  答复页正文在 `<div class="text" id="fontzoom">`。成文日期/时效性取 API `cwrq`/`xxgk_aging`。
- **结果**：530 件全入库（8 件 40-99 字超短实质批复二次复核后保留，见 §4）；
  delay 1.6s curl_cffi chrome124 直连无墙。

## 2. 信源二：税屋 shui5.cn 中央年份列（主量源，阿里云 WAF）

- **过墙**：playwright 有头（`SHUI5_HEADLESS=1` 可切无头，probe 实测无头也曾过），
  挑战页特征 = 正文含 `renderData` 且 len<12000；`File not found.` 短页=死链列。
  会话过期 → 换 page → 仍败重开整浏览器。单线程 2.2-3.2s 抖动。
- **列结构**：`/article/{slug}/` 第 1 页，`/article/{slug}/{colid}_{page}.html` 翻页；
  条目块 `div.xwt2`（title/日期 p.p3/栏目 p.p4 一致才计入，侧栏推荐位自动剔除）。
  **年份 slug 以站内年份导航为准**：2017-2019 全小写（`2018nianshuishoufagui`，
  驼峰会 File not found），1994-2016/2020 驼峰 `{yr}NianShuiShouFaGui`，2021+ `{yr}NianFaGui`。
- **采集口径（brief 优先反转）**：2020/2019/2018 函类全收（43 件）→ 1994-2017
  标题"批复"类 → 2021-2026 函类扫描（仅 2021 有 6 件税总函，2022-2026 为 0——
  中央近年函件不公开，公开走公告/12366，与调研预判一致）。
- **列表总量实测 4,191 件**（批复密度远超调研的 ~1,500 估：2004 峰值 458 件/年）。
  全局量控 ≤4,000 → 详情按优先序收至 **2,400 上限**（2020→…→1994 顺序，
  超出部分为最早期年份，被 cap 截断）。
- **详情**：正文 `<!--arcContent-->…<!--/arcContent-->`；长文分页 `{id}_{n}.html` 逐页拼接。
  文号从标题正则抽取（`国税函[2009]779号 …`），跨源与 fgk `docNum` 规范化对齐。

## 3. 信源三：税屋省税函（粤苏浙沪京，2023+）

- 5 省列：广东 `GuangDongShengCaiShuiFaGu`、江苏 `JiangSuShengCaiShuiFaGui`、
  浙江 `ZheJiangShengCaiShuiFaGui`、上海 `ShangHaiShiCaiShuiFaGui`、
  北京 `BeiJingShiCaiShuiFaGui`（列结构同上）。
- 口径：文号机关段匹配 `.{1,6}税.{0,3}函` 且年份 ≥2023（剔省府/人社/医保函）；
  连续 5 页无 ≥2023 命中即止（列按时间倒序）；量控 ≤1,000。

## 4. 质量门槛执行

- 函件正文 <100 字不收；**例外**：40-99 字且含"收悉/批复如下"的超短实质批复保留
  （一口径批件如 国税函〔2009〕455号 核桃油按食用植物油 13%——属实质口径，
  非"纯转发/形式函"；fgk 8 件经二次复核全部回收）。
- 标题黑名单（名单/会议/任免/值班/印章/着装）在列表阶段剔除。
- 批复类天然含"案情+口径"（主送机关+请示文号+口径段），全收不另设事实具体性门槛。

## 5. 去重键

`norm_docno`：去括号〔[]()（）〕/空格、全角数字转半角 → `机关|年|号`（如
`国税函|2009|779`）。fgk `govDoc.docNum` 为权威记录；税屋同文号跳过（progress 记
`dup_of:"fgk"`）。无文号类（建议提案答复）用 `title_norm+日期` 复合键。
与法规库（实测 0 函）、12366 库（5,019 件问答无文号）零重叠。

## 6. 结果对账

（采集完成后回填：fgk / 税屋中央 / 省函 件数、去重损失、质量抽评。见 STATE 更新。）

## 7. 复跑

```bash
cd work/taxcase
python adapters/pifu_r10.py --phase all            # fgk（无墙，~25 min）
python adapters/shui5_r10.py --mode central        # 税屋中央（挂机 ~2.5-4 h）
python adapters/shui5_r10.py --mode prov           # 5 省省税函（挂机 ~1-1.5 h）
```
