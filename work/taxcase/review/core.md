# China_Law 核心库深度代码审查（work/taxcase，开源前）

- 审查日期：2026-10-11
- 审查范围：taxcase_scrape.py / quality_prune.py / quality_prune2.py / quality_audit.py / structure_extract.py / build_manifest.py / caseopen_harvest.py / caseopen_to_md.py / repair_attachments.py / ocr_fill.py / add_watermark.py / jobs/cta_shuiantongbao.json
- 方法：逐行精读 + 运行时验证（AST 校验 `__doc__`、水印页脚对 quality 正则的实弹测试、manifest/corpus 数据取证）

## 总结论

**当前不建议直接开源发布。** 存在 1 个 P0（`build_manifest.py --prune` 会按 `原文链接` 批量误删合法文书，数据中已坐实 14038 个"重复"标记）与 6 个 P1（水印破坏全部 10 个模块的 `__doc__`、ocr_fill.py 七处硬编码绝对路径含仓库外路径与 Windows-only `.cmd`、日期比较用未归一化的字符串字典序、static_list 首页回退 URL 拼错、repair_attachments 无 main 守卫即 import 即跑全网重访、quality_prune v1 重跑会整批删除裁判文书）。断点续跑（append-only jsonl）语义在四个脚本中实现正确。水印页脚不含 UNIT_RE/VERB_RE/OUTCOME_MARK 任何关键词（"元"字担忧证伪），但含 4 个数字（"2026"），在 quality_prune2 的短文档回退路径上可把边界样本翻成 KEEP——当前库内 md 未被加水印（gitignored），该风险未实际发生。

---

## 发现清单

### P0

**[P0-1] build_manifest.py:65-69 + caseopen_to_md.py:66 —— `--prune` 按 `原文链接` 去重会整批静默删除合法文书（数据已坐实）**
- 根因 A：caseopen_to_md.py:66 给全部 1838 份裁判文书写同一个 `原文链接: https://caseopen.org/`。
- 根因 B：山东（2965 份，`https://shandong.chinatax.gov.cn/zfgspt/extranet/xzcf`）、河北（1874 份，`<http://wzyy.hebei...>`）的详情页 URL 是共享列表页/平台页（适配层写入）。
- 后果 1：manifest.csv 已把 **14038/31764** 行标为"重复"——其中大量是内容互不相同的不同案件。
- 后果 2：一旦执行 `python build_manifest.py --prune`，山东删 2964 份、河北删 1873 份、裁判文书删 1837 份，`os.remove` 无确认无备份。
- 后果 3（已发生）：taxcase_corpus.jsonl 的 `id = md5(url)[:16]`，31764 行仅 **17726 个唯一 id**（2965 行共用一个 id、1874 行共用一个、1838 行共用一个），训练语料 id 失效。
- 建议（三处都要修）：
  1. caseopen_to_md.py 写逐案链接：
     ```python
     doc_id = c.get("doc_id") or c.get("id") or c.get("case_id") or ""
     f"原文链接: https://caseopen.org/case/{doc_id}\n"   # 以站点真实路由为准
     ```
  2. build_manifest.py 去重键改为 `url + 标题`（共享列表页 URL 的不同案件标题不同），且 `--prune` 前对共享 URL 数量做熔断：
     ```python
     url_m = re.match(r"^<?(https?://\S+?)>?$", url)          # 顺带归一 <url> 与尾斜杠
     url_key = url_m.group(1).rstrip("/") if url_m else url
     dedup_key = (url_key, fm.get("标题", fm.get("title", "")))
     if url_key and url_key in seen:
         shared = url_counts[url_key]
         if args.prune and shared > 50:
             print(f"WARN 跳过: {url_key} 被 {shared} 个文件共享，疑似列表页URL"); continue
         ...
     ```
  3. corpus id 永远掺入文件名兜底：`hashlib.md5((url_key + "|" + fn).encode()).hexdigest()[:16]`。

### P1

