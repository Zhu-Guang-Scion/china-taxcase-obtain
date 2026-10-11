# 第七轮：河南省（henan.chinatax.gov.cn）——汇联 CMS 全站搜索 API 破局（97 件）

日期：2026-10-11 ｜ adapter：`work/taxcase/adapters/hn_cities_r7.py` ｜ 断点：`progress/hn_cities_r7.jsonl`
入库：**97 件**（`lawlibrary/专题/税务案例/河南省/<省局|17市>/税案通报/`，2023-01→2026-09，
正文汉字 min 239 / 中位 959 / max 5,639，quality_prune 全 KEEP）
背景：第五轮判"官网无数据"（只看了主站栏目）——本轮改攻市局子站，发现真正入口是搜索 API。

## 一、站点结构（实测）

- **19 市局子站 = 主站路径前缀**（非子域）：/zhengzhou/ /zhengzhoushiyanqu/ /kaifeng/ /luoyang/
  /pingdingshan/ /anyang/ /hebi/ /xinxiang/ /jiaozuo/ /puyang/ /xuchang/ /luohe/ /sanmenxia/
  /nanyang/ /shangqiu/ /xinyang/ /zhoukou/ /zhumadian/ /jiyuan/（首页底部导航）
- 汇联 CMS（dahe.cn）：列表静态分页 index_N.html（pageN = index_{N-1}）；
  详情 URL `/2026/10-10/142373.html`，正文 `div#mainText`，标题 h2.articleTit，
  日期 `日期：YYYY-MM-DD`，来源 `.con-source`
- 市局子站栏目只有 工作动态/基层动态/通知公告/市局文件——**没有稽查/失信专栏**
- **通知公告 ≈ 送达公告**（郑州 2,802 条），正文是**纯图片**（ueditor img 上传的公告扫描图），
  无 PDF 附件 → 程序性 DEL，OCR 不值得
- etax.henan = 电子税务局壳；wzjh.henan = 网站聚合/搜索服务（真入口在此）

## 二、关键突破：全站搜索 API（无验证码、GET 直连）

```
GET https://wzjh.henan.chinatax.gov.cn/search-api/open/api/external-new
  ?keywords=依法查处&siteId={站点ID}&searchRange=-1000&sortType=150
  &pageNumber=N&pageSize=15&fileType=0&docType=0
```
- **siteId 表**在 `/upload/4500180001/search/js/search1.js` 的 `search.list`（省站 4500180001 +
  19 市，如 郑州 4500150001 / 洛阳 4710000001 / 南阳 4574090001 …）
- **siteId 只搜本站**（-1/0 全省无效）→ 必须逐站循环 20 个 siteId
- 返回 `data.datas[]`：title/pubDate/channelName/selfUrl/**content（截断摘要，不能替代详情）**/
  totalRow/totalPage；selfUrl 有 `//henan` `://henan` `/henan` 三种残形，须归一化
- 前置开关 `shuijuIsStatic=false`（is-static.js）——为 true 时前端搜索弹"系统维护"，API 不受影响
- 关键词：依法查处 / 失信 / 虚开 / 偷税 / 骗取 / 稽查（6 词并集去重）

## 三、抓取与门槛（安徽模式）

- 20 站 × 6 关键词枚举（每词 ≤15 页）→ URL 去重 6,760 条 → 标题 KW 过滤
  （排除 送达/采购/裁量基准/司法解释/优秀案卷/风险防控 等）→ 抓详情 →
  内容门槛（≥120 汉字 + 经查/查处叙述 + 偷税/虚开/罚款要素）→ 入库
- 站内数据形态：
  - 省局税务新闻：总局体例查处通报（"河南省濮阳市税警联合依法查处…"）
  - **洛阳市独有：稽查局把《税务处理决定书》全文发在新闻栏**（5,639 字全文，含价税合计/
    违法事实/追缴税款/移送公安——本轮河南最富源，18 件）
  - 市局工作动态：本地媒体深度稿（"揭秘…案件"体）
- 事后清扫 2 轮：总局通稿镜像（来源=国家税务总局新媒体、标题无河南/市痕迹）删 19 件；
  干部培训/获奖/风险指引稿删 6 件
- **信阳/周口/驻马店 0 件**——三市工作动态全是服务/党建稿，无查处通报（数据形态如此）

## 四、坑

1. curl_cffi `follow_redirects` 参数不存在（0.16.3）——去掉即可
2. http 80 端口连不上（河南仅 https）
3. 搜索 API 的 content 字段是 **"…"截断摘要**（首尾拼接），必须回源详情页取全文
4. con-source 偶带乱码尾巴（"中原经济网？？"）——front matter 可读性小瑕疵，不影响正文
5. 列表页 newsCount 有显示封顶值，但搜索 API 的 totalRow 准确

## 五、复跑

```bash
python work/taxcase/adapters/hn_cities_r7.py            # 全部 20 站断点续跑
python work/taxcase/adapters/hn_cities_r7.py --only 洛阳 # 单站
```


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
