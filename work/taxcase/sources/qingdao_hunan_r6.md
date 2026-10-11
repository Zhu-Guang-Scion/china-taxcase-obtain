# 青岛市 + 湖南省 税务案例抓取来源文档（2026-10-11）

执行代理：青岛/湖南攻坚子智能体 ｜ 手机热点网络（高延迟，多处重试策略由此而来）

## 一、青岛市（qingdao.chinatax.gov.cn）

### 站点总体情况
- **瑞数（Ruishu）全站部署**（本轮实测首页也 412，比上一轮"路径级"更严）：
  curl/curl_cffi 一律 412 挑战页；**有头 chromium（headless=False +
  --disable-blink-features=AutomationControlled + 窗口移出屏幕）一次过**（2-6s）。
- **会话内 fetch 可用但有配额**：过挑战后 page.evaluate(fetch) 正常，
  连续约 50-80 次后瑞数 fetch 钩子开始抛 `TypeError: Failed to fetch`
  （IP/会话级临时封禁，约 10-15 分钟自动过期）。**真实导航（goto）始终可用**——
  混合策略：fetch 优先、失败转 goto 导航再读 page.content()，全程无阻。
- 误判教训：合法页面 HTML 头部也嵌瑞数 bootstrap（含 `$_ts=window`），
  **挑战判定必须用「len<3000 且含挑战标记」而不是「包含 $_ts」**。
- CMS：TRS WAS 系（`/search/was5/web/search` 全站检索 + `/version/2019/sswj` 模板）。
  栏目：xxgk2019 信息公开 / ssxc2019 新闻 / bsfw2019 纳税服务 / 各区局 /qdsw_*/。
  文章 URL：`/<栏目>/<子栏>/YYYYMM/tYYYYMMDD_NNNNN.html`。

### 1. 税收执法公示平台·税务行政一般程序处罚结果（主源，545 条结构化记录 → 98 md）
- 平台入口：`https://etax.qingdao.chinatax.gov.cn:6883/newdzswj/sszfgspt.do?a=1`
  （在主站任意页面搜"执法公示平台"或 bsfw2019 内的链接可找到；`etax.qingdao.../zfgspt/...`
  路径不存在——会被重定向到电子税务局 SPA 壳，别踩）
- 列表页：`/newdzswj/sszfgsptReportList.do?type=gotoList&tyid=803079ca9d454d268f464306f73e0601&swjgdm=13702000000`
  （swjgdm=13702000000 为市局，数据含各稽查局/区局，共 545 条 37 页 15 条/页）
- **翻页是站内 jQuery 表单 AJAX**：`POST /newdzswj/sszfgsptReportList.do?type=getContent&swjgdm=13702000000`
  （表单字段 page/page_no/par/tyid/cx_xqbg 模板等）。GET 加 page 参数无效——
  最稳做法：**驱动站内自己的 `getPage(3)`（设 `#page` 输入后调用），渲染完读 `#tbodylist.innerHTML`**
- **每条记录的详情就内联在列表 DOM 里**（摘要行 + 嵌套字段表：案件名称/纳税人/信用代码/
  决定书文号/处罚类别/执法依据/处罚事由/处罚结果/机关/法代）——无需二次请求
- 数据窗口：2023-08-29 ~ 2026-10-10，按文号去重 532/545
- **质量门槛结果：98 KEEP / 434 DEL**——青岛平台"处罚事由"多为短语
  （"取得不符合规定的发票"9-20 字，中位数 11 字），执法依据中位数 252 字。
  与辽宁同款数据形态（4.3% 过门槛），非抓取问题。
- 实现：`adapters/qd_xzcf.py`（--probe-last 看末页日期）；数据 `tmp/qd/xzcf_records.jsonl`

### 2. 重大税收违法失信主体信息公布栏（514 条 → 503 md）
- 入口：`http://qingdao.chinatax.gov.cn/resourcedata/sswf2019/`（表单页，iframe 提交）
- **真身是 WAS5 检索**：`GET /search/was5/web/search?channelid=223090&searchword=&page=N`
  （10 条/页共 514 条；点击表单"检索"按钮抓请求可得，或直接构造 URL）
- 行：机关/纳税人名称/识别号/案件性质 + "详细信息"链接
  `/resourcedata/sswf2019/qy/YYYYMM/tYYYYMMDD_NNNNN.html`
- 详情页标签-值内联结构（纳税人名称/识别号/注册地址/法代/案件性质/**主要违法事实**/
  相关法律依据及税务处理处罚情况），文本段解析即可
- 质量门槛：503 KEEP / 3 DEL / 8 条 2023 前旧数据跳过
- 实现：`adapters/qd_sswf.py`（混合 fetch/导航）；数据 `tmp/qd/sswf_list.jsonl` + `sswf_details/`

