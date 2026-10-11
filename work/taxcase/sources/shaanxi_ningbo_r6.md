# 陕西省 + 宁波市 税务案例抓取来源文档（第六轮）

抓取日期：2026-10-11 ｜ 执行代理：瑞数省攻坚（陕西+宁波）｜ 网络：手机热点
adapter：`work/taxcase/adapters/sx_nb.py`（陕西）、`nb_r6.py`（宁波）、`sx_nb_md.py`（两地离线转 md）
断点：`progress/sx_nb_r6.jsonl`；原始数据 `tmp/sx_nb/`

## 一、陕西省（shaanxi.chinatax.gov.cn，瑞数 412，HTTPS 未黑洞）

### 挑战通过
- 有头 chromium（headless=False + --disable-blink-features=AutomationControlled
  + --window-position=2400,100），轮询 body 文本>200 判定挑战完成——与四川/北京同款，
  两站挑战均自动通过，无需 msedge 降级。
- 主站 TRS CMS（col 栏目 + art 文章）；执法公示平台在**独立子域 HTTP :88**：
  `http://zfgs.shaanxi.chinatax.gov.cn:88`（同样瑞数）。

### 1. 重大税收违法失信主体（col15616）——本轮主源，67 件 md
- 栏目页是 TRS 自定义检索表单（field_NNNN 字段式），提交 GET
  `/module/search/index.jsp?field_1672=<年>&strSelectID=style_…&i_columnid=style_3&field=…`
  （快捷查询函数 yearchaxun(a) 设 field_1672=年 后 form.submit()，结果显示在 iframe）
- 分页：结果页附 `&page=N`；20 条/页
- **坑：年度查询跨年重叠**——2023/24/25/26 四年查询共返回 167 条 URL，去重后
  **唯一主体仅 67**（year 过滤实际不生效，各年返回同一滚动列表）
