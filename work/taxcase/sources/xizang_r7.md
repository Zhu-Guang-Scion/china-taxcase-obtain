# 西藏自治区税务局（第七轮 R7，2026-10-11 · 30分钟快探盒）

## 结论

| 源 | 结果 | 说明 |
|---|---|---|
| 重大税收违法失信主体公布栏 | ❌ 无此栏目 | 主站导航（首页>信息公开）无失信栏；`/module/jslib/bulletin/zdss.html` 404；jsearch 未部署 |
| etax 处罚平台 | ❌ 空壳 | `etax.xizang.chinatax.gov.cn:8443/sword?ctrl=XzzfgsptHomeCtrl_index` 200 但为 SPA 壳（6882B，`env.config.js` 404→跳转 `:5100` 新电子税务局）；`ajax.sword` 数据端点不存在——湖南式空壳 |
| **主站通知公告 税案通报/曝光** | ✅ **+16 件富全文入库**（16/16 过门槛，正文 255–1541 汉字） | 信源#4 新闻过滤路径；西藏体量极小符合预期 |

## 站点形态

- `https://xizang.chinatax.gov.cn` **无墙**（http 80 连不上，必须 https），curl_cffi chrome124 直连。
- TRS/大汉系：col 页 + `POST /module/web/jpage/dataproxy.jsp`（webid=1，col5513 的 unitid=13090）。

## 采集契约（通知公告 col5513 → 税案通报）

1. 列表：
   ```
   POST /module/web/jpage/dataproxy.jsp
   body: col=1&appid=1&webid=1&path=%2F&columnid=5513&sourceContentType=1
         &unitid=13090&webname=<双重URL编码:国家税务总局西藏自治区税务局>&permissiontype=0
         &startrecord=1&endrecord=400&perpage=400
   ```
   （**全部参数必须在 body**，query 串参数无效——实测 52B 空响应）
   total 301 条；record 为 CDATA 包 `<li><a href='/art/…'title='…'><span>[MM-DD]</span>`。
2. 标题过滤（案件类词 `查处|曝光|偷税|虚开|骗取|骗享|骗税|黑中介` − 程序类 `廉政|欠税的公告|信用修复|约束制度|惩戒机制|撤销|反馈通道|意见$`）→ **16 件**。
3. 日期：dataproxy 只有 `[MM-DD]`，**完整日期取 art URL 路径** `/art/YYYY/M/D/`（TRS 发布日期）。
4. 详情正文：大汉 `begin-->/end-->` 标记对，**取 CJK 最多的段**（标题段 15–40 字，正文段 255–1541 字；不要用 #zoom 定位——部分页面无该容器）。
   尾部会带 `<!--ZJEG_RSS.content.` 残片，入库后清除（16 件已清）。

## 数据画像

- 16 件全为稽查查处/曝光通稿：虚开发票 3 起、加油站偷税 3 批、骗享研发费用加计扣除、隐匿未开票收入、黑中介虚开团伙、涉税中介执业不规范等；涉案主体多建筑/医药/加油站，含移送公安叙述
- 时间跨度 2023-11～2026-04，正文中位 ~450 汉字，含违法事实+金额+处理处罚决定全文

## 复跑

- adapter：`adapters/xz_r7.py`（断点 `progress/xz_news_r7.jsonl`，清单 `tmp/r7/xz_case_items.json`）
- 输出：`lawlibrary/专题/税务案例/西藏自治区/税案通报/*.md`
- 西藏地市局（拉萨/日喀则/那曲/阿里等）内容直接发主站 col5513，无需分市采集


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