**[P1-1] add_watermark.py:22,41 —— `__author__` 赋值插在模块 docstring 之前，10 个核心模块 `__doc__` 全部失效（已 AST 验证）**
- `__author__ = "..."` 是语句；docstring 必须是模块第一条语句。现在 `taxcase_scrape.__doc__` 等 10 个模块均为 `None`（仅 add_watermark.py 自身幸免）。`help()`/pydoc/Sphinx autodoc/doctest 全部拿不到文档——文档字符串写得很认真，却一个字都读不到，开源观感极差。
- 顺带：shebang 未受影响（这些文件本无 shebang），`# -*- coding -*-` 仍在第 1 行，PEP 263 合规。
- 修复 wm_py（docstring 之后插属性）：
  ```python
  import ast
  def wm_py(p):
      src = open(p, encoding="utf-8").read()
      if MARK in src: return False
      lines = src.split("\n"); i = 0
      if lines and lines[0].startswith("#!"): i = 1
      if i < len(lines) and re.match(r"# -\*- coding", lines[i]): i += 1
      out = "\n".join(lines[:i]) + "\n" + PY_HDR + "\n".join(lines[i:])   # 只插注释头
      if "__author__" not in src:
          tree = ast.parse(out)
          ls = out.split("\n")
          if tree.body and isinstance(tree.body[0], ast.Expr) \
             and isinstance(tree.body[0].value, ast.Constant):
              ls.insert(tree.body[0].end_lineno, PY_ATTR.rstrip("\n"))    # docstring 之后
          else:
              out = out.replace(PY_HDR, PY_HDR + PY_ATTR, 1)
              open(p, "w", encoding="utf-8", newline="\n").write(out); return True
          out = "\n".join(ls)
      open(p, "w", encoding="utf-8", newline="\n").write(out); return True
  ```
- 存量修复：把 10 个文件里第 7-8 行的 `__author__`/`__copyright__` 挪到 docstring 结束引号之后即可（一行 sed/手工皆可）。

**[P1-2] ocr_fill.py:25-31,144 —— 七处硬编码绝对路径，含仓库外路径与 Windows-only 依赖，开源即不可用**
逐处列出：
  - :25 `sys.path.insert(0, r"E:\ai_coding_xiangmu\China_Law\work\taxcase")`
  - :28 `LIB = r"E:\...\lawlibrary\专题\税务案例"`
  - :29 `PROG = r"E:\...\progress\js_ocr_scan.jsonl"`
  - :30 `TMP = r"E:\...\tmp\ocr_dl"`
  - :31 `CLI = r"C:\Users\Administrator\AppData\Roaming\npm\mineru-open-api.cmd"`（npm 的 Windows 包装器，POSIX 上直接 FileNotFoundError，且无任何标注）
  - :144 `E:\ai_coding_xiangmu\MinerU高并发脚本\config.json`（**仓库外**的私有 token 配置，静默 except 吞掉）
  - 对照：同目录其余脚本全部 `__file__` 相对定位，唯独此文件用绝对路径。
- 修复：
  ```python
  HERE = os.path.dirname(os.path.abspath(__file__))
  sys.path.insert(0, HERE)
  LIB = os.path.normpath(os.path.join(HERE, "..", "..", "lawlibrary", "专题", "税务案例"))
  PROG = os.path.join(HERE, "progress", "js_ocr_scan.jsonl")
  TMP = os.path.join(HERE, "tmp", "ocr_dl")
  CLI = os.environ.get("MINERU_CLI", "mineru-open-api")   # 去 .cmd，靠 PATH
  # load_tokens 里：
  cfg = os.environ.get("MINERU_TOKEN_CONFIG", os.path.join(HERE, "mineru_tokens.example.json"))
  ```
  并在模块 docstring 标注 "MinerU CLI 需另行安装，Windows 下为 .cmd，POSIX 下请设 MINERU_CLI"。

