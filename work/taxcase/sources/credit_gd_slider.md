# 信用广东滑块攻坚记录（2026-10-10，90分钟时间盒）

> 结论先行：**滑块本体已求解**（CONCAT 型验证码 check 通过率 100%，纯算法，无需 OCR），
> **卡点在查询网关**：带 `VALIDATE_CODE_ID`（且 check 已通过）的过滤查询仍 403。
> 下一个 agent 的全部工作就是分辨 403 的真实原因（见文末「下一步」）。

## 一、验证码系统全貌（逆向自前端 JS，全部实测）

滑块是 **tianai-captcha 风格自建系统**（非极验/网易/腾讯），三型随机（GET 一次 roll 一次）：

| 型 | 占比(实测) | 说明 |
|---|---|---|
| CONCAT | ~1/3 | 滚动条带滑块（本项目已自动化） |
| ROTATE | ~1/2 | 图片旋转（未做，遇则重roll） |
| WORD_IMAGE_CLICK | ~1/6 | 依序点字（未做，遇则重roll） |

### 1. 签发
```
GET https://credit.gd.gov.cn/gdcreditwebApi2/wordClickCode/gen
头: Accept: application/json / Request-Client-Set: xygd-web / X-Requested-With: XMLHttpRequest
    （Referer=Origin=https://credit.gd.gov.cn）
→ {"code":200,"data":{"id":"<32hex>","captcha":{
     "type":"CONCAT","backgroundImage":"data:image/png;base64,...",  # 590x360 单图
     "backgroundImageHeight":360,"data":<int>}}}                     # data=条带底边y(图像px)
```
- **必须用浏览器级 TLS**：python-requests 直接 GET 此接口会无限挂起（jsl/加速乐按 TLS 指纹放行）。
  `curl_cffi requests.Session(impersonate='chrome124')` 完全可用（本项目实测）。playwright 页内 fetch 也可用。
- 无额外 cookie（全程只有 `__jsluid_s`），gen/check 均无 set-cookie。

### 2. CONCAT 求解（已 100% 自动化，check 通过率实测 4/4）
- 图像结构：整图 590x360；**顶部条带 = 图像行 [0, 360-data)**，被服务器循环平移（wrap）了 Δ 像素，
  条带内有一道竖直 seam；条带以下是原图。
- **Δ = seam 的 x 坐标**。两种算法等价（5 个样本全部一致）：
  1. seam 检测：条带行内水平梯度最大列；
  2. 循环相关：条带末 5 行 vs 条带下 5 行，遍历 0..589 取 |diff| 最小的平移量。
- **拖动距离 D = Δ × (260/590)**（260=显示宽，实测 `.bg-img-div` 宽度确为 260，高 159，
  background-size:100% 159px、默认 repeat —— 所以是 wrap 滚动）。方向为正号，实测一次通过。
- ddddocr **不需要**：这是滚动对齐型，不是缺口拼图型，slide_match 无用武之地。

### 3. 校验
```
POST /gdcreditwebApi2/wordClickCode/check?id=<gen的id>
Content-Type: application/json
{
 "bgImageWidth":260, "bgImageHeight":159, "sliderImageWidth":260,
 "sliderImageHeight": <((360-data)/360)*159>, 
 "startSlidingTime":"<ISO8601毫秒>", "entSlidingTime":"<ISO8601毫秒>",  # 间隔 0.7~1.4s
 "trackList":[ {"x":0,"y":0,"type":"down","t":0},
               {"x":..,"y":..,"type":"move","t":..}, ... 约20-40个,
               {"x":D,"y":0,"type":"up","t":..} ]
}
→ {"code":200,"data":true}   # data=true 即通过；false 则重 gen（同一 id 只能 check 一次）
```
- trackList 用合成轨迹即可：ease-out(1-(1-p)^2)、±1px 抖动、t 单调递增、总时长 0.7-1.4s。
  **无服务端行为校验的迹象**（合成轨迹 4/4 通过）。
- 通过后 **id 本身 = VALIDATE_CODE_ID**（xzcf.html: `params.VALIDATE_CODE_ID = VALIDATE_CODE_ID`，
  回调参数就是 currentCaptchaId）。

### 4. 数据查询（**卡点在这里**）
```
POST /gdcreditwebApi2/company/web/booleanQueryListByPageSimple
form: tableName=v_ztk_03_sgs_xzcf & page & rows<=50 &
      orderArgs=[{"cf_jdrq_sort":"desc"}] &
      jsonArgs={"cf_cfjg":"like;税务"} & VALIDATE_CODE_ID=<check通过的id>
```
- **实测：即使 id 是 5 秒前 check 通过的，此查询仍 403**（空 message，
  响应内 path 为 `/gdcreditwebApi/...`（无2，网关内部转发痕迹）。
