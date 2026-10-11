# adapters/ 开源前适配器深度审查报告

- 审查范围：`work/taxcase/adapters/` 全部 **65 个 .py**（任务书写 66，实际 .py 为 65 个，另有 1 个 `hn_xzcf_loop.sh`，一并覆盖；本报告按 66 个文件计）。每个文件均已打开通读，未抽样。
- 审查日期：2026-10-11　审查方式：只审不改。
- 语法验证：65/65 全部通过 `ast.parse`；无 BOM、无 shebang、无重复 coding 声明。

## 总结论

整体质量高于预期：**无「import 即执行采集」的文件**（唯一无 main 守卫的 `js_hanweb.py` 是纯库模块，顶层无网络调用）；网络调用普遍带 timeout（40–300s）与 2–4 次重试；断点（progress jsonl）与文件名冲突处理基本齐备。**开源阻断项集中在两处**：① 1 个硬编码 `sys.path`（P0，跨机器 import 即失败）；② 15 个文件 17 处硬编码 `E:/ai_coding_xiangmu/...` 输出路径（P1）。另有 10 个一次性侦察/测试脚本应移出 adapters/。

**P0 = 1 项；P1 = 8 项（涉及 24 个文件）；P2 = 若干（不影响运行）。建议归档/删除 10 个，特殊处理 1 个。**

---

## 一、发现清单

### P0（致命：路径错误 / import 失败）

| # | 位置 | 问题 |
|---|------|------|
| P0-1 | `js_hanweb.py:37` | `sys.path.insert(0, r"E:\ai_coding_xiangmu\China_Law\work\taxcase")` 硬编码绝对路径。换任何机器/目录该 path 不存在 → `import taxcase_scrape` 直接 ImportError，连带 `js_run.py`、`js_run2.py`（江苏全链路）不可用。修复：改为 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`。 |

（「import 即执行采集」类 P0：**0 个**。已逐文件核对顶层语句。）

### P1（开源阻断 / 可靠性重大）

| # | 位置 | 问题 |
|---|------|------|
| P1-1 | 15 文件 17 行硬编码 `E:/ai_coding_xiangmu/...` 输出路径 | 见下方明细。均为输出目录常量，换机器即写入失败或写错盘。修复模式统一：`LAWLIB = normpath(join(ROOT,"..","..","lawlibrary"))`（仓库内 45 个文件已用此模式，照抄即可）。 |
| P1-2 | 全部 66 文件 | `out_dir` / `progress` / `tmp` **无任何 CLI 参数或环境变量可配置**，全部为模块常量。开源后使用者无法指定输出位置。建议统一加 `--out-root`（或 `CHINA_LAW_ROOT` env）覆盖 `LAWLIB` 推导。 |
| P1-3 | `sd_sc_weixin.py:21` | 模块 import 时执行 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, ...)`。在 stdout 无 `.buffer` 的环境（pytest 捕获、部分 IDE）**import 即崩溃**；且污染导入方全局 stdout。应移入 main 或加 try。 |
| P1-4 | `hn_xzcf.py:28`、`ln_sword.py:51` | 模块级 `OCR = ddddocr.DdddOcr(show_ad=False)`：import 即加载 onnx 模型（重副作用）；未安装 ddddocr 时 import 失败，且这两个文件的验证码路径无法绕过。应移入函数内惰性初始化。 |
| P1-5 | `jx_xzcf_r7.py`（main, L363-404） | `ThreadPoolExecutor(max_workers=4)` 并发抓取同一站点，**违反 AGENT_BRIEF「单线程、delay≥2.5s、禁止并发轰站」的合规红线**；每页 shutdown/renew 线程池的写法也易泄漏。 |
| P1-6 | `csrc_penalty.py:72`、`mof_checks.py:44`、`ln_sword.py:148`、`hbcq_md.py:110/315-316` | 直接 `open()` 预生成的 tmp 文件（csrc_list.json / mof_sel.json / ln_swjgdm_all.json / hb_cq 系列 jsonl）且**无存在性检查**——采集链未跑过则裸 FileNotFoundError，且这 4 个 tmp 文件的生成脚本不在 adapters/ 内（一次性 inline 产出），开源后不可复现。 |
| P1-7 | `nb_r6.py:25`、`sx_nb.py:31-32` | tmp 输出写到**仓库根** `China_Law/tmp/sx_nb`（`ROOT/../..`），与其余 60+ 文件的 `work/taxcase/tmp` 约定不一致；开源打包若只含 work/ 会丢中间产物路径预期。 |
| P1-8 | `qd_hn_recon.py` 被生产文件依赖 | `hn_hardcase.py:20`、`hn_xzcf.py:19`、`qd_news.py:20`、`qd_sswf.py:19` 均 `from qd_hn_recon import pw_open`。它是侦察脚本（归档候选），却被 4 个生产 adapter 依赖——归档前必须先把 `pw_open` 抽到共享模块，否则一动就断。 |

