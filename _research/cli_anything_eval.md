# CLI-Anything 调研：是什么 & 对本项目有无借鉴意义（2026-10-13）

## 一、CLI-Anything 是什么

**HKUDS（港大数据智能实验室）2026 年项目**（[GitHub](https://github.com/HKUDS/CLI-Anything)，
[论文 arXiv:2606.03854](https://arxiv.org/abs/2606.03854)），口号 "Making ALL Software
Agent-Native"：把任意软件（尤其 GUI 桌面软件）变成 AI Agent 可调用的 CLI 工具。三层组成：

| 层 | 内容 |
|---|---|
| **CLI-Hub**（`pip install cli-anything-hub`） | Agent 友好 CLI 注册中心/包管理器：`cli-hub list/search/info/install/launch`，registry.json 现有 **79 个 CLI** |
| **7-Phase 生成器** | 给目标软件自动生成 CLI harness（`cli-anything-<software>`，pip 命名空间、统一 `--json` 输出、**Phase 6.5 自动生成 SKILL.md**） |
| **现成 harness** | GIMP/Blender/LibreOffice/QGIS/FreeCAD/Zotero/Obsidian…（创作与工程软件为主）+ **web 类：clibrowser/browser/safari/web-yu-pri** |

## 二、"利用 CLI-Anything 辅助抓取"指什么

CLI-Hub 里与抓取相关的实体是三个 web 类 harness：

1. **clibrowser**（外部项目 [allthingssecurity/clibrowser](https://github.com/allthingssecurity/clibrowser)，Rust 零依赖单二进制，v0.1.0）：
   `get`（抓取+缓存）→ `text/markdown/select/links/tables`（抽取）→ `click/fill/submit`（交互），
   另有 `search`、RSS、crawling、auth、**`--stealth` 隐身**；命令**顺序执行非管道**（get 后从缓存读）。
2. **browser**（DOMShell MCP）：把 **Chrome 无障碍树映射为虚拟文件系统**——Agent 用 `ls/cat/cd`
   的 Unix 心智模型浏览和操作网页。
3. **safari**（safari-mcp）：macOS 限定，84 工具含网络抓包——与我们无关。

## 三、对本项目的借鉴评估（结论：抓取主力不换，工程范式抄三样）

### 3.1 不换抓取主力

| 维度 | 我们已有（13 轮实战） | CLI-Anything 生态 | 判定 |
|---|---|---|---|
| HTTP 抓取 | curl_cffi chrome124（TLS 指纹破壳）+ polite_get 全局限速断点 | clibrowser `--stealth`（指纹质量未知，v0.1.0 早期） | 我们更强更专，不换 |
| JS 渲染/反爬 | playwright 有头（瑞数）、IAB 内置浏览器（网宿 WAF）、ddddocr | clibrowser/browser 均未证明能过国内政务站反爬 | 无替换证据 |
| 文档转换 | pymupdf/Word COM/MinerU | libreoffice harness（headless 转 PDF/DOCX） | 已覆盖 |

国内税务站的反爬是 **TLS 指纹+JS 挑战+验证码** 三层，CLI-Anything 生态全部未经此环境验证；
把抓取主链路押在 v0.1.0 的外部工具上风险大于收益。

### 3.2 值得直接抄的三样（工程范式）

1. **adapter 注册表 registry.json**：我们 66+ adapter 只有 SOURCES.md（人读），没有机器可发现的
   注册表。仿 CLI-Hub：每 adapter 一条 `{name, 信源, 入口, 断点文件, 踩坑文档, 栏目}`，
   Agent/增量任务可编程发现与调度。
2. **per-adapter `--probe` 自检（true-backend 测试思想）**：CLI-Anything 四层测试里的
   "真实后端 E2E"（真软件真调起真产物验证）最值得抄——给每个 adapter 加 `--probe`：
   读断点报进度 + 试抓 1 条验管线活着。月度增量前的健康检查就从"人肉记忆"变"一条命令"。
3. **GUI 软件自动化备选路线（7-Phase harness 方法论）**：我们的遗留痛点（PC 微信客户端人工取
   key、某些只有客户端/小程序的信源）恰是它的主场——将来再遇"无网页只有客户端"的信源，
   可用其生成器产出 harness 替代脆弱的坐标点击脚本。**记档备查，暂不引入。**

### 3.3 记档不采纳

- DOMShell "无障碍树→虚拟文件系统"：思路漂亮，但 IAB 的 domSnapshot 已满足需求
- cli-hub 分发/命名空间：我们的 adapter 不需要独立 pip 分发

## 四、来源

- [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything)（README 77KB，gh-proxy 镜像读取）
- [CLI-Hub registry.json](https://hkuds.github.io/CLI-Anything/registry.json)（79 条目，2026-06-19 更新）
- [allthingssecurity/clibrowser](https://github.com/allthingssecurity/clibrowser)（v0.1.0）
- 论文：CLI-Anything: Towards Agent-Native Computer Use（arXiv:2606.03854）