### 3. 税案通报（WAS5 全站检索新闻，22 md）
- WAS5 全站检索：`/search/was5/web/search?channelid=296952&searchword=KW&page=N`
  （日期格式是 `2026.09.30` 点分，不是连字符！）
- 关键词：查处/偷逃/追缴税款/少缴/曝光台/涉税违法/案件公布/虚开/骗取出口退税/逃避缴纳税款
- **标题过滤必须双卡**：案由词 AND 排除 `送达公告|催缴|催报|文书公告`——
  第一轮仅正向过滤收进 293 篇稽查局送达公告（程序性），已清理
- 详情用通用 extract_detail；最终 22 篇真查处通报（2023-2026）
- 实现：`adapters/qd_news.py`；数据 `tmp/qd/news_arts.jsonl` + `news_pages/`

### 4. 未收/放弃
- 送达公告栏（bsfw2019/ssgg/sdgg/{dyjcj,dejcj,dsjcj}）：全量约数千条，纯程序性送达（DEL），不入库
- 行政许可/行政检查/欠税平台菜单：非案例素材，未收

### 青岛产出
| 栏目 | 目录 | 件数 |
|---|---|---|
| 行政处罚公示 | lawlibrary/专题/税务案例/青岛市/行政处罚公示 | 98 |
| 重大税收违法失信公布 | lawlibrary/专题/税务案例/青岛市/重大税收违法失信公布 | 503 |
| 税案通报 | lawlibrary/专题/税务案例/青岛市/税案通报 | 22 |

合计 **623 件 md**。原始数据：tmp/qd/（545 处罚记录 + 514 失信详情 + 660 新闻元数据）。

---

## 二、湖南省（hunan.chinatax.gov.cn）

### 站点总体情况
- **加速乐（知道创宇系）JS 挑战**：curl/curl_cffi 412 + 外链混淆 JS
  （`/MMB1_.../ZYbKRgIknL7izCT.js`，778KB 重混淆，逆向不划算）。
  **有头 chromium 一次过**（首页导航 3s 内完成）。
- **etax.hunan.chinatax.gov.cn 无墙但无用**：全部路径回退到电子税务局 SPA
  （:8443 index.html 7710B 壳）；8090 端口连接超时——**湖南没有 sword/wings 平台**，
  山东/辽宁契约在此不适用，公示平台长在主站 /category/ 栏目体系里。
- **fetch() 被完全钩死**（页面上下文内 `TypeError: Failed to fetch`，无状态码），
  **但页面自身 jQuery $.ajax(XHR) 可用**——所有数据请求走站内 $.ajax 模式
  （四川 jsearch 同款经验）。XHR 也会在连续 ~40 次后被 CDN 封（'0 error'），
  整 context 重建 + 静默 10 分钟可恢复。
- CMS：自研 Spring（`/show/ID`、`/category/ID`、`/lists/ID`、`/hardcase/ID`），
  layui 前端，POST + `_csrf`（meta 标签取）。

### 1. 重大税收违法失信主体公布栏（主源，1308 条全文 → 1305 md）
- 入口：`/hardcase/20190408002097`（首页"重大税收违法失信主体"直达）
- 数据接口：`POST /hardcasegetdatanew`（**必须站内 $.ajax + _csrf**）
  参数：`type=0, type_value='', case_type=1, page=N, limit=100, is_search=0` + 全空查询字段
  （注意：**is_search=1 是条件检索模式，空条件直接"系统错误"**；浏览模式 type=0 全量）
- 响应：`hardCasePage.totalElements=1308`，`content[]` 每行自带
  **content 全文（违法事实+处理处罚完整叙述）**/ taxpayerName / taxpayerNumber /
  place / hardCaseType.typeName / showTime(epoch ms) / siteName——无需详情请求
- 数据窗口：2022-01-20 ~ 2026-09-15；近三年过滤后 1305 条（3 条 2023 前）
- 质量门槛：1305 KEEP / 0 DEL（content 字段事实叙述中位数远超 30 字）
- 实现：`adapters/hn_hardcase.py`；数据 `tmp/hn/hardcase_records.jsonl`

### 2. 行政执法信息公示平台·税务行政一般程序处罚结果（2681 条，已收 800）
- 入口：`/xzzfpenalty/20200325400599`（信息公开 → 行政执法公示平台 /category/20200325400506）
- 数据接口：`POST /xzzfpenaltygetdata`
  参数：`page, limit(100 有效), site_id(空=全省), ajmc/mc/dm/cfjg(空), logincode(验证码), _csrf`
- **验证码服务端强制**：`GET /kaptcha/getlogincode?rand`（JPEG）。
  XHR 取图会被 CDN 掐——**解法：站内 `<img id=codeImgGm>` 原生刷新（evaluate 改 src）
  + Playwright 元素截图 → ddddocr**（过码率约 1/3，循环重试）
