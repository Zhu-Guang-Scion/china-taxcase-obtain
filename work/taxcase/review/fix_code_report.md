# 开源审查修复报告 —— 代码修复（fix_code_report.md)

- 修复智能体：A（按审查报告修代码，只修 P0/P1，不做重构）
- 日期：2026-10-11
- 范围：`E:\ai_coding_xiangmu\China_Law` 工作区（git 跟踪中，未 commit）
- 对照审查报告：`work/taxcase/review/`（core.md / adapters.md / security.md）
- 验证方式：每步 `ast.parse`；收尾对全部 .py（git 跟踪 + 新增/移动文件并集，共 304 个）跑 ast 全量；`git grep` 确认 `E:\ai_coding_xiangmu` / `E:/ai_coding_xiangmu` 在跟踪中的 .py/.json 内零残留。

---

## 1. [P0] js_hanweb.py:37 硬编码 sys.path —— 完成

- 文件：`work/taxcase/adapters/js_hanweb.py`
- 改动：`sys.path.insert(0, r"E:\...\work\taxcase")` → 基于 `__file__` 动态定位
  （`os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`），支持 `CHINALAW_ROOT`
  环境变量覆盖；补 `import os`。
- 验证：ast.parse OK；adapters REPO 定位单测解析到仓库根。

## 2. [P0] 硬编码输出路径可移植化 —— 完成（22 处文件）

统一模式：`REPO = os.environ.get("CHINALAW_ROOT", <按 __file__ 定位的仓库根>)`，
输出路径改为 `os.path.join(REPO, "lawlibrary", ...)`；每处带注释
`# 可移植化（审查修复）：支持 CHINALAW_ROOT 环境变量`。

| 文件 | 改动 |
| --- | --- |
| adapters/court_cases.py | ROOT（最高法） |
| adapters/csrc_penalty.py | ROOT（证监会涉税行政处罚） |
| adapters/cta_swhg.py | OUT（总局税务合规典型企业案例） |
| adapters/gd_cases.py / gd_city_cases.py / gd_random_inspection.py | OUT_ROOT（广东省） |
| adapters/mof_checks.py | ROOT（财政部会计信息质量检查公告） |
| adapters/national_12366.py | LIB + OUT_DIR（OUT_DIR 改为 join(LIB, ...)） |
| adapters/sh_swxw.py | TARGETS 内两处 "out"（上海市税案通报/稽查公布） |
| adapters/sh_wsgg.py / sh_xzcf.py | OUT_DIR（上海市文书送达公告/行政处罚公示） |
| adapters/spp_cases.py | ROOT（最高检） |
| adapters/sz_cases.py | OUT_ROOT（深圳市） |
| adapters/zj_news_cases.py | ROOT（浙江省） |
| adapters/js_run.py | ROOT（江苏省，原 r"E:\..." 形式） |
| work/taxcase/ocr_fill.py | sys.path / LIB / PROG / TMP 全部动态化；CLI 改 `MINERU_CLI` env + `shutil.which` 回退；仓库外 `E:\ai_coding_xiangmu\MinerU高并发脚本\config.json` 改 `MINERU_TOKEN_CONFIG` env（空则只用 MINERU_TOKEN/MINERU_TOKENS） |
| work/scripts/cicpa_guide_supp.py | OUT_DIR / LIST_OUT |
| work/scripts/cicpa_enum.py | OUT |
| work/scripts/cicpa_std_download.py | OUT_DIR / LIST_OUT / ENUM / LOGS |
| work/scripts/fgk_search.py | sys.path 相对本文件（原 E:\ 硬编码），补 `import os` |
| work/scripts/mineru_upgrade.py | CLI 改 `os.environ.get("MINERU_CLI", shutil.which("mineru-open-api") or "mineru-open-api")` |
| work/taxcase/jobs/cta_shuiantongbao.json | out_dir 改相对路径 `lawlibrary/专题/税务案例/国家税务总局/税案通报`（配合下条） |
| work/taxcase/taxcase_scrape.py | run_job 支持相对 out_dir：非绝对路径时相对 **CWD** 解析，docstring 同步说明 |

