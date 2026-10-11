# 吉林省税务局（第七轮 R7，2026-10-11）

## 结论

| 源 | 结果 | 说明 |
|---|---|---|
| **主站 重大税收违法失信主体公布栏** | ✅ **+415 件全量入库**（415/415 过门槛，0 删 0 失败，事实叙述几乎全部富全文） | 瑞数全站墙，有头 chromium 会话内采集 |
| etax 处罚平台 | ❌ 不存在 | `etax.jilin.chinatax.gov.cn` 443/8090/zfgspt 全部连接失败（DNS 解析但无服务）——吉林未部署 wings/sword 平台 |
| 市局稽查通报/处罚类 | 🟡 低价值不投入 | jsearch 全文检索：`税务行政处罚` 74 条中主体为**处罚事项告知书/送达公告**（程序性，门槛必删）；白山市稽查局处罚公示仅 9 件且为 2019-2020 老数据；无安徽式市局稽查通报频道 |

## 站点形态

- `jilin.chinatax.gov.cn` **全站瑞数**（http/https 一律 412 + `$_ts`，含 `/col/`、`/module/`、`/art/` 全路径）。
  cookie 复放不可行（四川结论通用）→ 有头 chromium（`--disable-blink-features=AutomationControlled`）+ 会话内 `page.evaluate(fetch)`。
- **坑**：col19972 页 `window.onload` 自动 `$('#FormSearchTest').submit()`（target=iframe），playwright 轮询 `page.content()` 会撞「page is navigating」竞态。
  **解法**：过挑战时家页改用稳定的旧 art 页（如 `/art/2021/10/27/art_19712_434017.html`），cookie 域内通用。
- 站内有 **jsearch**（四川同款）：`POST /jsearchfront/plugin/interface/search/search.do`，**必须页面自身 jQuery $.ajax**（裸 fetch 415），websiteid=`111000000135000`。可用作栏目/全文检索探针。

## 失信栏数据链路（采集契约）

1. 栏目页 `/col/col19972/index.html`：分面查询 UI（地区 field_1136 / 违法性质 field_1137 / 年度 field_1138 / 纳税人名称 field_1113…），`#FormSearchTest` GET 提交到 `/module/search/index.jsp`。
2. 列表接口（会话内 fetch 直连）：
   ```
   GET /module/search/index.jsp?field_1136_large=&…&field_1126=&strSelectID=1113,1114,1115,1116,1117,1120,1123,1126,1136,1137,1138
       &i_columnid=19972&field=field_1113:1:1,…,field_1138:0:1&initKind=FieldForm&type=1,1,1,1,1,1,1,1,1,1,1
       &currentplace=&splitflag=&fullpath=0&currpage=N
   ```
   - **5 条/页**；行含 税务机关/纳税人名称/识别号/案件性质 + 详情链接 `../../art/YYYY/M/D/art_19972_<id>.html`
   - **分页窗口懒扩展**：页面上显示的 maxpage 会随翻页增长（11→21→…），**必须翻到「无新增」停**（脚本以连续 2 页新增 0 终止；实测全量 415 条）
   - 分面过滤参数实测不生效（field_1137_large=1 与默认同结果）——不影响，默认查询即全量
3. 详情页 `table.zdwf` 行式结构：`<td class="title_left">LABEL</td><td>值</td>`，值内嵌
   `<!--<$[..]>begin/end-->` 标记，**一个字段值可拆多个 begin/end 段**（主要违法事实常拆 2 段以「，」相连）。
   关键行：纳税人名称 / 纳税人识别号或社会信用代码 / 注册地址 / 法定代表人… / **主体违法性质** / **主要违法事实相关法律依据及税务处理处罚情况**（富全文：检查机关+期间+事实+金额+处理处罚）。

## 复跑

- adapter：`adapters/jl_r7.py`（断点 `progress/jl_sx_r7.jsonl`，全量 URL 清单 `tmp/r7/jl_sx_arts_all.json`）
- 输出：`lawlibrary/专题/税务案例/吉林省/重大税收违法失信公布/*.md`
- 若未来要补市局稽查通报：jsearch（页面 jQuery）`q=查处|曝光|稽查` 再筛 art_863/888/896/904/912 等市局栏目


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
