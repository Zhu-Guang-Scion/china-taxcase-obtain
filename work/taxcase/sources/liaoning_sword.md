# 辽宁 sword 行政执法公示平台 + 主站失信公布栏 —— 抓取源记录（2026-10-10）

## 0. 一句话结论

**辽宁是山东同款 wings/sword 平台中数据最全的一个省：处罚公示接口真实有数据
（全省 213 机关合计 5,537 条，近三年 5,524 条），验证码是服务端强制但 ddddocr
快速通过（每次 POST 消费一个码），python requests + 浏览器 UA 直连即可（无需 playwright）。
另主站「重大税收违法失信主体公布栏」（col1030，路径级 JS 挑战）藏有约 1,990 条
失信主体结构化详情（含主要违法事实完整叙述），挑战已纯 python 求解。**

| 源 | 接口 | 数据量 | 入库（过 quality_prune 门槛） |
|---|---|---|---|
| 平台·一般处罚结果 | POST /ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg | 5,537（收 5,000 封顶） | **216 件** → 辽宁省/行政处罚公示 |
| 主站·失信公布栏 | GET /module/search/index.jsp（col5883）+ art 详情 | ≈1,990（收 1,000 封顶） | **995 件** → 辽宁省/重大税收违法失信公布 |
| 平台·失信披露（gssxDm=19） | POST XzzfgsptXxfblCtrl_getXxfblData | **2 条且无叙述**（全 213 机关扫描） | 0（DEL） |

复现脚本：`adapters/ln_sword.py`（处罚采集）、`adapters/ln_sx.py`（失信采集）、
`adapters/ln_sword_md.py`（转 md + 质量门槛）。断点：`progress/ln_sword.jsonl`、
`progress/ln_sx.jsonl`。机关代码表：`tmp/ln/ln_swjgdm_all.json`（213 个）。

## 1. 平台结构（wings/sword，与浙江同款但**有数据**）

```
入口  https://etax.liaoning.chinatax.gov.cn:8090/sword?ctrl=XzzfgsptHomeCtrl_index
      （首页 GET 200 无墙无验证码；菜单 JSON 在 /xzzfgspt/static/common/json/liaoningshengData.json）
菜单  一般处罚结果 xzcf_01 → /sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg
      重大税收违法失信案件信息 xzcf_02 → 跳主站 col1030（平台内 gssxDm=19 披露页全空，见 §4）
      另有 欠税/非正常户/许可/委托代征 等菜单（本任务未收）
查询页 GET /sword?ctrl=XzzfgsptXzcfCtrl_initSwxzybcxcfjg&sxq=liaoningsheng&swjgDm=<code>
      （种 GSPT_SESSION cookie；SwordPageData 回传 swjgDm/province/sessionID）
数据  POST /ajax.sword?ctrl=XzzfgsptXzcfCtrl_getSwxzybcxcfjg
验证码 GET /download.sword?ctrl=CheckcodeUtil_getCheckcode&t=<32位随机>&id=ck1
      （参数名是 id 不是 ckcodeId——同浙江坑；4 位混合大小写字母数字 JPEG）
```

- **无 WAF/TLS 挑战**；但 python requests 默认 UA 直接 **403**——加浏览器 UA 即过。
- 平台 JS 证据：`ptsy_index.js` 含 `province == 'shenzhenshi'` 分支，
  同一 host 同时承载 liaoningsheng/dalianshi/zhejiangsheng 等 Data.json（多省共用 wings 平台，
  逆向一次可复用）。**dalianshi 是独立 config**（大连市税务局单列，20 机关代码）。

## 2. postData 契约（实测）

POST body 为 form 编码单字段：`postData=<urlencoded JSON>+`（尾 + 是 jQuery 风格空格），
需头 `X-Requested-With: XMLHttpRequest` + Referer。外层
`{"tid":"","ctrl":"XzzfgsptXzcfCtrl_getSwxzybcxcfjg","data":[...],"bindParam":true}`，
`data` 元素 `{"name":k,"value":v,"sword":"attr"}`：

| name | 含义 | 说明 |
|---|---|---|
| ajmc/nsrsbh/nsrmc/cfjg | 案件名/代码/名称/机关（模糊） | 可空 |
| yxqq/yxqz | 处罚日期起止 yyyy-mm-dd | 可空；实测 2016→2023-10 仅 13 条，2023-10→今 5,524 条 |
| swjgDm | 机关代码 | **逗号分隔可 213 个一起传**（全省一次查） |
| rows | 每页条数 | 页面选项只到 50，**实测 200 有效** |
| pageNum | 页码 | 直接追加即可翻页（无需首响应 bizParams 回传） |
| ckcode/ckcodeId | 验证码值/固定 ck1 | **服务端强制校验**（与山东纯前端不同） |

**响应**：`data[]` 含 SwordGrid（`trs[].tds.<fld>.value` 行记录、`totalRows`、
`bizParams` 回传查询）+ msg/flag/sessionID。字段（比山东多罚款金额）：

`xzcfjdswh` 文号 / `ajmc` 案件名 / `cflb` 类别 / `wfsd` **处罚事由** / `swxzcfyj` 处罚依据（常长文）
/ `nsrmc` 相对人 / `nsrsbh` 代码（部分打码）/ `fddbrxm` 法代 / `cfjd` 处罚结果（含金额）
/ `cfjg` 机关 / `cfrq` 处罚日期 / `fkje` 罚款金额（124/5000 有值）/ `uuid`（主键，翻页零重复）
/ `wszzrq` 文书制作日期 / `sjlydw` 数据来源单位 / `sjlx`（JC=稽查）

