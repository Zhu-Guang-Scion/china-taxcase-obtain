# 交易所官网 API 调研报告（第 16 轮）

调研日期：2026-10-12。调研方式：GitHub/知乎/CSDN 公开项目检索 + 本机实测（Git Bash curl、python requests、curl_cffi 0.16.3 三方对照）。
**本报告所有标注「实测可用」的接口均在 2026-10-12 从本机直接打通并取回真实数据。**

---

## 0. 结论速览

| # | 数据 | 交易所 | 接口 | 状态（2026-10-12 实测） |
|---|------|--------|------|--------------------------|
| 1 | 上市公司公告列表 | 深交所 | `POST /api/disc/announcement/annList` | **可用**（此前 500 的真因是 payload 格式，见 §1.1） |
| 2 | 监管措施（自律监管） | 深交所 | `GET /api/report/ShowReport/data` CATALOGID=`1800_jgxxgk` | **可用**（4855 条） |
| 3 | 纪律处分 | 深交所 | 同上 CATALOGID=`1800_jgxxgk_cf` | **可用**（2894 条） |
| 4 | 问询函/关注函（主板） | 深交所 | 同上 CATALOGID=`main_wxhj` | **可用**（7389 条） |
| 5 | 监管措施+纪律处分（上市公司+债券） | 上交所 | `GET commonSoaQuery.do` sqlId=`BS_GGLL_NEW` channelId=`9894,...` | **可用**（1006 条） |
| 6 | 监管问询 | 上交所 | 同上 channelId=`10743,10744,10012` | **可用**（2932 条） |
| 7 | 发行上市审核监管措施 | 上交所 | 同上 channelId=`15099,15100,15101,15102` | **可用**（182 条） |
| 8 | 上市公司公告列表 | 上交所 | `GET security/stock/queryCompanyBulletinNew.do` | **可用**（按代码过滤；**TITLE 关键词过滤实测无效**） |
| 9 | 公告全文检索 | 上交所 | `search/getESSearch.do`（sqlId=BS_GGLL 等） | **已死**（404），继任者 `search/getSearchResult.do` 存在但本环境超时（§3.4） |
| 10 | 公告全文检索 | 深交所 | annList 的 `keyword` 参数 | **被静默忽略**（不报错但不生效），全文检索建议仍走巨潮 |
| 11 | 旧版数据总貌 JSON | 深交所 | `GET /api/report/ShowReport?SHOWTYPE=JSON` | **已死**（一律 500），JSON 数据已迁移到 `/ShowReport/data`；`SHOWTYPE=xlsx` 的 Excel 导出仍在 `/ShowReport` |

**关于上轮两个失败的根因**：
- 深交所 annList 500：**不是 WAF 拦截，是 payload 类型错误**。`seDate` 必须是**二元数组** `["2026-10-09","2026-10-12"]`；传字符串 `"a~b"`、缺省、或只给部分字段都会直接 500（服务端反序列化失败）。本轮用普通 `python requests`（无需 TLS 伪装）即 200。
- 上交所 getESSearch.do 404：该端点确已下线。公告列表改走 `security/stock/queryCompanyBulletinNew.do`，监管类数据改走 `commonSoaQuery.do`（新 SOA 端点，官方页面 JS 在用）。

---

## 1. 深交所公告列表 API（annList）

### 1.1 接口规格

- **URL**：`https://www.szse.cn/api/disc/announcement/annList?random=0.<16位随机数>`
- **方法**：POST，`Content-Type: application/json`
- **必须 headers**（实测普通 requests + 以下 3 个头即可 200；Git Bash 的裸 curl 会被 50x 页面拒绝，用 curl_cffi `impersonate="chrome"` 或 python requests 均可）：
  - `Content-Type: application/json`
  - `X-Request-Type: ajax`（可选但建议带）
  - `Referer: https://www.szse.cn/disclosure/listed/fixed/index.html`
  - `User-Agent`: 常规浏览器 UA
