# 四川省税务局案例抓取 —— 续跑定稿（瑞数会话内方案，2026-10-10）

> 续跑背景：上一轮有头 playwright 拿到过真实页面，但导出 cookie（tmp/sc_cookies*.json）
> 经 curl_cffi 复放全部 412（瑞数 cookie 与 UA/会话绑定，与北京结论一致）。
> 本轮全程在 playwright 浏览器会话内完成抓取（北京同款手法），不再导出 cookie。
> adapter：`work/taxcase/adapters/sc_river.py`（--part etax|xz|sx|cols|md）
> 离线转 md：`work/taxcase/adapters/sc_river_md.py`；断点：`progress/sc_cols.jsonl`

## 一、挑战通过方式（核心经验）

1. **有头 chromium 过瑞数**：`headless=False` + `--disable-blink-features=AutomationControlled`
   + `--window-position=2400,100`（移出屏幕）；goto 后轮询 `page.content()`，
   判定 `body 纯文本长度>300 且前 3000 字节无 $_ts=window`（约 2-6s 自动完成）。
2. **一切数据请求走会话内 page.evaluate(fetch/$.ajax)**（带浏览器 cookie，稳定 200）；
   若中途再被挑战（响应含 $_ts），重新 goto 任一页面过挑战后重试即可。
3. **挑战误判坑**：`is_challenge` 不能用"无 body/无 title/文本短"判断——**JSON 响应会被
   误判成挑战**（本轮真实事故：209KB 的合法 JSON 被当挑战丢了 4 轮）。只认
   status∈{412,900} / 文本头部含 `$_ts=window`。
4. **编码坑**：etax JSON 响应 charset 头错（UTF-8 字节标成 GBK），`fetch().text()` 得
   乱码（"发票"→"鍙戠エ"）。解法：JS 侧 `arrayBuffer()` + `TextDecoder('utf-8')`
   （备用 gbk），不要用 r.text()。
5. **fetch ≠ $.ajax**：`/jsearchfront/plugin/interface/search/search.do`（失信公布栏数据
   接口）裸 fetch 一律 **HTTP 415**，换成**页面自身已加载的 jQuery `$.ajax`** 发完全相同
   的 JSON 体即通（page.evaluate 内直接写 $.ajax，contentType:"application/json"）。
6. **混合内容坑**：TRS dataproxy 返回的文章链接是 `http://sichuan...`，在 https 页面
   上下文 fetch 会被 Chromium 拦（`TypeError: Failed to fetch`）→ 抓详情前统一
   `http://sichuan.` → `https://sichuan.` 归一。
7. 站内静态 js/css 不受瑞数保护，curl 直连可下（逆向 dataQuery.js 全靠这一点）。

## 二、栏目探测结论（与旧记载的差异）

- **col2720 行政处罚公示**：真实页面存在，但 jpage `totalRecord:0`，dataproxy 返回
  空 `<datastore>`——栏目是**空壳**，处罚公示已迁行政执法信息公示平台。
  （dataproxy 机制本身已验证可用：col2719 行政许可公示返回 6 条。）
- **col8705 一般程序处理结果 / col11932 行政处罚决定和结果**：
  `/col/colNNNN/index.html` 一律 404，shandong.md 旧记载的入口已失效；
  col8705 的内容实为 etax 平台"税务行政一般程序处罚结果"模块（本轮主源）。
- **失信公布栏**：不在 etax（菜单 data-url 为空、zdsswf 系列 .spring 接口全 500），
  真身在主站 **col20038**（法定主动公开内容 col463 下），查询表单+表格页，
  数据由 `/images/154/dataQuery.js`（静态可下）驱动 jsearch search.do。
- 重大税收违法失信年度汇总文章：搜索引擎不可见，jsearch 行数据已覆盖同等字段。

## 三、实际数据源与抓法

### 1. etax 行政执法信息公示平台 —— 行政处罚公示（主源，1000 md）
- 页面：`https://etax.sichuan.chinatax.gov.cn/zfgspt/extranet/xzcf?city=ybs_3`
  （city 参数只影响菜单皮肤，数据全省）