**P1-1 硬编码路径明细（17 行 / 15 文件）**：

| 文件:行 | 内容 |
|---|---|
| csrc_penalty.py:31 | `ROOT = "E:/.../税务案例/证监会/涉税行政处罚"` |
| court_cases.py:31 | `ROOT = "E:/.../最高人民法院"` |
| mof_checks.py:29 | `ROOT = "E:/.../财政部/会计信息质量检查公告"` |
| national_12366.py:43,44 | `LIB` + `OUT_DIR`（44 行的 OUT_DIR 为死变量，FLAGS 用的是 LIB 拼接） |
| gd_cases.py:44 | `OUT_ROOT = "E:/.../广东省"` |
| gd_random_inspection.py:35 | 同上 |
| gd_city_cases.py:43 | 同上 |
| sh_xzcf.py:36 | `OUT_DIR = "E:/.../上海市/行政处罚公示"` |
| sh_wsgg.py:34 | `OUT_DIR = "E:/.../上海市/文书送达公告"` |
| sh_swxw.py:36,45 | 两个 source 的 `"out"` 各一处 |
| sz_cases.py:45 | `OUT_ROOT = "E:/.../深圳市"` |
| js_run.py:31 | `ROOT = r"E:\...江苏省"` |
| cta_swhg.py:18-19 | `OUT = ("E:/.../国家税务总局/税务合规典型企业案例")` |
| spp_cases.py:31 | `ROOT = "E:/.../最高人民检察院"` |
| zj_news_cases.py:33 | `ROOT = "E:/.../浙江省"` |

（另：`hn_xzcf_loop.sh` 内 `cd /e/ai_coding_xiangmu/...` 也是硬编码，随 .sh 一并处理。）

### P2（改进项，不阻断运行）

1. **抓取日期硬编码**（应为 `date.today()`）10 文件：ah_cities_r5(2026-10-10)、fj_cities_r7、hi_news_r7、hn_cities_r7、jx_xzcf_r7、gx_r7、gz_r7、gz_xzcf_r7、yn_r7、yn_xzcf_r7（后七个 TODAY="2026-10-11"）。开源后再运行会盖错日期戳。
2. **front matter 超出 AGENT_BRIEF 8 字段**：hlj_r7 / jl_r7 / ln_sword_md / qd_md（qd_xzcf extra）额外写 `记录KEY:`、`决定书文号:`——非规范字段，若下游按字段白名单解析需确认兼容。
3. **r7_md.py / sx_nb_md.py 的 write_md 不转义值内双引号**（其它 adapter 均做 `.replace(chr(34),'')`），值含 `"` 会产出非法 YAML；r7_md 发布日期回退用 `0000-00-00`（其它文件用 `nodate`）。
4. **文件名冲突策略不一致**：多数「exists 即跳过」；gx/gz/yn 系列做 `_k` 序号 + 内容（原文链接）校验（最佳实践，建议推广）；bj_all.write_md、gd_cases.save_article、gd_city_cases、tj_news、sh 系列直接覆盖写（同名不同记录会静默覆盖，靠 progress 降低概率）。
5. 死代码/笔误：r7_md.py:17-18 `if False else` 残留；hbcq_md.py:203 无效 lambda；sh_xzcf.py:94 `.strip("?xzcfswh=")` 误当前后缀剥离（幸而 url 未使用）；qd_md.py docstring 写的用法名 `qd_hn_md.py` 与文件名不符；national_12366.py:44 OUT_DIR 死变量。
6. qd_news.py:50-60 `fetch_in` 若 3 次尝试全部在 evaluate 处抛异常，循环后 `return r` 引用未绑定变量 → NameError。
7. ln_sword.py `S.verify=False` + `warnings.filterwarnings("ignore")`（禁证书校验，安全弱化）。
8. 超时偏大（150–300s）：hi_news_r7、hn_cities_r7、jx_xzcf_r7、nmg_r7(300)、sx7(300)、gx/gz/yn(200)。可接受但拖长失败恢复。
9. import 级 `os.makedirs` 副作用（无害但不符合库礼仪）：cta_swhg、gx_r7、gz_r7、gz_xzcf_r7、yn_r7、hb_r7、hbcq_cq、hbcq_hb、hbcq_river、sc_river、sx7、sx_nb、nmg_r7、qd 系列、hn_hardcase、hn_xzcf。
10. cta_swhg.py 使用 `t.random` / `t._last_ts`（taxcase_scrape 私有成员，重构公共库时会碎）。
11. 平台依赖：js_hanweb.py 旧 .doc 走 Windows Word COM（win32com，仅 Windows+Office 可用，已有失败回退）；hn_xzcf_loop.sh 为 bash（内含硬编码路径）。
12. sx_nb.py 验证码需人工识别写入 `tmp/captcha_answer.txt`（半自动流程，文档应注明）；bj_all/hb_r7/hbcq 系列为有头浏览器方案（headless=False，开源用户需 GUI 环境）——docstring 已写明原因（瑞数），属已知设计。

