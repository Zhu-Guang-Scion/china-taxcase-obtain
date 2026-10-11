# 开源前法规流水线 + 文档就绪审查（lawdocs）

- 审查对象：`work/scripts/` 全部 42 个 .py + 仓库级开源就绪（README / requirements / .gitignore / 文档交叉引用 / skill）
- 审查日期：2026-10-11 ｜ 只审不改 ｜ 审查人：法规流水线审查智能体
- 方法：逐文件通读敏感文件（flk_cookie/govlib/waf_watch/ima_*/mineru_upgrade 等 16 个），其余按结构化 grep（硬编码路径、import、except、subprocess、进度文件）+ 头部通读；`git status --ignored` / `git ls-files` 抽查；全部 50 个 tracked .md 的相对链接程序化校验。

---

## 一、总体结论

**当前状态：代码质量整体过硬（主链路 flk/gov 12 个核心脚本全部 `__file__` 相对寻址、限速、断点、重试齐备），但尚不可直接开源。** 存在 2 个 P0：

1. **README 快速开始前两条命令在任何非作者机器上必失败**——job JSON 与上海适配器（共 15 个 tracked taxcase 文件）把输出路径硬编码为 `E:/ai_coding_xiangmu/...`。
2. **`work/scripts/ima_*.py` 8 个文件与本项目开源主题无关且开源语境下不可运行/有合规风险**——其中 5 个依赖仓库外私有工程 `D:\AI Coding\tencent-ima-copilot-mcp`（含读取作者私有 .env 登录凭据），建议整体移出首版。

P1 共 10 项，集中在：其余硬编码路径（mineru CLI、cicpa/fgk 共 7 处 E:\ 常量）、README 三处事实性错误（pip 清单缺包、引用不存在的 diff_update.py、skill 名写错）、requirements 缺 pandas、合规表述与 LICENSE 附加声明自相矛盾。

---

## 二、发现清单

### P0（阻断开源 / 快速开始必失败 / 合规硬伤）

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| P0-1 | `work/taxcase/jobs/cta_shuiantongbao.json:6`（`out_dir`）、`work/taxcase/adapters/sh_xzcf.py:36`（`OUT_DIR`），另 12 个适配器同病：court_cases.py:31 / csrc_penalty.py:31 / cta_swhg.py:18 / gd_cases.py:44 / gd_city_cases.py:43 / gd_random_inspection.py:35 / mof_checks.py:29 / national_12366.py:43-44 / sh_swxw.py:36,45 / sh_wsgg.py:34 / spp_cases.py:31 / sz_cases.py:45 / zj_news_cases.py:33 | README 快速开始第 1、2 条命令（`taxcase_scrape.py jobs/cta_shuiantongbao.json`、`adapters/sh_xzcf.py`）的输出路径硬编码作者本机 `E:/ai_coding_xiangmu/China_Law/...`，新 clone 上 `os.makedirs` 直接抛异常或写错盘。共 15 个 tracked 文件（14 适配器 + 1 job json） | 统一改为 `__file__` 相对（`ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))`，同 quality_prune2.py:22 的既有模式）；job json 的 `out_dir` 改相对路径并由 taxcase_scrape.py 解析为 repo-root 相对 |
| P0-2 | `work/scripts/ima_api_probe.py:15,22`、`ima_collect_ids.py:16,21`、`ima_fulltext.py:17,22,87`、`ima_live_capture.py:15-16`、`ima_recon.py:18-19`、`ima_uploader.py:37,43-44`、`ima_audit.py:28`、`ima_intake.py:14` | ima 系列 8 文件：① 3 个文件 `sys.path.insert` 指向仓库外私有工程 `D:\AI Coding\tencent-ima-copilot-mcp\src`，任何第三方无法运行；② 2 个文件读取该私有工程的 `.env`（作者腾讯 ima 登录 cookie/bkn），属凭据文件读取 + 第三方专有平台（ima.qq.com）未公开 API 逆向；③ 私有知识库 ID `7343537326666625` 硬编码 5 处 + README:112；④ `ima_uploader.py:43-44`/`ima_audit.py:28` 在**模块导入时**读取 gitignored 的 `work/ima_upload/folders.json`/`kb_id.txt`——新 clone 上 `import` 即 FileNotFoundError；⑤ 与 LICENSE 附加声明"只取公开公示数据""不提供绕过访问控制的工具"直接冲突 | **8 个 ima_*.py 全部移出首版仓库**（保留在私有分支）。README 第 110-122 行的 IMA 专题叙述可保留（是数据来源文档，manifest 已含 11 件增量），但 L113"脚本见 work/scripts/ima_*.py"与 L16 `IMA_API_KEY` 提示需删除。详见第五节 |