- 说明：审查清单中提到的 `fetch_urumqi.py / std_gov_acct.py / kjs_enum.py / kjs_cas_download.py`
  经核查**已是** `__file__` 相对定位（无 E:\ 常量），无需改动（见"残留未修项"末尾备注）。
- 验证：ast.parse 全部 OK；REPO 解析单测通过；`python -c` 从仓库根解析相对 out_dir
  得到既有目录（存在性 OK）；jobs json `json.load` OK。

## 3. [P1] 水印 __author__ 位置（__doc__ 失效）—— 完成

- 新增逻辑：`add_watermark.py` 增加 `_insert_after_docstring()`——用 ast 定位模块
  docstring 的 `end_lineno`，`__author__`/`__copyright__` 插到 docstring 之后；
  版权头仍插在 coding 行后最前。docstring 顶部说明同步更新。
  冒烟测试：含水印输出的临时文件 `ast.get_docstring()` 非空且 __author__ 在
  docstring 之后；无 docstring 文件退化为头部后直插。
- 存量修复：一次性脚本把紧跟版权头、位于 docstring 之前的
  `__author__ = "Zhu-Guang-Scion"` / `__copyright__ = ...` 两行移动到模块
  docstring 之后，共 **105 个** .py（逐文件 ast 验证 `__doc__` 非空后才落盘）。
- 验证：全库 `__author__` 且 `ast.get_docstring()` 为 None 的文件从 109 降为 4
  （这 4 个是 fetch_urumqi.py / moji_analyze.py / moji_drill.py / moji_verify.py
  —— 本来就没有模块 docstring，与 __author__ 位置无关，非本次缺陷，未补写 docstring
  以避免越界改动）。

## 4. [P1] 侦察脚本归档 —— 完成

- 新增 `adapters/pw_common.py`：从 qd_hn_recon.py 抽出 `pw_open` / `body_text_len`
  / `log`（playwright 过墙公共逻辑）。
- 改 4 个生产 import 方：`qd_news.py`、`qd_sswf.py`、`hn_hardcase.py`、`hn_xzcf.py`
  的 `from qd_hn_recon import pw_open` → `from pw_common import pw_open`。
  （审查清单写的 qd_xzcf.py 经 grep 实际不 import qd_hn_recon，真正的第 4 个是
  hn_xzcf.py。）
- 移入 `adapters/_recon/`（mv，git 会在 commit 时识别 rename）共 11 个：
  hbcq_recon2~8.py（7 个）、qd_recon2.py、hn_hardcase_test.py、hbcq_river.py、
  qd_hn_recon.py。hn_hardcase_test.py 的 import 同步改为从上级 adapters 取
  pw_common。
- 新增 `adapters/_recon/README.md`：说明为过程脚本归档、生产勿 import。
- `hn_xzcf_loop.sh`：`cd /e/ai_coding_xiangmu/...` → `cd "$(cd "$(dirname "$0")" && pwd)/.."`。
- 验证：生产 adapters 目录 grep 无 qd_hn_recon import（仅 pw_common docstring 提及）；
  _recon/ 全部 ast.parse OK；pw_common 独立 import + `body_text_len` 调用 OK。

## 5. [P1] main 守卫 —— 完成

- `work/taxcase/repair_attachments.py`：全部执行体（遍历全库 + polite_get 重访）
  包进 `def main():`，加 `if __name__ == "__main__":`。
- `work/scripts/fetch_urumqi.py`：顶层 `with sync_playwright()`（import 即启动浏览器）
  包进 `main()` + 守卫。
- 排查方法：对 git 跟踪的全部 .py 找"无 __main__ 守卫 + 顶层（含一层嵌套）网络调用"，
  仅上述 2 个命中（work/taxcase/tmp/ 下还有几十个 explore_*.py 但均为 gitignore
  的未跟踪草稿，不入库，未处理）。其余无守卫文件（moji_* / build_catalog /
  xmlfallback / fixup39 / fgk_search 等）顶层只有本地文件处理，不在"顶层网络调用"
  范围，未动。
- 验证：两文件 ast.parse OK；import 侧不再触发网络（守卫遮蔽执行体）。

