# 新疆维吾尔自治区税务局（第七轮 R7，2026-10-11）

## 结论

| 源 | 结果 | 说明 |
|---|---|---|
| 主站 重大税收违法失信栏（/lslm/ 政府信息公开平台） | ❌ **平台死** | 站内检索定位到两条路径：`/lslm/zqq/zfxxgkml/xzzf/zdaj/`（43 字节空页）与 `/lslm/zfxxgkmlhw/gknr/xzzf/zdaj/`（列表在、2 个子栏目）——**子页/文章全部返回「访问页面服务异常」**（202011 失信公布栏 + 202003 案件查询两个入口同死）。旧平台已废弃，新平台未接 |
| etax.zinjiang /zfgspt 处罚平台 | ❌ 服务异常 | `https://etax.xinjiang.chinatax.gov.cn/zfgspt/extranet/index` → 1129 字节「访问页面服务异常」 |
| 主站 IRS 智能检索（唯一活数据链路） | ✅ **+41 件税案通报** | `search.shtml?code=1865de63c84`；**/irs/front/search POST 直调（会话内 jQuery $.ajax）翻页可靠** |
| 市局子站 tzgg 失信主体送达公告 | ❌ 全 DEL | 49 篇《税务事项通知书（失信主体确定/告知适用）》送达公告——程序性无事实，门槛正确拦截（未入库） |

## IRS 检索数据链路（采集契约，全程浏览器会话）

1. **瑞数**：https 首页 412（$_ts）；有头 chromium（--disable-blink-features=AutomationControlled）goto 后 1-2s 通过挑战。
   **http 80 端口整站关闭**（ERR_CONNECTION_TIMED_OUT），全部走 https。
2. 检索页 `GET /search/search.shtml?code=1865de63c84&dataTypeId=1&searchWord=<kw>`——URL 带 pageNo 无效，
   **UI 翻页点击会破坏后续 goto 的渲染状态**（后续关键词全 0）——不可用。
3. **核心接口（会话内 $.ajax，瑞数自动附令牌）**：
   ```
   POST /irs/front/search   (Content-Type: application/json; X-Requested-With: XMLHttpRequest)
   {"code":"1865de63c84","searchWord":KW,"dataTypeId":"1","orderBy":"related","searchBy":"all",
    "granularity":"ALL","isSearchForced":0,"filters":[],"pageNo":N,"pageSize":10}
   → data.middle.listAndBox[] (type=DATA) → data.{url,title_no_tag,time,source}
   ```
   裸 fetch 自拼 URL 缺 ahUfMqtu 令牌会 1000 系统错误——**必须用页面自身 $.ajax**。
4. 11 关键词并集（重大税收违法/虚开/骗取出口退税/骗取留抵退税/偷税/依法查处/涉税违法/逃避缴纳税款/税案/移送司法机关…）
   → 798 URL → 标题过滤（查处|稽查|虚开|骗取|偷税|…）382 候选 → 会话内 goto 逐篇抓（321 成功 / 61 死链"服务异常"）。
5. 正文容器 `div id="content"`（**div 深度平衡法提取**，正则到 `</div>` 会截断）。
6. **镜像去重**：同一通报在省局+各市局子站（hms/alt/wlmq…）重复发布——标题+正文前 120 字 md5 去重（59 镜像折叠）。
7. **筛选规则**：非新疆个案（总局级"曝光N起"/外省城市名）跳过（总局库已有）；采购/听证/随机抽查方案/失信通知书类标题剔除；
   同案"依法查处"通稿+"揭秘/还原"深度稿两篇都保留（内容不同）。

## 数据画像（入库 41 件）

- 2023-09 ~ 2026-07，虚开专票/农产品收购发票虚开/私户收款偷税/骗取出口退税为主
- 覆盖 乌鲁木齐/昌吉/哈密/阿勒泰/和田/阿克苏/吐鲁番/巴州/双河/阿拉尔 等 10+ 市州稽查局通报

## 复跑

- 脚本：`tmp/r7/r7_xj9.py`（API 采集）、`r7_xj10.py`（文章抓取）、`r7_xj_md.py`（转 md）；原始数据 `tmp/r7/xj_search_hits.json` + `xj_candidates.json` + `xj_arts/`
- 断点：`progress/xinjiang_r7.jsonl`（198 行）
- 输出：`lawlibrary/专题/税务案例/新疆维吾尔自治区/税案通报/`（41）
- 若 /lslm/ 平台复活：重探 `https://xinjiang.chinatax.gov.cn/lslm/zfxxgkmlhw/gknr/xzzf/zdaj/`


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
