# 福建 etax xxmh 处罚公示平台逆向记录——API 契约全破，验证码 check 不可满足（本轮 0 条）

- 攻坚日期：2026-10-10/11（第五轮夜间采集）
- 前置：`_research/rich_sources_round5.md` 第 2.2 节（预研判 P0"ddddocr 实测识别成功"——**本记录更正：预研只验了 ddddocr 能读出码，没验过后端接受；真实门禁是点选验证码且不可过**）
- 复现脚本与证据：`tmp/fj_probe_flow.py`（初探）、`tmp/fj_solver.py`（clickWord 求解器）、`tmp/fj_variant.py`（坐标变体校准）、`tmp/fj_pw.py`/`tmp/fj_pw2.py`（playwright 有头兜底+网络抓包）、`tmp/javasim/AnchorSim2.java`（Java2D 锚点几何模拟）、`tmp/fjq*_*/fpw_*`（各轮样张）

## 0. 一句话结论

**数据 API 契约（postData/分页/机关参数）与 sso 验证码全链路（get.do/check.do/SM4/captchaVerification）
已 100% 逆向到与真实浏览器逐字节一致，但 check.do 对一切与图面一致的点击坐标一律返回
6111 坐标错误——12+ 轮求解（含 playwright 真鼠标事件、VLM 双重验证的字-格映射、4 种坐标
策略、display/2x 空间假设）全部失败。判定：验证码服务部署缺陷（人机均不可过），本平台
当前不可采集（0 条入库）。** 与浙江 sword（空库）、信用浙江详情（点选码 1/8 过码率）同属
"省级平台自建门禁废掉"家族。

## 1. 平台结构（xxmh JSP + anji-plus 系 sso 验证码）

```
入口   https://etax.fujian.chinatax.gov.cn/xxmh/view/xzzf/xzzf_fj/ybcxcfjg.jsp?swjg_dm=13500000000
       （主站 fujian.chinatax.gov.cn /zfxxgkzl/zfxxgkml/xzzf/ ztree 官方直链此页，非死链）
数据   POST /xxmh/xzzf/swxzybcxcfjg/querySwxzybcxcfjg.do
       form: ajmc/xzxdrdm/xzxdrmc/cfjg/page/swjg_dm=13500000000/captcha
       返回(GBK): {count:"N-机关名", data[]:{jdswh,ajmc,cflb,cfsy,cfyj,xzxdrmc,xzxdrdm,fddbrmc,cfjg,cfjg2,cfrq2}}
       无 captcha/空 captcha → {"errMsg":"验证码校验失败"}（服务端强制，page=1 必需）
       页面分页回调 GG.kk→init(page,null)：jQuery 对 null 键直接省略 → 翻页请求不带 captcha 键
       （推断过码一次后翻页免码；未验证到——从未过过第一道码）
验证码 POST /sso/captcha/get.do  {"captchaType":"clickWord","clientUid":"point-<uuid>","ts":<ms>,"browserInfo":...}
       → repData{originalImageBase64(310x155 PNG), wordImageBase64(310x48 条带"请依次点击[X,Y,Z]"),
                 token(32hex), secretKey(32hex)}；repCode 0000
       POST /sso/captcha/check.do {"captchaType","pointJson","token","clientUid","ts"}
       pointJson = SM4-ECB-PKCS5( key=bytes.fromhex(secretKey), plain=JSON.stringify([{x,y}...] x→y 键序) ) hex 小写
       过码(0000)后业务参数 captcha = SM4(token + "---" + <同上JSON>) —— 即 captchaVerification
```

- **SM4 实现核对**：站点 `xxmh/view/xzzf/resource/js/sm4.js`（webpack 混淆）与 python gmssl
  `crypt_ecb` 输出逐字节一致（node eval 实测同一明文/密钥同密文）；秘钥 32 hex、明文 UTF-8、
  pkcs#5、ECB、输出小写 hex。
- 平台页 JSP（2021 年代）内旧的图片码流程（`/tycx-cjpt-web/cxptGz/builderCaptcha.do` + refreshYzm）
  已整段注释，现行由 `verify.js`（`/xxmh/view/xzzf/resource/captcha/js/verify.js`，anji-plus 前端改造版：
  AES→SM4）pointsVerify 弹层接管。

## 2. 验证码服务实测语义（repCode）

| repCode | repMsg | 真实含义（实测） |
|---|---|---|
| 0000 | - | 通过（从未出现过） |
| 6110 | 验证码已失效，请重新获取 | token 已消费（check 失败一次即烧毁 token，不可同码重试/暴力） |
| 6111 | 验证失败 | pointJson 解密+解析成功、点数正确，仅坐标比对不过（anji AJ-Captcha `API_CAPTCHA_COORDINATE_ERROR`） |
| 500 HTML | - | captchaType=speechRecognition 时后端分支未实现直接异常（服务部署缺陷旁证） |

其它旁证：get.do 传 blockPuzzle 仍回 clickWord 数据（wordImage 310x48、无 jigsaw）——项目级强制点选；
speech 请求同样回 clickWord 图，check 提交文本时 500。

## 3. 求解尝试全景（12+ 轮，全部 6111）

