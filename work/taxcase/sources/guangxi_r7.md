# 广西壮族自治区 · r7（2026-10-11）

## 结论
失信栏 **1,064 件全收，100% 过质量门槛**（0 DEL）。处罚平台 etax:8208 端口不通（连接超时），无补充源。

## 主源：重大税收违法失信主体信息公布栏
- **入口**： https://guangxi.chinatax.gov.cn/nsfw/sscx/sswfanj/ （主站 TRS，从 xxgk → 法定主动公开内容 → 机构概况左侧导航进入）
- **机制**： 页面查询表单走 `GET https://guangxi.chinatax.gov.cn/restSearch`，参数：
  ```
  channelid=290909 & searchword=(NF=YYYY) & orderby=RELEVANCE & page=N & pageSize=100
  ```
  - searchword 必须非空（空条件 alert 拒查）——**按 NF 年份枚举**：2014-2022 全 0，2023=28 / 2024=327 / 2025=486 / 2026=223，合计 1,064
  - pageSize=100 有效（一次请求 100 行），Referer 带栏目页即可，curl_cffi chrome124 直连无墙
- **行即富全文**（湖南 hardcase 同形态）：`ZYWFSS`（主要违法事实，cjk 中位 74 字，min 57——全部 ≥30 门槛）+ `XGFL_CFQK`（处理处罚）+ NSR_NAME/NSR_ID/AJXZ/ADDR/FDDBR_NAME/REG_ADDR/DOCRELTIME/DOCPUBURL
- 无需抓详情页（DOCPUBURL 已留档在 front matter 原文链接）

## 判死的路
- **etax.guangxi.chinatax.gov.cn:8208/zfgspt**（行政执法公示 wings 平台，主站导航指向它）：TCP 连接超时（http/https 均不可达）——服务下线或端口封禁，无法收处罚公示。若日后恢复，参考山东/辽宁同款 `query_swxz_ybcx_cfjg.spring` 接口。

## 坑
- 主站大量栏目页是 `<meta refresh>` 链（xxgk → jggk → jgzn），抓取要跟跳 2-3 层才到真导航页。
- restSearch 返回 `pager.dataCount` 与实际行数一致，无重复；DOCPUBTIME 与 DOCRELTIME 不同（DOCPUBTIME 是 2026-09-17 批量重发布时间）——**日期用 DOCRELTIME**。

## 产出
- adapter： `work/taxcase/adapters/gx_r7.py`（幂等可续跑）
- 断点： `work/taxcase/progress/guangxi_r7.jsonl`
- 库： `lawlibrary/专题/税务案例/广西壮族自治区/重大税收违法失信公布/` 1,064 md


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