**[P1-3] taxcase_scrape.py:294（配合 :135-137）—— `date_from` 停止条件用未归一化日期的字典序比较**
- parse_list_items:137 只做 `.replace(".", "-")`：`2026/09/28` 原样保留（`/`=0x2F > `-`=0x2D，恒不小于任何 `2026-xx-xx` 阈值，永不触发停止）；`2026.9.8` → `2026-9-8`（个位月/日与零填充阈值比较错序）。`ldate < date_from` 语义在两种常见格式下都是错的。
- 修复：
  ```python
  def norm_date(s):
      p = s.replace(".", "-").replace("/", "-").split("-")
      if len(p) == 3:
          try: return f"{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}"
          except ValueError: return ""
      return ""
  # parse_list_items: date_s = norm_date(m.group(1))
  # run_job:          if ldate and date_from and norm_date(ldate) < date_from:
  ```

**[P1-4] taxcase_scrape.py:166 + :35 —— static_list 首页回退 URL 拼错，且与 docstring 自相矛盾**
- 代码：`first = tpl.replace("{page}", "index.html")`。docstring:18-19 描述的模板约定是 `index_{page}.html`（第 1 页是 `index.html`，第 2 页 `index_1.html`），回退会拼出 `index_index.html.html`——首页 404 → polite_get 返回 None → `iter_list` 直接 return，抓 0 条。docstring:35 又写"默认模板page=1"，与代码行为（"index.html"）不一致，且 page=1 也不对（`index_1.html` 是第 2 页）。
- 修复：把 `first_page_url` 升级为 static_list 必填（缺失即 raise，比静默拼错 URL 好），docstring 同步改：
  ```python
  if "first_page_url" not in job:
      raise ValueError("static_list 模式必须提供 first_page_url（首页 URL 无页号段，无法从模板机械推导）")
  first = job["first_page_url"]
  ```

**[P1-5] repair_attachments.py:22-82 —— 全部逻辑在模块顶层执行，无 `main()` 守卫**
- `import repair_attachments`（哪怕只为复用其附件重提逻辑）就会对整个 lawlibrary 发起网络重访并改写 md。caseopen_to_md.py:16 已示范了 `import taxcase_scrape as t` 的用法，将来有人 `from repair_attachments import ...` 就触发。同目录所有脚本都有 main 守卫，唯独此文件没有。
- 修复：包进 `def main(): ...` + `if __name__ == "__main__": main()`，网络循环体内变量（done/out）收进函数或显式传参。

**[P1-6] quality_prune.py:30-33 —— KEEP_COLUMNS 缺"裁判文书"，v1 在当前库上重跑会整批删除裁判文书**
- 库里现有 `裁判文书网/` 1838 份判决书，栏目为"裁判文书（税务行政管理）"。v1 的 KEEP_COLUMNS 无"裁判文书"，判决书正文也没有"违法事实/处罚事由"小节（判决书是"经审理查明/本院认为"），`facts_text` 抽到 0 字 → `facts<30` → DEL。v2（NARRATIVE_KEEP 含"裁判文书"）已修，但 v1 脚本仍在仓库里可执行，且 `--go` 直接 `os.remove`。
- 修复：v1 头部加退役声明或硬熔断：
  ```python
  KEEP_COLUMNS += ["裁判文书", "判决", "裁定"]
  # 或更安全：遇到白名单/黑名单之外的未知栏目直接拒跑
  unknown = {col for _, col in stats if not any(k in col for k in KEEP_COLUMNS + DEL_COLUMNS)}
  if unknown:
      sys.exit(f"发现未分类栏目 {unknown}，请先确认规则再 --go")
  ```

### P2