### P1（发布前应修）

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| P1-1 | `work/scripts/mineru_upgrade.py:24` | `CLI = r'C:\Users\Administrator\AppData\Roaming\npm\mineru-open-api.cmd'`——作者本机 npm 全局路径，他机必失败 | `CLI = os.environ.get("MINERU_CLI") or shutil.which("mineru-open-api") or shutil.which("mineru-open-api.cmd")`，找不到时打印安装指引退出。token 走环境变量（L26-29）已是正确做法，保留 |
| P1-2 | `cicpa_enum.py:29`；`cicpa_std_download.py:25,26,27,28`；`cicpa_guide_supp.py:20,21`；`fgk_search.py:14` | 7 处硬编码 `E:\ai_coding_xiangmu\...` 常量（OUT/OUT_DIR/LIST_OUT/ENUM/LOGS）+ 1 处 `sys.path.insert` 硬编码 | 全部改 `os.path.join(os.path.dirname(__file__), "..", ...)`（同目录其余 28 个脚本既有模式）；fgk_search 的 sys.path 用 `os.path.dirname(os.path.abspath(__file__))` |
| P1-3 | `README.md:15` | 快速开始 pip 清单 `curl-cffi beautifulsoup4 lxml markdownify pymupdf python-docx openpyxl` **缺 `requests` 与 `pycryptodome`**——README 自己在 L137-138 要求跑的 `flk_enumerate.py`（需 requests）与 `govlib.py`（需 pycryptodome，RSA 生成）装不上；且全篇未提 `requirements.txt` | 改为 `pip install -r requirements.txt`（或补全两个包名） |
| P1-4 | `README.md:144` | 复现与更新块引用 `python work/scripts/diff_update.py old/lists new/lists`——**该文件不存在**（42 个脚本里没有） | 删除该行，或从历史补入 diff_update.py |
| P1-5 | `README.md:58,136` | skill 名写作 `~/.zcode/skills/china-law-aque`——本机实际目录为 `china-law-obtain`（L29 写对了），`china-law-aque` 不存在 | 统一为 `china-law-obtain` |
| P1-6 | `README.md:29`（另 58,130,136） | "配套 Claude/ZCode skill"全部位于 `~/.zcode/skills/`（仓库外），**未说明任何获取方式**——开源用户拿不到，声明等于空承诺 | 二选一：① 把三个 skill 打包目录收进仓库（如 `skills/`）并给安装说明；② README 明确"skill 为作者私有环境固化产物，等价能力即本仓库脚本 + SOURCES.md"，删掉打包版说法 |
| P1-7 | `requirements.txt` | **缺 `pandas`**：`fixup39.py:60`（懒导入、未守卫——need_parquet 非空即 ImportError）、`verify.py:332`（有 os.path.exists 守卫）、taxcase `jx_xzcf_r7.py` 在用。另缺 `aiohttp`（ima_uploader/ima_audit 模块级）与 `python-dotenv`（ima_recon.py:16）——若按 P0-2 移出 ima 则后两者无需补 | 补 `pandas>=2.0`（标注"可选：verify cross / fixup39 / 江西xlsx"）；ima 移出后 aiohttp/dotenv 不补 |
| P1-8 | `ima_uploader.py:168,274`、`ima_audit.py:91` | `aiohttp.TCPConnector(ssl=False)`——对 ima.qq.com OpenAPI 与 COS 上传**关闭 TLS 证书校验**（携带 API key 的请求可被中间人） | 随 ima 移出；若保留则去掉 `ssl=False` |
| P1-9 | LICENSE 附加声明 vs `~/.zcode/skills/china-law-obtain/SKILL.md`（描述含"网宿WAF破解"）、README:139"网宿WAF→flk_cookie.py" | LICENSE 承诺"不提供任何绕过网站访问控制的生产化工具"，而 skill/README 用"破解"措辞描述 flk_cookie/waf_watch——**自相矛盾**，开源后两头不讨好 | 保留 flk_cookie.py / waf_watch.py / govlib.py 本体（技术上是"真实浏览器会话初始化 + 公开前端参数复现"，含限速与退避），但统一措辞为"浏览器会话保持/公开搜索接口前端行为复现"，并在 README 已知技术要点处补一句边界说明 |
| P1-10 | `work/scripts/ima_intake.py:14`、`ima_uploader.py:37` | （随 P0-2 处置；若坚持保留 ima 系列）这两个文件的 `ROOT = Path(r"E:\...")` 必改 `Path(__file__).resolve().parents[2]`，且 ima_uploader.py:43-44 的模块级 `folders.json` 读取须下沉到 main() 并给出缺文件报错 | 见 P0-2 |