- 文章页 `/art/YYYY/M/D/art_15616_NNNNN.html`：[标签,值] 成对表格
  （纳税人名称/识别号/注册地址/案件性质/**主要违法事实+依据+处罚合并一行**）
- 转换：成对解析 → `**标签**：值`；合并行挂 `**主要违法事实**：`下（质量门槛按此识别，
  67/67 KEEP，事实叙述 111-164 字）
- 日期：URL 路径段（2023:7 / 2024:20 / 2025:20 / 2026:20）

### 2. 执法公示平台行政处罚（zfgs:88 /shaanxiswgscx）——放弃（双验证码+瑞数412）
- 入口：平台首页→行政处罚 col7 / 税务行政一般程序处罚结果 col34，两者同一 iframe：
  `/shaanxiswgscx/sxsw/xzcfPage.do?nCataid=6067`
- 数据接口：`GET /shaanxiswgscx/sxsw/xzcf.do`（页面 jQuery $.ajax + csrfToken header），
  参数 ajmc/xzxdrmc/xzxdrdm/cfjg/nCataId/currentPage/isCheckVerifyCode/verifycode
- 字段模板（JS 挖出）：field_806 决定书文号 / 807 案件名称 / 808 处罚类别 /
  **1450 处罚事由 / 1451 处罚依据** / 811 相对人 / 812 代码 / 813 法人 / 814 结果 / 815 机关
- **三层封锁无法批量**：
  1. 首查强制 4 位数字验证码（cfVerifycode.do 图片）；翻页 isCheckVerifyCode=false
     免码——但须先过首查
  2. 验证码图片扭曲度高：ddddocr（多预处理变体投票）≈0/8；人眼视觉识别 ≈0/9
     （6917/3917/9812/8841×2 等均"验证码错误"）
  3. 连续请求触发验证码端点**返回空白图**（像素 std≈22、全白）+ XHR 随机 412
     （瑞数对 XHR 拦截，页面重载后立即提交也常 412）
- 经验：提交前页面重载会**重生成验证码**致旧答案失效（截图→重载→提交=必败）；
  正确顺序是 载入→截图→提交 中间不导航，但仍被识别率卡死。放弃并记录。

### 3. 通知公告（col5383）——放弃（JS 渲染无数据接口）
- `/col/col5383/index.html` 直访/带 vc_xxgkarea 参数均返回 38KB 信息公开框架页，
  无 dataproxy/jpage 组件（webid=2 但 unitid 不可得），dataproxy 构造返回空。
- 首页 art_5383 文章存在，但列表机制为运行时注入，未找到可复刻接口。

### 4. 其他探明但未抓
- etax.shaanxi.chinatax.gov.cn = 电子税务局登录平台（非公示）
- `sxswjajcx/ajnsr/query.do` A级纳税人查询（非案例）
- 欠税公告 zfgs:88 col47 / col7163（欠税名单属 DEL 类，跳过）

## 二、宁波市（ningbo.chinatax.gov.cn，瑞数五代）

### 挑战通过
- 同款有头 chromium 挑战通过成功。**关键差异：瑞数五代，每个 URL（含静态 art 页）都要
  m4oH8x2I 查询令牌——会话内裸 fetch() 一律 412**，文章抓取必须逐页 page.goto
  （浏览器 JS 自动签名），列表数据靠 goto 后读渲染 DOM。

### 1. 重大税收违法失信主体信息公布栏（/zdsswfsxztxxgbl/）——主源，273 件 md
- 13 个区级子栏（dq/yzq 等）+ 11 个违法性质子栏数据**完全相同**（实测 yzq vs hsq
  页1 三行全等）——抓一份即可
- 表格（所属税务机关/失信主体名称/识别号/违法性质/详细信息链接），layui laypage
  点击翻页（a.layui-laypage-next，只渲染部分页码按钮，必须逐页点 next）
- 19 页 × 15 = 273 条唯一 URL；详情 art 页 [标签,值] 成对表格，含
  **主要违法事实 / 相关法律依据及税务处理处罚情况** 完整叙述
- 转换：同陕西成对解析；日期取 `<meta name="PubDate">`（宁波 art URL 无月日段）
- 质量门槛 273/273 KEEP，事实叙述 54-219 字

### 2. 涉税通知（/xxgk/tzgg/sstz/）——156 条枚举，0 入库（合理）
- 列表 658 条（layui count 属性），关键词（处罚|失信|违法|稽查|…）命中 156，详情全抓
- 正文容器 `#zoom`（info-cont div）
- 质量门槛全 DEL：149 条为稽查局**文书送达公告**（程序性：通知文号+纳税人名单表格，
  无违法事实叙述——符合"催报催缴/文书送达名单不收"的用户标准）；7 条为征求意见/
  证件遗失/搬迁/防诈提醒（无案情）
- 结论：sstz 栏目对案例库无增量价值，已验证放弃

### 3. 行政执法信息公示平台（/xxgk/xzzfxxgspt/）——放弃（canvas 验证码+加密查询）
- 结构：sj/xzcf（市级 税务行政普通程序处罚结果）+ 11 区子站；查询页 layui 表单
  （案件名称/相对人/代码/处罚机关）+ **canvas 绘制验证码**（4 位字母数字）
- 数据经 jpaas 单元接口 `/api-gateway/jpaas-publish-server/front/page/build/unit`
  （querydata 参数客户端加密为 m4oH8x2I 令牌），无验证码/错码均静默返回"暂无数据"
- canvas 绘制代码不在任何静态 JS（unitbuild.js 是加载器、customSearch.js 是通用
  搜索框架、plugins.js 仅 20 字节），验证码值服务端校验，无突破口
- 与天津处罚平台同结论：验证码封锁，放弃

## 三、两地踩坑摘要
1. 陕西主站 TRS 检索表单栏（失信栏）数据接口是 `/module/search/index.jsp`（GET 全参
   数表单序列化），不是四川的 jsearch search.do——通过触发页面 yearchaxun() 抓真实
   URL 才定位到。
2. 陕西失信年度查询的 year 过滤不生效（四年结果重叠），URL 去重后仅 67 唯一主体——
   **枚举后必须按 URL 去重再评估量**，否则虚高 2.5 倍。
3. 陕西 zfgs:88 执法平台：XHR 随机 412 + 验证码 + 重载失效三重坑；验证码端点被刷后
   返回空白图（攻击性限流），dddddocr 与人眼均读不动其扭曲数字。
4. 宁波瑞数五代全 URL 令牌：裸 fetch 412、必须 goto——详情批量抓取速度降至 ~7s/篇。
5. 宁波列表 layui 分页只渲染窗口内页码，跳页须逐页点 next（a[data-page='10'] 不存在）。
6. 宁波失信区级子栏数据全同（框架只换皮肤），抓一份即可，勿按 13 区重复抓。
7. 成对表格转 md：合并标签行（"主要违法事实相关法律依据及税务处理处罚情况"）需把
   值全文挂 `**主要违法事实**：` 下，否则 quality_prune 判 DEL（首转 167 全 DEL 的事故）。
8. 质量门槛实测：宁波 156 条涉税通知全 DEL（149 程序性送达 + 7 无案情）——程序性
   公告确实无训练价值，门槛有效拦截。

## 四、产出

| 地区 | 目录（lawlibrary/专题/税务案例/） | 件数 |
|---|---|---|
| 陕西省 | 重大税收违法失信公布 | 67 |
| 宁波市 | 重大税收违法失信公布 | 273 |

合计 **340 件 md**（全部含违法事实叙述 ≥54 字，2023-01 之后）。

放弃并记录：陕西处罚平台（验证码）、陕西通知公告（无接口）、宁波处罚平台（验证码）、
宁波涉税通知（全程序性）、两地欠税公告（名单类）。

## 五、复跑
```bash
cd work/taxcase/adapters
python sx_nb.py --part shixin    # 陕西失信（tmp/sx_nb/sx_shixin_urls.json 已枚举）
python nb_r6.py --part shixin    # 宁波失信（rows 文件缓存，仅补详情）
python nb_r6.py --part notice    # 宁波涉税通知（枚举用，入库为 0）
python sx_nb_md.py               # 离线转 md（幂等）
```
原始数据：tmp/sx_nb/（shixin_meta.jsonl / nb_shixin_meta.jsonl / nb_notice_meta.jsonl
+ nbsx_/nbnt_/sxart_*.html）


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
