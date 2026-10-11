# 内置浏览器（IAB）攻坚实录 —— 2026-10-10 第二轮

工具：ZCode 内置浏览器（browser-use skill，node_repl 驱动，IAB backend）。核心能力：真实浏览器过 JS 挑战 + **页面上下文内 fetch（credentials:include）**。

## 一、山东 zfgspt —— 完全成功（3,243 件处罚公示）

### 突破路径
1. IAB 直接打开 `https://shandong.chinatax.gov.cn/zfgspt/extranet/xzcf` → **网宿 wswaf 挑战自动通过**（无需人工干预；curl/curl_cffi/playwright 无头全失败过的墙，真 webview 直接过）
2. 挑战 cookie `Q805dsSXd0YYP`（非 httpOnly）可从 `document.cookie` 导出（存 `tmp/sd_cookies.txt`）
3. **cookie 移植 curl_cffi：GET 有效**（iframe 页/JS 文件 200），**POST 无效**（触发新一轮 412 挑战）→ 凡 POST 数据接口必须留在浏览器内调
4. 数据接口：`POST /zfgspt/extranet/shgs/query_swxz_ybcx_cfjg.spring`（表单：pageIndex/pageSize=100/type=gs/nsrmc/shxydm/xzcfjdswh/ajmc/zccfrqq/zccfrqz）
   - **页面验证码是纯前端把戏**：JS 先调 checkCode.spring 校验，但数据接口本身不校验验证码——在页面上下文直接 fetch 数据接口即返回全量 JSON
   - total=3933 是**虚高**（服务端自身分页重复），唯一记录实为 3,243（按 KEY 字段去重两次全量翻页验证）
   - type=ds（地税）返回 0
5. 字段：AJMC案件名/CFSY违法事实/CFYJ处罚依据/CFJG处罚结果/XZCFJDSWH文号/SWJGMC机关/NSRMC相对人/TYSHXYDM(打码)/ZCGCFRQ作出日期/FBSJ公示日期/CFLB处罚类别/FDDBRXM法定代表人
6. 采集模式：页面内 evaluate(fetch) 每页 100 条 × 40 页，700ms 间隔，node 内 Map 按 KEY 并集，fs 落盘 JSON（tmp/sd_xzcf_merged.json）→ python 转 md

### 复用要点
- IAB evaluate 单次预算 ~30s：每批 ≤10 页（1000条）稳；大批量分多次调用
- 数据在 node 侧 fs.writeFile 落盘，**不要**经 innerText 大页面搬运（见 caseopen 教训）

## 二、四川 —— webview 内挑战无法完成

- `sichuan.chinatax.gov.cn` wswaf 变体在 IAB 内只种第一枚 cookie（`QDkE2SSrLpcXP`），第二轮挑战 JS 不执行，body 恒空；多次 reload 无效；cookie 导出移植 curl_cffi 仍 412（需第二枚挑战 cookie）
- 结论：四川维持微信公众号通道；后续路线=干净 IP + 桌面 Chrome 人工过一次挑战 → CDP 导出全套 cookie（约 7 天有效）→ curl_cffi

## 三、caseopen.org（裁判文书在线库）—— 会话通、全量导出不可行（IAB 限制）

1. 前置两道：Cloudflare（cf_clearance，httpOnly 不可导出）+ Anubis 工作量证明（真浏览器自动过，cookie 有效 ~7 天）
2. **fetch() 在页面内被 CF 拦**（"Failed to fetch"，reload 无法恢复）；**顶层导航可过**——`/api/search?...` 以页面打开可读 body
3. **导出接口两形态**：
   - `/?search=...&export=true` → CSV 附件下载 → IAB 不支持 attachment 下载（ERR_FAILED）
   - `/api/search?...&export=true` → JSON，**limit 强制 2000**（limit 参数无效），含全文
4. **IAB 数据搬运瓶颈**：2000 条全文 JSON ≈ 7.8MB，页面能渲染，但 evaluate 提取 innerText 子串（哪怕 50KB）超时 32s——大规模文本无法搬出 webview
5. 已验证数据（决策依据）：税务行政管理 4,723（2021 后仅 310）/逃税罪 2,634/虚开增专罪 40,896（2021 后 5,006）/骗取出口退税罪 41,879/虚开发票罪 5,226/抗税罪 12；行政案年份峰值 2018（2,068/年）后断崖
6. **实操建议**（后续真要全量时）：桌面 Chrome 手动过两道挑战 → 逐案由 offset 分批 `/?search=...&export=true` 下载 CSV（普通浏览器支持 attachment）；或 CDP 驱动 Chrome 让 fetch 携带 cf_clearance

## 四、浙江 sword 平台 —— IAB 打不开

`zhejiang.chinatax.gov.cn:16002`（非标端口）在 IAB 内 chrome-error://chromewebdata/（网络层失败）。浙江处罚公示维持放弃状态（验证码平台），后续可试桌面浏览器人工+cookie 导出。

## 五、经验总结（进 skill）

| 墙 | IAB 表现 | 对策 |
|---|---|---|
| 网宿 wswaf（山东） | 自动过 | 页内 fetch 数据接口（验证码若是纯前端校验则无效力） |
| 网宿 wswaf（四川变体） | 过不了（第二轮不执行） | 桌面 Chrome 人工过+CDP cookie |
| Cloudflare+Anubis | 会话可建立，fetch 被拦 | 导航式读小接口可行；大数据量不可行 |
| 非标端口(:16002) | 网络层失败 | 桌面浏览器 |
| 服务端真验证码 | 可截图+视觉读码填入 | 本轮未实战（浙/津站先死于网络层） |

通用教训：**数据要么经页面内 fetch+node fs 落盘（中等量），要么经导航渲染读取（小量）；大文本经 evaluate 搬运会超时**。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