**taxcase_scrape.py**
- [P2] :65-83 `Resp` 用 `type("M", (), {...})` 伪造 match 对象——能跑但脆弱；且 `dict(getattr(r, "headers", {}))` 把 CaseInsensitiveDict 拍成普通 dict，丢失大小写不敏感查找（curl_cffi/requests 偶发小写 `content-type` 时 charset 探测失效）。建议改两分支普通变量赋值，headers 保留原对象或 get 两种大小写。
- [P2] :88-106 `polite_get` 裸 `except Exception: pass` 零日志，重试 3 次全败后返回 None，调用方只见 "fetch failed"；404 与超时/5xx 同样返回 None，不可区分（iter_list 无法区分"翻到底了"与"真故障"）。建议返回 `(status, resp)` 或定义 `FetchError`。
- [P2] :128 `if host not in url` 是子串判断，`https://www.chinatax.gov.cn.evil.com/` 能通过。建议 `urlparse(url).netloc.endswith(host)`。
- [P2] :246 附件正则 `\.(pdf|docx?|xlsx?|zip|rar)$` 锚定结尾，带查询串（`.pdf?down=1`）漏收；repair_attachments.py:60 的 `[^"]*\.(?:pdf|docx?|xlsx?)[^"]*` 才是对的——两处应统一抽成公共函数。
- [P2] :251 `md.replace("\\\\*\\**", "**")` 转义写错（匹配的是 6 字符字面量 `\\*\**`，几乎永不命中）。原意应是 `md.replace("\\*\\*", "**")`（修 markdownify 转义的 `\*\*`）。:253-254 的注释"去掉行内残留的空白转义"与后续代码不对应。
- [P2] :296-297 注释说"连续20条早于阈值"，代码 `n_old` 是**累计**计数（中间夹新条目不清零），散射的旧条目攒满 20 也停。要么重置计数实现"连续"，要么改注释。
- [P2] :308-309 fetch 失败的进度记录没 `flush()`（:315 parse 失败路径有）——崩溃即丢，续跑会重抓。统一加 `prog.flush()`。
- [P2] :317-331 `safe_filename` 截 80 字符，同名（同日期+同名长标题截断）不同 URL 会静默互相覆盖（`open(fpath, "w")`）。建议文件名追加 `hashlib.md5(url).hexdigest()[:6]`。
- [P2] :56-62 import 副作用：`import taxcase_scrape` 即创建 `progress/` 目录 + requests Session（caseopen_to_md/repair_attachments 都中招）。建议把 makedirs 挪进 run_job。
- [P2] :209 `<PUBLISHTIME>` 正则大小写敏感且 `[0-9-]{8,10}` 放行 `2026-09-2` 这类截断值；front matter `发布日期` 会写出 `20260928`（无连字符）与 `2026-09-28` 两种形态，下游按字符串排序/比较不稳。

**quality_prune.py**
- [P2] :17 `shutil` 导入未用；:61 `decide(column, region, body)` 的 `region` 参数未用。
- [P2] :100-105 全库逐文件 `open().read()` 不关闭（CPython 引用计数兜底，风格问题）。
- [P2] :58 `has_attachment_full` 用 `"附件（"` 判定——ocr_fill 写入的"## 附件（扫描件 OCR 全文）"章节会让程序性公告自动变 KEEP，这是 ocr_fill 的设计意图，但建议在两个文件的 docstring 里互相注明这个耦合。

**quality_prune2.py**
- [P2] :89 `["主要违法事实", "违法事实", "案件事实"] + FACT_KWS` 关键词重复，同一小节被 finditer 抓两遍、facts 长度近似翻倍，30 字门槛形同 15 字（偏向多留，注释声称"防止误杀"，但重复是失误不是策略）。去重：`list(dict.fromkeys([...]))`。
- [P2] :36 `UNIT_RE` 里 `人|条|份|笔|车` 极宽松（"3人"即算"单位词"），与 :35 `OUTCOME_MARK` 的"纳入"（匹配"纳入预算管理"）同属规则宽松项——建议在 docstring 标注已知误报面。
- [P2] :94-95 无事实小节时 `facts = squeeze(body)[:1200]` 兜底：若 body 含水印页脚（见"水印副作用验证"），"CLAW-ZGS-2026" 贡献 4 个数字，可把"1 个数字+单位"的边界样本翻成 KEEP。当前库内 md 未加水印（gitignored），未实际发生；开源后若水印脚本跑到数据 md 上会成真。建议兜底前先 `body = re.sub(r"\n---\n\n> 记录与代码作者.*$", "", body, flags=re.S)` 或干脆去掉兜底。

