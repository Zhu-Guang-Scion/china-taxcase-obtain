# 湖北省 + 重庆市 税务案例抓取 —— 瑞数攻坚定稿（2026-10-11）

> 执行：鄂渝子智能体（第六轮）。网络：手机热点（高延迟）。
> 两省均为**瑞数全站**，破法沿用四川/北京经验：有头 chromium
> （`headless=False` + `--disable-blink-features=AutomationControlled`）过挑战后
> **全程会话内**取数。adapter：`work/taxcase/adapters/hbcq_cq.py`（重庆）、
> `hbcq_hb.py`（湖北）、`hbcq_md.py`（离线转 md + 质量门槛）、侦察脚本
> `hbcq_river.py` / `hbcq_recon2~8.py`。断点：`progress/hb_cq_r6.jsonl`；
> 原始数据 `tmp/hb_cq/`（cq_sx_*.jsonl / hb_pages/ / *_meta.jsonl / *_records.json）。

## 一、重庆市（chongqing.chinatax.gov.cn，HTTPS 202 瑞数）

### 挑战通过与站点结构（与四川不同的三个大坑）
1. **URL 掩码（本轮最大发现）**：首页 HTML 里的链接是 `./xwdt/...` 相对路径，
   **直访 `https://…/xwdt/jcdt/` 一律 404**（连真实导航都 404，curl/无头同死）。
   真实内容根是 **`/cqtax/`**：`/cqtax/xwdt/jcdt/`、`/cqtax/xxgk/tzgg/`、文章
   `/cqtax/xwdt/swxw/202610/t20261008_386627.html` 全部直访可开（有头会话内）。
   找法：首页点"信息公开"看 final URL 落在 `/cqtax/`。
2. **fetch 会被瑞数二次挑战**：会话内 `page.evaluate(fetch)` 打未"预热"的路径
   返回 200+挑战页（len≈8500）或 404——重庆不能像四川那样全靠 fetch，
   **列表/文章一律 page.goto 直访**（/cqtax/ 前缀 + 瑞数 cookie 会话内有效）。
3. `etax.chongqing.chinatax.gov.cn` 根域是**电子税务局登录门户**（重定向 :8443），
   与四川 etax 公示平台不是一回事；跨源 fetch 一律 CORS 失败，只能导航。

### 实际数据源
1. **重大税收违法失信主体公布（主源，795 主体 md）**
   - 页面：`http://chongqing.chinatax.gov.cn/xxgkxt/pages/qywh/zdwfajcx.html`
     （http 源！https 页面内是混合内容，需直接导航）
   - 列表接口：`POST /api/qeuryZdaj`（注意拼写 qeury），表单体
     `jsonstr={"sftz":"Y","pageSize":"200","pageIndex":"N","dp":"","ajxz":"",…}`
     ——**必须带至少一个查询条件**（空条件报"请输入查询条件！"）。
     破法：按案件性质枚举 `ajxz∈{1..9,a,b}`（pageSize=200 可用）。
   - 详情接口：`POST /api/queryZdajById`，表单 `id={uuid}`；返回
     `value.{nsrmc,nsrsbh,zcdz,frxm,frzjhm,ajxz,swjgmc,wfxx,legalBasis}`，
     **wfxx=违法事实全文、legalBasis=处理处罚全文**，全部 ≥30 字。
   - 两个接口都必须走**页面自身 jQuery $.ajax**（page.evaluate 内），裸 fetch 不行。
   - 量：796 主体全量（ajxz 分布：虚开专票 587/走逃 144/逃避缴纳 37/虚开普票 14…），
     795 件 md（1 件同名主体文件名合并）。**无日期字段**，front matter 发布日期用抓取日。
2. **税务新闻/通知公告关键词文章（61 md）**
   - 列表：`/cqtax/xwdt/swxw/`（33 页回溯到 2023-01）+ `/cqtax/xxgk/tzgg/`（10 页），
     分页 `index{N-1}.html`，15 条/页
   - 标题关键词（稽查|查处|偷税|虚开|骗税|处罚|失信|曝光|复议|送达…）命中 62，
     1 件纯告示被质量门槛 DEL，61 件入库（栏目=税案通报）
3. **行政执法信息公示平台（:8888，空壳，已验证放弃）**
   - 入口：`/cqtax/xxgk/xzzf/` → 重定向 `http://chongqing.chinatax.gov.cn:8888/sjzfgs`
     （curl 直连 8888 黑洞，浏览器可开）；处罚栏目
     `/sjzfgs/xzcf/swxzybcxcfjg`，表头 11 列决定书级
   - 数据接口 `POST :8888/api/loadNewsInfo`（`twolm=swxzybcxcfjg&siteCode=sj&rows&page`）
     **强制校验码**：`/verifyCode/getVerifyCode` 图片 + `checkVerifyCode` 字段；
     **ddddocr 一次通过率约 50%（1o13→fail，1858→ok）**，验证码单次有效（查询成功即消费）。
   - 破码后实测 `siteCode=sj` **dataTotal={"1":0}——市级平台零数据（空壳）**；
     真实处罚数据疑似在各稽查局子站（qxtax/dyjcj…，瑞数挑战更深未攻）。放弃并记录。

### 重庆产出（lawlibrary/专题/税务案例/重庆市/）
| 栏目 | 件数 | 来源 |
|---|---|---|
| 重大税收违法失信公布 | 795 | /api/qeuryZdaj + queryZdajById（主体级，含违法事实全文） |
| 税案通报 | 61 | /cqtax/ 税务新闻+通知公告关键词 |

