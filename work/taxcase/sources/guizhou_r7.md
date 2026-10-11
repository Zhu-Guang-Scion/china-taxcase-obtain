# 贵州省 · r7（2026-10-11）

## 结论
失信栏 **1,197 件全收**（源数据 1,216 行含 27 条重复行，100% 过门槛）+ 行政处罚结果公示 **215 件过门槛**（1,137 条中 912 件短语型事实被门槛正确过滤）。

## 源 1：重大税收违法失信主体信息公布栏
- **入口**： https://guizhou.chinatax.gov.cn/zdsswfsxajxxgbl/index.html （主站首页 → 我要查询 → 重大税收违法失信主体信息查询，经 JS redirect 三跳到 /zdsswfsxajxxgbl/）
- **机制**： 页内 jQuery ajax `POST https://guizhou.chinatax.gov.cn/irs/front/list`，JSON body：
  ```json
  {"pageNo":1,"pageSize":100,"tenantId":71,"tableName":"t_17e6b2c59ad",
   "searchFields":[],"sorts":[{"sortField":"save_time","sortOrder":"DESC"}],
   "customFilter":{"operator":"or","properties":[
     {"property":"f_202211853800","operator":"eq","value":"5735176"}]},
   "channelId":"5735176","isPage":true}
  ```
- **两个硬条件**（实测）：①必须 **https** + `Origin: https://guizhou.chinatax.gov.cn` 头——用 http 或无 Origin 返回 `{"success":false,"msg":"系统错误"}`；②customFilter 的 channel 过滤不可省
- **行即富全文**：`f_2022210646272`（主要违法事实，中位 77 cjk）+ `f_2022210441122`（处理处罚）+ f_2022118461091（名称）/f_2022118237203（识别号）/f_2022118992009（地区）/f_2022210398099（案件性质）/f_202211845（法定代表人）/f_2022118615143（注册地址）/f_2022210630938（公布依据）/save_time/rec_id
- 覆盖至 2026-09；total=1,216，唯一 rec_id 1,189

## 源 2：行政处罚结果公示（双公示平台）
- **入口**： http://guizhou.chinatax.gov.cn/xzzfxxgspts/gzsswj/xzcf/swxzybcxcf/ （主站"行政许可、行政处罚双公示"三跳到达）
- **机制**： 同一个 `/irs/front/list` API，仅 channelId=5793970——**同一张表 t_17e6b2c59ad 按 channel 切失信/处罚两个视图，字段语义按渠道变**：
  - 失信渠道 f_2022118461091=纳税人名称；处罚渠道同字段=**违法事实全文**
  - 处罚渠道映射：f_2022118981169 相对人 / f_2022118439324 证件号 / f_2022118992009 处罚依据（全法条）/ f_2022118615143 罚款额 / f_2022118237203 文书字轨 / f_2022118305177 法定代表人 / f_202211845 机关 / f_2022118888238 决定日期
- **数据形态**（如实记录）：1,137 条中约 80% 违法事实是短语（"丢失发票25份"级，中位 19 字）——辽宁 wfsd 同款形态，quality_prune 门槛 DELETE 912 件、KEEP 215 件（含虚开等富叙述）

## 坑
- irs/front/list 的 channel 过滤字段是 `f_202211853800`（带 `<em>` 高亮回显），不要拿回显值当过滤值——过滤用裸 channelId 数字
- 站内 JS redirect 页（`var lm="..."` + document.write Refresh）多且嵌套，抓取要解析 JS 里的目标 URL 而非 meta refresh

## 产出
- adapter： `work/taxcase/adapters/gz_r7.py`（失信）+ `gz_xzcf_r7.py`（处罚）
- 断点： `progress/guizhou_r7.jsonl` + `progress/guizhou_xzcf_r7.jsonl`
- 库： `lawlibrary/专题/税务案例/贵州省/{重大税收违法失信公布,行政处罚公示}/`


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