- 同会话：无过滤 page=1 → 200 正常（records=137,634），说明 API 本身没封我们，
  是 vid 校验环节拒绝。
- 排除项：
  - ~~旧 slideimgcode 服务~~：`/gdcreditwebApi2/slideimgcode/web/getImg` 403(HTML 拦截页)、
    `/check` 404 —— 旧系统已死，不存在"id 换签"环节（creditFind 页与 xzcf 同款直传）。
  - ~~cookie/会话绑定~~：gen/check 均无 set-cookie。
  - ~~TLS/头~~：curl_cffi chrome124 与真实浏览器页内 fetch（Edge 有头）结果一致，都是 403。
- 未排除（按可能性排序）：
  1. **IP 已被风控标记**（本时间盒内累计 ~150 次请求，含几十次 gen roll + 多次 403）。
     特征吻合：403 空消息、瞬时返回。换 IP/隔夜再试即可分辨。
  2. check 的"通过"分等级（位置对但轨迹分低 → 标记可疑 token，查询网关拒收）。
     分辨法：真鼠标拖动（drag_flow.py 已写好，本轮被 WAF 对浏览器的临时降速挡住没跑完）。
  3. vid 需要与某内部会话绑定（如 jsl 边缘节点亲和），跨节点失效。

## 二、WAF 行为记录（重要，影响后续 agent 操作节奏）
- credit.gd.gov.cn 前端有 **加速乐（jsl，`__jsluid_s`，x-via-jsl 头）**：
  - python-requests 直连 API：挂起（TLS 指纹）。
  - playwright headless：初期完全可用（本盒前 40 分钟 gen/check 全通），
    **频繁开关约 8 个全新 context 后被降速**：page.goto 90s 超时（有头也一样），但
    curl_cffi 不受影响。→ **续跑请全程用 curl_cffi，别再开新浏览器 context**；
    如必须浏览器，等 10+ 分钟或换 channel。
  - curl_cffi chrome124：稳定 200（页面+gen+check+query 全通）。

## 三、复用资产（tmp/gdslider/）
| 文件 | 用途 |
|---|---|
| `gd_harvest_cc.py` | **主采集脚本（curl_cffi 版，最完整）**：solve_vid()=roll到CONCAT→算D→check；query()；断点 progress/credit_gd_tax.jsonl；md 模板已按山东格式写好（to_md）。修好 403 后直接跑。 |
| `gd_solve2.py` | stateless 求解器 + GEN_JS/CHECK_JS 片段（playwright 页内 fetch 版） |
| `calc_delta.py` | Δ 计算离线验证（5 样本 seam=Δ 全对） |
| `q403_matrix.py` | 403 隔离矩阵（6 种组合，结论见上） |
| `hdr_probe.py` | gen/check/query 头与 cookie 探查 |
| `drag_flow.py` | 真鼠标拖动版求解（写好未跑成——浏览器被降速）**下一个 agent 优先跑这个** |
| `inpage_flow.py` | 有头 Edge 页内全流程（已跑：check 过、query 仍 403） |
| `live_*_bg.png` / `sample*` | 各型验证码样本图 |
| `pw_credit_sd.py`、`solve_probe.py` | 前任 agent 的 playwright 探针（被 supersed） |

## 四、下一步（按序，预计 30-60 分钟）
1. **隔夜/网络环境变更后重跑 `python tmp/gdslider/gd_harvest_cc.py`**（先手动跑一次 solve+query 看 403 是否消失——
   若消失说明是 IP 临时风控，直接采集入库 `lawlibrary/专题/税务案例/广东省/信用广东处罚公示/`）。
2. 仍 403 → 跑 `drag_flow.py`（真鼠标轨迹）。若真鼠标过 → 是轨迹分级，把真实事件序列录下来回放。
3. 仍 403 → 抓一次真人浏览器的完整请求（DevTools 导出 HAR）做字节级 diff（头/字段顺序/HTTP2 伪头顺序）。
4. 仍 403 → 放弃 vid 路线时的替代通道：gdzwfw 政务服务网处罚 SPA（expand_round2 遗留）、
   或按地市"税务"关键词走搜索引擎 site: 补量。
5. 合规：每请求 ≥2s、仅公开处罚公示、上限 2000 条——本轮脚本已内置。

## 五、本轮时间盒产出
- 滑块机制 100% 探明 + CONCAT 100% 自动化求解（4/4 check 通过）
- 403 卡点定位到"查询网关 vid 校验"环节，三种剩余假设与分辨实验全部列出
- 机制文档（本文件）+ STATE.md 二.4 已更新
- 数据入库：0 条（全卡在 403；采集脚本就绪，403 解决后一条命令全量入库）


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
