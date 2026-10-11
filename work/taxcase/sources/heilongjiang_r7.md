# 黑龙江省税务局（第七轮 R7，2026-10-11）

## 结论

| 源 | 结果 | 说明 |
|---|---|---|
| **主站 重大税收违法失信主体信息公布栏** | ✅ **+454 件入库**（456 URL 全枚举，454 过门槛；1 件违法事实空被门槛删；0 失败） | **全站无墙**，curl_cffi chrome124 直连采集，速度最快的一省 |
| etax 处罚平台 | ❌ 不存在 | `etax.heilongjiang…:8090/sword` 连接失败；`/zfgspt/` 返回「页面不存在」温馨提示页——**旧 etax 已迁移至全国统一新电子税务局**，wings/sword 处罚公示平台黑龙江未部署（同浙江空库但更彻底：服务直接没了） |
| 主站行政处罚公示栏 | ❌ 无此栏目 | 主站导航（纳税服务 col7574/公众查询 col7589/通知公告 col16776）无行政执法公示栏目；`module/search` TRS 检索接口返回「您的操作出现异常」（参数形态非辽宁款） |

## 失信栏数据链路（采集契约，全部 GET 直连）

1. 挂件页 `/module/jslib/bulletin/zdss.html`（山东系 jslib bulletin，css 前缀 sdgs_*；iframe：`b ullentop.jsp` 查询表单 + `first.jsp` 占位介绍）。
   入口：主站 首页>涉税查询>公众查询 col7589 >「重大税收违法失信主体信息公布栏」。
2. 查询页 `bullenrightfortop.jsp?nsrmc=…&nsrsbh=…`（8 个条件字段，**至少一个非空**）→ 页内 jpage 配置
   `proxyUrl='ajaxfors.jsp'`、`tablename=jcms_141`、totalRecord。
3. 数据代理（**核心**，GET，忽略分页参数直接全量返回）：
   ```
   GET /module/jslib/bulletin/ajaxfors.jsp?startrecord=1&endrecord=1000&perpage=1000
       &tablename=jcms_141&nsrmc=<URL编码模糊词>&（其余条件空）
   → dataStore = [ "<tr>…所属税务机关|纳税人名称|纳税人识别号|案件性质|<a href='…/art_6410_<id>.html'>详细信息" ]
   ```
4. **全量枚举法**：nsrmc 是 SQL LIKE 模糊匹配，多词并集取饱和——
   `公司`(426) + 厂/店/部/合作社/站/行/队/宾馆/超市/经销/运输/尔滨/大/物流/… 补到 **456 条**（第二轮补词仅 +7，判定饱和；个体户/非公司主体靠非「公司」词捕获）。
5. 详情页 `/art/YYYY/M/D/art_6410_<id>.html`：两列表格 `bgcolor="#f4fcff"` 的 label td + 值 td（值内嵌 `<!--<$[..]>begin/end-->` 标记）。
   关键行：纳税人名称 / 纳税人识别号或社会信用代码 / 注册地址 / 法定代表人（姓名、性别、证件脱敏号）/ 案件性质 / **「主要违法事实相关法律依据及税务处理处罚情况」（富全文单行）**。
   注意与吉林差异：HLJ 该富全文是**一行**（吉林拆两段）；HLJ 无 `class="title_left"`，靠 bgcolor 定位行。

## 数据画像（入库 454 件）

- 案件性质以 虚开专票/虚开普通发票/逃避缴纳税款 为主，另见骗取出口退税
- 日期跨度：art URL 2023-10 起～2026-09（滚动公布栏）
- 1 件 DEL（`dishonesty`：wfsd 空值，牡丹江顺心木业 骗取出口退税——上游详情空表）

## 复跑

- adapter：`adapters/hlj_r7.py`（枚举词表内置；断点 `progress/hlj_sx_r7.jsonl`；URL 缓存 `tmp/r7/hlj_sx_urls.json`）
- 输出：`lawlibrary/专题/税务案例/黑龙江省/重大税收违法失信公布/*.md`
- 若未来黑龙江接入新处罚平台：重探 `etax.heilongjiang.chinatax.gov.cn:8443`（瑞数墙，需有头）与 :5100 新电子税务局公示入口


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
