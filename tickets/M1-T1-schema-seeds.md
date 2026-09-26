# M1-T1 · L0 schema + 种子字典

**状态**：done（2026-09-25） ｜ **上游**：charter §4 L0/L1、§6 M1；PRD F1/F2

## 任务

- `schemas/core-v0.yaml`：四实体（well / wellbore / sensor_channel / production_daily）的字段、类型、**单位制**、枚举取值域、数值量程声明；production_daily 挂规则模型 `arps_production`（Arps 递减 + 含水率爬升 + 停机事件 + 噪声），模型参数一并声明在 schema。
- `fieldforge/seeds/dicts.json`：种子字典——虚构油田名/区块码、标准传感器目录（油压/套压/温度，带量程与采样间隔）。

## 验收

- [x] schema 可加载并过结构校验（`fieldforge.schema.load_schema`），每个字段有 unit 或 enum 取值域或量程
- [x] 种子字典头部带"全部虚构"声明
- [x] 生产时序为拍板域 Q2（生产时序先行）：production_daily 覆盖 365 天日度
