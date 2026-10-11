# 开源前独立安全审查报告（security review）

- **仓库**：`E:\ai_coding_xiangmu\China_Law`（git 单提交 a8b84a7 "v2.0.0"，共 176 个 tracked 文件）
- **审查范围**：`git ls-files` 全部文件，逐文件不抽样（118 py / 51 md / 1 json / 1 sh / 1 out / 1 csv / 1 txt / LICENSE / .gitignore）
- **审查日期**：2026-10-11
- **审查者**：开源前独立安全审查智能体（只审不改）
- **检查项**：①密钥/凭证残留 ②PII ③危险代码 ④合规表述 ⑤数据泄露 ⑥水印完整性

---

## 一、总结论

# **修复后发布**

**P0 = 0，P1 = 3，P2 = 6。** 无任何技术性阻断项：无硬编码密钥、无自然人 PII、无危险代码执行路径、无正文数据泄露、水印全覆盖（118/118 .py + 1/1 .json）。三项 P1 全部是**文档层面的合规表述问题**（免责声明与内容自相矛盾、IP 风控规避措辞、"破解/收割"用语群），属发布前应完成的措辞修正，不涉及技术事实删除，合计约 2 小时工作量。

---

## 二、发现清单

### P1-1 免责声明与仓库内容自相矛盾（合规一致性）
**[P1] `LICENSE:28`**（README 数据边界声明为同向佐证）
- 问题：LICENSE 附加条款声明"**本仓库不提供任何绕过网站访问控制的生产化工具**"，但仓库实际包含可运行的验证码自动识别集成（`work/taxcase/adapters/hbcq_cq.py:109-155`、`work/taxcase/adapters/hn_xzcf.py:21-135`、`work/taxcase/adapters/ln_sword.py:31-123` 的 ddddocr 过码循环）、大汉 CMS JS 挑战令牌解码器（`work/taxcase/adapters/ln_sx.py` decode_lmcl）、滑块验证码求解算法全文（`work/taxcase/sources/credit_gd_slider.md`）。声明与事实不符本身就是风险：平台方审查时一旦发现矛盾，比"没有声明"更糟。
- 建议：改写声明使其与事实一致，例如——"本仓库工具链仅用于中国政府信息公开数据的低频合规采集（单线程、限速≥2.5s、只取公开公示信息）；部分文档包含对政府网站防护机制的技术研究记录，不构成对任何商业平台访问控制的规避工具，禁止用于批量高频抓取或商业用途。"事实保留，承诺明确。

### P1-2 "换手机热点新 IP"记录呈现为风控规避成功经验
**[P1] `work/taxcase/SOURCES.md:127`、`SOURCES.md:131`**（关联 `work/taxcase/sources/credit_gd_slider.md:76,106`、`_research/scrape_sichuan_zhejiang_guangdong.md:218`）
- 问题：第四节标题"手机热点新 IP **破**两省"与正文"**换手机热点（新 IP）直接验证了『403=IP 风控』假设**……新 IP 下 check 5/5、过滤查询 200"，把 IP 出口轮换写成了可复制的对抗操作手册（SOURCES.md 是 README 重点推荐阅读的"总战报"）；`_research` 里另有"换出口 IP（住宅/4G 热点）"对策建议。IP 轮换对抗平台风控是平台方最敏感的行为类别之一。
- 建议：不改事实、改框架——保留"403 疑似 IP 级限流"的实验结论，但把叙述重心从"换 IP 绕过了"改为"网络环境变更后的对照实验证实限流是 IP 级、非账号级"，并明确"本项目常规作业不依赖 IP 轮换，遇持续 403 即停"（与 AGENT_BRIEF"不要死磕"原则一致）。标题删去"破"字。

