# china-taxcase-obtain — 中国税务稽查与处罚案例采集处理工具链

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

两套经过全量实战验证的政府公开数据采集-清洗-质检-结构化流水线，以及配套的完整踩坑实录：

0. **法规库流水线**（`work/scripts/`，附属组件）：国家法律法规数据库（flk.npc.gov.cn）+ 国家规章库（gov.cn）→ 28,000+ 件现行有效法规，官方 docx + Markdown 双格式，四层校验体系
2. **税务案例库流水线**（`work/taxcase/`）：31 个省级行政区税务局 + 总局 + 两高/财政部/证监会 + 12366 → 31,764 件**富全文**稽查/处罚/失信案例（含质量双要素门禁与要素结构化），`work/taxcase/SOURCES.md` 是八轮实战的完整反爬与机制战报

> **数据边界声明**：本仓库只开源**代码、规则、机制文档与 manifest.csv 元数据索引**（31,764 件案例 + 27,795 件法规的标题/日期/来源/链接清单）。文书原文数据不随仓库分发——请用本工具链从官方渠道自行采集（合规要点：单线程、限速、只取公开公示数据）。

## 快速开始

```bash
pip install -r requirements.txt
# 环境变量（可选功能）：MINERU_TOKEN / MINERU_TOKENS（扫描件 OCR）、MINERU_CLI（mineru-open-api 命令行路径）

# 税务案例采集（任选一个源，全部支持断点续抓）
python work/taxcase/taxcase_scrape.py work/taxcase/jobs/cta_shuiantongbao.json   # 总局税案通报
python work/taxcase/adapters/sh_xzcf.py                                          # 上海处罚公示
# 更多源见 work/taxcase/SOURCES.md（〇a-〇l 各轮战报）与 work/taxcase/sources/*.md（各省接口契约）

# 质量门禁（双要素：案情具体性 + 处罚结果）→ 结构化 → 清单
python work/taxcase/quality_prune2.py
python work/taxcase/structure_extract.py
python work/taxcase/build_manifest.py
```

配套 ZCode/Claude skill（含全部适配器与文档的打包版）：本仓库 `work/taxcase/` 即其源码母本；skill 安装方式见各 SKILL.md（tax-case-obtain / china-law-obtain / china-law-search）。

## 仓库结构

```
├── work/scripts/          # 法规库流水线（flk 枚举/下载、规章库、镜像补齐、乱码修复、MinerU OCR、四层校验、md 整理）
├── work/taxcase/          # 税务案例流水线
│   ├── taxcase_scrape.py  #   通用抓取库（curl_cffi chrome124 指纹 / 限速 / 断点 / md 转换）
│   ├── adapters/          #   40+ 省市/平台适配器（每省接口契约已固化）
│   ├── quality_prune2.py  #   质量门禁 v2（双要素，防"处罚信息孤悬"）
│   ├── structure_extract.py  # 要素结构化（税种/违法类型/法条/罚款倍数/金额/移送司法）
│   ├── SOURCES.md         #   ★ 八轮实战总战报（全部入口/机制/反爬对策/坑）
│   └── sources/           #   30+ 份分省踩坑实录
├── _research/             # 预研报告（百度网盘 API / 公开项目调研 / 裁判文书价值研判 / 富信源调研）
└── lawlibrary/manifest.csv  # 数据索引（标题/机关/日期/链接；原文不入库）
```

## 已知技术要点（详见 SOURCES.md）

- 税务系统全线 TLS 指纹反爬 → `curl_cffi impersonate="chrome124"`（注意本环境 timeout 量纲坑）
- 瑞数/网宿墙 → 有头 chromium 会话内采集（六省实战打法）；网宿 wswaf（山东）在真实浏览器自动过
- 验证码三类：纯前端把戏（山东数据接口不验）/ 图片码 ddddocr（辽宁 75%）/ 点选汉字码（识别率低，换源）
- **质量规律**：重大税收违法失信公布栏的富全文密度远高于处罚公示平台（后者事由多为分类短语）

---

# 中国大陆现行法律法规规章制度库（项目原始档案）

构建时间：2026-10-08/09（校验于 10-09） ｜ 数据源：国家法律法规数据库 (flk.npc.gov.cn) + 国家规章库 (gov.cn) + 公开镜像交叉验证
更新工具：`china-law-obtain` skill（见下文「配套 skill」）

## 最终交付（lawlibrary/）