### 断点（progress）与规范一致性核对

- 全部 progress jsonl 都落在 `work/taxcase/progress/`（`t.PROG_DIR` 或 `ROOT/progress`，二者同目录），命名 `<job>.jsonl`，无冲突重名。跨 progress 去重的文件（gd_random_inspection、gd_city_cases 读 gd_cases.jsonl）逻辑正确。
- front matter 8 字段（title/来源机关/栏目/地区/发布日期/原文来源/抓取日期/原文链接）在 60+ 文件中拼写一致；偏差仅 P2-2 所列附加字段。
- 文件名 `{发布日期}_{safe_filename(标题)}.md` 全仓一致（r7_md/sx_nb_md 另附 key 短缀，见 P2-4）。

### 水印副作用核查（维度 6）

65/65 文件：首行 `# -*- coding: utf-8 -*-` 位置正确（PEP263 第 1–2 行内）；无 shebang 被顶掉（原文件本无 shebang）；无 BOM；无第二处 coding 声明；`__author__`/`__copyright__` 位于 docstring 之前合法；全部通过语法解析。**水印插入未破坏任何文件的执行。**

### 可运行性核查（维度 2）

- sys.path 基准：49 个文件用 `HERE/ROOT = dirname(dirname(abspath(__file__)))` 模式 → 从仓库任意 cwd 直接 `python adapters/xxx.py` 均可找到 `taxcase_scrape`；taxcase_scrape 依赖的 `polite_get/extract_detail/safe_filename/load_progress/PROG_DIR/MarkdownConverter/_last_ts/random` 全部存在（已核对源码）。
- `quality_prune.decide`（fj/gx/gz/hlj/jl/hbcq_md/ln_sword_md/qd_md/r7_md/sx_nb_md/sc 系列引用）位于 `work/taxcase/quality_prune.py`，sys.path 正确可达。
- 例外：js_hanweb.py（P0-1）；gd_random_inspection.py 依赖 `gd_cases`（同目录，正确）；hn/qd 四文件依赖 qd_hn_recon（P1-8）。
- 二进制依赖面：curl_cffi（主力）、playwright+chromium（有头）、ddddocr（渝/湘/辽）、openpyxl、pymupdf、python-docx、bs4、markdownify、requests、PIL（sx_nb）。开源需在 README 列全。

---

## 二、66 文件逐一状态表

硬编码=文件内 `ai_coding_xiangmu` 出现行数；可运行=按仓库根布局 `python work/taxcase/adapters/<f>` 是否能跑（依赖齐备前提下）。