### P1-3 "破解/已破/100% 破解/攻破/收割"词汇群
**[P1] 主要命中位置**：
- `work/taxcase/SOURCES.md:125`（"大汉 JS 挑战已纯 python **破解**"）、`SOURCES.md:142`（"滑块本体 **100% 破解**"）
- `work/taxcase/STATE.md:39-40`（"滑块已破……验证码本体 **100% 破解**"）
- `_research/scrape_sichuan_zhejiang_guangdong.md:54,92`（章节标题"网宿 wswaf **破解**生态""瑞数 412 **破解**生态"）、`:36,111`（"已被本项目 playwright 有头**攻破**"）
- `work/taxcase/adapters/hbcq_cq.py:10`（"验证码 ddddocr **破解**"）
- "收割"作采集同义词遍布约 40 个文件（`README.md:49`、多数 adapter docstring、SOURCES.md 多处、`work/taxcase/R7_BRIEF.md:20` 等）
- 问题：语境本身是政府公开数据采集的技术研究记录（`_research` 第 8 节有自我合规分析，是正面资产），但"破解/攻破/收割"的战争语汇会让平台方或举报者第一眼定性为恶意工具，"收割"对政府站点语境观感尤其差。
- 建议：全局措辞替换，不删事实——"破解"→"求解/自动识别/自动化通过（机制研究记录）"；"攻破"→"通过"；"收割"→"采集/抓取/全量收录"；_research 两处"破解生态"标题改为"对抗机制研究（公开项目调研）"。sed 级替换后人工过一遍语境即可。

### P2 清单

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| P2-1 | `work/taxcase/pr.out` | 0 字节空文件被 tracked（`.gitignore` 的 `work/taxcase/*.out` 只防新增、不除已跟踪） | `git rm --cached work/taxcase/pr.out` 后提交 |
| P2-2 | `work/taxcase/adapters/hn_xzcf_loop.sh` | 唯一未含 CLAW-ZGS-2026 水印的可执行脚本（水印规范范围为 .py/.json，.sh 在范围外，故不计失分） | 补一行注释水印，与全库一致 |
| P2-3 | `work/scripts/mineru_upgrade.py:24`、`work/taxcase/ocr_fill.py:31` | 硬编码本机路径 `C:\Users\Administrator\AppData\Roaming\npm\mineru-open-api.cmd`（Administrator 为 Windows 默认账户名，非个人 PII；但泄露本机布局且不可移植） | 改为 `shutil.which("mineru-open-api")` 或环境变量/参数 |
| P2-4 | `work/scripts/ima_api_probe.py:15`、`ima_collect_ids.py:16`、`ima_fulltext.py:17`、`ima_live_capture.py:15`、`ima_recon.py:18`（均 work/scripts/）、`work/taxcase/ocr_fill.py:144` | 依赖仓库外本机绝对路径：`D:\AI Coding\tencent-ima-copilot-mcp`（其 .env 持有认证）、`E:\ai_coding_xiangmu\MinerU高并发脚本\config.json`（持有 token）。**这些外部文件均未入库（已验证），无泄露**；但他人克隆后不可运行，且公开了作者本机密钥存放位置 | 路径参数化（--env-file/--config 或环境变量），README 说明外部依赖 |
| P2-5 | `work/scripts/flk_cookie.py:43-48`、`work/taxcase/adapters/bj_all.py:338` 等 30+ 处；requirements.txt:4 | `--disable-blink-features=AutomationControlled`（浏览器自动化检测关闭）搭配 curl_cffi `impersonate="chrome124"` TLS 指纹模拟。属常规工程手段、代码可不改，但应与 P1-1 声明一并如实标注用途与边界 | 在 README 技术要点处补一句用途说明，措辞随 P1-1 处理 |
| P2-6 | `work/taxcase/adapters/sh_xzcf.py:17` | "yzmflag=1 可**绕过**验证码（客户端逻辑，服务端放行）"——事实准确（服务端自身不校验），仅"绕过"一词观感 | 改为"服务端在 yzmflag=1 时不强制验证码（客户端逻辑如此）" |

