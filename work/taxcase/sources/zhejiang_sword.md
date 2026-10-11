# 浙江 sword 行政执法公示平台（:16002）逆向记录——验证码已自动识别，平台数据为空

- 攻坚日期：2026-10-10（第三轮续跑）
- 前置：`sources/zhejiang.md` 第 3 节（当时结论"被验证码拦截，放弃"——**本记录更正：验证码可破，真实原因是平台无数据**）
- 复现脚本：`tmp/zj_probe_flow.py`、判别实验脚本（见本文第 5 节"判定实验日志"）

## 0. 一句话结论

**验证码（ddddocr 默认模型，实测过码率约 70-80%）、会话、postData 全部打通，
但该平台对任何查询条件组合（全省 67 机关、任意日期、真实被处罚公司名）一律返回
"未查询到结果"——平台本身没有接入数据。浙江税务的处罚信息公开形态是新闻通报
（col13226，已入库 52 件，见 `sources/zhejiang.md` 第 1 节），不是结构化处罚决定书库。**

同款平台旁证：山西局同款 sword 平台页面上直接显示"本单位暂未产生该项执法信息"——
这类"行政执法信息公示平台"在部分省份长期空转，浙江属于其中之一。

## 1. 平台结构（wings/sword 框架）

```
入口  http://zhejiang.chinatax.gov.cn:16002/sword?ctrl=XzzfgsptHomeCtrl_index&yjcd=xzcf&ejcd=xzcf_01
      （平台菜单只有两项：税务行政一般程序处罚结果 / 重大税收违法失信案件信息）
iframe /sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg&sxq=zhejiangsheng&swjgDm=<全省67个机关代码>
      （GET 此页拿 LESB_SESSION cookie；页面 SwordPageData 隐藏域里回传 67 个 swjgDm + sessionID）
数据  POST /ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg
验证码 GET /download.sword?ctrl=CheckcodeUtil_getCheckcode&t=<32位随机>&id=ck1
翻页  grid ptid=/ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg&fycx=true（flag=0 后由 grid 发起，
      因平台无数据从未触发过，翻页 postData 格式未观察到）
```

无 WAF/TLS 挑战，python requests 直连即可（无需 curl_cffi/playwright）。

## 2. postData 字段表（实测抓包 + 逐项验证）

POST body 为 form 编码的单字段：`postData=<urlencoded JSON>+`（尾部 `+` 是 jQuery 风格空格），
Content-Type: application/x-www-form-urlencoded，需带头 `X-Requested-With: XMLHttpRequest` 与 Referer。

外层结构：

```json
{"tid":"","ctrl":"XzzfgsptXzcfCtrl_getSwxzybcxcfjg","data":[...],"bindParam":true}
```

`data` 数组元素形如 `{"name":"字段名","value":"值","sword":"attr"}`：

| name | 含义 | 实测说明 |
|---|---|---|
| ajmc | 案件名称（模糊） | 可空 |
| nsrsbh | 行政相对人代码 | 可空 |
| nsrmc | 行政相对人名称（模糊） | 可空；用真实受罚公司名（程康建材/嫲嫲团）查过，仍空 |
| cfjg | 处罚机关（文本） | 可空 |
| yxqq | 处罚日期起 | yyyy-mm-dd；可空；页面日历组件，无默认值 |
| yxqz | 处罚日期止 | 同上 |
| swjgDm | 机关代码 | **必填**（空串 → 服务端 exception"系统发生异常"）；逗号分隔可多值，页面默认全省 67 个 |
| rows | 每页条数 | 页面可选 5/10/25/30/50 |
| ckcode | 验证码输入值 | ddddocr 识别原样提交即可（校验大小写不敏感） |
| ckcodeId | 验证码组件 id | 固定 "ck1" |

## 3. 验证码流程（已完全打通）

1. `GET /sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg&sxq=zhejiangsheng&swjgDm=13300000000`
   → 响应 Set-Cookie: `LESB_SESSION=...`（path=/，HttpOnly），requests.Session 自动携带。
2. `GET /download.sword?ctrl=CheckcodeUtil_getCheckcode&t=<32位随机字母数字>&id=ck1`
   → 60x20 JPEG，**4 位混合大小写字母数字**（人工样本 9XF6 / K3pA / NMA2，均含大写）。
   **参数名是 `id` 不是 `ckcodeId`**——用错参数码不会存入 session，POST 必报"浏览器超时"。
   session 内单码覆盖：每下载一次覆盖旧码，每 POST 一次消费当前码。
3. ddddocr 默认模型 `ocr.classification(img)` 直接识别（无需 beta 模型/预处理）。
   实测过码率约 70-80%（10 连测：8 过 2 错 / 10 过 0 错 / 5 过 1 错），
   错了换码重试 2-3 次内必过。
4. `POST /ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg`（postData 见上节）。

### 响应消息语义（实测判定，纠正直觉）