| # | 文件 | 硬编码行 | 可运行 | 级别 | 备注 |
|---|------|:--:|:--:|:--:|------|
| 1 | ah_cities_r5.py | 0 | 是 | P2 | 抓取日期硬编码 |
| 2 | bj_all.py | 0 | 是 | P2 | write_md 无 exists 检查；有头 playwright |
| 3 | court_cases.py | 1(L31) | 否* | P1 | *硬编码 ROOT；余良好 |
| 4 | csrc_penalty.py | 1(L31) | 否* | P1 | 另依赖 tmp/csrc_list.json（无检查，P1-6）；save() 只打印不落盘 |
| 5 | cta_swhg.py | 1(L18) | 否* | P1 | import 即 makedirs；用 t._last_ts/t.random 私有成员 |
| 6 | fj_cities_r7.py | 0 | 是 | P2 | 抓取日期硬编码；was5 重试+超时齐 |
| 7 | gd_cases.py | 1(L44) | 否* | P1 | 干净，仅路径 |
| 8 | gd_city_cases.py | 1(L43) | 否* | P1 | 附件抽取（docx/pdf）+预算控制，设计好 |
| 9 | gd_random_inspection.py | 1(L35) | 否* | P1 | 跨 progress 去重正确 |
| 10 | gx_r7.py | 0 | 是 | P2 | 冲突处理最佳（_k+内容校验）；TODAY 硬编码 |
| 11 | gz_r7.py | 0 | 是 | P2 | 同 gx 模式；timeout=200 |
| 12 | gz_xzcf_r7.py | 0 | 是 | P2 | 同上；fetch 未查 status_code 即 r.json() |
| 13 | hb_r7.py | 0 | 是 | P2 | 原始 jsonl 落 tmp/hb_r7（供 r7_md） |
| 14 | hbcq_cq.py | 0 | 是 | P2 | ddddocr 过码；有头；tmp 原始层 |
| 15 | hbcq_hb.py | 0 | 是 | P2 | 同上 |
| 16 | hbcq_md.py | 0 | 是* | P1 | *输入 jsonl 缺失即崩（P1-6）；死 lambda L203 |
| 17 | hbcq_recon2.py | 0 | 是 | 归档 | 一次性侦察 |
| 18 | hbcq_recon3.py | 0 | 是* | 归档 | tmp 无 makedirs（先跑过 recon2 才不崩） |
| 19 | hbcq_recon4.py | 0 | 是* | 归档 | 同上 |
| 20 | hbcq_recon5.py | 0 | 是* | 归档 | 同上 |
| 21 | hbcq_recon6.py | 0 | 是* | 归档 | 同上 |
| 22 | hbcq_recon7.py | 0 | 是* | 归档 | 同上 |
| 23 | hbcq_recon8.py | 0 | 是* | 归档 | 同上 |
| 24 | hbcq_river.py | 0 | 是 | 归档 | harvest 部分 SystemExit 占位未实现 |
| 25 | hi_news_r7.py | 0 | 是 | P2 | timeout=150；抓取日期硬编码 |
| 26 | hlj_r7.py | 0 | 是 | P2 | FM 加 记录KEY 字段；动态日期 |
| 27 | hn_cities_r7.py | 0 | 是 | P2 | timeout=150；抓取日期硬编码 |
| 28 | hn_hardcase.py | 0 | 是 | P1 | 依赖 qd_hn_recon（P1-8）；断点续跑完整 |
| 29 | hn_hardcase_test.py | 0 | 是 | 归档 | 接口冒烟测试 |
| 30 | hn_xzcf.py | 0 | 是 | P1 | 模块级 ddddocr（P1-4）；依赖 qd_hn_recon |
| 31 | hn_xzcf_loop.sh | 1(cd行) | 否 | P1 | bash 循环驱动；内含 /e/ 硬编码路径 |
| 32 | jl_r7.py | 0 | 是 | P2 | FM 加 记录KEY；playwright 惰性导入（好） |
| 33 | js_hanweb.py | 1(L37) | **否** | **P0** | 硬编码 sys.path；库模块无 main 守卫（合理）；Word COM Win-only |
| 34 | js_run.py | 1(L31) | 否* | P1 | *ROOT 硬编码；argv 式 main |
| 35 | js_run2.py | 0 | 否* | P1 | 随 js_run/js_hanweb 断链 |
| 36 | jx_xzcf_r7.py | 0 | 是 | P1 | 4 线程并发违反单线程红线（P1-5）；抓取日期硬编码 |
| 37 | ln_sword.py | 0 | 是* | P1 | *codes json 缺失即崩（P1-6）；模块级 ddddocr；verify=False |
| 38 | ln_sword_md.py | 0 | 是 | P2 | FM 加 决定书文号/记录KEY |
| 39 | ln_sx.py | 0 | 是 | P2 | LMCL 挑战解码自包含，干净 |
| 40 | mof_checks.py | 1(L29) | 否* | P1 | 依赖 tmp/mof_sel.json（P1-6） |
| 41 | national_12366.py | 2(L43,44) | 否* | P1 | L44 OUT_DIR 死变量；分片 worker 设计好 |
| 42 | nb_r6.py | 0 | 是 | P1 | tmp 写到仓库根（P1-7） |
| 43 | nmg_r7.py | 0 | 是 | P2 | timeout=300；原始层+离线转换分离 |
| 44 | qd_hn_recon.py | 0 | 是 | P1 | 被 4 个生产文件 import（P1-8），不能直接归档 |
| 45 | qd_md.py | 0 | 是 | P2 | docstring 文件名笔误；conv_generic 泛化好 |
| 46 | qd_news.py | 0 | 是 | P2 | fetch_in 潜在 NameError |
| 47 | qd_recon2.py | 0 | 是 | 归档 | 一次性侦察 |
| 48 | qd_sswf.py | 0 | 是 | P2 | 依赖 qd_hn_recon |
| 49 | qd_xzcf.py | 0 | 是 | P2 | 平台内联表解析 |
| 50 | r7_md.py | 0 | 是 | P2 | `if False` 死代码；YAML 引号不转义；0000-00-00 回退 |
| 51 | sc_river.py | 0 | 是 | P2 | 大而全（cols/xz/sx/etax）；import 级 makedirs×4 |
| 52 | sc_river_md.py | 0 | 是 | P2 | 离线转换，被 sc_river --part md 调用 |
| 53 | sd_sc_weixin.py | 0 | 是* | P1 | *import 重包 stdout（P1-3）；反爬冷却设计好 |
| 54 | sh_swxw.py | 2(L36,45) | 否* | P1 | 硬编码 out×2 |
| 55 | sh_wsgg.py | 1(L34) | 否* | P1 | 硬编码 OUT_DIR |
| 56 | sh_xzcf.py | 1(L36) | 否* | P1 | 硬编码 OUT_DIR；L94 strip 误用 |
| 57 | spp_cases.py | 1(L31) | 否* | P1 | 硬编码 ROOT；死链302判别好 |
| 58 | sx7.py | 0 | 是 | P2 | 名字像 recon 实为山西正式收割，**保留** |
| 59 | sx_nb.py | 0 | 是 | P1 | tmp 写仓库根（P1-7）；人工验证码文件 |
| 60 | sx_nb_md.py | 0 | 是 | P2 | YAML 引号不转义 |
| 61 | sz_cases.py | 1(L45) | 否* | P1 | 硬编码 OUT_ROOT |
| 62 | tj_news.py | 0 | 是 | P2 | job 配置化最规范的一个 |
| 63 | xz_r7.py | 0 | 是 | P2 | 干净 |
| 64 | yn_r7.py | 0 | 是 | P2 | TODAY 硬编码；冲突处理佳 |
| 65 | yn_xzcf_r7.py | 0 | 是 | P2 | 同上 |
| 66 | zj_news_cases.py | 1(L33) | 否* | P1 | 硬编码 ROOT |

