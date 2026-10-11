# 山西省 税务案例抓取来源文档（第七轮）

抓取日期：2026-10-11 ｜ adapter：`adapters/sx7.py`（采集）、`adapters/r7_md.py --part sx`（转 md）
断点：`progress/shanxi_r7.jsonl`；原始数据：`tmp/sx_r7/xzcf_records.jsonl`（1,923 条 JSON）

## 一、站点机制（shanxi.chinatax.gov.cn，无墙直连）

- 主站根路径 `/` 直连 200（**/index.html 404**，入口用根路径）。
- 执法公示平台独立应用：`/xzzfgsptWeb/web`（Spring + mybatis + jQuery myPagination）。
- 注意山西=shanxi、陕西=shaanxi（拼音域名校验过，勿混）。

## 二、重大税收违法失信栏——空库（浙江剑同款，机制通 0 数据）

- 入口 `/topic/zdsswf/sx-11400`：查询表单 → `POST /common/extQuery?sqlid=web_zdsswf`
  （body `start=(page-1)*limit`，插件 myPagination6.0.1 以 URL 带 &page=N + POST start 翻页）。
- 实测：GET 返回"系统出错"、**POST 通但 totalRow=0**；NSRMC=有限公司 / 案件性质 /
  年度 / 省市两级（sx/ty/dt/cz…）全条件 0 条。非法 sqlid 会抛 ibatis 异常——证明
  端点活着、就是库里没数据。真浏览器复刻同结果（表格显示"没有找到相关数据"）。
- 详情接口 `POST /common/commonQueryOneData`（sqlid=web_ajxq&ajbh=…）字段契约已挖出
  （NSRMC/NSRSBH/ZYWFSS/FLYJ_CLJG/XSRQ 等）——库若日后接入数据可直接复用。

## 三、行政执法公示平台·税务行政一般程序处罚结果——主源，1,923 件 md

1. 平台首页 `/xzzfgsptWeb/web/list/11400-2661`（行政处罚栏）→ 左侧导航 reveal：
   数据碎片 `/xzzfgsptWeb/xzcfweb/swxzybcfjg/<orgid>-2662`。
2. **省级 orgid=11400 显示"本单位暂未产生该项执法信息"——数据在市级**。
   碎片页内联脚本把真 API 注释掉了，挖出契约：
   `POST /xzzfgsptWeb/commonRemote/extQuery?sqlid=swxzybcfjg&limit=100&lmdm=2662
    &orgid=<市orgid>&swjgdm=<orgid*1e7>&db=xzzf&page=N`，body `start=(N-1)*100`。
3. **市级 orgid=11401…11411**（太原/大同/阳泉/长治/晋城/朔州/晋中/运城/忻州/临汾/吕梁）：
   - 有数据：11401 太原 471 / 11402 大同 397 / 11403 阳泉 161 / 11404 长治 291 /
     11405 晋城 392 / 11406 朔州 211 → **合计 1,923**
   - 0 数据：11407-11411（晋中/运城/忻州/临汾/吕梁）
   - limit=100 有效；Referer 需带平台页（session 无强校验但带上稳）
4. 字段（大写下划线）：JDSWH 决定书文号 / AJMC 案件名称 / CFLB 处罚类别 /
   **CFSY 处罚事由**（4～692 字）/ CFYJ 处罚依据 / XZXDRMC 相对人 / XZXDRDM 代码 /
   FDDBRXM 法人 / **CFJG 处罚结果（处罚内容全文）** / CFSWJG 处罚机关 / CFRQ 处罚日期
   （机关字段自带市名，无需 orgid→市名映射）。
5. 质量门槛：1,923/1,923 KEEP（CFSY+CFJG 合并后事实叙述 min 168 / median 362 字）。

## 四、坑

1. 失信栏 extQuery 必须 POST（GET 报"系统出错"），且 body 要 `start=0`。
2. 市级 swjgdm = orgid×10^7 拼出（11401 → 114010000000）。
3. 省级页面"暂未产生执法信息"不代表全省无数据——必须逐市 orgid 枚举。

## 五、产出

| 目录（lawlibrary/专题/税务案例/） | 件数 |
|---|---|
| 山西省/行政处罚公示 | 1,923 |

## 六、复跑

```bash
cd work/taxcase
python adapters/sx7.py                 # 11 市 orgid 枚举采集（断点续跑）
python adapters/r7_md.py --part sx     # 离线转 md（幂等，质量门槛就地判定）
```


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
