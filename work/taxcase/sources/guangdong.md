# 广东省 + 深圳市 税务案例抓取来源文档

抓取日期：2026-10-10 ｜ 范围：2023-01-01 之后 ｜ adapter：`work/taxcase/adapters/gd_cases.py`、`sz_cases.py`

## 一、广东省税务局（guangdong.chinatax.gov.cn）

### 1. 实际使用的栏目/接口

| 栏目 | 入口 URL | 结构/接口 | 抓取量 |
|---|---|---|---|
| 以案释法（法治公平与税同行专题，省局税案曝光专栏） | https://guangdong.chinatax.gov.cn/gdsw/fzgpystx_yasf/list.shtml | TRS + AJAX 分页接口 `/gdtaxejs/common/search/{channelId}?_pageSize=20&page={n}&_isAgg=true&_isJson=true&_template=index`（channelId=`d46d7c83a9454be597ad514b7d90a499`，全站 common_list 页同机制） | 28 件（全量） |
| 税案通报/曝光（散落在 媒体视点 mtsd / 税务新闻 swxw / 基层动态 jcdt / 市县子站） | 站内搜索 POST https://guangdong.chinatax.gov.cn/search5/search/s | TRS search5（开普云），表单参数 siteCode=bm29190001&searchWord=…&pageNum=…，返回 searchResultAll.searchTotal[]（含绝对 url/pubDate/title） | 关键词枚举依法查处/骗取出口退税/虚开增值税/偷税案件/曝光 涉税/重大税收违法失信/税务行政处罚决定 |
| 合计 |  |  | **去重 48 个 URL，成功 42 md，6 件为纯图片页（无文本层）跳过** |

同构站点提示：GD 全站 common_list.shtml 的翻页不在静态页上，靠 `/default/xhtml/static/libs/list.js` 发上述 JSON 接口；**`channelId` 藏在列表页内联 JS**（`channelId = "…"`），拿到后即可翻页。列表接口返回的 `url` 是 `../../gdsw/...` 相对路径，**基准是站点根**（不是接口路径！按接口路径 urljoin 会拼成 /gdtaxejs/gdsw/... 全部 404，踩过）。

### 2. 探明但无法抓取的栏目（均为省局官方入口）

| 栏目 | 入口 URL | 状况 |
|---|---|---|
| 重大税收违法失信主体信息公布栏 | https://guangdong.chinatax.gov.cn/siteapps/webpage/gdtax/zdsswfaj/index.jsp | 2019 版 JSP 应用。POST query.jsp 带 quarter/yf/taxNature/channelId 各参数均返回"此类信息查询暂无记录"；按名称检索走 `/wcm/extends/web/jsp/portal/zdsswfaj/content_service1.jsp` 但页面检索按钮带图片验证码。**实际已废弃（空壳）** |
| 信用信息双公示-行政处罚 | https://guangdong.chinatax.gov.cn/siteapps/webpage/gdtax/sgs_new/xzcf_list.jsp?sitecode=gdtax&webcode=gdsw | 服务端渲染分页，**无论 dfbm 传省局(440000/440000JG)还是市局(440100/442000JG 等，区县 id 在页面 id 属性里)一律"共0条"**，废弃 |
| 行政执法公示平台-行政处罚（省局+21市子平台） | https://guangdong.chinatax.gov.cn/gdzfgs/zfpt_index.shtml → /gdzfgs/swxzcf/zfpt_iframe_list.shtml（iframe 指向 sgs_new/zfgspt_xzcf_list.jsp） | 同上，0 条 |
| 县区基层政务公开目录（如封开） | https://guangdong.chinatax.gov.cn/gdswzz/zqfksw_jczwgkbzml/zone_scroll.shtml | 目录页表格里的"行政处罚决定和结果公示"链接全部指回上述空壳 JSP |

结论：**广东省局把处罚/失信明细公示迁出了自建网站**（实际在"信用广东"/广东政务服务网），省站可抓的高价值内容就是以案释法专栏 + 稽查新闻通报。

## 二、深圳市税务局（shenzhen.chinatax.gov.cn）

### 1. 实际使用的接口

| 栏目 | 入口 | 结构/接口 | 抓取量 |
|---|---|---|---|
| 税案通报/曝光/处罚送达公告（覆盖市局主站 + 福田 ftqswj、宝安 baqswj、龙岗 lgqswj、龙华 longhqswj、坪山 psqswj、南山 nsqswj、前海 qhswj 等区局子站 + 法定公开 zdgkml 频道） | 站内搜索页 https://shenzhen.chinatax.gov.cn/sztax/search/html/searchResult.html | **搜索后端在外部 SaaS：POST https://zs.kaipuyun.cn/search5/search/s**（siteCode=bm29360001；ctx 在 /sztax/search/static/common/config.js 里定义），返回结构与广东自建 search5 相同 | 关键词枚举同广东；命中后回源 shenzhen.chinatax.gov.cn 抓详情 |
| 合计 |  |  | **去重 144 个 URL，日期过滤后 107；成功抓取 106，落盘 83 个唯一 md**（23 件为同一通报在多个区局子站跨发，文件名同名去重各留一份）；失败 1 件（页面已 404 下架：第三稽查局失信主体公告送达 /sztax/hlwfbgjc/202609/d80023e6...shtml） |

