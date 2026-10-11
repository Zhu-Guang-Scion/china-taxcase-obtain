# 宁夏回族自治区税务局（第七轮 R7，2026-10-11）

## 结论

| 源 | 结果 | 说明 |
|---|---|---|
| **主站 重大税收违法失信主体 col16187** | ✅ **+599 件入库**（599/599 全量，0 DEL） | http 412 瑞数；有头一次通过挑战；**`/module/search/` 也有挑战（与甘肃不同）**，列表+详情全程浏览器会话 |
| 主站 税案通报（税务新闻 col10968 + 通知公告 col10881） | ✅ **+1 件**（固原虚开案，545 字富全文） | 48 页标题扫仅 1 命中——宁夏案件通报密度极低，数据重心全在失信栏 |
| zfgs:9443 行政执法信息公示平台（sword wings） | ❌ **空壳** | 模块配置可读（`paramsArrry.modulesDataObj['xzcf']` → `/sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg`）；验证码 ddddocr 一次过（`#ck1_img` canvas 截取）；**空条件/日期区间/nsrmc=宁夏/cfjg=稽查局 四种查询全「没有数据」**——同重庆:8888 先例，省级平台未接数据 |
| 失信模块互链 | 记档 | sword 平台"重大税收违法失信案件信息"菜单直接链回主站 col16187（印证唯一数据源） |

## 失信栏数据链路（采集契约，全程浏览器会话）

1. 栏目页 `/col/col16187/index.html`：TRS FieldForm（vc_name 纳税人名称 / field_147 识别号 / field_150 法人+身份证），
   `modifyQuery()` 提交前把隐藏 `isQuery` 置 1——**裸 GET 必须 `isQuery=1` 且带空字段参数**，否则返回 1703 字节空壳。
2. **列表接口（核心）**：
   ```
   GET /module/search/index.jsp?field=field_148:1,field_149:1,vc_name:1,field_147:1,field_150:1,field_151:1
       &i_columnid=16187&strSelectID=104,147,148,149,150,151&initKind=FieldForm
       &currentplace=&splitflag=&fullpath=0&isQuery=1&vc_name=<URL编码模糊词>&field_147=&field_150=&…&currpage=N
   → 7 列富行：信息标题|显示时间|纳税人识别号|案件性质|公布机关|法定代表人|详细
   ```
   显示时间即真实发布日期（2026-09 集中公布 500+，回溯至 2019）。
3. **全量枚举法（LIKE 饱和）**：`公司`(592) + 厂/部/站/陈/马/… 补齐 → **599 条**（第二轮补词仅 +7，判定饱和；
   自然人主体在本栏几乎不存在——19 个姓氏词 0 增量）。
4. 详情 `/art/YYYY/M/D/art_16187_<id>.html`：2 列表 + **`begin-->…end-->` 标记包裹字段值**（辽宁款）。
   字段 15 项：名称/识别号/组织机构代码/注册地址/法定代表人/违法期间法人/财务负责人/实际负责人/中介机构/
   案件性质/**主要违法事实（富全文）**/**相关法律依据及税务处理处罚情况（富全文）**/检查机关/公布机关。
   **坑**：`纳税人名称` 偶带 `<$[信息标题]>` TRS 标记残留，须 `<!--|-->|<\$\[[^\]]*\]>` 清洗（否则文件名非法）。

## sword 空壳判定过程（复跑用）

- 首页 `https://zfgs.ningxia.chinatax.gov.cn:9443/sword?ctrl=XzzfgsptHomeCtrl_index`（**无瑞数**，浏览器秒开）
- 模块树：`pg.evaluate("() => JSON.stringify(paramsArrry.modulesDataObj['xzcf'])")`
- 验证码：`#ck1_img` → canvas → ddddocr（本轮 3/3 一次过）；`#ck1_input` 填码 + `search()` 提交
- 若未来接入数据：`search()` 源码给出参数 `{ajmc,nsrmsbh,nsrmc,cfjg,swjgDm,yxqq,yxqz,ckcodeId}`，网格 id=`ybqxcfGrid`，pageSize 选择器 `#ybqxcfGrid_pagingBar_info_pageSize`

## 复跑

- 脚本：`tmp/r7/r7_nx1.py`（列表+详情）、`r7_nx_md.py`（转 md）、`r7_nx2/3.py`（sword 试探）；原始数据 `tmp/r7/nx_sx_rows.json` + `nx_arts/`
- 断点：`progress/ningxia_r7.jsonl`（599 行）
- 输出：`lawlibrary/专题/税务案例/宁夏回族自治区/重大税收违法失信公布/`（599）+ `税案通报/`（1）


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
