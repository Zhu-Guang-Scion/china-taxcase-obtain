# R10 暂停快照（2026-10-12 定格）

> 用户指令：暂停所有任务并快照，以便断点续跑。本文件为恢复锚点。
> 库现状：34,214 + 批复 3,668 + 媒体 232 ≈ **38,114 件**（三件套仍是 R9 口径 34,214，未重建）

## 一、本轮已完成（无需重做）

| 线 | 结果 | 产出 |
|---|---|---|
| 调研·公众号通道 | 完成 | `_research/wechat_channels_r10.md`：官网替代矩阵最优；wechat2rss 免费源 0 税务号；RSSHub 公共实例挂；wechatDownload（9.7k★）唯一整号历史通道但取 key 需人工 1 分钟（留给用户） |
| 调研·批复信源 | 完成 | `_research/pifu_sources_r10.md` + probe_r10/（fgk API 抓包、税屋 8 篇正文样本、密度曲线） |
| 门禁扩则 | 完成 | quality_prune2 NARRATIVE_KEEP 增 批复/税函/答复/税务媒体/专栏/评析（ast 验证过） |
| 税务媒体专栏 | **+232 完成** | 中国税务报 195（税案通报 97+合规案例 98，round3"域名已死"误报已纠）+ KPMG 快讯 23 + 文涛说税（搜狐镜像）14；知乎（403+登录墙）/德勤安永普华（JS 渲染）/威科（SPA 登录墙）/明税搜狗（antispider 3×420s 无效）全部探明落空。`sources/media_r10.md` + adapters{ctaxnews,wentao_sohu,kpmg,mingtax_weixin}_r10.py |
| 批复·fgk | **+530 完成** | 批复 471+国税函 333+税总函 22+建议提案答复 124（去重后 530），search5 API 白名单过滤契约在 `sources/pifu_r10.md` §1 |

## 二、暂停中（断点续跑指引）

### 批复·税屋 shui5（进行到 3,138/上限 4,000）
- **已完成**：中央列近年优先反转（2020→2018→2017…1994→2021-2026）大部分年份；进度 `progress/pifu_r10.jsonl`（src=shui5，ok 3,102+）
- **未完成**：①中央列早年份尾段与现行年（2021-2026）剩余页；②**省函（MAX_PROV=1000）整段未开始**——省清单已缓存 `progress/pifu_r10.shui5_prov_items.json`
- **续跑**：`python work/taxcase/adapters/shui5_r10.py`（断点幂等，会话过期自动重开有头浏览器；WAF 打法：正文含 renderData 且 len<12000=挑战页，换 page→重开浏览器）
- 量控：全局 ≤4,000（fgk 530 + central 2,400 + prov 1,000）

## 三、恢复后收尾清单
1. 等税屋收满 → `python work/taxcase/quality_prune2.py`（干跑复核新栏目）
2. `python work/taxcase/structure_extract.py && python work/taxcase/build_manifest.py`
3. SOURCES.md 升 v10（〇n 节：公众号矩阵+批复双源+媒体专栏，含 wechatDownload 人工通道说明）
4. skill 同步（新 adapters + sources 文档 + quality_prune2）
5. git commit + push GitHub（新 adapter/文档）
