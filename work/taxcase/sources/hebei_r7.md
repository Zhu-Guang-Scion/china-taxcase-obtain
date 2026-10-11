# 河北省 税务案例抓取来源文档（第七轮）

抓取日期：2026-10-11 ｜ adapter：`adapters/hb_r7.py`（有头采集）、`adapters/r7_md.py --part hb`（转 md）
断点：`progress/hebei_r7.jsonl`；原始数据：`tmp/hb_r7/penalty_all.jsonl`

## 一、站点机制（瑞数，HTTPS 残）

- 主站 hebei.chinatax.gov.cn：**HTTPS 证书与域名不匹配**（curl 报 no alternative certificate
  subject name，verify=False 则 504）——HTTPS 通道不可用；**HTTP 通道瑞数 412**（$_ts 挑战）。
- 有头 chromium（--disable-blink-features=AutomationControlled）过挑战无压力；
  **`/index.html` 是 404**（"您访问的页面不存在"——曾被误判为挑战不过），入口用根路径 `/`。
- 执法公示平台在独立子域 `http://wzyy.hebei.chinatax.gov.cn/LawPublicity/`（同样瑞数）。

## 二、重大税收违法失信主体信息——空库（实测）

- 页面 `/LawPublicity/law/adPenalty/taxDishonestyCases`，RuoYi 式 bootstrap-table
  （utils.js 的 `$.table`）。数据接口
  `/LawPublicity/app-publicity-service/law/penalty/findTaxDishonestyCasesList?cid=27&uid=`，
  POST（pageSize/pageNum + queryCity/queryType/queryDate/NSRMC/...）。
- **坑 1：页面自带 `$.table.init` 因脚本 404 根本不初始化**——需在页面上下文手动
  `$.table.init({...})`（带原生 columns，否则表格行渲染为空）后 jumpCity/jumpType 才生效。
- **坑 2：evaluate 里 fetch/$.ajax 一律 412/500**——数据请求必须由页面自身
  bootstrap-table 发起（URL 带瑞数动态令牌 R432t1Wu=...），故采集=UI 驱动 + 
  `$('#bootstrap-table').bootstrapTable('getData')` 读原始行（含未脱敏 NSRSBH）+
  `nextPage` 翻页。
- 实测全维度 0 条：全部/省局/石家庄/唐山/保定/邯郸/雄安/定州（jumpCity）、
  虚开（jumpType）、2024（jumpDate）——空库（浙江剑/山西 zdsswf 同款形态）。

## 三、行政执法公示平台·税务行政一般程序处罚结果——主源

1. 页面 `/LawPublicity/law/adPenalty/taxPenaltyResult`，接口
   `.../penalty/findTaxPenaltyResultList?cid=26&uid=`，同款 bootstrap-table 玩法。
2. **省级 uid='' 是空壳（"本税务机关尚未产生此信息"）——数据按市会话切换**：
   `.listwzqbox a[data-id]` 程序化 click → POST changeCity（带令牌，程序化 click 可过）
   → **必须整页重新 goto**（changeCity 绑定只做局部 load，不整页导航查询仍回省级空数据）
   → 手动 init → getData/nextPage 采集。total==0 时再切一次市重试（时序竞争偶发）。
3. 城市 data-id：2 石家庄 / 3 唐山 / 4 秦皇岛 / 5 邯郸 / 6 邢台 / 7 保定 / 8 张家口 /
   9 承德 / 10 沧州 / 11 廊坊 / 12 衡水 / 167 雄安 / 171 定州 / 172 辛集。
4. 字段（原始 JSON）：XZCFJDSWH 决定书文号 / AJMC 案件名称 / CFLB 处罚类别 /
   CFSY 处罚事由 / CFYJ 处罚依据 / NSRMC 相对人 / NSRSBH 代码（未脱敏）/
   FDDBRXM 法人 / CFJG 处罚结果 / CFSWJG 处罚机关 / ZCGCFRQ 处罚日期 + uid/SXUUID。
5. pageSize=50 有效（pageList [10,25,50,100]）。

## 四、坑（汇总）

1. HTTPS 证书错配 → 只能 HTTP；/index.html 404 勿当挑战死循环。
2. 挑战通过有时滞性（goto 偶发 50s 超时），pw_open 型轮询重试 4 次必过。
3. 表格不自带 init（脚本 404）；columns 必须带字段映射，否则 getData 行为异常。
4. evaluate 发起的 XHR 全被瑞数拦（fetch/$.ajax 都 412）——只有页面自身逻辑发出的
   请求带令牌。采集一切靠 UI 驱动 + getData。
5. 城市切换后不整页重导航，查询仍打到省级（空数据假象）。

## 五、产出

各市平台 total：石家庄 273 / 唐山 251 / 秦皇岛 46 / 邯郸 178 / 邢台 175（首轮时序竞争
假 0，重跑即得）/ 保定 307 / 张家口 119 / 承德 41 / 沧州 337 / 廊坊 218 / 衡水 120 /
雄安 62 / 定州 27 / 辛集 15 —— 城市会话有**跨市重叠**（稽查局案件在多市列表同时出现：
石家庄 273→173、沧州 337→187、雄安 62→50），raw 2,207 按文号+uid 全局去重。

| 目录（lawlibrary/专题/税务案例/） | 件数 |
|---|---|
| 河北省/行政处罚公示 | **1,907**（去重后全部过质量门槛 facts≥30；日期跨度 2019-10→2026-09） |

## 六、复跑

```bash
cd work/taxcase
python adapters/hb_r7.py            # 全城市（断点 pen_city 续跑）
python adapters/hb_r7.py --city 2   # 单市
python adapters/r7_md.py --part hb  # 离线转 md
```


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
