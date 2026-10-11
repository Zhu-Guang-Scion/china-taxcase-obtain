# 北京市 + 天津市 税务案例抓取来源文档

抓取日期：2026-10-10 ｜ 执行代理：京津子智能体 ｜ 通用库：`work/taxcase/taxcase_scrape.py`（未改动）

## 一、北京市（beijing.chinatax.gov.cn）

### 站点总体情况（重要踩坑）
- **瑞数（Ruishu）反爬全站部署**：`$_ts` JS 挑战。
  - HTTPS(443) 从本网络**直接黑洞超时**（curl/curl_cffi/playwright 全部 21s 超时），只有 HTTP(80) 有响应。
  - HTTP(80) 裸请求返回 **412 + JS 挑战页**；无头 playwright 也被识别（412 卡死）。
  - **唯一可行路径：有头 playwright chromium**（`headless=False` + `--disable-blink-features=AutomationControlled`），等瑞数 JS 自动重载后 DOM 才有内容（约 2-6s，须轮询 body 文本长度 >300 判定，不能只看 title）。
  - 瑞数 cookie 复用到 curl_cffi **极不稳定**（同 cookie 连续请求 412/200 交替，每次响应会滚动更新 cookie），不要指望 cookie 复用方案。
- 抓取实现：`work/taxcase/adapters/bj_all.py`（playwright 有头，part A/B）。
- 站内静态资源（js/css）不受瑞数保护，curl 直连可下（用于读 page.js 确认分页规则）。

### 1. 税案通报（质量最高，40 件）
- 入口：`http://beijing.chinatax.gov.cn/bjswj/c106920/ztzl_erji.shtml`
- CMS：TRS。文章 URL：`/bjswj/c106920/yyyymm/<32位hash>.shtml`
- 分页：`createPageHTML('page_div',3,1,'ztzl_erji','shtml',45)` → 第2页 `ztzl_erji_1.shtml`、第3页 `ztzl_erji_2.shtml`。
- **坑：`ztzl_erji_1.shtml` 服务端返回 412「资源访问异常」（真实缺页）**，第1、3页各 20 条可抓。栏目计数 45，实际可得 40（缺口 5 条集中在 2026-04 末；已用站内搜索 search5 与通知公告栏目回溯 8 页双重验证均无此 5 条，判断为已删除/计数陈旧，放弃）。
- 正文容器：`#xwzx_content_all`（页面有 `xwzx_content_all` 与 `xxgk_content_all` 两个重复容器，只取第一个，否则正文重复）；标题/日期可用 `<meta name="ArticleTitle">` 与「发布时间：」行。
- 噪音行：「发布时间：/来源：/[大][中][小]/打印」需清洗。

### 2. 行政处罚公示 — 行政执法信息公示平台（61 件，决定书级结构化数据）
- 页面：`http://beijing.chinatax.gov.cn/bjsat/xzzf/xzzf_sj/ybcxcfjg.html`（栏目名「税务行政一般程序处罚结果」，首页导航：信息公开 → 双公示专栏 → 行政处罚公告）
- 数据接口（页面 JS 里挖出，`allUrl=""` 为相对路径）：
  `POST /bjsat/xzzf/SwxzybcxcfjgServlet?page={n}&swjg_dm=11100000000`
  body：`ajmc=&xzxdrdm=&xzxdrmc=&cfjg=`（全空=浏览全部），10 条/页
- 响应 JSON：`{"count":"65-10","swxzybcxcfjgList":[...]}`，count 前 4 位为总数（65）。
- 字段：`XZCFJDSWH 决定书文号 / AJMC 案件名称 / CFLB 处罚类别 / WFSD 违法事实 / SWXZCFYJ 处罚依据 / CFJD 处罚决定 / NSRMC 相对人 / NSRSBH 识别号 / FDDBRXM 法定代表人 / CFJG 处罚机关 / CFRQ 处罚日期`。
- 接口同样在瑞数后：用 playwright 打开平台页后在 `page.evaluate(fetch(...))` 内调用（带浏览器 cookie），稳定 200。
- 平台仅保留**最近 65 条滚动窗口**（本次覆盖 2026-04-08 ~ 2026-09-24）；跨页有 4 条重复（相邻页数据滚动），按决定书文号去重后 61 件。

### 3. 重大税收违法失信主体公布栏（放弃）
- 入口：`http://beijing.chinatax.gov.cn/bjsat/office/jsp/zdsswfaj/wwquery.jsp`
- 纯查询表单（按纳税人名称/识别号/法人等），表单 `action/ListXxk.do` POST 返回 404「资源访问异常」，右侧结果 iframe `xxktime.jsp` 只是壳。**无批量列表接口，无法全量抓取**。

### 4. 行政复议（放弃）
- 入口：`http://beijing.chinatax.gov.cn/bjswj/c104466/cs_li.shtml`
- 栏目弹窗明示：「2020年5月22日以后的行政处罚公告信息请至行政执法信息公示平台查询，**本栏目暂停更新**」——近三年无内容，跳过。

### 北京产出
| 栏目 | 目录 | 件数 |
|---|---|---|
| 税案通报 | lawlibrary/专题/税务案例/北京市/税案通报 | 40 |
| 行政处罚公示 | lawlibrary/专题/税务案例/北京市/行政处罚公示 | 61 |