**quality_audit.py**
- [P2] :32-37 `TEMPLATE_MARKERS`、`META_ONLY_PATTERNS` 定义后从未使用（死代码，且 `"送达.*公告"` 是把正则写在"标记词"命名空间里，误导读者以为已参与判定）。
- [P2] :97 `files_lvl` 收集后从未使用；:121-124 `removed` 计数从不打印；:17 `shutil` 未用。
- [P2] :69 `if "判决" in column` 匹配不到"裁判文书（税务行政管理）"（不含"判决"二字），判决书走 :84 泛化分支靠 `cjk>=600` 兜成 RICH——碰巧能跑，属未定义行为。补 `"裁判文书"` 关键词。

**structure_extract.py**
- [P2] :38 发票违规正则结尾孤悬 `| accepting`——英文残留字面量，任何正文含 " accepting" 即误标"发票违规"。删除。
- [P2] :93-96 `WENSU_CAUSE_HINTS` 死代码。
- [P2] :132-138 `AMOUNT_RES` 抽到的金额保留原始分组（含 `2,340,000.00` 的逗号/中文逗号），未过 `norm_num`，与 :127 罚款倍数的归一化不一致，下游数值化会炸。统一 `amounts[name] = norm_num(mm.group(1))`。
- [P2] :197 重写 front matter 时剥离全部空行——纯格式扰动造成 git diff 噪音；有 `if new_txt != txt` 写盘守卫尚可。

**build_manifest.py**
- [P2] :64-68 先 append 再在重复分支 `rows.pop()`——依赖"rec 恰好是最后一个元素"的脆弱写法，重排即错。把重复判断挪到 append 之前。
- [P2] :53 共享/占位 URL（`<http://...>` 包裹、尾斜杠变体）不做归一化，同一目标页的 `url`/`<url>`/`url/` 互不去重（manifest 中 1874 行带 `<>` 包裹即为实证）。

