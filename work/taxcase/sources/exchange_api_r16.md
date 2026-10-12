# 沪深交易所官网 API 深度调研（R16 · 2026-10-12）

> 用户指令：再深入调研官网 API 及其他路径能否取得更多消息。
> 本文档全部为**本机实测**结论；子智能体公开项目调研见 `_research/exchange_api_r16.md` 与
> `_research/exchange_paths_r16.md`。

## 一、上交所：新统一接口 commonSoaQuery.do（本轮核心突破）

上交所已把老接口（commonQuery.do / getESSearch.do sqlId=BS_GGLL 等）废弃迁移到
**`GET https://query.sse.com.cn/commonSoaQuery.do`**（老 ESSearch 404、queryCompanyBulletinNew
返回空 result 壳）。仍需 `Referer: https://www.sse.com.cn/...`，否则拒。

```
GET https://query.sse.com.cn/commonSoaQuery.do?isPagination=true
    &pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1
    &sqlId=BS_KCB_GGLL_NEW&siteId=28&channelId=<栏目组>
    &type=&stockcode=&extWTFL=&createTime=&createTimeEnd=&order=createTime|desc,stockcode|asc
```

| channelId | 栏目 | 总量（2026-10） | 实测页 |
|---|---|---|---|
| 10007,10008,10009,10010 | 监管措施（监管工作函/监管关注等） | **5,555** | /disclosure/credibility/supervision/measures/ |
| 10743,10744,10012 | 监管问询（问询函/重组审核意见函） | **2,932** | /regulation/supervision/inquiries/ |

关键字段：`docTitle`（**标题含事由**，如"关于XX公司YY事项的监管工作函"）、`stockcode`、
`extGSJC`（公司简称）、`extWTFL`（文书分类）、`cmsOpDate`、`docId`、
**`docURL`（PDF 相对路径，加 `http://` 前缀即直链）**。

发现路径：页面纯前端渲染 + require.js 动态模块，静态逆向断头；**IAB 开页面 →
`performance.getEntriesByType("resource")` 一把抓真实 XHR**（本轮最快解法，值得复用）。

注意：`jsonCallBack=jsonpCallbackNNN` 可省略（省略后直接返回纯 JSON）；pageSize=100 可用。

## 二、深交所：ShowReport 老接口健在，页面大改版

深交所官网页面路径全面变更（/disclosure/announcements/ 等老路径 404），但
**`GET https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=<码>&PAGENO=<页>&random=<随机数>`**
健在（random 防缓存必带）：

| CATALOGID | 栏目 | 总量 | 页面入口（新路径） |
|---|---|---|---|
| 1800_jgxxgk | 监管措施 | **4,855** | /disclosure/supervision/measure/measure/index.html |
| main_wxhj | 问询函件（关注函/年报问询函，含回复 hfck） | **7,389** | /disclosure/supervision/inquire/index.html |

- 监管措施字段：gkxx_gsdm/gsjc/gdrq/gkxx_jgcs（措施类型）/gkxx_sjdx（对象）/**hjnr（内含
  `encode-open='/UpFiles/zqjghj/xxx.pdf'` → 拼 https://www.szse.cn 前缀直链）**
- 问询函字段：gsdm/gsjc/fhrq/hjlb（函件类别）/ck（函件 PDF）/hfck（**回复 PDF**）
- **列表均无事由字段**——涉税筛选只能靠 PDF 全文把关（adapter 已内置全文复核）

annList（/api/disc/announcement/annList）也修通了：`channelCode:["fixed_disc"]` 必须非空
（null → 500），返回 {announceCount, data[]}，**不支持关键词参数**（keyword/title 均无效），
只能按日期/股票/频道翻页——检索场景不如巨潮，弃用。

## 三、其他路径结论（详见子代理报告）

- 纪律处分：上交所上市公司监管导航下无独立 disposition 页（并入 trading/listing/bond 各条线），
  涉税信披违规的直接处分案例少（重大财务造假由证监会处罚，库内已有证监会栏目）——本轮不单列
- 问询函：两所接口均已打通（合计 10,321 条），但**标题无事由、全文必提税**（年报问询函
  收入/税负段），标题级筛选无区分度——若收需按"附件名/函件类别含税"或全文 NLP 筛，等评估结论
- 北交所/新三板：巨潮同源可查，量级见子代理 B 报告

## 四、入库约定（R16）

- adapter：`adapters/exchange_measure.py`（两所监管措施，标题筛+全文复核双闸）
- 目录：`上交所/监管措施/`、`深交所/监管措施/`；断点 `progress/exchange_measure.jsonl`
- 深交所列表无事由 → 全量下 PDF 后以"全文含税要素"把关（TAX_TITLE 词表 + 税字头词）


## 五、收尾补充（全部实测）

- **深交所 PDF 真实下载域是 `reportdocs.static.szse.cn`**：hjnr 里 encode-open 相对路径挂 www.szse.cn
  会 404（IAB 页面点击 window.open 捕获才拿到真实域）
- **深交所纪律处分 CATALOGID=1800_jgxxgk_cf（2,894 条）标题涉税命中 0**——与子代理 B 评估一致
  （涉税<5% 且标题不可筛），判死；xlsx 整表导出（SHOWTYPE=xlsx）对该 catalogid 返回空数组
- **两所监管措施标题/正文涉税率都极低**（上交所 5,555 条标题 0 命中；深交所抽查正文无税字，
  事由集中在募集资金/坏账/信披更正类）——监管措施路径产出预计几十件，属"低密度但权威"补充
- 深交所 annList 补充（子代理 A）：seDate 必须二元数组、channelCode 必填
  （listedNotice_disc=全部公告）、pageSize≤50、keyword 被静默忽略——确认弃用（巨潮覆盖）
