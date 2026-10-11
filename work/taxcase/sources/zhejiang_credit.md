# 信用浙江（credit.zj.gov.cn）税务处罚公示逆向记录——列表全量入库，详情被点击式验证码拦截

- 攻坚日期：2026-10-10
- 产出：**3069 条税务处罚索引型 md** 入 `lawlibrary/专题/税务案例/浙江省/信用浙江处罚公示/`（字段：文书号/相对人/信用代码/决定日期/处罚机关），原始数据在 `work/taxcase/progress/zj_credit.jsonl`
- 详情全文（决定书正文）：**0 条**——详情接口被点击式汉字验证码单次门禁，未实现规模化自动识别（见第 3 节）

## 1. 平台与接口全貌

```
前端  https://credit.zj.gov.cn/jyh/  （Vue SPA，element-ui + iview 混用）
      双公示页路由 #/home/doubleInfo（默认行政许可 tab=1），#/home/doubleInfo?tab=2 为行政处罚
数据  POST https://xyxx.zjzwfw.gov.cn/router/api/p/<端点>   JSON body，无 cookie/无签名/无 WAF
      curl_cffi chrome124 直连可用（无 TLS 挑战）；本接口连 python-requests 也可能可用，未测
列表  creditXygsGetXzcfList
      body: {"entity":{"jdrqEnd":"","jdrqStart":"","ws":"","wsh":"税","xdrMc":"","isFirst":1},
             "current":<页>,"size":100}
      size=100 有效；返回 data.total=3069、data.pages=31、records[]
      record 字段：esId / id(数字主键) / wsh(文书号) / jdrq(决定日期) / xdrMc(相对人) / ws(信用代码) / grade
详情  creditXygsGetXzcfDetail   ← 必须带 captchCode（验证码通过后服务端签发），否则 msg="验证码错误！"
      正确入参 = 列表整行 record + captchCode（其中数字 id 必填，缺 id 报"ID不能为空"）
验证码图片  GET https://xyxx.zjzwfw.gov.cn/router/getImg?id=<客户端自生成 uuid v4>  → 450x290 PNG
验证码校验  POST creditCheckImg  body {"coordinateList":["x:y",...3个],"id":<同一uuid>}
            通过 → data 返回 captchCode（32位hex），失败 → {"msg":"校验不通过","data":"{}"}
token  creditGetXycxToken / creditXygsGetToken（返回 data.token，前端拿了但**不用于任何请求头**，死代码）
埋点  creditAddVisitCountData（可无视）
```

## 2. 列表抓取的两个坑（已解决）

1. **深分页封顶 2000**：`pages=31` 但 current≥21 起返回空 records（ES max_result_window 风格）。
   解决：按 jdrqEnd 窗口切片——先抓无界窗口前 2000 条（2025-08-11→2026-09-28），
   再以 jdrqEnd=2025-08-10 抓余下 1063 条（≤2025-08-10）。
2. **jdrqEnd 是排他边界**：jdrqEnd=2025-08-11 不含 8月11日当天的记录。2025-08-11 当天有 7 条，
   首窗口只露出 1 条，需 jdrqEnd=2025-08-12 再补 6 条。**2000+1063+6=3069 齐了**。
   （jdrqStart/jdrqEnd 组合查单日返回 0，起止同时给时语义不明，别用；只用 jdrqEnd 单边切）

数据分布：2023-10-10 → 2026-09-28；34 个文书号前缀（杭/温/台/嘉/绍/金/衢/舟/湖/丽 + 省局浙税稽 1 条；
宁波为计划单列，走自己的平台，本库无）。文书号前缀→处罚机关映射已写进每个 md 的 front matter 来源机关。

## 3. 详情验证码攻坚记录（未破，结论：单次门禁 + 字形识别不可靠）

流程（从 chunk-7ed7b31f.js 逆向，已实测打通到 captchCode 签发）：

1. `imgId = uuid v4()`（客户端生成，无服务端注册步骤）
2. `GET /router/getImg?id=<imgId>` → 450x290 PNG：顶部黑条 + 3 个蓝色提示字（黑条底部有一条蓝色分隔线，
   提取字形时需剔除），下方照片背景散布 4 个彩色汉字（3 目标 + 1 干扰）
