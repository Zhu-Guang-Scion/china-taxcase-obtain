# 浙江政务服务网·行政处罚结果信息公开系统（xzcf.zjzwfw.gov.cn）采集记录【P0 已收】

- 攻坚日期：2026-10-10（第五轮信源调研 P0 落地）
- 产出：**1,193 件**含违法事实叙述≥30字的决定书全文 md → `lawlibrary/专题/税务案例/浙江省/行政处罚公示/`
- 原始数据：`work/taxcase/progress/zj_zwfw.jsonl`（+`zj_zwfw.s0/s1.jsonl` 分片，合计 6,291 条详情全文）；`progress/zj_zwfw_list.jsonl`（列表 6,302 条索引）
- 脚本：`tmp/zj_zwfw_harvest.py`（采集，可断点续跑，支持 --shard/--nshards 双 worker）/ `tmp/zj_zwfw_ingest.py`（入库，幂等）/ `tmp/zj_zwfw_compare.py`（与信用浙江索引比对）
- 与信用浙江（credit.zj.gov.cn，索引 3,069 条、详情被点击式验证码挡）**同一上游归集**，本系统零验证码，正文可直接取

## 0. 一句话结论

API 裸奔（无验证码/无签名/无 WAF，multipart POST 直连），税务过滤靠**文书号含"税"模糊匹配**（xzcfws_code=税），
详情接口 `punishDetail` 返回的 `xzcf_zy` 字段=详情页全文（与 GitHub playwright 样本逐字一致，已对拍验证）。
全库税务记录 6,302 条（2023-10-10 → 2026-09-30，仅近三年窗口），详情取回 6,291（11 条详情端点已无数据）；
**19.0% 过质量门槛**（税务摘要普遍偏短，中位数 105 字）。

## 1. 接口契约（全部实测）

```
列表  POST https://xzcf.zjzwfw.gov.cn/api-gateway/jpaas-punishment-server/open-api/punishment/searchPunishList
      Content-Type: multipart/form-data（curl_cffi requests 直接 data= 即可）
      字段: xzcfws_code(文书号·模糊) / xzcfws_name(案件名·模糊) / bxzcf_name(被处罚对象·模糊) /
            begindate / enddate(YYYY-MM-DD) / bxzcf_type(1=个人 2=单位) / deptId / areacode / pageNo / pageSize
      返回: data.punishList[] = {unid, guid, xzcfws_code, xzcfws_name, bxzcf_name, bxzcf_type,
            bxzcf_legalman, xzcf_date, orgnode} + total/pageTotal
详情  POST .../open-api/punishment/punishDetail    字段: guid（unid 也可）
      返回: data.punish = 列表全字段 + xzcf_zy（决定书摘要全文，<br> 分段，段首"标签："）
部门  POST .../open-api/punishment/searchPunishDeptList（本轮带 areacode 返回空列表，弃用；省税务局 deptId=001003028 已知可用）
```

### 1.1 参数实测要点（坑）

| 项 | 实测结论 |
|---|---|
| areacode | **6 位市码**（330100=杭州）与 12 位（330100000000）均可；`3301` 报 500；`330000` 全省不稳定（系统错误）→ 省本级用 deptId=001003028（total=6） |
| pageSize | 服务端上限 **20**（传 50 也只回 10，传 20 回 20） |
| xzcfws_code | **子串模糊匹配**：`税` → 文书号含"税"即中（税务全层级文书号必含税：杭税一稽罚/温税稽罚/浙税稽罚…）；6,302 条实测 0 条非税务机构混入 |
| 日期 | begindate/enddate 有效（杭州 2025+ = 781 / 全量 1,378）；列表默认按日期倒序 |
| 偶发"系统错误" | code=200 + success=false + message=系统错误，**重试即过**（6 次退避重试；全程仅 11 条最终失败=详情端点已无该记录"无相关行政处罚信息"） |
| 详情页 URL | `https://xzcf.zjzwfw.gov.cn/punishment/#/punishdetails?unid=<unid>&guid=<guid>&xzcfws_code=<urlencoded 文号>`（SPA hash 路由，从 app.js chunk 映射 {110:"546a3dcc"} 逆向确认） |