- 接口：`POST /zfgspt/extranet/shgs/query_swxz_ybcx_cfjg.spring`
  body：`nsrmc=&shxydm=&cfjg=&xzcfjdswh=&ajmc=&zccfrqq=&zccfrqz=&type=gs&pageSize=200&pageIndex={N}`
- 响应：`{"success":true,"total":1367,"data":[…]}`，字段 XZCFJDSWH 决定书文号 / AJMC
  案件名称 / NSRMC 相对人 / TYSHXYDM 信用代码 / FDDBRXM 法人 / CFLB 类别 / CFJG 结果 /
  SWJGMC 机关 / ZCGCFRQ 作出日期 / **CFSY 违法事实全文 / CFYJ 处罚依据全文** / FBSJ 发布
- 量：total 1367（唯一 KEY 1306，滚动窗口跨页有重）；**全省覆盖**（成都145/绵阳91/
  宜宾62/会理52/内江51/泸州50/达州50/德阳43…）；近三年过滤后按日期倒序取 1000 件
  （量控 cap，较早的 306 件 2023 年记录未入库，原始数据在 tmp/sc_etax/records.jsonl）

### 2. 重大税收违法失信主体信息公布栏（col20038，1000 md）
- 接口：`POST /jsearchfront/plugin/interface/search/search.do`（**必须页面 jQuery $.ajax**）
  body：`{"groupFields":null,"q":"","groupTargets":{"websiteid":"510000000000000"},
  "signs":"JCMS","fetch_fields":"title,url,column,module,deploytime,zdnsrmc,zdnsrsbh,
  zdzzjgdm,zdzcdz,zdfddbr,zdcwfzr,zdgbjg,zdajxz,zdwfqjfr,zdsjfzr,zdzjjg,zdzywfss,zdswclcf",
  "filterQuery":"+(column:20038)","p":{页},"pg":100}`
- 响应：`{total:1290, dataResults:[…]}`；**行自带主要违法事实（zdzywfss，HTML）与
  税务处理处罚（zdswclcf）全文**，无需抓详情页；deploytime 为 epoch 毫秒
- 量：取前 1000 件（量控 cap；余 290 件较早，原始在 tmp/sc_etax/shixin_rows.jsonl）

### 3. 通知公告 col19241 + 全站搜索（补抓，2 md）
- col19241 dataproxy 枚举 141 条（2023 起），关键词（复议|送达|处罚|失信|违法|稽查|
  偷税|虚开|骗税|欠税）命中 2，剔除采购比选噪音 1，入库《四川省税务行政处罚裁量基准
  （试行）》1 件
- 全站搜索 q=行政复议决定书：命中 1（眉山市 2026-08-11 送达公告，眉税复决字〔2026〕14号）
  → 入库 行政复议/；**各市局复议送达公告多在各市子站/附件，未逐一抓**（下轮可按市扩展）

## 四、产出

| 目录（lawlibrary/专题/税务案例/四川省/） | 件数 | 来源 |
|---|---|---|
| 行政处罚公示 | 1000 | etax 平台结构化记录（决定书级） |
| 重大税收违法失信公布 | 1000 | col20038 jsearch 行（主体级） |
| 通知公告涉税公告 | 1 | col19241 |
| 行政复议 | 1 | 站内搜索（眉山） |
| （税案通报） | 3 | 前轮微信通道产出，未动 |

合计本轮新增 **2002 件 md**（全省目录 2005 件）。

## 五、复跑

```bash
cd work/taxcase
python adapters/sc_river.py --part sx      # 失信+通知公告+复议搜索（一会话）
python adapters/sc_river.py --part etax --max-records 1400
python adapters/sc_river_md.py             # 离线转 md（断点幂等）
```
断点 progress/sc_cols.jsonl：etax:{KEY} / sx:{url尾} / art:{md5} 三类 key；
原始数据 tmp/sc_etax/*.jsonl、tmp/sc_pages/*.html、附件 tmp/sc_atts/。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