\* "否\*" = 代码逻辑本身可跑，仅因硬编码路径/缺失 tmp 前置文件在本机以外环境不可复现。

---

## 三、建议归档/删除的一次性脚本（10+1 条）

移至 `work/taxcase/adapters/_recon/`（或直接删除，git 历史可寻回）：

1. hbcq_recon2.py
2. hbcq_recon3.py
3. hbcq_recon4.py
4. hbcq_recon5.py
5. hbcq_recon6.py
6. hbcq_recon7.py
7. hbcq_recon8.py
8. qd_recon2.py
9. hn_hardcase_test.py（接口冒烟，任务已完成）
10. hbcq_river.py（recon 框架，harvest 永久 SystemExit 占位，功能已被 hbcq_cq/hbcq_hb 取代）

特殊处理（不建议直接移）：

11. **qd_hn_recon.py** —— 名为 recon，实为 `pw_open` 共享库：`hn_hardcase.py`、`hn_xzcf.py`、`qd_news.py`、`qd_sswf.py` 四个生产文件 import 它。正确做法：把 `pw_open`（连同其依赖 `body_text_len`）抽到 `work/taxcase/` 公共层或新 `browser_common.py`，四处改 import 后再归档 qd_hn_recon.py；否则归档动作会制造 4 个 P0。

另：`hn_xzcf_loop.sh` 建议随湖南链路保留但去掉 `cd /e/...` 硬编码（改 `cd "$(dirname "$0")/.."`）。

## 四、开源前修复优先序（供执行参考）

1. P0-1：js_hanweb.py sys.path 相对化（一行改动，解锁江苏链路 3 文件）。
2. P1-1：15 文件 17 行输出路径改相对（统一照抄 ah_cities_r5.py 的 LAWLIB 模式）。
3. P1-2：加 `--out-root`/env 覆盖（建议只做一层：所有文件读 `CHINA_LAW_ROOT` env，缺省走相对推导）。
4. P1-3/P1-4：sd_sc_weixin stdout 重包、hn_xzcf/ln_sword 模块级 OCR 移入函数。
5. P1-5：jx_xzcf_r7 并发降为单线程（与合规承诺一致）。
6. P1-6：4 处 tmp 前置文件加存在性检查 + 友好报错（或补齐生成脚本）。
7. P1-8：抽 pw_open → 归档 11 个 recon/test。
8. P2 批量项：TODAY 动态化、YAML 引号转义、冲突处理统一为 gx 模式。