| # | 方案 | 结果 |
|---|---|---|
| 1 | 旧图码 builderCaptcha.do + ddddocr 码值提交业务 API | 4/4 "验证码校验失败"；后经 VLM 复核 ddddocr 读码**完全正确**（2c6Kmt）→ 后端已不认旧码 |
| 2 | clickWord：ddddocr det 找字框 + ddddocr/RapidOCR/ddddocr-beta 识艺术字映射 | 背景为彩色低对比艺术字（gray 62-170），各引擎单字识别率 ~20-40%，覆盖 3/3 目标率 <10% |
| 3 | 饱和度通道提取+二值化+闭运算后 OCR | 略有提升仍不足（RapidOCR 全图只认 1-2 字） |
| 4 | 模板匹配（条带目标 vs 背景）多尺度+旋转 | 同字不同字体，NCC 0.35-0.58 无区分度，死路 |
| 5 | 字形 NCC/Hu 矩（裁剪归一化） | 正确对得分反而更低，死路 |
| 6 | VLM（analyze_image）标签九宫格映射（T1-T3 上排 + 1-4 下排，CLAHE 增强裁剪） | 映射质量高且可双验证（多轮 strip/bg 双读一致）——坐标中心提交仍 6111 |
| 7 | VLM 全弹窗图（条带+背景同图） | 与 6 交叉一致 → 排除映射错误 |
| 8 | 坐标变体：中心 / 锚点LB(x1+3,y2-5) / 中点 / 角度查表锚点 | 全 6111 |
| 9 | playwright **有头真浏览器**点击（真实鼠标事件，完整 verify.js 流程） | 同样 6111；网络抓包解密浏览器实发 pointJson 与我的提交逐值一致（坐标空间/变换 100% 正确） |
| 10 | display 空间(400x200)假设提交 | 6111 |
| 11 | 2x 坐标空间假设 | 坐标超出图面无法形成合法点击（前端钳制），结构性不可测 |
| 12 | 随机 3/4 框中心（语义探测 12 连发） | 0/12 过 → check 按字+序严格比对，非集合匹配 |

### 锚点几何（Java2D 模拟实测，simhei 25px，角 -45..+45 每 5°）

存储比对点=drawString 锚点（字左基线，即旋转不动点）。相对 ink bbox 左上角偏移：
θ=-45°:(12,30)；-30°:(8,29)；-15°:(4,26)；-5°:(0,23)；0°:(-1,21)；+15°:(-2,18)；+30°:(-3,16)；+45°:(-2,13)。
锚点距字中心 ≤17px → AJ 标准 HAN_ZI_SIZE=25px 容差下中心点击必过；实际不过 → 部署容差远小于
标准（疑百分比制 ~2% → x±6px/y±3px，或坐标空间错位）。minAreaRect/PCA 估角对近方形字误差
±5-80°，锚点精化到 ±3px 不可达。

## 4. 判"部署缺陷"的证据链

1. 真浏览器（playwright 完整前端链路）同样 6111——排除我方请求层任何差异；
2. SM4/请求体/坐标变换与浏览器逐字节一致（网络日志解密比对）；
3. 字-格映射 VLM 双重验证一致（多轮），点击落点均在字 ink 上（饱和度验证 S≥59）；
4. speech 分支 500（未实现）、blockPuzzle 被强制 clickWord（配置与代码不一致）；
5. 旧图码后端已不认但页面代码残留——迁移做了一半的形态；
6. AJ 标准 ±25px 容差下人类式中心点击必过，实际全拒。
（对拍基准：辽宁 sword 平台同场景 ddddocr 过码率 ~75%、山东 IAB 直取——闽浙两家 xxmh/sword
自建门禁是省局级个案，非技术栈共性。）

## 5. 坑与经验

1. **预研"ddddocr 实测识别成功"≠可过码**：本轮预研只验证了图码可读，没验证后端接受；点选码
   的"识别"包括字、序、坐标三要素，缺一不可。
2. anji-plus 系（repCode 0000/6110/6111 + get.do/check.do + CaptchaVO 字段名）一旦确认，SM4/AES
   变体看 `resource/captcha/js/verify.js` 的 encrypt 调用即可；本站是 SM4-ECB（gmssl 一致）。
3. check 失败即烧 token（6110），一码一试，无法同图暴力；get.do 无频控（12 连发无 6201）。
4. VLM 标签九宫格做"字-格映射"质量高（配合 RapidOCR 读条带目标、ddddocr det 给精确框），
   本轮真正卡死的是**服务端比对基准不可知**，不是识别。
5. playwright 抓 XHR + 服务端密钥解密 pointJson，是验证"我的请求=浏览器请求"的最快手段，
   五分钟排除全部请求层嫌疑——值得固化为攻码标准步骤。
6. Java2D `drawString` 锚点=左基线=旋转不动点；模拟一次（javasim/AnchorSim2.java）可得
   角度→锚点偏移表，用于此类点选码的锚点精化（本轮因角度估计精度不足未能兑现）。

## 7. 抓取量汇总

| 项 | 数量 |
|---|---|
| 求解/探测请求（get/check/query 各类） | 100+ 次 |
| 结构化处罚记录 | **0 条（验证码不可过）** |
| 入库 md | 0 件 |
| 验证码样张/证据 | tmp/fj_cap_*.png、fjx_*.png、fjq*_*.png、fpw_*.png、javasim/sim_*.png |

## 8. 复跑条件（何时值得再试）

- 平台换回图片码/滑块（JSP 里 refreshYzm 复活或 blockPuzzle 生效）→ 直接按第 1 节契约采集；
- check.do 修复（可过）→ 求解器三件套现成：RapidOCR 条带 + ddddocr det + VLM 九宫格映射，
  每码一次 VLM 中转 ~25s，量控内可完成；
- 若福建数据走信用福建/福建政务服务网双公示（未探），另开信源记录。


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