```
lawlibrary/
├── manifest.csv                       # 总清单（库/类别/标题/机关/日期/专题/来源/原文件/Markdown/链接）
├── 国家法律法规数据库/
│   ├── 宪法|法律|行政法规|监察法规|地方法规|司法解释/
│   │   ├── 原文件/   *.docx / *.pdf / *.doc（官方原始文件）
│   │   └── Markdown/  *.md（front matter + 正文，第X条加粗，表格转md表）
├── 国家规章库/
│   ├── 部门规章|地方政府规章/{原文件,Markdown}/
└── 专题/
    ├── 涉税法规/<库>/<类别>/          # 标题含 税种/税收/发票 等关键词（原文件+md 副本）
    ├── 涉会计法规/<库>/<类别>/        # 标题含 会计/审计/注册会计师/总会计师/财务
    └── 国资监管法规/<业务子类>/       # 2026-10-09 增量：IMA共享知识库 14 件国资法规（仅 Markdown）
        ├── 综合监管/  投资管理/  产权与资产交易/
        ├── 合规管理与廉洁从业/  贸易管理/  招标采购/
```

工作区（work/）与镜像（mirrors/）为过程数据；lawlibrary/ 为最终成品。

## 覆盖范围（现行有效，flk sxx=3 + 规章库全库）

| 库 | 类别 | 条目数 | 官方口径对照 |
|---|---|---|---|
| 国家法律法规数据库 | 宪法 | 7 | 官方展示 7 个宪法文本/修正案 |
| 国家法律法规数据库 | 法律（含法律解释/修正案/决定） | 340 | 官方核心法律 302 |
| 国家法律法规数据库 | 行政法规 | 605 | 官方 605（精确一致） |
| 国家法律法规数据库 | 监察法规 | 2 | 官方 2 |
| 国家法律法规数据库 | 地方法规（含法规性决定） | 15,746 | 官方 15,711 |
| 国家法律法规数据库 | 司法解释 | 561 | 官方 560 |
| 国家规章库 | 部门规章 | 2,675 | 库本身仅收录现行有效 |
| 国家规章库 | 地方政府规章 | 7,848 | 库本身仅收录现行有效 |
| **合计** | | **27,784** | |

## 校验体系（work/verify/）

1. **数量对账** counts_report.json：枚举数 vs 官方 aggregateData vs 磁盘文件数 vs 进度数
2. **文件完整性** integrity_report.json：docx=有效ZIP含document.xml、pdf=%PDF头、大小阈值
3. **抽样内容** sample_report.json：每类抽 40 件——标题命中/正文字数/第X条结构
4. **镜像交叉** cross_report.json：LawRefBook 条数比对（镜像版本滞后已证实）、HF 2023 快照标题集合比对（差异均被生态环境法典编纂等立法事件解释）、lawtext bbbs 覆盖率
5. **manifest.csv**：每件法规的下载状态/来源（官方API/lawtext镜像/lawtext_md/api_content）/双格式路径

## 已知边界

- 规章库 26 组重复条目（同一规章两个发布页），一份文件服务两条记录
- 极少数老页面正文以 PDF 附件提供（已下载 `*_附件*.pdf`）
- 约 24 件 2020-2021 司法解释官方仅扫描版 PDF：原文件保留 PDF，md 正文取自 HuggingFace 同题同日快照并在 md 内注明
- 通知/意见/指引等规范性文件不属于两库收录范围（法定法规规章之外）

## 增量：IMA 国资法律法规专题（2026-10-09）

**来源**：腾讯 ima 共享知识库「国资法律法规」（ID 7343537326666625，创建者：法苑文道）之「国资法律法规（可下载）」文件夹，14 件。
**采集方式**：复用 `~/.zcode` 的 tencent-ima-copilot MCP 认证，逆向 ima.qq.com 网页端 API（`knowledge_tab_reader/get_knowledge` 取元数据、QA 流 `fileList` 块取 media_id、QA 全文输出取正文），脚本见 `work/scripts/ima_*.py`。
**PDF 原件说明**：IMA 服务端将文件二进制下载限定在桌面客户端加密通道（`/cgi-bin/s/file_manager/get_media`，需客户端 crypto bridge），网页/API 通道仅返回解析文本，故本专题只含 Markdown 无原文件；原件可在 ima 桌面客户端手动下载。2026-10-09 补充实测（computer-use 操控客户端）：单件下载链路（聊天引用→预览窗口→下载按钮→落盘 Downloads）验证可行，约 10-15 秒/件，首件《中央企业发展规划管理办法》116KB 已归档至 `work/ima_dl/originals/`；但批量自动化受 ima 客户端 Electron 无障碍树裁剪（400 元素上限、地址栏/输入框常缺位）+ 全局合成输入禁用限制，聊天输入框与滚动无法程序驱动，剩余 13 件建议客户端内手动下载（文件夹内逐条点开→右上角下载）。

