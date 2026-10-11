# 内蒙古自治区 税务案例抓取来源文档（第七轮）

抓取日期：2026-10-11 ｜ adapter：`adapters/nmg_r7.py`（列表+详情）、`adapters/r7_md.py --part nmg`（转 md）
断点：`progress/neimenggu_r7.jsonl`；原始数据：`tmp/nmg/`（zdaj_rows.json / zdaj_meta.jsonl / zdaj_*.html）

## 一、站点机制（neimenggu.chinatax.gov.cn，无墙直连）

- **无反爬**：curl_cffi chrome124 直连全通（首页/列表/详情均 200），全轮未见过 412/瑞数。
- CMS 为 TRS 系（/nsfw/... 栏目 + tYYYYMMDD_NNNNN.html 文章页）。

## 二、重大税收违法失信主体信息公布栏——主源，487 件 md（全量）

1. 栏目页 `/nsfw/sscx/zdaj/`：高级检索表单（纳税人名称/识别号/注册地址/组织机构代码/
   法定代表人/财务负责人），**表单 action 指向 `/was5/search`，隐藏 channelid=214090**
   （页面另有一个 channelid=286494 的全站搜索表单——别混，那是站内全文检索）。
2. 真数据接口（青岛 WAS5 同款）：
   `GET /was5/search?channelid=214090&searchword=&sortfield=-DOCRELTIME&perpage=100&page=N`
   - 返回 HTML 表格：所属税务机关/纳税人名称/识别号/案件性质/详细信息链接；
     页脚「共有487条记录 当前页数:1/总页」
   - **perpage=100 有效**（默认 10，可提效 10 倍）；5 页收全 487
   - 案件性质列是内联 `<script>`（var anj='…'）JS 映射输出，抓列表时用正则取 anj 原值
3. 详情 `/nsfw/sscx/zdaj/<地区码>/<yyyymm>/tYYYYMMDD_NNNNN.html`：
   [标签,值] 成对表格，含 **主要违法事实相关法律依据及税务处理处罚情况** 全文
   （合并行，需挂 `**主要违法事实**：` 下过质量门槛——宁波/陕西同款事故坑）；
   `<meta name="PubDate">` 取发布日期。
4. 质量门槛：487/487 KEEP（dishonesty 规则，事实叙述全部 ≥30 字）。

## 三、坑

1. **行解析正则回溯陷阱**：整页 115KB 用跨单元格 `.*?` 大正则匹配 <tr> 会灾难性回溯
   （首轮作业卡死 15 分钟无输出）。必须 split("<tr") 逐行再取格。
2. 列表单元格文本会带属性残渣（`id="sbh444"class="sbh"…>值`），清洗时取 `>` 后段。
3. 站内 WAS5 全文搜索（channelid=286494）会把普通新闻也搜出来，与失信库无关。

## 四、产出

| 目录（lawlibrary/专题/税务案例/） | 件数 |
|---|---|
| 内蒙古自治区/重大税收违法失信公布 | 487 |

## 五、复跑

```bash
cd work/taxcase
python adapters/nmg_r7.py --part list   # 枚举 487 行 URL → tmp/nmg/zdaj_rows.json
python adapters/nmg_r7.py --part det    # 详情断点续抓
python adapters/r7_md.py --part nmg     # 离线转 md（幂等，质量门槛就地判定）
```


---

> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
