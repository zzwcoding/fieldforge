# fieldforge

油气领域专用**合成数据生成工作台**。"Synthea 之于医疗 = 本项目之于油气"：通用合成数据框架没有油气 schema、单位制、物理约束；油气物理引擎能产"真物理"数据但没有面向 ML 的封装——本项目补中间这一层。

- **状态**：M0 立项 ✅（2026-09-25）→ M1 tracer bullet ✅（2026-09-25）→ M2：T0 算力实测 ✅（flow 2026.04 容器化，SPE1 0.45s / Norne 164s，扫参规模已拍板粗精两档）、T2 注入器 v1 ✅；T1 物理适配器 / T3 传感器读数待开工
- **License**：Apache-2.0（计划；GPL 物理引擎一律独立进程集成，SDV/CTGAN 等 BUSL 组件仅限内部实验）
- **红线**：合成数据仅用于算法研发、测试、演示与教学，**禁止用于储量申报、生产决策等真实业务**——该声明强制写入输出 manifest。

## 快速开始（M1：一口合成井 × 365 天）

依赖：Python ≥ 3.10 + PyYAML（其余全标准库）。

```bash
python3 -m fieldforge generate --recipe recipes/one_well_365d.yaml --out out
python3 -m unittest tests.test_m1 -v      # 冒烟测试（可复现性/符合性/领域常识）
```

输出 `out/`：`well.csv`、`wellbore.csv`、`sensor_channel.csv`、`production_daily.csv`、`manifest.json`。

- **同 seed 字节级可复现**（`--seed 42` 覆盖配方种子）。
- **Parquet**：M1 未内置依赖，`pip install pyarrow` 后加 `--format parquet`。
- 种子字典（油田名/区块码/传感器目录）**全部虚构**，见 `fieldforge/seeds/dicts.json`。

## 当前能力边界（M1）

规则打底骨架：Arps 递减 + 含水率爬升 + 停机事件 + 乘性噪声；四实体 schema 驱动（字段/单位/枚举/量程声明，发射前逐格符合性检查）。M2-T2 注入器 v1：坏点 / 缺测 / 连续停机窗口（独立随机流、manifest 记账、注入点由 seed 复现，供评估闸门重建 ground truth）。传感器**日度读数时序**与**物理打底（OPM Flow 独立进程扫参）**在 M2-T3 / M2-T1，见 tickets/。

## 文档地图

| 路径 | 是什么 |
|---|---|
| [docs/charter.md](docs/charter.md) | 立项稿：定位/目标/非目标/技术路线 L0–L5/里程碑/风险与决策记录 |
| [docs/prd.md](docs/prd.md) | PRD 骨架 v0.1（F1–F10） |
| [docs/research/](docs/research/) | GitHub 合成数据生态调研报告（2026-09-25 快照，原件在 teach-petro-agent 仓） |
| [tickets/](tickets/) | M1 拆票（T1 schema/T2 引擎/T3 验收，含遗留项） |
| [schemas/core-v0.yaml](schemas/core-v0.yaml) | L0 领域 schema：四实体 + 单位制 + 取值域 + 规则模型参数 |
| [recipes/](recipes/) | 场景配方（声明式生成任务） |
| [fieldforge/](fieldforge/) | 包源码：schema 加载 / 生成引擎 / 符合性检查 / 输出 / CLI |