**caseopen_harvest.py**
- [P2] :18-19 `sys.stdout.buffer` 在 pythonw / pytest capture 下不存在，import 即 AttributeError。包 try 或用 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`（3.7+，效果等价且更稳）。
- [P2] :95 `fout` 从不显式 close；:131 DONE_MARK 用 `json.dump(..., open(...))` 不关闭——CPython 能兜，风格上补 with。
- [P2] :51 Turnstile 坐标点击 (205,312) 硬编码（已注明"截图实测"，但开源用户视口不同即失效）；:63 `"Just" in title` 启发式粗糙。建议至少把坐标提为模块常量并注明失效场景。
- [P2] :97 `headless=False` 需要桌面环境（docstring 已注明"有头导航法"，算已标注；CI 上需 xvfb，可在 docstring 补一句）。

**caseopen_to_md.py**
- [P2] :59 title 里套 `safe_filename`，标题里的 `/` 会被替换成 `_`，显示失真——safe_filename 应只用于文件名。
- [P2] :74-75 `os.path.exists(fpath): continue` 静默吞同名碰撞（不同案件同名截断），且该 skip 不计入 `dup`，统计失真。至少 print 一行。
- [P2] :65 `抓取日期: 2026-10-10` 硬编码，应 `date.today().isoformat()`（taxcase_scrape 就是这么做的）。

**ocr_fill.py**（路径类见 P1-2）
- [P2] :171 token 失效判定 `"token" in blob.lower()` 与 `\b40[13]\b` 匹配输出任意位置——MinerU 输出里任何含 "token"/"403" 的正常文本（进度、页数）都会误判 TokenDead → 健康token被拉黑 → 全部 token "失效"提前终止。建议只认 exit code + 明确短语（"Unauthorized"/"invalid token"）。
- [P2] :126 `import pymupdf` 在函数内且未捕获 ImportError——没装的用户拿到裸 traceback。try/except 给出"请安装 pymupdf"。
- [P2] :32,:213 `TODAY = "2026-10-10"` 硬编码进 `OCR:` 标记——重跑日期不变，标记失真。用 `date.today().isoformat()`。
- [P2] :238-243 write_back 前两个分支条件不同但表达式完全相同（冗余）；无 name 的第二个附件会重复插入 "## 附件（扫描件 OCR 全文）" 标题。合并三分支为：有 name 且已有章节→带名追加；否则视情况新增章节。
- [P2] :159 `run_mineru(pdf_path, out_dir, seq)` 的 `seq` 参数未使用。
- [P2] :269 续跑跳过集合不含 `pdf_broken`/`download_fail`（每次重跑都重下重验）——若是故意重试，docstring 注明；否则并入跳过。

**add_watermark.py**（`__doc__` 见 P1-1）
- [P2] :68-69 `git ls-files` 失败（非 git 环境/git 不在 PATH）时 check=False、stderr 丢弃，main 静默输出 "水印完成: py+0 json+0 md+0"。校验 `returncode` 并报错。
- [P2] :82 `rel not in ("README.md", "LICENSE")` 只保护仓库根；嵌套 README（docs/README.md）会被追加页脚。改为 `os.path.basename(rel) not in (...)` 或精确根路径判断。
- [P2] :54 wm_json 以 indent=2 重写整个文件——单行 json 会变多行，纯格式 diff 噪音。可先 `json.dumps(..., indent=2)` 与原文比对决定是否重写，或保留原样式只追加键。

**jobs/cta_shuiantongbao.json**
- [P2] :7 `out_dir` 为绝对路径 `E:/ai_coding_xiangmu/...`，开源用户原样运行即写到别人机器不存在的盘符。建议支持相对仓库根的路径（taxcase_scrape 里 `if not os.path.isabs(out_dir): out_dir = os.path.join(HERE, ...)`）。:13 `_copyright` 键由水印注入，run_job 只读已知键，无害（水印脚本自己声称"加载器只读已知键，安全"，核实属实）。

---

## 水印副作用专项验证（实测）

1. **`__doc__` 失效：坐实。** AST 验证 11 个文件中 10 个（除 add_watermark.py 自身）首语句是 `__author__` 赋值而非字符串字面量 → `__doc__ is None`。修复见 P1-1。
2. **shebang：无影响。** 全部文件本无 shebang；`# -*- coding: utf-8 -*-` 保持在第 1 行，PEP 263 合规。
3. **quality 正则被水印干扰：直接干扰证伪，间接干扰坐实一个。**
   - md 页脚 `> 记录与代码作者：Zhu-Guang-Scion · github.com/... · CLAW-ZGS-2026 · MIT` 实测对 `UNIT_RE`（万?元|份|倍|%|税率|车|张|笔|条|人）、`VERB_RE`、`OUTCOME_MARK` 均**零命中**——"元"字不在水印里，担忧不成立。
   - 但页脚含 "2026"（4 个数字）：实测 `facts = '罚款0.5万元' + 页脚` 时 digits=6、unit=True，quality_prune2:65 的 `digits>=2 and has_unit` 由 False 翻 True。仅在"无事实小节 + 短文档"回退路径（:94-95）生效。
   - **现实状态：lawlibrary 的 md 全部被 gitignore、未加页脚**（实证：taxcase_corpus.jsonl 31764 行含作者名 0 行），当前库未被污染。风险在于 add_watermark 是幂等重跑工具，未来若数据 md 入 git 会成真。建议 wm_md 显式排除数据目录（`lawlibrary/`）。
4. **py 版权头 vs quality 门禁：无交集。** quality 三脚本只走 lawlibrary 的 .md，不读 py。

## 断点续跑（append-only jsonl "最新行为准"）审计结论

- taxcase_scrape.load_progress:267-279 —— 只取 `ok:True` 行入 done（"任一 ok 即跳过"），失败行自然重试；url ok 后不会回退为 not-ok，语义正确。副产品：被 quality_prune 删掉的文件不会重抓（url 已在 done）——符合"删了就别再抓"的意图，建议在 docstring 注明。
- ocr_fill.load_progress:44-59 —— dict 后写覆盖前写，`done[pdf_url]` 恒为最新记录，"最新行为准"实现正确；skip 条件只认 `ocr_done/not_scanned/not_pdf`，失败态重试（正确）。
- caseopen_harvest:84-131 —— seen 由全量行重建、DONE_MARK 整写；崩溃在"写行后、落 done_pages 前"的窗口会重做该页，靠 seen 去重，幂等成立。
- repair_attachments:22-30 —— 同 taxcase_scrape 语义，正确；无 `原文链接` 的文件不写进度，每次重跑重扫（只读本地文件，代价可忽略）。
- 唯一瑕疵：taxcase_scrape:308-309 fetch 失败记录未 flush（见 P2）。