失败/跳过：税案通报第 2 页 5 条（服务端缺页）；失信公布与行政复议栏目不可批量（见上）。

---

## 二、天津市（tianjin.chinatax.gov.cn）

### 站点总体情况
- 自研 JSP/Struts CMS（`.action` 后缀），**无瑞数**，curl_cffi chrome124 指纹直连可用，`polite_get` 全程无拦截。
- 列表分页是 **POST 表单**：`POST /u_zlmViewMx.action`，data=`{lmdm,fjdm,page,d}`（GET 带参同样返回第一页）。
- 文章标题/日期在 `<meta name="ArticleTitle">` / `<meta name="PubDate">`；正文用通用 `extract_detail` 即可（但 h1 会取到站点名，须用 meta 覆盖）。
- 栏目代码见 `createWzdt.action` 网站地图：市局 fjdm=11200000000，lmdm：010003 通知公告 / 020001 税务新闻 / 010017 权利救济 等；区局按 `/11241000000/` 等数字路径。

### 1. 税案通报（自税务新闻栏目筛取，43 件）
- 入口：`https://tianjin.chinatax.gov.cn/u_zlmViewMx.action?fjdm=11200000000&lmdm=020001`（税务新闻，50 页，15 条/页）
- 天津**无独立"税案通报"栏目**，稽查查处通报混在税务新闻里；采用标题关键词过滤（稽查|查处|偷税|虚开|骗税|复议|处罚|失信…）后抓详情，2023-01-01 起共 51 个关键词命中、43 件落盘（8 件详情解析失败为纯附件公告或超短文）。
- 文章 URL 形如 `/11200000000/0200/020001/20260724085801651.shtml`。

### 2. 通知公告涉税案例（6 件）
- 入口：`https://tianjin.chinatax.gov.cn/u_zlmViewMx.action?fjdm=11200000000&lmdm=010003`（58 页）
- 同样关键词过滤；命中的主要是**稽查局《税务检查/事项通知书》公告送达**（附 zip 名单）与复议提示，共 6 件。12 个 parse 失败项均为纯附件 .xls 公告（收费目录清单类），非案例素材。

### 3. 行政处罚公示平台（放弃 — 验证码封锁）
- 入口：`https://tianjin.chinatax.gov.cn/xzzfgspt/init_xzzfxzcf.action?fjdm=11200000000&lmdm=0501`（行政执法信息公示平台 → 税务行政处罚）
- 数据 iframe：`swxzcfcx_init.action` → 查询表单 POST `swxzcfcx_cxinfo.action`，**强制图片验证码**（`servlet/code`），空码/带会话 POST 一律 503。无法批量抓取，放弃。
- 菜单里另有：税务行政许可 `init_xzzfxzxk.action`、欠税公告 `init_xzzfxzzs.action`（同平台，未抓）。

### 4. 重大税收违法失信公布（放弃 — 无批量接口）
- 入口：`https://tianjin.chinatax.gov.cn/wzcx/cx_zdwfaj.action?szsf=11200000000`
- 按名称/识别号等条件查询（名称须>4字），默认「没有检索到您要查询的信息」，无浏览全量入口。

### 5. 权利救济（跳过）
- 仅《行政复议指南》《权利救济途径》两篇静态指南，无决定书。

### 天津产出
| 栏目 | 目录 | 件数 |
|---|---|---|
| 税案通报 | lawlibrary/专题/税务案例/天津市/税案通报 | 43 |
| 通知公告涉税案例 | lawlibrary/专题/税务案例/天津市/通知公告涉税案例 | 6 |

实现：`work/taxcase/adapters/tj_news.py`（POST 翻页 + 关键词过滤 + meta 覆盖标题日期 + 详情日期二次校验）。

---

## 三、两市踩坑摘要
1. 北京瑞数：HTTPS 黑洞 + HTTP 412，无头被识别，必须有头 playwright 轮询 body 判定加载完成；cookie 复用不可靠。
2. 北京处罚平台接口藏在页面 JS（`allUrl` 为空串的相对路径 servlet），page.evaluate 内 fetch 复用已过挑战的会话。
3. 北京 TRS 列表第 2 页服务端真缺（412 资源访问异常），计数 45 实得 40，已双路验证。
4. 北京文章页双容器（xwzx/xxgk）导致正文重复，只取 `#xwzx_content_all`。
5. 天津列表分页为 POST 表单（u_zlmViewMx.action + page 字段），GET 不翻页。
6. 天津标题/日期靠 meta ArticleTitle/PubDate，h1 是站点名。
7. 天津处罚平台强制验证码（503），失信查询按名检索无全量——两栏目放弃并已记录。
8. 相对路径陷阱：adapter 里 LAWLIB 曾多写一层 `..` 导致文件落到 `E:\ai_coding_xiangmu\lawlibrary`，已修复搬迁；列表日期缺失时需在详情侧二次做 date_from 校验，防止 2022 文件混入（已修复+清理）。

## 四、总量
北京市 101 件 + 天津市 49 件 = **150 件 md**。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