### P2（建议修 / 低危）

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| P2-1 | `fetch_urumqi.py:19,14,38,45` | 一次性修复脚本：模块级 `from playwright.sync_api import sync_playwright`（playwright 标"可选"却 import 即需）+ 全部 cwd 相对路径（`work/lists/...`），离开仓库根目录运行即错 | 移入 `work/scripts/oneoff/` 子目录并在 README 标注"历史一次性脚本"，或直接移出首版 |
| P2-2 | `moji_analyze.py`、`moji_drill.py`、`moji_verify.py` | 同为一次性分析脚本，cwd 相对路径（`work/verify/mojibake_report.json`、`lawlibrary/...`），且 moji_verify 硬编码 4 个具体文件名 | 同 P2-1 |
| P2-3 | `gap_fetch.py:24`、`gap_fetch_proxy.py:31`、`upgrade_fetch.py:28`、`md_fill.py`（MIRRORS）、`mirror_fill.py:55-56`、`fixup39.py:61`、`verify.py:330` | 7 个脚本依赖 `mirrors/data-docx.jsonl`/`law_full.parquet`/`regulations/`——mirrors/ 已 gitignore 不随仓库分发，README L141 又让用户跑 `upgrade_fetch.py`，无人能复现 | README 补一节"镜像索引获取"：lawtext/legal-data-docx（GitHub）与 HF twang2218/chinese-law-and-regulations 的下载方法 |
| P2-4 | `build_catalog.py:34,51` | 模块级加载 `work/lists/enumData.json`——该文件没有任何脚本生成（来自 flk enumData 接口手工获取），新 clone 上 import 即崩；产物 `法规目录索引/` 也被 ignore（合理，但输入来源未记录） | 加载下沉 main()；docstring 记录 enumData.json 的获取 URL |
| P2-5 | `redoc.py:31` | `load_cookie_session()` 直接 `json.load(open(...flk_cookies.json))`，无存在性检查——文件缺失时裸 traceback | `os.path.exists` 判断 + 友好提示先跑 flk_cookie.py |
| P2-6 | `waf_watch.py:62-67` | `subprocess.run` 无 `timeout`——子下载进程死锁则看护进程永久挂起 | 加 `timeout=24*3600` 或改 Popen+轮询 |
| P2-7 | `organize_md.py:46`、`build_catalog.py:20` | 支持 `CHINA_LAW_WORK` 环境变量（好设计）但 fallback 是 `os.getcwd()`，且该变量全文档未提及 | README 复现一节补一行环境变量说明 |
| P2-8 | `work/taxcase/pr.out`（已 tracked） | 进程输出日志误提交；`.gitignore` 末行虽有 `work/taxcase/*.out` 但对已跟踪文件无效 | `git rm --cached work/taxcase/pr.out` |
| P2-9 | `README.md:7` | "28,000+ 件现行有效法规"与自身 L93 合计 27,784（+11 IMA = 27,795，L122）不符，夸大约 200 件 | 改"27,800 件"或"近 2.8 万件" |
| P2-10 | `ima_intake.py:110`（死代码：date 赋值立即被 111 覆盖）、`ima_recon.py:16`（`from dotenv import load_dotenv` 死导入，且是未声明依赖的模块级导入） | 随 P0-2 移出；无需单独修 | — |
| P2-11 | `requirements.txt:15` | ddddocr/playwright 标"可选"对 work/scripts 基本成立（flk_cookie.py:38 懒导入、WAF 激活时才需要），但 taxcase 侧 `ln_sword.py:31`、`hn_xzcf.py:21` 是**模块级** import ddddocr，30+ 文件模块级 import playwright——"可选"仅指不跑这些适配器 | requirements 注释补一句"taxcase 部分适配器模块级依赖 playwright/ddddocr，跑对应省份前需安装" |
| P2-12 | 全目录 26 处 `except Exception: pass/continue` | 无真正裸 `except:`（全部 `except Exception`，90 处总量），吞噬点多在重试循环/进度行解析/浏览器清理语境，属合理容错；但进度文件解析处静默跳过损坏行可能掩盖磁盘问题 | 低优先：关键路径（Progress.__init__）损坏行计数打印一句 |
| P2-13 | `fixup39.py:60` | `import pandas as pd` 懒导入未守卫（P1-7 已含依赖声明，此处代码层） | try/except ImportError + 提示 |

