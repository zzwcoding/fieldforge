# P2-T4 · M4 文档层 v1 —— 班报模板叙述化 + 数值一致性机判回流（F6 起步）

**状态**：done（2026-09-27，模板叙述化 v0.1） ｜ **上游**：charter §4 L4、§6 M4；PRD F6

## 任务（实际落地）

- `fieldforge/narrate.py`：一行生产事实 → 一篇班报（well_info 上下文 + oil_production_daily 行 → 中文班报文本，含停产日句式）；批量 = 某井全期语料（每日一篇 .txt + narration_manifest.json）。
- **数值一致性机判回流**（F6 验收要求"文中数值与结构化源一致，抽查可机判"）：逐字段正则提取比对，容差=文本舍入位的一半（含水率 1 位 → ±0.05，油量 2 位 → ±0.005）；不合格语料 narrate 退出码 1，不得入评测集。
- CLI：`fieldforge narrate --data out-tpa --well N-01 --days 7`。
- 样例随仓：[docs/reports/m4-sample-班报语料.md](../docs/reports/m4-sample-班报语料.md)（N-01 井 7 天，机判全过）。

## 验收

- [x] 模板自产自检零违例；篡改文本（30.00→35.00）必被机判逮住
- [x] 停产日句式与生产日句式同构（字段句齐全，不因分支漏句）
- [x] "查无此井"返回码 2（对齐平台 W-F9-3 合法数据态）

## 备注

- **LLM 叙述化待选型（charter Q7）**：接口已定为"per-row 事实 dict → 文本"，接模型后只换 daily_report 实现，机判回流层不变——LLM 产出的班报必须过同一道数值一致性闸。
- 工单/完井报告叙述化、reports 桶 PDF 对接属 M4 后续票。
