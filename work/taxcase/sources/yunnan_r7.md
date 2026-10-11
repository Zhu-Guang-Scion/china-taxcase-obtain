# 云南省 · r7（2026-10-11）

## 结论
失信栏 **495 件**（496 主体 - 1 件源站事实字段为空按门槛删）+ 行政处罚公示 **934 件**（量控收前 115 页，2024-10→2026-10，含同页同主体去重）。两源均为决定书级富文本。

## 源 1：重大税收违法失信案件信息公布栏（bulletin）
- **入口**： https://yunnan.chinatax.gov.cn/bulletin/index.html （不在主站导航里！从 /col/col3842 政府信息公开 → /pub/info 行政执法信息公示平台 → 左栏"重大税收违法失信..."进入；主站首页/信息公开页均无直接链接）
- **架构**： 首页 iframe 拼装：`bullentop.jsp`（查询表单）+ `first.jsp`（静态介绍）+ `bullenrightfortop.jsp`（列表壳）。页面带瑞数 $_ts 但 curl_cffi chrome124 直连可用，无需浏览器。
- **列表接口**： `GET /bulletin/ajaxfors.jsp?tablename=jcms_41&title=&key=`（**必须带 title/key 空参数**，裸 tablename 会 404）→ 返回 `dataStore = [...]` **全量 496 行**（地区/名称/识别号/案件性质/详情URL），210KB 一次拿完
- **详情**： art_8101_*.html，字段在 `<!--<$[X]>begin-->value<!--<$[X]>end-->` 标记对里（辽宁同款）。**模板两变体**：标准 12 段与 14 段（多公布日期/依据两字段）——**末段恒为"主要违法事实法律依据及处理情况"**，按末段取事实即两变体通吃（首跑按 segs[11] 固定索引误判 95 件 bad，改末段后全数补齐）
- 覆盖 2020-02 → 2026-09

## 源 2：税务行政普通程序处罚结果（/pub 平台）
- **入口**： https://yunnan.chinatax.gov.cn/pub/info/topic?id=7add1dde1f5145c38116951262909832&parentId=c22386b90f4b45fb8614d53c4e635ede&department=15300000000&pageNumber=N
- **机制**： 服务端渲染 HTML 表（无 API），分页参数 `pageNumber`，241 页 × ~13 行 ≈ 3,100 条，日期倒序 2023-08-19 → 2026-10-10（全在三年内）
- **11 列决定书级结构化**：决定书文号/案件名称/处罚类别/处罚事由/处罚依据（全法条引用）/相对人名称/代码/法定代表人/处罚结果（金额叙述）/处罚机关/处罚日期
- **量控**： 每省 ≤2,000——失信已收 495，处罚收前 115 页得 934 件（页均 8-13 行，文号+代码+日期三元组去重后）；余 126 页（2023-08→2024-10）复跑改 MAX_PAGES=241 即可续
- 质量门槛：事由列常是短语，但依据+结果列富文本——md 里合并进"## 违法事实及处理处罚情况"单节，由 facts_text 全量计入

## 坑
- /pub/info 平台是全省统一政务公开系统（department=15300000000 是税务部门码），同平台还有"执法服务"等 topic，可按 topic id 扩展
- bulletin 列表接口对空 title/key 参数敏感（缺失即 404，不是空结果）
- 详情页瑞数脚本体积大（17KB/页）但纯静态内容可解析，无需执行 JS

## 产出
- adapter： `work/taxcase/adapters/yn_r7.py`（失信，幂等）+ `yn_xzcf_r7.py`（处罚，MAX_PAGES 量控）
- 断点： `progress/yunnan_r7.jsonl`（496 行）+ `progress/yunnan_xzcf_r7.jsonl`
- 库： `lawlibrary/专题/税务案例/云南省/{重大税收违法失信公布,行政处罚公示}/`


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