### 敏感逻辑专项评估（任务一.2）

- **flk_cookie.py**：本质是"用无头真实浏览器访问 flk.npc.gov.cn 首页并保存 cookie"——与任何正常用户浏览器行为一致，不含验证码破解、不含凭据伪造；带 30 分钟新鲜度、launch 三级降级。**开源必要性高**（README L139 明示它是 WAF 期下载的前置），保留。风险仅在措辞（见 P1-9）。
- **govlib.py**：`gen_appkey()` 用前端 JS 里公开可见的 RSA 公钥+APPID 做 PKCS1v15 加密，复现的是 gov.cn 规章库前端每个浏览器都会发的请求；无账号、无绕过；枚举自带 0.6s+随机限速与 athena_ 失效重生成。**核心必要性极高**（规章库唯一枚举路径），保留，建议在 docstring 加一句"复现公开前端行为，无凭据参与"。
- **waf_watch.py**：20 分钟探测一次 WAF 是否解除、解除后以 3 workers 慢速续传。技术上是"可用性看护 + 断点续传"，不是攻击工具；间隔礼貌。保留，但 P1-9 的措辞统一必须覆盖它（"WAF 看护"比"破解"准确）。
- **ima_* 系列**：见 P0-2 与第五节，**建议全部移出**。

### subprocess / 断点文件 / 裸 except 专项（任务一.3）

- **subprocess 仅 2 处**：`mineru_upgrade.py:68`（列表参数、无 shell=True、timeout=1200、env 定制——安全，仅 CLI 路径问题 P1-1；stderr 为 bytes 手工 decode，正确）；`waf_watch.py:62`（sys.executable + `__file__` 相对脚本路径、encoding/errors 指定——正确，缺 timeout 见 P2-6）。**全仓库无 shell=True、无字符串拼接命令**。
- **断点文件**：设计统一且可移植——flk/gov/standards 全部走 `work/lists/*_dl_progress_<cat>.jsonl` 追加式 JSONL + latest-wins 读取（flk_download.Progress / gov_download.Progress 线程安全带锁），路径均由 `__file__` 推导。唯一例外：fetch_urumqi.py:45 cwd 相对（P2-1）。ima_uploader 进度在 gitignored work/ima_upload（合理）。
- **裸 except**：0 处真裸；`except Exception` 共 90 处，其中 26 处静默吞噬——评估见 P2-12。