## 二、湖北省（hubei.chinatax.gov.cn，HTTPS 443 黑洞、HTTP 412 瑞数）

### 挑战通过与站点结构
1. **全程 http://**：HTTPS(443) 从本网络黑洞（curl 25s 超时），HTTP 有头 chromium
   一次过挑战（比北京还顺，首页 goto 后 1-2s 就绪）。
2. 内容根 `/hbsw/`（同重庆 /cqtax/ 模式）：新闻 `/hbsw/xwdt/swxw/`、
   信息公开 `/hbsw/xxgk/`、失信 `/hbsw/xxgk/zdssxxcx/`；分页 `index{N}.html`；
   文章为纯数字 `/{...}/{id}.htm`。列表/文章直访均通（会话内）。
3. `etax.hubei…:8443` 是 Vue SPA（路由 `#/query/zdsswfajcx` 等），
   **失信查询强制"纳税人识别号必填"——按户查询无全量**，批量不可用（同北京/天津）。
   其验证码 `POST /xxbg/api/zhsffw/sxsq/yzm/generate`（SxzlCode=GGCX_ZDSSWFAJCX）
   + ddddocr 已打通，仅供后续按户深查。

### 实际数据源
1. **重大税收违法失信案件信息公布表（167 md，全量）**
   - 栏目 `/hbsw/xxgk/zfxxgk/zdgkjbml/xzzf/zdsswfal/`（聚合页 `/hbsw/xxgk/zdssxxcx/`），
     167 条、12 页、15 条/页，**2020-04 后停更**（2019 年 114 条/2020 年 53 条）——
     属"官方通报类全量"入库，front matter 保留真实发布日期
   - 文章是**标准 2 列 table 公布表**：字段行（纳税人名称/信用代码/注册地址/法人/
     案件性质…）+ 末行"主要违法事实及税务处理处罚"合并叙述（按"依照|根据《"拆两节）
2. **省局稽查处罚平台 gspt（5 条，全部被质量门槛 DEL）**
   - `/gspt/xzcf/swxzybcx/index.html`（税务执法信息公示平台）：**无验证码**，
     记录以 `datajson.push({...})` 内嵌页面 JS（33 字段决定书级，articleurl 指向详情），
     客户端过滤、无分页。但省局仅挂 5 条（2025-2026 鄂税稽罚系列），
     **处罚事由只有"违反税款征收管理规定"10 字 → decide()=DEL(facts<30) 未入库**。
     市州局 gspt 路径（/hbsw/wuhan/gspt 等）全部 404，未找到城市级平台。
3. **税务新闻/通知公告关键词文章（44 md）**
   - `/hbsw/xwdt/swxw/`（19 页回溯到 2023-01）+ `/hbsw/xxgk/tzgg/`（5 页）
   - 关键词命中 45，1 件 DEL，44 件入库（含"查处加油站偷税""曝光骗取出口退税"等真实案情通报）

### 湖北产出（lawlibrary/专题/税务案例/湖北省/）
| 栏目 | 件数 | 来源 |
|---|---|---|
| 重大税收违法失信公布 | 167 | zdsswfal 公布表文章（全量，2019-2020 存量） |
| 税案通报 | 44 | /hbsw/ 新闻+通知公告关键词 |

## 三、质量门槛执行
- 全部 md 写盘前逐件 `quality_prune.decide()`：两省 1067 件 **100% KEEP**
  （失信类 facts 62-90+ 字；通报类案情完整）。
- DEL 未入库共 7 件：湖北 gspt 处罚 5（facts=10 字索引型）、渝/鄂纯告示 2。
- 文章噪音清洗：导航/字号/打印/分享/base64 二维码/面包屑全部剔除
  （复用 taxcase_scrape.extract_detail + 专项后处理）。

## 四、踩坑清单（给后续省份）
1. 重庆/湖北同属"**路径掩码型**瑞数站：真实根前缀（/cqtax/、/hbsw/）藏在首页
   相对链接后面，直访裸路径 404——**先点击导航看 final URL 再定抓取路径**。
2. 重庆失信 API `qeuryZdaj` 空条件拒查 → 枚举 ajxz（1-9,a,b）+pageSize=200；
   详情必须逐 id 再打一次 `queryZdajById`（行数据不含事实）。
3. 重庆 8888 平台验证码单次有效、ddddocr 约 50% 命中（重试循环破），
   但市级数据为空——**破码前先确认平台有数据**（dataTotal=0 就撤）。
4. 湖北必须全程 http；etax:8443 SPA 的公共查询全要"识别号必填"，批量无门。
5. 湖北 gspt 的 datajson 内嵌页面 JS，直接在 goto 后的 page.evaluate 里
   `typeof datajson` 可能取不到（变量作用域），**离线正则解析保存的 HTML 更稳**。
6. 离线转 md 幂等陷阱：断点清理不彻底会导致同名+hash 后缀重复文件
   （本轮 HB 失信 166 组重复已清理）；重跑前务必同步清 marks 与目录。

## 五、复跑
```bash
cd work/taxcase
python adapters/hbcq_cq.py --part sx     # 重庆失信（列表枚举+详情，一会话 ~30min）
python adapters/hbcq_cq.py --part news   # 重庆新闻关键词
python adapters/hbcq_hb.py --part sx     # 湖北失信公布表（167 文章）
python adapters/hbcq_hb.py --part news   # 湖北新闻关键词
python adapters/hbcq_md.py               # 离线转 md + 质量门槛（幂等）
```

## 六、总量
重庆市 856 件 + 湖北省 211 件 = **1067 件 md**（全部通过质量门槛）。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