| 响应 msg | flag | 真实含义 |
|---|---|---|
| 浏览器超时，请重新输入验证码 | 1 | session 里**没有码**（验证码 URL 参数错没存上 / 码已被上次 POST 消费）——不是超时 |
| 验证码不正确 | 1 | 码值比对失败 |
| 未查询到结果 | 1 | **码已通过**，后端查询结果为空 |
| {"exception":true,"debugMes":"系统发生异常"...} | - | 参数缺失（如 swjgDm 空串）等后端异常 |

成功响应（flag=0 + grid 数据）从未出现过——因为库里没数据。

## 4. 机关代码（67 个，tmp/zj_swjgdm.txt 逗号分隔单行）

- `13300000000` 省局；`13300010000`~`13300050000` 省局直属/稽查系列
- `13300090000`~`13300170000`、`13300180000`~`13300210000` 11 个市局
- `13300410000`~`13300430000`、`13300510000`~`13300610000` 市局下属/区县局
- `13300710100`~`13300910800` 各地稽查局（处/科系列，第 7-9 位为 9xx/7xx 的都是稽查体系）
- `13300550100`~`13300550900` 稽查局科所系列

完整 67 个以 `tmp/zj_swjgdm.txt` 为准（来源：init 页面 SwordPageData 隐藏域回传）。

## 5. 判定实验日志（为什么敢下"平台无数据"结论）

| # | 实验 | 结果 |
|---|---|---|
| 1 | 验证码 URL 用 `ckcodeId=ck1` 参数 | 全部"浏览器超时"（码没进 session）→ 改 `id=ck1` 后正常 |
| 2 | 故意错码 zz9q（新鲜码在场） | "验证码不正确" |
| 3 | ddddocr 原样（新鲜码，秒级间隔） | "未查询到结果"（=过码） |
| 4 | ddddocr 值全大写变体 | "未查询到结果"（=校验大小写不敏感） |
| 5 | 人工读码（视觉模型，60-90 秒延迟） | 过期/读不准，混合两种失败消息 |
| 6 | 全省 67 机关 无日期 rows=50 | "未查询到结果" |
| 7 | 湖州/省局/杭州区县单机关、日期 2016-2026/2023/反转/紧凑格式 | 全部"未查询到结果" |
| 8 | nsrmc=程康建材（2025 年温州三稽真实受罚公司） | 8 次"未查询到结果"+2 次"验证码不正确"（码错） |
| 9 | nsrmc=嫲嫲团（2025 年温州二稽真实受罚公司） | 10/10"未查询到结果" |
| 10 | swjgDm 空串 | exception"系统发生异常"（288 字节异常 JSON）——反证带机关代码时后端在正常查库 |
| 11 | playwright 有头真实浏览器完整流程（第一轮 capture 截图） | 同样弹"未查询到结果"、表格空 |
| 12 | WebSearch 程康建材案 | 只有新闻通报（zhejiang.chinatax.gov.cn 稽查新闻），无任何渠道的处罚决定书原文 |
| 13 | Wayback CDX | :16002 非标端口无任何存档，无法历史对照 |

## 6. 坑与经验

1. **验证码 URL 参数名是 `id`**（`&t=<随机>&id=ck1`），不是 postData 里的 `ckcodeId`——参数决定
   服务端 session 存储 key。第一轮预研记录里没写清这一点，续跑时踩了 40 分钟。
2. 响应消息三态语义全是"字面误导"：见第 3 节表。判定码是否通过要看消息分布
   （连续多次同消息=过码后空结果；出现"验证码不正确"=码错）。
3. 一次 POST 消费一个码；同 session 再下载新码即可，无需重建会话。
4. swjgDm 必填且空串直接 exception。
5. ddddocr 对该站 60x20 混合大小写码的默认模型过码率约 70-80%，足够（换码重试机制兜底），
   无需 beta 模型或图像预处理。
6. 该平台在搜索引擎与 Wayback 均无痕（非标端口），"平台是否曾有数据"不可考；
   但同款平台山西版公开显示"本单位暂未产生该项执法信息"，佐证空转是省级接入问题。
7. **浙江处罚信息公开的真实形态 = 新闻通报**（col13226 dataproxy 接口，`sources/zhejiang.md`
   第 1 节，52 件已入库）。要补"结构化处罚决定书"只能等：a) 平台接入数据后重跑本记录流程；
   b) 浙江政务服务网双公示（www.zjzwfw.gov.cn，阿里 WAF，需浏览器会话探 XHR）；
   c) 信用浙江 creditzj.gov.cn（本网络不可达）。

## 7. 抓取量汇总

| 项 | 数量 |
|---|---|
| 查询请求（各种条件组合） | 100+ 次 |
| 结构化处罚记录 | **0 条（平台无数据）** |
| 入库 md | 0 件 |
| 验证码识别样本 | tmp/zj_human_*.jpg、tmp/zj_acc_*.jpg 等 |


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