深圳 TRS 静态分页规律（备用）：列表第 1 页 `common_list.shtml`，第 N 页 `common_list_N.shtml`（`createPageHTML('page_div',53,1,'common_list','shtml',781)`，如税务新闻 53 页 781 篇）。详情 URL 形如 `/sztax/xwdt/swxw/202609/<32位hash>.shtml`，**无 content_ 前缀**——通用 `parse_list_items` 的正则匹配不到，须用 title 属性取标题、`<span class="time">`取日期。

### 2. 探明但无法抓取的栏目

| 栏目 | 入口 URL | 状况 |
|---|---|---|
| 违法案件公告（稽查文书公告送达，量大，索引内 4453+ 条） | 查询页 https://shenzhen.chinatax.gov.cn/sztax/nsfw/gzcx/ywggcx/wfajgg_cx.shtml | 已迁入 `/sztaxapp/` 应用：查询接口 POST /sztaxapp/wfajgg/findCx **强制图片验证码**；详情 `/sztaxapp/wfajgg/show/{token}` token 即焚（"链接已经失效"）；搜索引擎索引里的旧静态 URL（/sztax/nsfw/gzcx/wfajgg/YYYYMM/hash.shtml）**全部 404**。adapter 已按 URL 模式排除，避免无效请求 |
| 重大税收违法失信主体查询 | https://shenzhen.chinatax.gov.cn/mhsofpro/otherproject/wgtg/list.jsp | JSP + ValidCodeServlet 验证码 + token 门禁，无法合规批量抓取 |

注意：深圳"关于送达《税务行政处罚决定书》的公告"（区局 tzgg 栏）是可访问的 TRS 页，已入库（归类"行政处罚公示"）；与上述 wfajgg 稽查送达栏不是同一系统。

### 3. 行政执法公示平台（szxz 子域）

入口 https://szxz.shenzhen.chinatax.gov.cn/xzzfgs/ → JS 跳转 `/xzzfgs/sword?ctrl=XzzfgsptHomeCtrl_index`，wings 框架 SPA（SwordAdapter.js），导航参数 yjcd/ejcd/mk/sxq，内容 iframe + 会话态。未投入抓取（同为处罚结果查询类，量控考虑放弃，记录备查）。

## 三、踩坑记录（两站通用 + 各自）

1. **TLS 指纹**：guangdong/shenzhen 两站对 python-requests 均可能返回壳页/404，全程 curl_cffi(chrome124)（`t.polite_get` 内置）；深圳部分详情页直连偶发 404，带 Referer 正常。
2. **广东编码**：UTF-8 为主，polite_get 的 meta 探测未触发问题。
3. **search5 返回标题带 `<span>` 高亮标签**，入库前必须剥掉。
4. **search5 全文匹配噪音大**（法规、采购、人事都命中"行政处罚"），必须再用标题正则（查处|曝光|骗取|虚开|偷税|失信|违法|处罚|税案…）收紧 + 排除 URL（/zcwj/政策文件 /zcjd/解读 /wfajgg/即焚链接）。
5. 广东 gdtaxejs 列表接口 URL 相对路径基准是站点根（`../../` → `/`），不是接口 URL。
6. 广东/深圳的失信公布、处罚结果查询类 JSP 全部带验证码或已废弃，别死磕；高价值替代是"以案释法"专栏 + 稽查局通报新闻。
7. 深圳搜索后端在 zs.kaipuyun.cn（开普云 SaaS）而非本域，跨域 POST 需带 Origin/Referer；广东 search5 在本域 /search5/。
8. 6 件广东以案释法条目为纯图片新闻（无文本层），extract_detail 得不到正文，已在 progress jsonl 记 err=fetch/parse；属正常跳过。
9. 深圳列表页无静态翻页链接（page.js 动态生成），但其分页 URL 规律简单（list_N.shtml），静态抓取也可行。

## 四、产出统计

- 广东省：`lawlibrary/专题/税务案例/广东省/税案通报/` **42 件 md**（以案释法 2026 批次 22 件 + 2025-2026 稽查通报/媒体深度案件报道 20 件），6 件纯图片页跳过。
- 深圳市：`lawlibrary/专题/税务案例/深圳市/` **83 件 md**（税案通报 80 + 行政处罚公示 3；年份分布 2023:20 / 2024:11 / 2025:64 / 2026:11）。「重大税收违法失信公布」唯一命中件页面已 404；「行政复议」在两市索引中均为法规类文档、无决定书原文，两类目录未产生文件（如实记录）。
- 合计 **125 件 md**；失败/跳过明细见 `work/taxcase/progress/gd_cases.jsonl`、`sz_cases.jsonl`（URL 去重 + ok 标记，可增量重跑）。
- 全量 md 已做后处理：剥离空表格头（`| | | |`）、浏览/打印/分享噪音行。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