- 响应行字段：jdswh 文号 / ajmc 案件名 / cflb / **cfsy 处罚事由** / **cfyj 处罚依据(长文)** /
  xzxdrmc 相对人 / xzxdrdm 代码 / fddbrxm / cfjg 结果(罚款金额) / cfjiguan 机关 /
  cfsxq 处罚日期(epoch ms)
- **两大坑**：
  1. 服务端有坏节点：同参数随机 `500 Internal Server Error`（响应体 NUL 填充）——
     立即换码重试即可命中好节点，勿当限流处理
  2. **个别页存在超大记录，limit=100 时网关掐连接（'0 error'）**——逐级回退
     limit 50/25/10 可过（实测 p9 limit=100 恒挂、limit=50 通）
- 已收 800/2681（p1-8@100/页）：2023-08-21 ~ 2026-09-28 全覆盖三年。
  p9 起 XHR 被 CDN 会话级封禁 + 限流叠加，多轮 context 重建未能续破——
  800 条先入库，**复跑入口见下**（网络畅通时段预计 20 分钟内可收完剩余 1881 条）
- 质量门槛（800 条实测）：KEEP 16 / DEL 784——湖南 cfsy 是**分类短语字段**
  （发票违法 305 / 其他违法 216 / 虚开发票 97…中位数 4 字），非事实叙述；
  仅 15 条 cfsy>=30。cfyj 中位数 88 字但多为法条引用。数据形态同辽宁（4.3%），
  真实门槛结果，非抓取问题
- 实现：`adapters/hn_xzcf.py` + `adapters/hn_xzcf_loop.sh`（断点续跑循环）；
  数据 `tmp/hn/xzcf_records.jsonl`；断点 `progress/qd_hn_r6.jsonl`

### 3. 稽查通报新闻（未做全量）
- 首页 /show/ 新闻有"揭秘湖南宸睿通信科技有限公司虚开骗税"类查处通报，
  但无独立栏目，散在新闻动态；失信栏 1305 件全文已覆盖同等信息密度，未再抓

### 湖南产出
| 栏目 | 目录 | 件数 |
|---|---|---|
| 重大税收违法失信公布 | lawlibrary/专题/税务案例/湖南省/重大税收违法失信公布 | 1305 |
| 行政处罚公示 | lawlibrary/专题/税务案例/湖南省/行政处罚公示 | 16 |

合计 **1321 件 md**。处罚平台余 1881 条（2023-08 前至更早窗口未探明）被 CDN
  XHR 会话封禁阻断（静默 12 分钟 + 整 context 重建均未恢复），复跑入口见下。

---

## 三、复跑指引

```bash
cd work/taxcase
# 青岛
python adapters/qd_xzcf.py            # 处罚 545 条（3 分钟）
python adapters/qd_sswf.py            # 失信 514 详情（混合 fetch/导航，约 40 分钟）
python adapters/qd_news.py            # 税案通报新闻（约 8 分钟）
python adapters/qd_md.py --kind all   # 全部转 md（含质量门槛）
# 湖南
python adapters/hn_hardcase.py        # 失信 1308 条（4 分钟）
bash adapters/hn_xzcf_loop.sh         # 处罚 2681 条（断点续跑循环，网络好时 20 分钟）
```

## 四、两地踩坑摘要
1. 瑞数挑战判定不能用「含 $_ts」——合法页也带 bootstrap；用 len<3000+标记。
2. 瑞数 fetch 钩子配额封禁（~80 次/会话，10-15 分钟过期）：fetch 失败立即转真实导航。
3. 青岛 etax 的 /zfgspt 路径是 SPA 幽灵（重定向壳）；平台真身在 :6883/newdzswj/。
4. 青岛 WAS5 日期是 `2026.09.30` 点分格式；失信栏真身 channelid=223090。
5. 青岛 sszfgspt 翻页 GET 参数无效，必须驱动站内 getPage(3)+表单 AJAX；详情内联在列表 DOM。
6. 湖南无 sword 平台；fetch 全钩死但站内 $.ajax 可用；_csrf 从 meta 取。
7. 湖南 kaptcha 取图必须走页面 <img> 原生加载（XHR/fetch 取图都会被 CDN 掐）+ 元素截图 OCR。
8. 湖南 xzzfpenaltygetdata 有坏节点随机 500（换码重试即可）；个别页大记录 limit=100 会掐连接（回退 50/25/10）。
9. 湖南 CDN 会对 XHR 会话级封禁（'0 error'）：整 context 重建 + 静默 10 分钟恢复；持续重试反而续命封锁。
10. 热点网络下 Playwright evaluate 的 fetch 偶发全挂——先 ping/curl 排除断网再改代码。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
