# 税务案例库 第三轮任务 · 暂停快照（2026-10-10 18:00 定格）

> 用户指令：暂停所有任务，快照备断点续跑。本文件为恢复工作的唯一权威锚点。
> 库现状：**9,048 件 md**（第二轮结束 8,056 → 本轮 +992，主要是 12366）

## 一、本轮已完成（无需重跑）

| 任务 | 结果 | 产出 |
|---|---|---|
| 川浙粤预研 | 完成 | `_research/scrape_sichuan_zhejiang_guangdong.md`：浙江=ddddocr 全自动可抓；四川=有头 playwright 过瑞数（rs-reverse 纯算差临门一脚）；广东=信用广东滑块 ddddocr slide_match；另发现四川的墙实为**瑞数系**非网宿（shandong.md 记载需更正） |
| 老附件提取 | 完成 100/101 | 84 个 md 回填 .doc(Word COM)/.xlsx(openpyxl)/.xls(Excel COM) 全文，零 C 盘安装；`sources/old_attachments.md`；失败 1 件（连云港死链） |
| 12366 flag 探测 | 完成 | zlflag=3 办税流程有价值（停业登记/限售股申报等指南型内容，样例已入库 3 件）；zlflag=5 表单价值待定 |

## 二、暂停中任务（断点续跑指引）

### 1. 12366 全库 —— ✅ 已完成（2026-10-10 全量收口，勿重跑）
- **zlflag=2 问题解答 5,019/5,027**（8 件服务端空内容死链）；**zlflag=3 办税流程 196/196**；
  **zlflag=5 表证单书 259/274**（15 件纯骨架页 skip）。合计新增 md 5,474 件。
- 结果与对账细节：`sources/12366_full.md`；断点 jsonl 含 .w1/.w2/.retry/.verify 分片（load_done glob 合并去重）

### 2. 浙江 sword 处罚公示——✅ 已终局（2026-10-10 续跑完成：验证码已自动识别，平台 0 数据）
- **结论**：ddddocr 验证码识别打通（过码率 70-80%）、会话/postData/67 机关代码全部打通，
  但平台对所有查询条件返回"未查询到结果"——**平台未接入数据，可抓记录 0 条**。
  完整机制与 13 组判定实验：`sources/zhejiang_sword.md`（含 postData 字段表、验证码 URL
  参数 `id=ck1` 坑、响应消息真实语义）。zhejiang.md 第 3 节已同步更正。
- **无需再投入**；若未来平台接入数据，按 zhejiang_sword.md 流程重跑即可（脚本模式在文档第 1 节）。

### 3. 四川（已完成 ✅ 2026-10-10 续跑收尾，+2002 md）
- **cookie 复放确认不可行**（瑞数 cookie 与会话绑定，curl_cffi 一律 412）；本轮全部在
  有头 playwright 会话内完成（adapter `adapters/sc_river.py`，手法/坑全记录在
  `sources/sichuan_river.md`）
- 产出：行政处罚公示 1000（etax zfgspt 结构化接口，total 1367 全省，量控 cap）+
  重大税收违法失信公布 1000（col20038 jsearch search.do，total 1290）+ 通知公告/复议 2
- 旧记载更正：col2720 空壳、col8705/col11932 已 404——处罚公示真源是 etax 平台
  `query_swxz_ybcx_cfjg.spring`；失信真源是主站 col20038（jsearch，须页面 jQuery $.ajax，
  裸 fetch 415）
- 断点：`progress/sc_cols.jsonl`；原始数据 `tmp/sc_etax/*.jsonl`

### 4. 信用广东滑块（滑块已求解，卡查询网关 403）
- **2026-10-10 攻坚结果：验证码本体 100% 求解，数据查询 403 未过，0 条入库**
- 滑块 = tianai 风格三型随机（CONCAT/ROTATE/WORD_IMAGE_CLICK）；CONCAT 型已全自动求解
  （check 通过率 5/5，纯算法无需 OCR：Δ=条带seam的x坐标，D=Δ*260/590，合成 ease-out 轨迹即可）
- **卡点**：check 通过的 id 作 VALIDATE_CODE_ID 带过滤查询仍 403（curl_cffi 与真实浏览器一致）；
  剩余假设=①IP 临时风控（本轮请求量大）②轨迹分级标记 ③网关节点亲和。分辨实验已列在机制文档第四节
- **机制与复用资产全在 `sources/credit_gd_slider.md`**（脚本 tmp/gdslider/gd_harvest_cc.py 就绪，
  403 解决后直接跑即入库 广东省/信用广东处罚公示/）
- **续跑第一步**：隔夜重跑 gd_harvest_cc.py（先手动 solve+query 试 403 是否消失）；
  勿再频繁开 playwright 新 context（jsl 会降速浏览器，curl_cffi chrome124 不受影响）

## 三、通用恢复入口

```bash
cd /e/ai_coding_xiangmu/China_Law/work/taxcase
# 全部 adapter 与断点约定见 AGENT_BRIEF.md 与 SOURCES.md
python adapters/national_12366.py --help   # 12366 续跑
# 浙/川续跑：新 agent 任务提示词模板见本文件第二节对应小节（自包含可直接派发）
```

## 四、库当前清单（暂停时点）

- manifest/structured/corpus 三件套为**第二轮定稿**（8,056 件口径）；本轮新增 992 件尚未重建
- **恢复完成后收尾动作**：`python structure_extract.py && python build_manifest.py` 重建，再更新 SOURCES.md/skill/README


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