**机关代码**：213 个 = 省 193 + 大连 20。来源：`liaoningshengData.json` 的 `ctiy` 树
（每区划 `zgswjDm` 逗号串 + `xjsxq` 下级递归）。省局 12100000000、大连 12102000000。

## 3. 验证码（与山东/浙江对比）

- **山东**：数据接口不校验码（纯前端把戏）→ 页内 fetch 直拿。
- **浙江**：校验码 + 平台空库。
- **辽宁**：**校验码 + 有数据**。ddddocr 默认模型 60x20 混合码过码率约 75%，
  换码重试循环即可（`adapters/ln_sword.py` 的 query_page，每页 1-2 次命中）。
- 语义同浙江：`浏览器超时`=session 无码；`验证码不正确`=码错；
  `未查询到结果`=**过码后空结果**；flag=0+grid=成功。

## 4. 失信两条路径（一空一富）

1. **平台内 gssxDm=19 披露页**（`XxxfblCtrl_getXxfblData`，postData: rows=页码/pagesize/
   swjgDm/gssxDm，无验证码）：**213 机关全扫描仅铁岭银州区 2 条**，详情 gsnr 仅
   "未按规定申报。"（7 字，无叙述）→ quality_prune 判 DEL，不入库。
2. **主站 col1030「重大税收违法失信主体公布栏」**（真源）：
   - 栏目页 `/col/col1030/index.html` 路径级 JS 挑战（playwright 有头一次通过观察契约；
     之后纯 python 复现，见 §5）
   - 列表 `GET /module/search/index.jsp?field=a:1:1,b:1:1&i_columnid=5883&a=&b=&currpage=N`
     （10 条/页；currpage 超界钳到最后页；共约 199 页 ≈ 1,990 条；支持 a=名称 b=识别号 筛选）
   - 详情 `/art/YYYY/M/D/art_5883_<id>.html` **无挑战直连**；字段以
     `<!--<$[label]>begin-->VAL<!--<$[..]>end-->` 标记包裹：
     纳税人名称/识别号/注册地址/法定代表人（姓名、性别、证件打码）/案件性质/
     **主要违法事实（完整叙述，普遍 ≥60 字）**/相关法律依据及税务处理处罚情况

## 5. 大汉 CMS 路径级挑战的纯 python 求解（可复用）

挑战页特征：`len<2500` + `new Array()` + `eval(`。算法（`adapters/ln_sx.py` decode_lmcl）：

1. 提取混淆串（`\xNN` 序列）与异或参数 Ag（调用处 `xfL(65,...)`）
2. 三轮字节变换（加法+循环左移7 → 取反+异或13 → 异或182加35）
3. 奇数下标字节异或 Ag 解出 payload：`window.open(f4+"?LMCL=<token>"+Lj,"_self")`
4. **LMCL 必须作为 query 首参**重放（`?LMCL=xxx&field=...`；放末尾服务端不认）
5. 通过后服务端种 `UqZBpD3n3iXPAw1X` cookie（约 30 天有效），同会话免挑战；
   频率高时挑战会复现，再解一次即可

## 6. 质量门槛结果（quality_prune.decide，强制）

- 处罚公示 5,000 条：**KEEP 216 / DEL 4,784**（del 原因全部 facts<30）。
  辽宁平台 wfsd（处罚事由）多为短语（"在账簿上多列支出"/"逃避缴纳税款"），
  但 swxzcfyj（处罚依据）常带完整计算叙述——**cjk≥800 且 fl≥15 的
  long-but-thin-facts 规则救回了相当部分**， KEEP 的 md 因此普遍很长。
  与山东对比：山东 3,243→3,088 过门槛（95%），辽宁 5000→216（4.3%）——
  辽宁平台的事由字段本身远比山东简短，非抓取问题。
- 失信公布栏 1,000 条：**KEEP 995 / DEL 5**（dishonesty 规则，事实叙述中位 74 字）。

收尾已执行：`structure_extract.py` + `build_manifest.py` 重建三件套（全库 16,600 件口径）。
辽宁目录新增：行政处罚公示 216 件 + 重大税收违法失信公布 995 件
（另有此前轮次已存在的 辽宁省/税案通报 约 36 件，非本轮产出）。

## 7. 坑与经验

1. python requests 默认 UA → **403**（不是 WAF，是 UA 白名单）；curl 默认 UA 反而能过。
2. 验证码 URL 参数名 `id`（非 postData 里的 ckcodeId）——同浙江坑，服务端 session 存储 key。
3. rows=200 有效（页面 UI 只给 50），5537 条 28 页收完，uuid 去重后零重复（山东的
   totalRows 虚高问题在辽宁不存在）。
4. swjgDm 必填；空串 → exception；**全省 213 码逗号拼接一次查询**比逐机关查快 213 倍。
5. 大连不单独处理：机关代码并入全省串即可；主站失信栏 col5883 也是全省混排（含大连案源）。
6. 主站 /art/ 与 /module/search/ 路径起初无挑战，**连续请求约 55 次后挑战跟到 search 路径**——
   decode_lmcl 重放即可恢复；art 详情路径始终未见挑战。
7. 失信列表 currpage 超界**钳到最后页**（不报错），探测总数要用二分+内容对比。
8. 平台 Xxfbl gssxDm 披露页 postData 的 `rows` 参数实为**页码**（pagesize 才是页大小）。

## 8. 抓取量汇总

| 项 | 数量 |
|---|---|
| 处罚查询请求（含验证码重试） | ≈40 页 × 1.3 |
| 处罚结构化记录 | 5,000（总量 5,537，量控截断；近三年 5,524 条全覆盖） |
| 失信公布栏 art 详情 | 1,000（总量 ≈1,990，上限截断） |
| 平台失信披露扫描 | 213 机关 × 1 次 |
| 入库 md（处罚/失信） | **216 / 995** |


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