## 性能审查结论

无 O(n²)/灾难回溯类问题。要点：AMOUNT_RES/MULTI_RE 的 `[^。；]{0,25}?`/`.*?` 均有界或线性；structure_extract 写盘有 `new_txt != txt` 守卫；quality 三脚本每文件完整读入是固有成本。小项：ocr_fill 对同一 md 在 collect_targets 与 write_back 各读一次（可传文本）；extract_detail:213 `soup.get_text(" ")[:3000]` 先建全文再切片（可先截 html）。

---

## 每文件审查小结

| 文件 | 小结 |
|---|---|
| taxcase_scrape.py | 骨架扎实（限速/重试/断点/去重齐全、`__file__` 定位、写盘 newline="\n"），但日期归一化缺失（P1-3）、static_list 首页回退拼错（P1-4）、Resp 编码探测实现偏 hack；polite_get 返回 None 语义过载。 |
| quality_prune.py | 规则清晰、留档+空目录清理做得好；v1 规则表缺"裁判文书"是重跑炸弹（P1-6），shutil/region 死代码，"连续20条"注释与累计实现不符。 |
| quality_prune2.py | 双要素门禁设计合理，v1 教训沉淀到位；失信分支关键词重复致长度虚增、UNIT_RE 过松、无事实节兜底路径对水印数字敏感（当前未触发）。 |
| quality_audit.py | 分级思路可用；约 1/4 代码是死代码（TEMPLATE_MARKERS/META_ONLY_PATTERNS/files_lvl），removed 不打印，"判决"关键词匹配不到"裁判文书"栏目。 |
| structure_extract.py | 幂等重写 fm + 留附件行的设计正确（v1 误删已有 repair 兜底）；" accepting" 英文残留、金额未归一化、WENSU_CAUSE_HINTS 死代码。 |
| build_manifest.py | 与共享 URL 数据源组合成 P0：去重键、corpus id 双双失真（已实证 14038 重复标记、17726/31764 唯一 id）；rows.pop() 写法脆弱；utf-8-sig 供 Excel 是好细节。 |
| caseopen_harvest.py | 断点/去重/Turnstile 应付逻辑完备且实测能跑；stdout 重包装在无 tty 环境会炸、坐标点击与 "Just" 启发式硬编码、文件句柄不显式关。 |
| caseopen_to_md.py | 清洗与空文书跳过合理；致命点是全体共用 `原文链接: https://caseopen.org/`（P0-1 根因），另 title 滥用 safe_filename、抓取日期硬编码、同名碰撞静默跳过。 |
| repair_attachments.py | 修复思路与更好的附件正则值得回流主脚本；但全模块顶层执行无 main 守卫（P1-5），import 即全网重访。 |
| ocr_fill.py | 断点/token 轮换/质检/回写链路完整，是全链路里工程化最重的；但七处硬编码绝对路径（含仓库外与 C:\Users）是开源阻断项（P1-2），token 失效误判与 pymupdf 裸 ImportError 需收口。 |
| add_watermark.py | 幂等与 README/LICENSE 豁免意识不错；但 `__author__` 前置毁掉全部 10 个模块 `__doc__`（P1-1），git 失败静默、嵌套 README 不豁免、json 重排格式。 |
| jobs/cta_shuiantongbao.json | 字段与 run_job 契合、_copyright 注入无害；out_dir 绝对盘符路径需相对化。 |

## 优先修复顺序建议

1. P0-1（防误删 + id 修复，30 分钟）
2. P1-1（`__doc__` 存量挪行 10 处 + wm_py 修复，20 分钟）
3. P1-2（ocr_fill 路径参数化，20 分钟）
4. P1-3/P1-4（taxcase_scrape 日期与首页，20 分钟）
5. P1-5/P1-6（main 守卫 + v1 熔断，10 分钟）
6. P2 按文件顺带清理