**14 件处置**：
- 11 件为两库范围外的规范性文件（意见/指引/通知/非令发布办法），系本项目此前无法覆盖的增量，全部转 md 入库；其中 3 件因 IMA 解析文本存在实质缺口（缺条款/拼接痕迹），改用官方公开源全文替换：《中央企业发展规划管理办法》（国资委令第45号，商务部全球法规网）、《国有企业领导人员廉洁从业规定（2026修订）》（人民网发布）、《中央企业违规经营投资责任追究实施办法》（国资委令第46号，国资委官网）
- 《中央企业违规经营投资责任追究实施办法》为 2026 施行的正式版（国资委令第46号），主库仅有 2018 试行版，作为新条目入库
- 《政府投资条例》《中央企业合规管理办法》《企业国有资产监督管理暂行条例（2019修订）》3 件主库已有官方版，IMA 件仅作专题内 md 副本，不重复计入 manifest

**分类**（lawlibrary/专题/国资监管法规/，共 14 件 md）：综合监管 1 ｜ 投资管理 5 ｜ 产权与资产交易 3 ｜ 合规管理与廉洁从业 3 ｜ 贸易管理 1 ｜ 招标采购 1。
manifest.csv 由 27,784 行增至 27,795 行（+11）。

## 增量：税务案例库（2026-10-10/11，八轮完成——31 省全覆盖）

**位置**：`lawlibrary/专题/税务案例/`（**纯 md，终库 31,764 件 / 295MB，RICH 96.4%**）+ `manifest.csv` + `taxcase_corpus.jsonl`（微调语料）+ `taxcase_structured.jsonl`（要素结构化）。
**第八轮（质量门禁 v2）**：二次清洗"处罚信息孤悬"——v1 的 30 字门槛漏了三种形态（法条+金额凑字数 / 分类模板句超30字 / 走逃户批量同文模板），v2 改为**双要素门禁**（案情具体性=数字+单位或动词，且处罚结果要素；`quality_prune2.py`），再删 3,154 件（浙江1,087/江西729/福建告知书247/辽宁205…），全部留档 `pruned_files_v2.json`。误杀教训与门禁规则已固化 AGENT_BRIEF/skill。
**第七轮（扩围+攻坚，+13,772）**：16 省区全下 + 福建翻案——冀1,907/晋1,923/蒙487/河南翻案97/江西2,036（xlsx决定书级）/琼60/桂1,064/滇1,429/黔1,412/甘181/宁600/青150/新41/吉415/黑454/藏16/福建市局1,500（中位839字）。**31 省全覆盖**。
**第六轮（瑞数队列，+3,351）**：湘1,321/渝856/青岛623/宁波273/鄂211/陕67。**第五轮**：删6,722+门槛固化；裁判文书1,838/浙江政务网1,193/辽宁1,211/安徽128。**前四轮**：总局1,214、上海、江苏、四川、山东3,243、信用广东、12366全库5,474、两高/部委、OCR 111件等。
**工具与经验**：`~/.zcode/skills/tax-case-obtain`（120+ 文件）。总战报 `work/taxcase/SOURCES.md`（v8，〇b-〇l 全记录，含质量门禁 v1→v2 演进与踩坑）。
**增量更新**：重跑 job/adapter（断点续抓）每月一次；新源过 `quality_prune2.py` 门槛 → `structure_extract.py` → `build_manifest.py`。

## 复现与更新

```bash
# 全流程脚本在 work/scripts/（也已固化为 ~/.zcode/skills/china-law-aque）
python work/scripts/flk_enumerate.py        # 枚举 flk（叶子分类码+sxx=3，pageSize500）
python work/scripts/govlib.py               # 枚举规章库（athenaappkey 本地RSA生成）
python work/scripts/flk_download.py <类> 5  # 官方 docx 下载（网宿WAF→flk_cookie.py）
python work/scripts/gov_download.py <类> 4 # 规章库 HTML→docx（API正文回退）
python work/scripts/upgrade_fetch.py 5      # md来源升级官方docx（gh-proxy加速+sha256）
python work/scripts/verify.py all           # 四层校验
python work/scripts/organize_md.py          # 整理+md+涉税/涉会计专题 → lawlibrary/
# 增量更新：新旧 lists 目录 diff（脚本见 china-law-obtain skill）
```

---

## 作者与许可

**Author: [Zhu-Guang-Scion](https://github.com/Zhu-Guang-Scion)** · Repo: [china-taxcase-obtain](https://github.com/Zhu-Guang-Scion/china-taxcase-obtain) · 水印标识 `CLAW-ZGS-2026`（各源码文件头部）

代码与文档遵循 MIT License（见 [LICENSE](./LICENSE)）；数据不入库分发，索引清单见 `lawlibrary/manifest.csv`。转载请保留水印与出处。
