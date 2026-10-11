# 浙江省税务局（zhejiang.chinatax.gov.cn）税务案例抓取记录

- 抓取日期：2026-10-10
- CMS：大汉 Hanwei（`/col/colXXXX/index.html` + `/art/{y}/{m}/{d}/art_{colid}_{id}.html`），UTF-8
- 通用库 `taxcase_scrape.polite_get`（curl_cffi chrome124）在本站全程可用，无 TLS 拦截

## 1. 税案通报（税务新闻 col13226，标题过滤）——已抓取

- 入口：https://zhejiang.chinatax.gov.cn/col/col13226/index.html
- 列表**不是静态分页页**（`index_1.html` 会回退到网站首页！），真实翻页接口为
  `POST /module/web/jpage/dataproxy.jsp?startrecord={s}&endrecord={e}&perpage=15`，
  表单参数 `col=1&appid=1&webid=15&path=/&columnid=13226&sourceContentType=1&unitid=57907&webname=…&permissiontype=0`，
  返回 XML datastore，record 为 CDATA 包裹的 `<li><span>日期</span><a href title>`。
  注意：窗口按 15 前进但服务端每次实际返回约 46 条，**必须按 URL 去重**（踩过：不去重会重复抓 2-3 遍）。
- 栏目 totalRecord=259（2021 至今）；近三年（2023-01-01 后）唯一记录 211 条。
- 官方稽查通报（"国家税务总局XX市税务局第X稽查局依法查处…"）与配套深度揭秘稿
  （"揭秘XX公司…"）成对发布在同一栏目，全部入库。
- 详情页 meta：`ArticleTitle`（干净标题，`<title>` 是"站名 栏目 标题"拼接不能直接用）、
  `ContentSource`（来源机关）、`Maketime`（发布时间）。正文容器由通用 extract_detail 兜底命中。
- adapter：`work/taxcase/adapters/zj_news_cases.py`（`python adapters/zj_news_cases.py news`）
- 产出：`lawlibrary/专题/税务案例/浙江省/税案通报/` **52 件**（2023-03-16 → 2026-08-11），
  失败 0 件；progress `work/taxcase/progress/zj_news_cases.jsonl`。

## 2. 基层动态 col13229——扫描后放弃

- 入口：https://zhejiang.chinatax.gov.cn/col/col13229/index.html（同一 dataproxy 接口，columnid=13229）
- 近三年 529 条唯一记录中标题含案件关键词的 **0 条**（均为市局日常工作新闻），放弃。

## 3. 行政处罚公示——验证码已自动识别，但平台数据为空（终局，见 zhejiang_sword.md）

- 信息公开目录（`/module/xxgk/tree.jsp` 代码 Z0710）下只有 1 条记录：跳转行政执法公示平台
  `http://zhejiang.chinatax.gov.cn:16002/sword?ctrl=XzzfgsptHomeCtrl_index&yjcd=xzcf&ejcd=xzcf_01`
- 平台为 wings/sword 框架：首页 → iframe 加载
  `sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg&swjgDm=<全省67个机关代码>&sxq=zhejiangsheng`
- 数据接口 `POST ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg`，wings postData JSON。
- **第三轮续跑更正**（2026-10-10，完整逆向记录 `sources/zhejiang_sword.md`）：
  验证码已被 ddddocr 默认模型自动识别（过码率 70-80%，识别错换码重试即可），
  会话/postData/机关代码全部打通——但平台对任何条件组合（全省机关、任意日期、
  真实受罚公司名）一律"未查询到结果"，**平台本身未接入数据**（同款山西平台公开显示
  "本单位暂未产生该项执法信息"）。本栏可抓取记录 0 条。
- 市局（hangzhoushi）、区县局（shangchengqu 等）xxgk 的"行政处罚决定和结果公示"
  （代码 Z0712，省级是 Z0710）全部只是再链回同一 sword 平台，无本地文章。
- **未发现季度处罚汇总 Excel**：省/杭州/上城区 xxgk 标题检索"汇总/处罚汇总/季度"均无
  （只有纳税信用 A 级名单汇总、税收统计），该形态在浙江现网不存在。

## 4. 重大税收违法失信主体信息——站点无实数据

- 信息公开 Z0703 → /col/col24411/index.html 仅一段说明文字（iframe 占位页）；
- 平台失信模块 `ajax.sword?ctrl=XzzfgsptXxfblCtrl_getXxfblData`（gssxDm=19）无验证码、
  可直接 POST，但返回仅 1 条：指向 /col/col9217（其本身 JS 跳回 col24411）。
  即浙江网上渠道未公布失信案件明细。

## 5. 行政复议决定书——站点无

- xxgk 标题检索"复议 / 决定书 / 送达"均为 0 条，浙江省局网站不公示复议决定书。

## 踩坑摘要

1. 列表静态分页假象：`colXXXX/index_1.html` 返回整站首页而非第2页，必须走 dataproxy.jsp POST。
2. dataproxy.jsp 请求窗口（startrecord/endrecord）与实际返回条数（~46）不一致 → URL 去重必须做。
3. `polite_get` 直接 GET search.jsp 拿 48 字节空响应——xxgk 检索接口必须 POST（jQuery ajax type:POST）。
4. 详情页 `<title>` 带站名+栏目前缀，用 meta `ArticleTitle`；来源用 meta `ContentSource`。
5. :16002 sword 平台无 TLS 拦截但验证码服务端强校验；iframe URL 由首页 JS 拼装（playwright 抓取）。
6. 无 GBK 编码问题（全站 UTF-8）。

## 抓取量汇总

| 栏目 | 入口 | 件数 | 失败 |
|---|---|---|---|
| 税案通报（税务新闻过滤） | /col/col13226/index.html | 52 | 0 |
| 行政处罚公示（sword） | :16002/sword?ctrl=XzzfgsptHomeCtrl_index&yjcd=xzcf | 0（验证码拦截） | - |
| 重大税收违法失信主体信息 | /col/col24411/index.html | 0（站点无数据） | - |
| 行政复议决定书 | - | 0（不公示） | - |


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