---

## 三、42 文件状态表

| 文件 | 硬编码路径 | 敏感/依赖 | 主要问题 | 处置 |
|---|---|---|---|---|
| build_catalog.py | 无（env/cwd） | enumData.json 未分发 | P2-4 模块级加载 | 保留+修 |
| cicpa_enum.py | **E:\ L29** | — | P1-2 | 保留+修 |
| cicpa_guide_supp.py | **E:\ L20-21** | — | P1-2 | 保留+修 |
| cicpa_std_download.py | **E:\ L25-28(4处)** | — | P1-2 | 保留+修 |
| fetch_urumqi.py | cwd 相对 L14,38,45 | 模块级 playwright L19 | P2-1 一次性 | 移 oneoff/ |
| fgk_search.py | **E:\ L14(sys.path)** | — | P1-2 | 保留+修 |
| fix_rtf_xml.py | 无 | 懒 flk_cookie | except-swallow 合理 | 保留 |
| fixup39.py | 无 | pandas 懒未守卫；mirrors parquet | P2-3/P2-13 | 保留+修 |
| flk_cookie.py | 无 | 懒 playwright（WAF cookie） | P1-9 措辞 | 保留 |
| flk_download.py | 无 | — | 质量佳：熔断/降速/重排 | 保留 |
| flk_enumerate.py | 无 | — | 无 | 保留 |
| gap_fetch.py | 无 | mirrors 索引 | P2-3 | 保留+文档 |
| gap_fetch_proxy.py | 无 | mirrors 索引 | P2-3 | 保留+文档 |
| gov_download.py | 无 | — | 无 | 保留 |
| gov_repair.py | 无 | — | 无 | 保留 |
| govlib.py | 无 | RSA athenaappkey | P1-9 措辞+免责 | 保留 |
| ima_api_probe.py | **E:\ L22 + D:\ L15** | 私有 MCP 工程、私有 KB id | P0-2 | **移出** |
| ima_audit.py | （经 ima_uploader） | aiohttp 模块级；kb_id.txt import 即读 | P0-2/P1-8 | **移出** |
| ima_collect_ids.py | **E:\ L21 + D:\ L16** | 私有 MCP、KB id | P0-2 | **移出** |
| ima_fulltext.py | **E:\ L22,87 + D:\ L17** | 私有 MCP、KB id | P0-2 | **移出** |
| ima_intake.py | **E:\ L14** | 依赖 ima_dl 产物 | P0-2/P2-10 死代码 | **移出** |
| ima_live_capture.py | **E:\ L16 + D:\ .env L15** | 私有登录凭据读取 | P0-2 | **移出** |
| ima_recon.py | **E:\ L19 + D:\ .env L18** | 凭据读取；dotenv 死导入 L16 | P0-2 | **移出** |
| ima_uploader.py | **E:\ L37** | 模块级读 folders.json L43-44；ssl=False | P0-2/P1-8 | **移出** |
| kjs_cas_download.py | 无 | — | 自包含，无 | 保留 |
| kjs_enum.py | 无 | — | 无 | 保留 |
| md_fill.py | 无 | mirrors/regulations | P2-3 | 保留+文档 |
| mineru_upgrade.py | **C:\Users\... L24** | MINERU_TOKEN env（好） | P1-1 | 保留+修 |
| mirror_fill.py | 无 | mirrors（isdir 守卫） | 无 | 保留 |
| moji_analyze.py | cwd 相对 | — | P2-2 一次性 | 移 oneoff/ |
| moji_drill.py | cwd 相对 | — | P2-2 一次性 | 移 oneoff/ |
| moji_fix.py | 无 | 懒 docx/gd | 无 | 保留 |
| moji_verify.py | cwd 相对+硬编码文件名 | — | P2-2 一次性 | 移 oneoff/ |
| mojibake_scan.py | 无 | 懒 pymupdf/docx | 无 | 保留 |
| organize_md.py | 无（env/cwd） | 懒 pymupdf；win32com 守卫 | P2-7 | 保留+文档 |
| redoc.py | 无 | cookie 文件未守卫 L31 | P2-5 一次性 | 保留+修 |
| standards_organize.py | 无 | — | 无 | 保留 |
| std_gov_acct.py | 无 | — | 无 | 保留 |
| upgrade_fetch.py | 无 | mirrors 索引、第三方 gh-proxy | P2-3 | 保留+文档 |
| verify.py | 无 | pandas 守卫导入 | 无实质问题 | 保留 |
| waf_watch.py | 无 | subprocess 无 timeout | P2-6/P1-9 | 保留+修 |
| xmlfallback.py | 无 | 纯 stdlib | 无 | 保留 |