### 误报澄清（已人工辨别，无需处理）
- 11 位"手机号形"数字（`swjgdm=13702000000`、`13500000000`、`13300000000` 等，遍布 sources/*.md 与 adapters）：全部为**税务机关代码**（swjg_dm/department 参数，尾数多为 0；`work/taxcase/sources/zhejiang_sword.md:84-88` 明确是机关代码区间枚举），非手机号。
- manifest.csv 中 18 位数字（`indentifier=115323000151673132`、`id=662443883900174336`）：政府公文文号/雪花 ID，非身份证。全库身份证号（严格出生日期位校验）命中数为 **0**。
- manifest.csv L18515/18517/19553 命中"收割"：系法规标题《拖拉机和联合收割机驾驶证管理规定》《联合收割机跨区作业管理办法》。
- 32 位 hex 串（govlib.py APPID、各 channelid/tyid/topic id）：政府站点 CMS 公开参数；govlib.py 的 PUBKEY_B64 为 gov.cn 前端公开 RSA 公钥——非机密。
- `_research/wenshu_value_assessment.md:70` 的 contact@caseopen.org：开源项目组织公开联系邮箱（GitHub issue 转述），非自然人 PII。
- `work/taxcase/adapters/ln_sx.py:47` 的 `"eval(" in text`：检测抓取内容里的混淆 JS 特征字符串，非执行 eval。

---

## 三、各检查项结论摘要

| 检查项 | 结论 | 依据 |
|---|---|---|
| 1 密钥/凭证 | **通过** | 全库（含 git 历史，单提交）扫描 sk-/API_KEY=/password=/BDUSS/STOKEN/Bearer/Cookie 值/URL 内嵌凭证/JWT/32+hex/长 base64：0 真实命中。所有凭证路径均为环境变量（MINERU_TOKEN(S)、IMA_API_KEY、IMA_CLIENT_ID、IMA_COOKIES、IMA_X_IMA_COOKIE/BKN）或仓库外本地文件（已验证未入库）。`mineru_upgrade.py` 脱敏验证通过且无遗漏路径；`ocr_fill.py` 同口径（env + 仓库外 config.json，fail-soft）。WAF cookie 落 work/lists/（已 ignore）。flk 的 wzws cookie 为匿名挑战 cookie，非账号凭证 |
| 2 PII | **通过** | 身份证号 0 命中；自然人邮箱 0（唯一非 noreply 邮箱为组织公开联系方式）；物理住址 0；11 位机关代码全部人工辨别为 swjgdm。adapters 中"身份证号码"均为官方公示表格字段名标签而非数值；含 PII 的成品数据（失信公布等 31,764 件）全部位于 gitignored 目录未入库；_research/tax_case_projects.md:153 明确"入库前脱敏策略先行" |
| 3 危险代码 | **通过** | 无 eval/exec 执行（唯一命中 ln_sx.py:47 是字符串特征检测）；无 os.system、无 shell=True；subprocess 共 4 文件全部列表参数（mineru_upgrade.py:68 / waf_watch.py:62 / add_watermark.py:68『git ls-files』/ ocr_fill.py:166）；shutil.rmtree 仅限 work/mineru_tmp、work/taxcase/tmp 项目临时目录；无 pickle/yaml.load/marshal/ctypes/chmod；文件写入目标均为项目目录或参数化 out_dir |
| 4 合规表述 | **P1×3 + P2×2**（见第二节） | 正面资产：LICENSE 有免责条款、README 有数据边界声明与"只取公开公示数据"要点、AGENT_BRIEF 有"量控与合规"节（单线程/delay≥2.5s/禁止并发轰站/不死磕）、_research 第 8 节有反爬法律灰色自我分析；需修正的是声明-内容矛盾与攻击性语汇 |
| 5 数据泄露 | **通过** | lawlibrary 仅 manifest.csv 入库：11 列（库/类别/标题/公布机关/公布日期/时效性/专题/来源/原文件/Markdown/原文链接）全为元数据，最长字段 145 字符（URL），**无正文列**；.gitignore 正确覆盖 lawlibrary/*（1.1GB zip、法规目录索引/、专题/等均未入库）、work/downloads|lists|logs|verify|ima_dl|ima_upload、tmp/、progress/ 等；md 文档最大 33KB（SOURCES.md）均为机制记录非数据副本；git 历史单提交，无曾提交后删除的数据文件 |
| 6 水印 | **通过**（规范范围内 100%） | CLAW-ZGS-2026 覆盖 118/118 .py 与 1/1 .json（jobs/cta_shuiantongbao.json 内嵌 _copyright 字段）；范围外 .sh 1 个未覆盖（P2-2，建议补） |

---

## 四、逐文件过审记录（176/176）

说明：矩阵由脚本对每个文件逐行执行六类检查的模式匹配生成，命中项再经人工辨别（见备注列）。密钥/PII/危险代码列"通过"= 无命中或命中已确认为误报；合规表述（C4）与数据泄露（C5）的逐文件措辞命中行号已并入 P1-3/P2 清单与备注列，两检查项的全库结论见第三节。

| 文件 | 密钥/凭证 | PII | 危险代码 | 水印 | 备注（人工辨别/佐证） |
|---|---|---|---|---|---|
| `.gitignore` | 通过 | 通过 | 通过 | — |   |
| `LICENSE` | 通过 | 通过 | 通过 | — |   |
| `README.md` | 通过 | 通过 | 通过 | — |   |
| `_research/baidu_netdisk_api.md` | 通过 | 通过 | 通过 | — |   |
| `_research/hf_twang.md` | 通过 | 通过 | 通过 | — |   |
| `_research/rich_sources_round5.md` | 通过 | 通过 | 通过 | — |   |
| `_research/scrape_sichuan_zhejiang_guangdong.md` | 通过 | 通过 | 通过 | — |   |
| `_research/tax_case_projects.md` | 通过 | 通过 | 通过 | — |   |
| `_research/wenshu_value_assessment.md` | 通过 | L70邮箱 | 通过 | — | C2 L70 contact@caseopen.org 为开源项目组织公开联系邮箱（issue 转述），非自然人 PII → 通过 |
| `lawlibrary/manifest.csv` | 通过 | 通过 | 通过 | — | C5：11 列全为元数据（最长字段 145 字符=URL），无正文列 → 通过；C4 命中『收割』系法规标题《联合收割机…管理规定》→ 误报 |
| `requirements.txt` | 通过 | 通过 | 通过 | — |   |
| `work/scripts/build_catalog.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/cicpa_enum.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/cicpa_guide_supp.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/cicpa_std_download.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/fetch_urumqi.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/fgk_search.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/fix_rtf_xml.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/fixup39.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/flk_cookie.py` | 通过 | 通过 | 通过 | 有 | C1 WAF cookie 为匿名 wzws cookie，写 work/lists/（已 ignore）→ 通过 |
| `work/scripts/flk_download.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/flk_enumerate.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/gap_fetch.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/gap_fetch_proxy.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/gov_download.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/gov_repair.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/govlib.py` | 通过 | 通过 | 通过 | 有 | C1 PUBKEY_B64 为 gov.cn 前端公开 RSA 公钥、APPID 为站点公开参数（均取自其前端 index.js），非机密 → 通过 |
| `work/scripts/ima_api_probe.py` | 通过 | 通过 | 通过 | 有 | C1 认证走仓库外 MCP 项目（tencent-ima-copilot-mcp）→ 通过（附 P2 外部路径） |
| `work/scripts/ima_audit.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/ima_collect_ids.py` | 通过 | 通过 | 通过 | 有 | 同 ima_api_probe，认证在外部 MCP 项目 → 通过 |
| `work/scripts/ima_fulltext.py` | 通过 | 通过 | 通过 | 有 | 同 ima_api_probe → 通过 |
| `work/scripts/ima_intake.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/ima_live_capture.py` | 通过 | 通过 | 通过 | 有 | C1 认证头来自仓库外 .env（未入库）；抓包输出 work/ima_dl/ 已 ignore → 通过（附 P2 外部路径） |
| `work/scripts/ima_recon.py` | 通过 | 通过 | 通过 | 有 | C1 认证来自仓库外 .env → 通过（附 P2 外部路径） |
| `work/scripts/ima_uploader.py` | 通过 | 通过 | 通过 | 有 | C1 CLIENT_ID/API_KEY 均环境变量；COS secretId/Key 为 API 下发临时凭证（运行期）→ 通过 |
| `work/scripts/kjs_cas_download.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/kjs_enum.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/md_fill.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/mineru_upgrade.py` | 通过 | 通过 | L68;L154 | 有 | C1 token 全走 MINERU_TOKEN/MINERU_TOKENS 环境变量，缺失即退出（脱敏验证通过，无遗漏路径）；C3 L68 subprocess 列表参数、L154 rmtree 限 work/mineru_tmp → 通过 |
| `work/scripts/mirror_fill.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/moji_analyze.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/moji_drill.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/moji_fix.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/moji_verify.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/mojibake_scan.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/organize_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/redoc.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/standards_organize.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/std_gov_acct.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/upgrade_fetch.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/verify.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/scripts/waf_watch.py` | 通过 | 通过 | L62 | 有 | C3 L62 subprocess 列表参数（调本库脚本）→ 通过 |
| `work/scripts/xmlfallback.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/AGENT_BRIEF.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/R7_BRIEF.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/SOURCES.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/STATE.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/adapters/ah_cities_r5.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/bj_all.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/court_cases.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/csrc_penalty.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/cta_swhg.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/fj_cities_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/gd_cases.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/gd_city_cases.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/gd_random_inspection.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/gx_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/gz_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/gz_xzcf_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hb_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_cq.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_hb.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon2.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon3.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon4.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon5.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon6.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_recon8.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hbcq_river.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hi_news_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hlj_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hn_cities_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hn_hardcase.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hn_hardcase_test.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hn_xzcf.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/hn_xzcf_loop.sh` | 通过 | 通过 | 通过 | 缺(P2-2) | 全部通过；水印缺失见 P2-2（在 py/json 规范范围外） |
| `work/taxcase/adapters/jl_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/js_hanweb.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/js_run.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/js_run2.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/jx_xzcf_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/ln_sword.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/ln_sword_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/ln_sx.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/mof_checks.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/national_12366.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/nb_r6.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/nmg_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/qd_hn_recon.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/qd_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/qd_news.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/qd_recon2.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/qd_sswf.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/qd_xzcf.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/r7_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sc_river.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sc_river_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sd_sc_weixin.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sh_swxw.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sh_wsgg.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sh_xzcf.py` | 通过 | 通过 | 通过 | 有 | C4 L17『yzmflag=1 可绕过验证码』为事实记录（服务端放行该参数）→ 通过（附 P2 措辞建议） |
| `work/taxcase/adapters/spp_cases.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sx7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sx_nb.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sx_nb_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/sz_cases.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/tj_news.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/xz_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/yn_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/yn_xzcf_r7.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/adapters/zj_news_cases.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/add_watermark.py` | 通过 | 通过 | L68 | 有 | C3 L68 subprocess 列表参数（git ls-files）→ 通过 |
| `work/taxcase/build_manifest.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/caseopen_harvest.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/caseopen_to_md.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/jobs/cta_shuiantongbao.json` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/ocr_fill.py` | 通过 | 通过 | L166;L305;L321;L332;L343 | 有 | C1 token=环境变量+仓库外本地 config.json（未入库）；C3 subprocess 列表参数、rmtree 限 tmp → 通过 |
| `work/taxcase/pr.out` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/quality_audit.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/quality_prune.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/quality_prune2.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/repair_attachments.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/sources/12366_full.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/anhui_tianjin_r5.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/beijing.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/browser_round2.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/credit_gd_slider.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/expand_round2.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/fujian_cities_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/fujian_etax.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/gansu_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/guangdong.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/guangxi_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/guizhou_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/hainan_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/hebei_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/heilongjiang_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/henan_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/hubei_chongqing_r6.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/jiangsu.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/jiangxi_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/jilin_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/lianggao.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/liaoning_sword.md` | 通过 | 通过 | L94 | — | C3 L94 命中的 eval( 是文档引述挑战页特征字符串，非代码执行 → 通过 |
| `work/taxcase/sources/neimenggu_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/ningxia_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/ocr_补全.md` | 通过 | 通过 | 通过 | — | 全部通过（1920B 研究记录，无敏感内容） |
| `work/taxcase/sources/old_attachments.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/qingdao_hunan_r6.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/qinghai_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/shaanxi_ningbo_r6.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/shandong.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/shanghai.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/shanxi_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/sichuan_river.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/xinjiang_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/xizang_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/yunnan_r7.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/zhejiang.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/zhejiang_credit.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/sources/zhejiang_sword.md` | 通过 | 通过 | 通过 | — | C2 L84-88 为税务机关代码区间（swjgDm 枚举，13300000000 形态尾数多为 0）→ 人工辨别通过 |
| `work/taxcase/sources/zhejiang_zwfw.md` | 通过 | 通过 | 通过 | — |   |
| `work/taxcase/structure_extract.py` | 通过 | 通过 | 通过 | 有 |   |
| `work/taxcase/taxcase_scrape.py` | 通过 | 通过 | 通过 | 有 |   |
