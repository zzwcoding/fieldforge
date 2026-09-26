# M1-T3 · 冒烟测试 + 验收收口

**状态**：done（2026-09-25） ｜ **上游**：charter §6 M1 验收物；PRD F9

## 任务

- `tests/test_m1.py`（stdlib unittest，零第三方依赖）：
  - 同种子两次生成 `production_daily.csv` 字节级一致（可复现）
  - 行数=配方天数、日期连续、产量非负、停机日（producing_hours=0）产量=0、含水率上限、manifest 单位表覆盖全部 production_daily 字段
- README 补"快速开始"用法；验收跑通记录。

## 验收（charter M1 原文）

- [x] 一条命令生成 1 口井 × 365 天点表
- [x] 全部字段来自 schema 声明，零手写数据
- [x] 同种子可复现（测试保证）

## 遗留（进 M2）

- 传感器**日度读数**时序（当前 M1 只产通道注册表，读数时序随 F4 噪声注入器在 M2 落）
- 物理打底（OPM Flow 独立进程适配器，Q8 算力实测先行）