- **payload 字段（全部实测验证）**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `seDate` | **list[str]，2 个元素** | `["起始日","结束日"]`，格式 `YYYY-MM-DD`。传字符串 `"a~b"` → **500**；缺失 → 500。跨度无限制（实测 2020-01-01~2026-10-12 正常，count=241 万） |
| `channelCode` | list[str] | 渠道码，见下表。与 stock 至少给一个，否则 500 |
| `stock` | list[str] | 6 位证券代码，如 `["000001"]`，可选 |
| `bigCategoryId` | list[str] | 报告大类码，可选。实测 `010301` 有效（年报类，6002 条） |
| `pageSize` | int | 最大 **50**（传 100 实际返回 50） |
| `pageNum` | int | 页码，从 1 起 |

- **channelCode 实测值**：

| channelCode | 含义 | 实测（2026-10-09~10-12 窗口） |
|---|---|---|
| `listedNotice_disc` | 上市公司全部公告（临时+定期） | count=1694 |
| `fixed_disc` | 定期报告 | 正常返回（三季报等） |
| `bond_disc` / `fund_disc` | 实测返回 count=0 | 码值可能已变，勿依赖 |

- **keyword 检索**：`keyword` 参数被**静默忽略**（带上后 count 与不带完全一致，258048 条不变）。深交所公告全文检索没有开放 API，关键词场景继续走巨潮（项目已有 cninfo 通道）。
- **返回结构**：`{"announceCount": N, "data": [{"id","secCode":[...],"secName":[...],"title","publishTime","attachPath",...}]}`；PDF 下载前缀 `https://disc.static.szse.cn/download` + `attachPath`（如 `/disc/disk03/finalpage/2026-08-15/xxx.PDF`）。

### 1.2 可直接运行的代码（实测 200）

```python
import random, requests  # 普通 requests 即可，无需 curl_cffi

def szse_annList(se_date, channel="listedNotice_disc", stock=None,
                 big_category=None, page_size=50, page_num=1):
    url = f"https://www.szse.cn/api/disc/announcement/annList?random={random.random()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "X-Request-Type": "ajax",
        "Referer": "https://www.szse.cn/disclosure/listed/fixed/index.html",
    }
    payload = {
        "seDate": list(se_date),          # 关键：必须是二元数组 ["2026-10-01","2026-10-12"]
        "channelCode": [channel],
        "pageSize": page_size,             # 上限 50
        "pageNum": page_num,
    }
    if stock:
        payload["stock"] = stock           # ["000001"]
    if big_category:
        payload["bigCategoryId"] = big_category
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    for row in j["data"]:
        row["pdf"] = "https://disc.static.szse.cn/download" + row.get("attachPath", "")
    return j

j = szse_annList(["2026-10-09", "2026-10-12"], stock=["000001"])
print(j["announceCount"], len(j["data"]))
```

curl_cffi 等价写法（若目标环境裸 curl 被 50x 拒绝时备用）：

```python
from curl_cffi import requests as cr
r = cr.post("https://www.szse.cn/api/disc/announcement/annList?random=0.3186550785026882",
            json={"seDate": ["2026-10-09", "2026-10-12"],
                  "channelCode": ["listedNotice_disc"], "pageSize": 50, "pageNum": 1},
            headers={"Content-Type": "application/json", "X-Request-Type": "ajax",
                     "Referer": "https://www.szse.cn/disclosure/listed/fixed/index.html"},
            impersonate="chrome", timeout=30)
```

