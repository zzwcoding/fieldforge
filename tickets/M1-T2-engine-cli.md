# M1-T2 · 生成引擎 + 输出 + CLI

**状态**：done（2026-09-25） ｜ **上游**：charter §4 L1/L5/L8 输出；PRD F2/F8/F9/F10

## 任务

- `fieldforge/engine.py`：schema 驱动的生成引擎——静态字段生成器（字典/枚举/日期区间/量程浮点）+ 序列模型（`arps_production`、`standard_sensor_set`）；全部随机性经 `random.Random(seed)`，同种子同输出。
- `fieldforge/emit.py`：CSV 输出（字段顺序取自 schema）+ `manifest.json`（schema/recipe/seed/python 版本、逐字段单位表、行数、**合成数据声明**）；Parquet 为可插拔后端（import pyarrow，缺失则明确报错提示安装）。
- `fieldforge/check.py`：发射前 schema 符合性检查（类型/枚举/量程/外键/日期可解析），违例即中止（exit 2）——F7 评估闸门的 M1 内嵌最小版。
- `fieldforge/cli.py`：`fieldforge generate --recipe ... [--seed N] [--out DIR] [--format csv|parquet]`；`python -m fieldforge` 同效。

## 验收

- [x] `python3 -m fieldforge generate --recipe recipes/one_well_365d.yaml` 一条命令产出 1 口井 × 365 天四张表 + manifest
- [x] 全部字段来自 schema 声明，零手写数据行；manifest 含单位表与合成声明（F10）
- [x] 符合性检查违例可机判中止
