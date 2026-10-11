# _recon/ —— 过程侦察脚本归档

> 审查修复（P1）：本目录存放逆向侦察/一次性探测脚本，**不参与生产抓取流程**。
> 生产 adapter 请勿 import 本目录内模块；有头过墙公共逻辑已抽到
> `../pw_common.py`（`pw_open` / `body_text_len` / `log`）。

| 脚本 | 用途（过程产物） |
| --- | --- |
| qd_hn_recon.py | 青岛/湖南 chromium 过墙侦察（栏目与接口摸底） |
| qd_recon2.py | 青岛二轮侦察 |
| hn_hardcase_test.py | 湖南 hardcase 失信接口测试 |
| hbcq_recon2.py ~ hbcq_recon8.py | 河北/重庆多轮侦察迭代 |
| hbcq_river.py | 河北/重庆栏目"河流"遍历侦察 |

均为历史过程脚本：结论已沉淀进对应生产 adapter（qd_* / hn_* / hbcq_*）与
SOURCES.md，留档仅供追溯。运行需要本机有头 chromium 环境。

---
> 记录与代码作者：Zhu-Guang-Scion · github.com/Zhu-Guang-Scion · CLAW-ZGS-2026 · MIT