汇总：**可原样保留 21 个；保留+小修 13 个；移 oneoff/ 5 个；建议移出首版 8 个（全部为 ima_*）**；42 个中含硬编码绝对路径 13 个（E:\ 12 文件、D:\ 5 文件、C:\Users 1 文件）。

---

## 四、requirements.txt 对账表（全仓库 import 口径）

| 包 | requirements 声明 | 实际使用（模块级/懒） | 判定 |
|---|---|---|---|
| requests | ✓ 核心 | work/scripts 11 文件 + taxcase | 一致 |
| curl_cffi | ✓ 核心 | taxcase 25 文件（含 README:48 说明） | 一致 |
| beautifulsoup4 / lxml / markdownify | ✓ 核心 | taxcase（scrape + md 型适配器） | 一致 |
| openpyxl | ✓ 核心 | taxcase jx_xzcf_r7 | 一致 |
| python-docx | ✓ 核心 | work/scripts 10 文件 + taxcase | 一致 |
| pycryptodome | ✓ 核心 | govlib.py:23-24（模块级） | 一致（但 README pip 清单漏，P1-3） |
| pymupdf | ✓ 核心 | organize_md:176 / mojibake_scan:151（懒） | 一致 |
| playwright | 注释"可选" | scripts：flk_cookie:38 懒 / flk_download(经 flk_cookie) / waf_watch(经 flk_cookie) / fetch_urumqi:19 **模块级**；taxcase **30+ 文件模块级** | 基本属实但两处例外（P2-1/P2-11） |
| ddddocr | 注释"可选" | taxcase：ln_sword:31、hn_xzcf:21 **模块级**；hbcq_cq:109、sx_nb:155 懒 | 属实但模块级两处需注明（P2-11） |
| pywin32 | 注释"可选" | organize_md:230-232（try 守卫）；taxcase js_hanweb | 属实，Windows-only 已注明 |
| **aiohttp** | ✗ **缺** | ima_uploader / ima_audit（模块级） | 缺——随 ima 移出则无需补 |
| **pandas** | ✗ **缺** | fixup39:60（懒未守卫）、verify:332（守卫）、taxcase jx_xzcf_r7 | **缺，应补（P1-7）** |
| **python-dotenv** | ✗ **缺** | ima_recon:16（模块级**死导入**，从未调用） | 缺——随 ima 移出则无需补 |
| Pillow | ✗ 缺 | taxcase sx_nb（PIL 截图） | 缺（P2，taxcase 侧） |

---

## 五、ima 系列处置建议（任务一.2 专项结论）

**一句话：8 个 ima_*.py 与"法规+税务案例官方公开数据采集"的开源主题无关，且其中 5 个依赖仓库外私有工程/私有登录凭据、任何人无法运行，建议整体移出首版仓库（含 README L16 IMA_API_KEY 提示与 L113 脚本指引；README 第 110-122 行 IMA 专题的数据来源叙述可保留）。**

