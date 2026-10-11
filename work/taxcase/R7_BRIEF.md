# 第七轮扩围简报（必读）

## 任务
把「税务稽查/处罚案例库」扩到未覆盖省份。质量门槛强制：`work/taxcase/quality_prune.py` 的 `decide()` 判定，DEL 不入库（违法事实叙述≥30 中文字符）。

## 信源优先级（六轮实战总结，按富全文密度排序）
1. **重大税收违法失信主体公布栏**（各省主站 xxgk/行政执法栏目下，TRS col 或检索表单）——**密度最高**：四川1,000/辽宁995/湖南1,305/重庆795/青岛503/宁波273/陕西67 全是富全文（每主体含违法事实+处理处罚全文）。先找这个！
2. **处罚决定书级平台/接口**（etax/sword/spring/zfgspt，山东-辽宁-四川同款 wings 平台；查询式 API 枚举如重庆 qeuryZdaj）
3. **市局子站稽查通报**（大汉/TRS 静态列表，安徽模式：16 市中位 907 字）
4. 税案通报/曝光（新闻过滤）

## 探测流程（每省 5-10 分钟）
1. `curl_cffi` chrome124 探主站（**timeout=150 才是 15 秒**——本机 timeout=N 实按 N×100ms 解析）
2. 412/$_ts/$_ss = 瑞数/网宿墙 → 有头 chromium 打法（见下）；200 = 直连抓
3. 找失信栏：站内导航"信息公开/行政执法公示/重大税收违法"、或站内搜索"重大税收违法"
4. 找处罚平台：etax.<省>.chinatax.gov.cn、:8090/:8443/:6883/:8888 端口、/zfgspt /sword?ctrl=XzzfgsptHomeCtrl_index 等模式（详见 SOURCES.md 〇h/〇e 与 sources/*.md 契约库）

## 墙的对策（按成本）
- TLS 指纹（requests 拿到无数据壳页）：curl_cffi chrome124（必用 polite_get）
- 瑞数/网宿 412：**有头 chromium**（launch(headless=False, args=["--disable-blink-features=AutomationControlled"])，goto 后轮询 body 长度过挑战）→ 会话内采集：fetch 失败即转真实导航（青岛招）、站内 $.ajax（湖南招）、TextDecoder 处理 charset（四川招）、jQuery $.ajax 而非裸 fetch（四川 415 教训）
- 验证码：图片码 ddddocr（辽宁 75% 过码率）；点选汉字码识别率低→换其他源
- 挑战死循环/人机均不可过：截图留证、记档、跳下一省

## 输出规范
- lawlibrary/专题/税务案例/<省名>/<栏目>/，front matter 与库内一致
- 文档 work/taxcase/sources/<省拼音>_r7.md（入口/机制/量/坑），断点 work/taxcase/progress/<省>_r7.jsonl
- 量控：每省 ≤2,000 件，近三年优先（失信栏历史存量可全收）
- 完成或定格时：入库件数 + 判死原因写清楚


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