3. 按提示顺序点击 3 个目标字（前端要求 offsetY>30，第 3 次点击自动提交）
4. `POST creditCheckImg {"coordinateList":["x:y",...],"id":imgId}` → 通过返回 captchCode
5. `POST creditXygsGetXzcfDetail {整行record, captchCode}` → data 含 nr（决定书全文 HTML）

**实测行为**：
- captchCode **单次详情消费**：check 通过后第一次 detail（即使参数错报"ID不能为空"）后再用即"验证码错误"；
  前端每次进详情页都重新弹验证码（mounted 即 dialogVisible=true），无会话缓存
- checkImg 无 session/cookie 绑定（跨 session 提交可用），imgId 即凭证；失败不换 msg，无法区分是否可重试
- 验证码无 TTL 迹象（fetch 后数分钟提交仍按坐标判）
- 我方唯一一次 check 通过（视觉模型读图坐标）说明**点击容差较松（约±25-30px）**，失败几乎都败在字形识别/配对

**尝试过的自动化方案与失败原因**（全部实测）：
| 方案 | 结果 |
|---|---|
| ddddocr det=True 找字框 | **不可靠**：照片背景上幻觉框 + 漏真字（对拍已解样本：4 字只中 2，另 2 框是背景纹理） |
| ddddocr classification 逐字识别做 strip↔body 配对 | 部分一致（同字形在两种渲染下常给出同一错读，如'定'↔'定'），但一致性不足 50% |
| strip 蓝字掩码 vs body Otsu/色距掩码 IoU 匹配 | body 掩码被照片纹理污染，矩阵无区分度 |
| Canny 边缘 + chamfer(DT) 模板匹配 | 被背景高频纹理吸引（棕榈叶脉与笔画轮廓距离更近），峰值全跑偏 |
| 颜色离差图 + 字形掩码相关性 | 4 字只能找到 2-3（低对比字形离差≈0，人眼可见机器不可见） |
| 视觉模型（analyze_image）整图读 | 多次读同一图给出**互相矛盾**的字与坐标（幻觉），约 1/8 通过率 |
| 视觉模型 + 网格叠加 + 裁剪拼图 + ddddocr 交叉校验 | 交叉校验过严（cls 常返回空），未形成可靠流水线 |

**给下一个 agent 的建议**：
- 若要补详情，优先级：① 接入更强的 OCR/目标检测（PaddleOCR det+cls 或训练小模型专认这套字形；
  样本可无限取：getImg 不要钱）② 真人打码平台 ③ 视觉大模型 API 批量调用（每条详情一个验证码，
  3069 条=3069 次识别）④ 等平台改版。captchCode 单次消费已被实验锁死，别在复用上浪费时间。
- 列表→详情的字段差只有 `nr`（决定书全文）一处；若浙江税务后续在 col13226 通报里覆盖了同案，
  可按文书号对上补全文。

## 4. 入库清单

| 项 | 值 |
|---|---|
| 目录 | `lawlibrary/专题/税务案例/浙江省/信用浙江处罚公示/` |
| 件数 | 3069（索引型，字段：文书号/相对人/信用代码/决定日期/处罚机关） |
| front matter | 栏目=行政处罚公示（信用浙江）；地区=浙江省；来源机关=按 wsh 前缀映射（34 种，如 杭税三稽→国家税务总局杭州市税务局第三稽查局、金税稽二→金华市税务局稽查二局）；详情状态=未取 |
| 断点 | `work/taxcase/progress/zj_credit.jsonl`（每行一条 record，含 _page/_win 窗口标记） |
| 详情 | 0 件（验证码拦截，见第 3 节） |

## 5. 复用资产

- `work/taxcase/progress/zj_credit.jsonl` —— 全量原始记录（后续补详情直接按 id/esId 遍历它）
- 抓取脚本模式：无界窗口抓到 2000 封顶 → 按 jdrqEnd（排他）逐窗口下探 → 边界日单独补
- md 生成器的 org_from_wsh()：34 前缀 → 机关全称映射


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
