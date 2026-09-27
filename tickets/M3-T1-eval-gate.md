# M3-T1 · 评估闸门 v1（F7）

**状态**：done（2026-09-27） ｜ **上游**：charter §4 L5、§6 M3；PRD F7

## 任务（实际落地）

- `fieldforge/evaluate.py`：三族指标插件化注册 + JSON/HTML 报告，`fieldforge evaluate` 子命令（fail → exit 1，即"未过闸门不得出库"的 CLI 语义）。
- **质量族**：q1 行数与 manifest 账实一致；q2 数值列非退化；q3 同构参照分布对比（纯 stdlib KS 统计量 + 均值偏差；均值差 >10× 判"不同分布域"记 skipped 不硬判）。
- **隐私族**：p1 主键重复率（schema 驱动，读 manifest.schema.file → schema primary_key）；p2 数值组合重复率（全合成场景的结构性隐私信号）；p3 anonymeter 三类攻击 = skipped（需真实参照数据，`--real` 接口已留，不硬编）。
- **物理一致性族（自研差异化）**：f1 物质平衡（含水率 ∈ [0,1]）；f2 停机一致性（hours=0 ⇒ 产量 0）；f3 传感器量程合法性；f4 停机读数静稳；f5 日间递减率合理性（对数跳变界，与注入尖刺设计幅度对齐）。

## 样例报告（charter M3 验收物，随仓 docs/reports/）

| 样例 | overall | 说明 |
|---|---|---|
| [m3-sample-pass.json](../docs/reports/m3-sample-pass.json)（+.html） | **pass**（10 pass + 1 skipped） | 干净五表出库样例 |
| [m3-sample-fail-injected.json](../docs/reports/m3-sample-fail-injected.json)（+.html） | **fail**（f3 + f4） | 注入数据被闸门精准抓住：量程越界 35.445 > 35、停机静稳被坏点打破——**闸门抓坏点能力实证** |

## 验收

- [x] 三族指标齐全（质量 3 + 隐私 3 + 物理 5 = 11 指标）
- [x] 样例评估报告 JSON/HTML 随仓
- [x] 指标为函数插件（注册即用）；fail→exit 1 闸门语义
- [x] 单测 7 条（好数据过 / 量程越界 fail / 停机不一致 fail / 主键重复 fail / 参照恒等 KS=0 / anonymeter skipped / CLI exit code 语义）全过

## 备注（后续票）

- anonymeter 三类攻击：`--real` 接口已留，待真实锚点数据（Volve/FORCE，charter Q5 license 审阅后）接入即为真隐私评估。
- 生成时自动过闸（emit 内嵌 gate）与"未过闸不出库"的流程级强制，属后续集成票。
- 递减率 f5 的阈值（2×/3×）按当前注入器设计幅度对齐；注入器参数变更时需联动。