分层理由：

1. **不可运行（硬伤）**：ima_api_probe / ima_collect_ids / ima_fulltext `sys.path.insert(D:\AI Coding\tencent-ima-copilot-mcp\src)`；ima_live_capture / ima_recon 读该工程 `.env` 的登录 cookie——第三方既没有这个工程也没有这份凭据，这些文件在开源仓库里是死代码。
2. **合规风险**：逆向 ima.qq.com 未公开 web API + 复用作者 MCP 会话凭据抓取第三方平台内容（14 件国资法规，且 3 件因解析缺口最终仍改用官方源替换——README:117 自己承认质量不可靠），与 LICENSE 附加声明"只取公开公示数据"冲突；私有 KB ID `7343537326666625` 属他人（创建者"法苑文道"）创建的知识库，公开指向无必要。
3. **主题无关**：ima_uploader / ima_audit 是把本地库同步到**作者个人的腾讯 ima 知识库**的云工具（需 IMA_CLIENT_ID/IMA_API_KEY + gitignored 的 folders.json/kb_id.txt，后者导致新 clone import 即崩）——与数据采集流水线无关，属个人运维工具。
4. **替代闭环**：该专题 11 件增量已入 manifest.csv、README 有完整来源与处置记录；数据可复现性不依赖这些脚本（3 件已改官方源，其余为范围外规范性文件，官方渠道可达）。移出脚本不损失任何开源价值。
5. **次优方案**（若作者坚持保留）：仅保留 ima_uploader（OpenAPI 官方接口、密钥走环境变量），修复 E:\ 路径与模块级 folders.json 读取、去掉 ssl=False，并挪到独立的 `extras/ima/` 目录 + 显著免责声明；其余 7 个（私有依赖/凭据读取/一次性 intake）无论如何都应移出。

---

## 六、开源就绪其余结论

- **.gitignore**：抽查通过——该忽略的都忽略了（work/lists 含 cookie 与进度、work/ima_upload 含 kb_id/edge_profile/cookies、downloads/mirrors/tmp/logs/verify、lawlibrary 数据 + 根目录 zip、法规目录索引）；`!lawlibrary/manifest.csv` 反向规则生效；无"不该忽略被忽略"。唯一残留：`work/taxcase/pr.out` 先提交后加规则（P2-8）。
- **敏感信息**：`git ls-files` 全量扫描无 cookie/token/.env/kb_id 被跟踪；硬编码 KB ID 仅在 ima 脚本与 README 叙述中（随 P0-2 处理）。
- **文档交叉引用**：50 个 tracked .md 的链接与反引号路径程序化校验，`](path)` 形式 **0 失断链**；7 处反引号路径指向未分发数据目录（lawlibrary/专题/...、work/taxcase/tmp/...）——均为叙述性数据路径，非文档错误。
- **作者/许可/数据边界一致性**：LICENSE（MIT + 数据边界附加声明）、README（L3 badge/L149-153）、.gitignore（数据不入库的实际执行）三方口径一致；仅 README:7 "28,000+" 数字与自身表格矛盾（P2-9）、P1-9 措辞矛盾需统一。
- **skill 获取方式**：README L29 声称配套 skill 但未给获取途径，且 L58/L136 名称写错（china-law-aque ≠ china-law-obtain）——P1-5/P1-6。
- **快速开始命令核对**：第 1、2 条命令因硬编码 E:/ 必失败（P0-1）；第 3-5 条（quality_prune2 / structure_extract / build_manifest）路径全部 `__file__` 相对、可运行，但依赖前两条产出的数据；pip 依赖清单缺 requests/pycryptodome（P1-3）。

**修复顺序建议**：P0-1（路径参数化，机械性改动）→ P0-2（ima 移出，git rm + README 两处删改）→ P1-1/P1-2（11 处路径常量）→ P1-3~P1-7（README/requirements 事实修正）→ P1-9（措辞统一）→ P2 择机。