信息来源：payload 骨架来自 [XG1997/crawler_SZSE](https://github.com/XG1997/crawler_SZSE/blob/main/crawler_szse.py)（其 `seDate` 传的就是二元 list）、[知乎-爬取深交所公告](https://zhuanlan.zhihu.com/p/21220561867)、[博客园-深交所财报爬虫](https://www.cnblogs.com/mysteriouspavilion/articles/15464430.html)；**字段合法性（seDate 数组、channelCode、pageSize 上限、keyword 无效）为本轮 2026-10-12 实测**。

---

## 2. 深交所监管信息公开 API（ShowReport/data）★ 本轮最大增量

深交所「监管信息公开」系列页面（`/disclosure/supervision/...`）不再用 annList，而是走通用报表接口。**JSON 数据路径为 `/api/report/ShowReport/data`**（旧文档里的 `/api/report/ShowReport?SHOWTYPE=JSON` 已一律 500；`/ShowReport` 仅作 Excel 导出，`SHOWTYPE=xlsx` 仍可用且不需要浏览器伪装）。

### 2.1 接口规格

- **URL**：`https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID={catalog}&PAGENO={n}`
- **方法**：GET
- **headers**：`X-Request-Type: ajax` + `Referer`（对应页面）+ 普通 UA。实测普通 `requests` 即 200。
- **返回**：JSON 数组含 1 个对象 `[{metadata, data, error}]`；`metadata.recordcount/pagecount/pagesize(=20)`；行数据在 `data`。
- **Excel 全量导出**：`https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID={catalog}&random=0.39339437497296137`（实测 234KB，akshare 同款用法）。

### 2.2 已验证的 CATALOGID（均从官方页面 `data-s-catalog-id` 属性提取并实测）

| CATALOGID | 页面 | 数据 | 字段（前缀为列名） |
|---|---|---|---|
| `1800_jgxxgk` | `/disclosure/supervision/measure/measure/index.html` 监管措施 | **4855 条 / 243 页** | `gkxx_gsdm` 公司代码、`gkxx_gsjc` 简称、`gkxx_gdrq` 公告日期、`gkxx_jgcs` 措施类型（监管函等）、`gkxx_sjdx` 涉及对象、`hjnr` 详情 PDF 链接（`encode-open='/UpFiles/zqjghj/xxx.pdf'`） |
| `1800_jgxxgk_cf` | `/disclosure/supervision/measure/pushish/index.html` 纪律处分 | **2894 条 / 145 页** | `xx_gsdm`、`jc_gsjc`、`xx_fwrq` 发文日期、`xx_cflb` 处分类别（公开谴责等）、`xx_bt` 标题、`ck` PDF 链接 |
| `main_wxhj` | `/disclosure/supervision/inquire/index.html` 问询函（主板） | **7389 条 / 370 页** | `gsdm`、`gsjc`、`fhrq` 发函日期、`hjlb` 函件类别（关注函/问询函等）、`ck` 函件 PDF、`hfck` 回复 PDF |
| `1760_zsn` | `/disclosure/supervision/check/index.html` | 有目录 | 未展开 |
| `ZJJGJG` | `/disclosure/supervision/supervise/index.html` | 有目录 | 未展开 |

- PDF 下载主机：`https://reportdocs.static.szse.cn` + `/UpFiles/zqjghj/xxx.pdf`（实测 200，application/pdf）。
- **过滤参数**（来自 metadata.conditions，实测生效）：监管措施用 `txtZqdm`（代码/简称）、`txtjgsy`（涉及对象）、`txtDate`/`txtEnd`（日期起止）；问询函用 `txtZqdm`、`selecthjlb`（函件类别）、`txtStart`/`txtEnd`。日期过滤实测：`txtDate=2026-01-01&txtEnd=2026-10-12` → 135 条。
- 创业板问询函 tab：页面 HTML 只内嵌 `main_wxhj`，猜测的 `cyb_wxhj` 等实测无效；创业板问询函可经 annList 公告流（`listedNotice_disc` + 标题含「问询函」）覆盖。

### 2.3 可直接运行的代码（实测 200）

```python
import re, requests

def szse_report_page(catalog, page=1, extra=None):
    """深交所监管信息公开（ShowReport/data）。extra: {'txtDate':'2026-01-01','txtEnd':'2026-10-12'} 等"""
    params = {"SHOWTYPE": "JSON", "CATALOGID": catalog, "PAGENO": str(page)}
    params.update(extra or {})
    r = requests.get("https://www.szse.cn/api/report/ShowReport/data", params=params,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                 "X-Request-Type": "ajax",
                 "Referer": "https://www.szse.cn/disclosure/supervision/measure/measure/index.html"},
        timeout=30)
    r.raise_for_status()
    return r.json()[0]   # {metadata, data, error}

top = szse_report_page("1800_jgxxgk", page=1)
print(top["metadata"]["recordcount"])          # 4855
for row in top["data"]:
    m = re.search(r"encode-open='([^']+)'", row["hjnr"])
    pdf = "https://reportdocs.static.szse.cn" + m.group(1) if m else None
    print(row["gkxx_gsdm"], row["gkxx_gsjc"], row["gkxx_gdrq"], row["gkxx_jgcs"], pdf)
```

信息来源：`/ShowReport/data` 路径与 `SHOWTYPE=JSON&CATALOGID=` 参数形态来自深交所官方前端 JS `res.szse.cn/modules/report/js/report_new.min.js`（本轮从线上抓取解析：`url: pathObj.report_path + "/ShowReport/data"`，导出用 `"/ShowReport" + SHOWTYPE=XLSX`）；各 CATALOGID 来自官方页面的 `data-s-catalog-id` 属性；akshare（`stock/stock_summary.py`）同族接口仅用 xlsx 导出路径（见 §6）。

---

## 3. 上交所（query.sse.com.cn）

### 3.1 公告列表：`security/stock/queryCompanyBulletinNew.do`（实测可用）

- **URL**：`https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do`
- **方法**：GET（官方页面用 jsonp；不加 `jsonCallBack` 直接返回纯 JSON 也 200）
- **必须 headers**：`Referer: https://www.sse.com.cn/disclosure/listedinfo/announcement/`（**缺省或错的 Referer 会返回「系统繁忙」**）+ 普通 UA
- **关键 query 参数**（官方页面 JS `search_listedCompanyInfo_2021.js` 中的 announceParam，实测验证）：

| 参数 | 说明 |
|---|---|
| `isPagination=true` | 必须 |
| `pageHelp.pageSize` / `pageHelp.pageNo` | 分页（页面用 25/页） |
| `pageHelp.cacheSize=1` | **必须带上**，缺失时 total=0（实测） |
| `pageHelp.beginPage=1` / `pageHelp.endPage=1` | 建议带 |
| `SECURITY_CODE` | 6 位代码过滤，实测 `600000`→1747 条、`600519`→1037 条 |
| `START_DATE` / `END_DATE` | `YYYY-MM-DD` |
| `securityType` | `0101`=主板，`120100,020100,020200,120200`=科创板，五码并列=全部 |
| `reportType2` | `LSGG` 历史公告 / `DQBG` 定期报告 |

- **返回**：`pageHelp.total`、行在 **`pageHelp.data`**（注意不是 `result`）：`TITLE、SECURITY_CODE、SECURITY_NAME、SSEDATE、BULLETIN_TYPE_DESC、URL`（相对站内 PDF 路径，拼 `https://www.sse.com.cn` + URL）。
- **关键词**：页面 JS 的 `TITLE`（关键字）参数实测**不过滤**（TITLE=税务 total=0），`keyWord`/`productId` 亦无效。**上交所公告关键词检索无稳定 API**，继续走巨潮。

```python
import requests, json

def sse_bulletins(code, start="2026-01-01", end="2026-10-12", page=1, size=25):
    params = {
        "isPagination": "true",
        "pageHelp.pageSize": size, "pageHelp.pageNo": page,
        "pageHelp.beginPage": 1, "pageHelp.endPage": 1, "pageHelp.cacheSize": 1,
        "SECURITY_CODE": code, "START_DATE": start, "END_DATE": end,
    }
    r = requests.get("https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do",
        params=params, timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                 "Referer": "https://www.sse.com.cn/disclosure/listedinfo/announcement/"})
    r.raise_for_status()
    j = r.json()
    rows = j["pageHelp"]["data"]
    for row in rows:
        row["pdf"] = "https://www.sse.com.cn" + row["URL"]
    return j["pageHelp"]["total"], rows

total, rows = sse_bulletins("600000")
print(total, rows[0]["TITLE"], rows[0]["pdf"])
```

### 3.2 监管措施/纪律处分/监管问询：`commonSoaQuery.do` + sqlId=BS_GGLL_NEW（实测可用，本轮核心）

上交所「诚信档案-监管信息公开」页面（`/disclosure/credibility/supervision/measures/` 等）的数据接口已从 `commonQuery.do` 演进到 **`commonSoaQuery.do`**（SOA 新端点；官方 JS `search_regulatoryInformation_2021.js` 中 `measuresUrl/inquiriesUrl: sseQueryURL + "commonSoaQuery.do?jsonCallBack=?"`）。

- **URL**：`https://query.sse.com.cn/commonSoaQuery.do`
- **方法**：GET
- **headers**：`Referer` 指向对应 sse.com.cn 页面（实测必须，否则 403/系统繁忙）+ 普通 UA。普通 `requests` 即可 200。
- **公共参数**：`sqlId=BS_GGLL_NEW&siteId=28&isPagination=true&pageHelp.pageSize=25&pageHelp.pageNo=N&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1&order=createTime|desc,saveTime|desc`
- **业务参数**（官方 JS 原文）：`type`（板块）、`stockcode`（证券代码或简称）、`extTeacher`（涉及对象）、`extWTFL`（监管类型）、`extGGDL`（监管问询类型）、`createTime`/`createTimeEnd`（起止日期）
- **返回**：jsonp 文本（剥壳后）`pageHelp.total` + 行在 `pageHelp.data`；每行是 CMS 文档对象，关键字段：`docTitle`、`docURL`（**完整 PDF 相对路径**，如 `www.sse.com.cn/disclosure/credibility/bonds/regulatory/inquiries/auto/c/10834367/files/xxx.pdf`）、`extTeacher`（涉及对象）、`extWTFL`（类型，如「债券监管措施」）、`stockcode`、`createTime`、`docId`、`docType`、`channelId`。

**channelId 频道表（来自官方 JS/页面 channelCode 属性，均实测）**：

| channelId | 内容 | 实测 total |
|---|---|---|
| `9894,9895,9896,12428,12093,12094,12095,12429,9890,9891,9892,12426,12090,12091,12092,12427` | 上市公司+债券监管措施（`/disclosure/credibility/supervision/measures/`） | 1006 |
| `10743,10744,10012` | 监管问询（`/disclosure/credibility/inquiries/`） | 2932 |
| `15099` 或 `15099,15100,15101,15102` | 发行上市审核监管措施（`/regulation/listing/measures/`） | 125 / 182 |
| `13141,20614` | 监管动态 | 未展开 |
| `10007,10008,10009,10010` + sqlId=`BS_KCB_GGLL_NEW` | 科创板监管措施（JS 中的 KCB 变体） | **实测 0**（码值疑似过期） |

注意：纪律处分没有独立页面/API，上交所已把「纪律处分决定书」并入上述监管措施频道（`extWTFL` 区分类型；纪律处分类文档 URL 落在 `/disclosure/credibility/...` 路径下）。

```python
import json, time, requests

def sse_soa(channel_id, page=1, size=25, extra=None):
    cb = f"jp{int(time.time()*1000)%99999}"
    params = {
        "jsonCallBack": cb,
        "isPagination": "true",
        "pageHelp.pageSize": size, "pageHelp.pageNo": page,
        "pageHelp.beginPage": 1, "pageHelp.endPage": 1, "pageHelp.cacheSize": 1,
        "sqlId": "BS_GGLL_NEW", "siteId": "28",
        "channelId": channel_id,
        "order": "createTime|desc,saveTime|desc",
    }
    params.update(extra or {})   # 如 {"stockcode":"600000","createTime":"2026-01-01","createTimeEnd":"2026-10-12"}
    r = requests.get("https://query.sse.com.cn/commonSoaQuery.do", params=params, timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                               "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                 "Referer": "https://www.sse.com.cn/disclosure/credibility/supervision/measures/"})
    t = r.text.strip()
    j = json.loads(t[t.find("(")+1:t.rfind(")")])
    rows = j["pageHelp"]["data"]
    for row in rows:
        url = row.get("docURL") or ""
        row["pdf"] = ("https://" + url) if url and not url.startswith("http") else url
    return j["pageHelp"]["total"], rows

MEASURES_CH = ("9894,9895,9896,12428,12093,12094,12095,12429,9890,9891,9892,"
               "12426,12090,12091,12092,12427")
total, rows = sse_soa(MEASURES_CH)
print(total, rows[0]["docTitle"], rows[0]["pdf"])
```

### 3.3 旧端点存亡对照（实测）

| 端点 | 状态 |
|---|---|
| `query.sse.com.cn/search/getESSearch.do?sqlId=BS_GGLL` | **404**（与上轮试探一致，确认死亡） |
| `query.sse.com.cn/commonSoQuery.do` | **404**（注意与 `commonSoaQuery` 一字之差） |
| `query.sse.com.cn/commonQuery.do?sqlId=BS_GGLL` | 200 但 **result 恒为空**（旧壳仍在、无数据；`FS_*`/`COMMON_SSE_*` 老式 sqlId 未逐一验证） |
| `query.sse.com.cn/search/getSearchResult.do`（`search=qwjs&searchword=...`，POST jsonp） | 官方 JS 在用的全文检索端点；本环境实测**超时无响应**（60s 0 字节），`search=xxpl` 变体返回系统繁忙。标注：**存在但不稳定，暂不可依赖** |

### 3.4 承诺履行/持股变动（同族 sqlId，出自官方 JS，未逐一实测）

- 承诺履行：`commonQuery.do?sqlId=SSE_XXPL_SSGSXX_SSGSCXJL_CNLYQK_L`（详情 CLOB：`SSE_XXPL_SSGSXX_SSGSCXJL_CNLYQK_CLOB_L`）
- 持股变动：`commonQuery.do?sqlId=COMMON_SSE_XXPL_CXJL_SSGSGFBDQK_S`（参数 `COMPANY_CODE/NAME/BEGIN_DATE/END_DATE/BOARDTYPE`）

---

## 4. 发行上市审核（IPO/再融资问询）

- 上交所审核中心历史域名 `listing.sse.com.cn`、`audit.sse.com.cn`：**DNS 均已不解析**（本轮实测 Could not resolve host）。现行入口并回主站：`/regulation/listing/measures/`（发行上市审核监管措施，见 §3.2 channelId=15099 段）；IPO 披露在 `/listing/disclosure/ipo/`（页面可见）。
- 深交所 `listing.szse.cn`：根路径 404，`szsePath.js` 中仍登记为创业板域名（`domainChinextHttps`），具体在用子路径需浏览器确认。
- **对税务案例库的实际建议**：年报/税务问询函本质上以「公告」形式发布——深交所走 `main_wxhj`（§2.2）+ annList 标题过滤，上交所走 §3.2 监管问询频道（channelId=10743,10744,10012）+ §3.1 公告列表，已足够覆盖，无需依赖审核中心。

---

## 5. TLS/反爬现象记录（对工程实现的意义）

1. Git Bash 自带的裸 `curl` 访问 `www.szse.cn/api/*` 一律收到 50x 维护页（响应头带 `s-cnection: close`）；同一台机器上 **python `requests` 与 `curl_cffi`（chrome 伪装）均正常**。若目标环境出现连不通，优先换 `curl_cffi impersonate="chrome"`，但**先检查 payload 格式**——本轮证据显示 500 的主因是 `seDate` 类型错误而非指纹拦截。
2. 上交所对 `Referer` 校验严格：`queryCompanyBulletinNew.do` / `commonSoaQuery.do` 缺 Referer 或 Referer 不对应会返回「系统繁忙」或空结果；`pageHelp.cacheSize=1` 缺失会导致 total=0。
3. 两所均无需 Cookie（实测先访问首页取 cookie 与直连无差别）。

---

## 6. akshare 及开源项目实现摘录

### 6.1 akshare（github.com/akfamily/akshare，主线持续维护）

akshare 对两所的封装集中在市场统计类，**未封装 annList 公告列表与监管措施**（公告类走巨潮/东财）。其深交所 `ShowReport` 用法（`akshare/stock/stock_summary.py`，本轮实测该 xlsx 路径仍可用）：

```python
# akshare/stock/stock_summary.py —— stock_szse_summary
url = "http://www.szse.cn/api/report/ShowReport"
params = {
    "SHOWTYPE": "xlsx",
    "CATALOGID": "1803_sczm",
    "TABKEY": "tab1",
    "txtQueryDate": "-".join([date[:4], date[4:6], date[6:]]),
    "random": "0.39339437497296137",
}
r = requests.get(url, params=params)
# pd.read_excel(BytesIO(r.content)) —— 直接吃 Excel
```

对本项目的启示：akshare 证明 `/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=...` 的**整表 Excel 导出通道**（普通 requests，无需伪装）至今有效——监管措施/纪律处分/问询函三个目录都可以 `CATALOGID=1800_jgxxgk` 等直接导出全量 Excel（实测 234KB），适合一次性初始化入库，增量再用 `/ShowReport/data` JSON 分页。

### 6.2 其他项目（按时效分级）

| 项目/文章 | 内容 | 时效判断 |
|---|---|---|
| [XG1997/crawler_SZSE](https://github.com/XG1997/crawler_SZSE/blob/main/crawler_szse.py) | annList POST 完整代码，`seDate` 二元 list、`channelCode:["fixed_disc"]`、X-Request-Type 头 | 形态与 2026-10 线上一致（本轮实测沿用其 payload 即 200） |
| [知乎：爬取深交所上市公司公告（附代码）](https://zhuanlan.zhihu.com/p/21220561867)（2025） | annList 参数与避坑 | 与实测一致 |
| [博客园：爬取深交所财报](https://www.cnblogs.com/mysteriouspavilion/articles/15464430.html)（2021） | seDate/bigCategoryId 码表 | 框架仍对，个别码值（bond/fund 渠道）已失效 |
| [腾讯云：REITs 版 annList](https://cloud.tencent.com/developer/article/2431333)（2024） | `reits.szse.cn/api/disc/announcement/annList` 同构接口 | 未实测 |
| [CSDN：交易所爬虫避坑](https://blog.csdn.net/bthbt/article/details/139608613)（2024） | 500/防爬经验 | 与 §5 现象吻合 |
| [CSDN：批量下载上交所报告](https://blog.csdn.net/u013781175/article/details/96566376)（2019） | 旧版接口 | **年代久远，接口已换**，仅参考思路 |
| 深交所官方前端 `res.szse.cn/modules/report/js/report_new.min.js`、上交所官方 `search_regulatoryInformation_2021.js` / `search_listedCompanyInfo_2021.js` | 本轮直接解析得出 §2/§3 全部参数 | **第一手、当前有效**（线上现行版本） |

---

## 7. 对税务案例库的落地建议

1. **公告增量**：沪深公告继续以巨潮（已有 329 件）为主库；两所官网接口作为**交叉校验/补漏通道**——深交所 annList（§1.2，注意 seDate 数组）、上交所 queryCompanyBulletinNew（§3.1，按 SECURITY_CODE 逐公司拉）。
2. **监管措施/纪律处分入库**（新增维度，建议立即做）：
   - 深交所：`ShowReport/data` 三个 CATALOGID 全量分页（约 1.5 万条），或 xlsx 一次性导出；
   - 上交所：`commonSoaQuery.do` 两个频道全量分页（约 4000 条），PDF 直链都在返回里。
   - 其中标题含「税务/税收/发票」的处分与处罚决定是税务案例的直连来源。
3. **问询函**：深交所 `main_wxhj`（关注函/问询函类别字段 `hjlb` 可过滤）+ 上交所问询频道（`extGGDL` 类型字段），按标题关键词「税务」二次筛选。
4. **失败重试准则**：深交所 500 → 先查 payload（seDate 数组、channelCode 必填）；上交所系统繁忙 → 查 Referer 与 cacheSize=1；仍失败再上 curl_cffi。

---

## 附：本轮实测原始证据摘要（2026-10-12）

- `POST annList` `{"seDate":["2026-10-09","2026-10-12"],"channelCode":["listedNotice_disc"],"pageSize":30,"pageNum":1}` → 200 `{"announceCount":1694,...}`
- `GET ShowReport/data?SHOWTYPE=JSON&CATALOGID=1800_jgxxgk&PAGENO=1` → 200，recordcount=4855；`1800_jgxxgk_cf` → 2894；`main_wxhj` → 7389
- `GET ShowReport?SHOWTYPE=xlsx&CATALOGID=1800_jgxxgk` → 200（234040 字节 Excel）
- `GET ShowReport?SHOWTYPE=JSON&CATALOGID=1945_day` → 500（旧 JSON 路径已死）
- `GET commonSoaQuery.do?sqlId=BS_GGLL_NEW&siteId=28&channelId=9894,...` → 200，total=1006；channelId=10743,10744,10012 → 2932；15099,15100,15101,15102 → 182
- `GET queryCompanyBulletinNew.do?...cacheSize=1&SECURITY_CODE=600000` → 200，total=1747，行在 pageHelp.data
- `GET getESSearch.do?sqlId=BS_GGLL` → 404；`commonSoQuery.do` → 404
- `reportdocs.static.szse.cn/UpFiles/zqjghj/*.pdf` → 200 application/pdf