### 1.2 各市税务量（xzcfws_code=税）

杭州 1,378 / 温州 978 / 金华 754 / 台州 730 / 嘉兴 674 / 绍兴 675 / 丽水 403 / 衢州 262 / 湖州 232 / 舟山 217 / 省本级 6 → **合计 6,302（去重 guid 后）**
（宁波 total=0：计划单列市，数据走自己平台，与信用浙江口径一致）

## 2. 质量门槛结果

- `xzcf_zy` 字段即详情页全文（嵊州市监案例 858 字与 GitHub playwright 样本逐字对拍一致）——**无需浏览器**，punishDetail 一步到位
- 但**税务条目普遍偏短**：zy 长度中位数 105 字（市监等条目可达 2,700 字）；"违法事实"段常为 4-22 字（如"进行虚假纳税申报"）
- `quality_prune.decide()`（栏目=行政处罚公示）判定：**KEEP 1,193 / DEL 5,098**（DEL 原因全部 facts<30；KEEP 里 1,182=facts≥30、11=long-but-thin-facts）——**忠实保留原始段落标签，未改标签抬门槛**
- 过门槛样本形态：违法事实段为完整叙事（如"在账簿上多列支出，扣缴义务人不履行代扣代缴义务，应扣未扣、应收而不收税款"）+ 处罚依据法条 + 罚款金额

## 3. 与信用浙江索引（3,069 条）的文号比对

**文号交集 3,060 条 → 覆盖率 99.7%**（仅 9 条索引文号在政务网检索不到，多为 2023-10-10 窗口边界或已撤公示；另有 1 条为采集时详情端点无数据的 11 条之一）
反向：政务网独有 3,230 条（2023-10 以前的信用浙江索引窗口之外 + 各市 2024 以来新增），说明**本系统完全覆盖并远超信用浙江的税务处罚公示量**——信用浙江 3,069 条索引的正文回填问题就此解决（同文号直接取 xzcf_zy）。
仅索引有的 9 条文号前缀：杭税×4、嘉税/金税/绍税/温税/衢税各 1。

> 备注：信用浙江索引含宁波（甬税）条目 0 条（其索引本身也无宁波，计划单列走自己平台），两侧口径一致。

## 4. 入库口径

- 目录：`lawlibrary/专题/税务案例/浙江省/行政处罚公示/`；文件名 `{xzcf_date}_{bxzcf_name}-{xzcfws_code}.md`
- front matter：地区=浙江省 / 栏目=行政处罚公示 / 来源机关=orgnode（处罚机关节点名）/ 原文链接=详情页 hash URL / 决定书文号、记录KEY=ZJXZCF+对象+文号
- 正文：忠实分段 `## 违法事实 / ## 处罚依据 / ## 处罚决定 / ## 行政处罚履行方式和期限`（按 xzcf_zy 原标签），文末标注数据来源
- 标签/要素：违法类型（虚开/偷税/骗取出口退税/应扣未扣…关键词）、税种、适用法条（regex）、罚款金额自动抽取

## 5. 复跑/续收

- 采集：`python tmp/zj_zwfw_harvest.py`（读列表/详情 jsonl 断点，自动跳过已取 guid；单线程 delay 1.0s；提速可 `--shard 0 --nshards 2` 与 `--shard 1 --nshards 2` 双开，分片写 `zj_zwfw.s{K}.jsonl`）
- 入库：`python tmp/zj_zwfw_ingest.py`（幂等，自动读主文件+分片，重跑只增量写）
- 日常增量：列表会随公示更新增长（采集当日即观测到 +2 条），重跑 harvester 即可只取新增
- 11 条取不到详情的记录：详情端点返回"无相关行政处罚信息"，属上游已撤数据，无法补


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
