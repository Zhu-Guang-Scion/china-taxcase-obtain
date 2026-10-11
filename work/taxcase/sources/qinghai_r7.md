# 青海省税务局（第七轮 R7，2026-10-11）

## 结论

| 源 | 结果 | 说明 |
|---|---|---|
| **主站 重大税收违法失信主体信息公布栏** | ✅ **+113 件入库**（114 全量，1 件事实 9 字被门槛删） | **全站无墙**（http 200 直连；https 证书域名不匹配 403，全程 http） |
| 主站 税案通报（税务新闻+通知公告关键词） | ✅ **+37 件**（64 命中→青海相关 47→3 件裁量基准类规范文件手工剔除） | swxw 14 页 + tzgg 20 页标题关键词扫 |
| etax:7201 行政执法信息公示平台（sword） | ❌ 判死 | 首页 outlink（base64 ct_outlink_displace 解码得 etax.qinghai:7201/sword?ctrl=XzzfgsptHomeCtrl_index）；**http 52 空回复、https 黑洞、有头浏览器同死**（http goto 40s 超时 / https ERR_TIMED_OUT）——服务未对外 |

## 失信栏数据链路（采集契约，全部 GET 直连，curl_cffi chrome124）

1. 入口页 `/web/zdsswfsxaj/zdaj.shtml`：按 9 市州（iframe.shtml?ssswjgmc=青海省…）、11 类案件性质
   （iframe.shtml?ajxz=虚开增值税专用发票…）、按年（iframe.shtml?time=2025年度）三组 iframe 切片——
   全部指向同一个 TRS 云搜索渠道。
2. **数据接口（核心）**：
   ```
   GET /common/search/6279081b27f8406ea6bc8fdd3e5257bc?_isAgg=false&_isJson=true&_pageSize=100
       &_template=index&_rangeTimeGte=&_channelName=&page=N        → {"data":{"total":114,"results":[…]}}
   ```
   results 行的 `domainMetaList[1].resultList` 自带结构化元数据：
   `nsrmc/nsrsbh/zzjgdm/zcdz/ajxz/ssswjgmc` + **`zywfss`=主要违法事实全文 + `xgflyj`=法律依据及处理处罚全文**。
   免详情页即可成文；详情页 `/web/zdsswfsxaj/YYYYMM/<uuid>.shtml` 为标准 2 列公布表（与元数据一致，113/114 全抓成功留档 `tmp/r7/qh_arts/`）。
3. 量：**114 主体全量**（2019-2026 滚动；虚开专票/虚开普票为主，走逃次之）。

## 税案通报

- 列表 `/web/swxw/list.shtml`（14 页）+ `/web/tzgg/xxgk_fdzd_list.shtml`（20 页），TRS 静态分页 `list_N.shtml`；
  标题关键词（稽查|查处|偷税|虚开|骗税|骗取|处罚|失信|曝光|追缴|抗税|逃避|违法）+ 青海地名过滤（排除总局级/外省通稿）。
- 正文容器 `<article id="page-newContent">`（含 `&ensp;` 实体；`发布时间` 行取日期）。
  **坑**：不能先 `re.sub('<!--.*?-->')` 再抽正文——文章正文包裹在未闭合注释区间里，先删注释会把正文整段吃掉。

## 复跑

- 脚本：`tmp/r7/qh1.py→qh_md.py`（失信）、`r7 汇报内 qh_news_md.py`（通报）；原始数据 `tmp/r7/qh_sx.jsonl` + `qh_news_arts.jsonl`
- 断点：`progress/qinghai_r7.jsonl`（160 行）
- 输出：`lawlibrary/专题/税务案例/青海省/重大税收违法失信公布/`（113）+ `税案通报/`（37）
- 复跑条件：7201 平台若恢复，先 curl 试 `http://etax.qinghai.chinatax.gov.cn:7201/sword?ctrl=XzzfgsptHomeCtrl_index`


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