## 6. [P1] taxcase_scrape.py 三处 + quality_prune.py —— 完成

- `_norm_date()` 新增：容忍 `/` `.` 分隔与缺零填充，归一化 YYYY-MM-DD；
  应用于 `parse_list_items`（源头）、`run_job` 的 `ldate < date_from` 比较（含
  `date_from` 本身归一化）。
- static_list 首页回退 bug：删除默认值 `tpl.replace("{page}", "index.html")`
  （会拼出 `index_index.html.html`）；改为未给 `first_page_url` 时第一页 =
  `tpl.replace("{page}", "")`，并以注释 + 模块 docstring 说明约定（首页为独立
  index.html 的站点必须显式给 first_page_url）。当前无在用 static_list job，
  无行为回归面。
- docstring 与实现同步：模块 docstring 更新（out_dir 相对 CWD 解析约定、
  first_page_url 新约定、_norm_date 说明）。
- `quality_prune.py`（v1）：KEEP_COLUMNS 补 `"裁判文书"`（防误用 v1 重跑删判决书），
  文件头 docstring 加"已被 quality_prune2 取代，勿再执行 --go"警告。

## 7. [P1] 其他小项 —— 完成

- `sd_sc_weixin.py`：stdout 重包加 `hasattr(sys.stdout, "buffer")` 保护。
- `jx_xzcf_r7.py`：`--workers` 默认 4 → 1，help 注明"合规红线：单线程（审查修复
  自 4 降为 1）"。保留 CLI 可调参数未做硬限制（避免重构；默认值已合规）。
- `nb_r6.py` / `sx_nb.py`：TMP 从仓库根 `tmp/sx_nb` 统一到
  `work/taxcase/tmp/sx_nb`（`os.path.join(ROOT, "tmp", "sx_nb")`），docstring 的
  输出说明同步改。注意：旧目录 `<repo>/tmp/sx_nb` 下的历史缓存不会自动迁移，
  首次重跑会重建（进度断点在 progress/ 不受影响）。

## 8. 全量验证 —— 通过

- ast.parse：git 跟踪 .py（110）+ 新增/移动（_recon/ 11、pw_common.py）+ 工作区
  其余未跟踪 .py，合计 **304 个**：**0 语法错误**。
- 残留 grep：`git grep -F 'E:\ai_coding_xiangmu' -- '*.py' '*.json'` 与
  `git grep -F 'E:/ai_coding_xiangmu' -- '*.py' '*.json'` 均**零命中**（exit 1）。
  磁盘上仍含该串的只有：已 staged 删除的 `work/scripts/ima_*.py`（8 个，另一修复
  线程处理，不入库）、gitignore 的 `work/taxcase/tmp/`、`work/ima_upload/` 草稿。
- `.md` 文档中的路径引用按要求未改。

---

## 残留未修项（P2/范围外，明确不动）

1. **4 个无模块 docstring 的脚本**（fetch_urumqi.py、moji_analyze.py、moji_drill.py、
   moji_verify.py）：`__author__` 前置无害（无 docstring 可遮蔽）；补写 docstring
   超出"只修 P0/P1"边界。
2. **`jx_xzcf_r7.py` 并发可调**：`--workers` 仍可手动传 >1（默认已 1）。硬顶需改
   argparse 校验，属重构，未做。
3. **`fetch_urumqi.py` 的 CWD 相对输入** `work/lists/gov_...jsonl`：非 E:\ 硬编码，
   属约定问题（P2），未动。
4. **work/taxcase/tmp/ 下几十个 explore_*.py 草稿**：gitignore 未跟踪，审查范围外。
5. **`work/scripts/ima_*.py`（staged 删除）与 `work/ima_upload/`**：由安全修复线
   处理（.gitignore 已含 `work/scripts/ima_*.py`），本线未触碰。
6. **fetch_urumqi.py / std_gov_acct.py / kjs_* 的 "E:\ 常量"**：核查后确认这些文件
   本来就基于 `__file__` 定位，审查清单该项与实际不符，无需修复（记录在此）。
7. **P2 各项**（审查报告 core.md/adapters.md 中的其余 P2 建议）：按指令一律不动。

---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
