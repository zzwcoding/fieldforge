# P2-T3 · 亚日传感器粒度（15 分钟档 / nearline）

**状态**：done（2026-09-27；两项决策按 Owner 委托"按推荐执行"拍板） ｜ **上游**：tpa/docs/business-setting.md:30（秒级 RTU、15 分钟档入仓）

## 拍板记录

- **采样策略 = 分层采样**：全量 120 井保持日度（sensor_reading），**前 2 口 EW 重点井升 15 分钟档全期**（sensor_reading_subdaily，96 读数/日/通道 = 210,240 行）——全量铺 1,260 万行/年不值得，重点井样本足以支撑规则 11 与近实时演示。
- **交付形态 = 合同全量 Parquet**（P2-T2 已就位），CSV 留作调试态。

## 任务（实际落地）

- schema 增 `datetime` 类型 + `sensor_reading_subdaily` 实体（PK (channel_id, ts)，双外键，量程截断沿用通道声明）。
- 引擎模型 `subdaily_sensor_readings`：日内曲线 = 日度骨架状态 × 96 读数 + 高频微噪声（量程 0.5%）；停机时段整段静稳常值。
- **规则 11（传感器零值 2 小时告警）启用**：15 分钟档 ×8 连零即告警——干净基线 pass；W-DP-D2-4 实时域钩子闭环。
- `evaluate._load_data` 支持 Parquet 交付态读取（与 CSV 同构）。

## 验收

- [x] 行数 = 2 井 × 3 通道 × 96 × 365 = 210,240；单通道单日 96 读数、15 分钟步长（测试断言秒级差集合 = {900}）
- [x] 停机时段整段静稳（同通道当日值唯一）
- [x] 规则 11 在干净合同数据上 pass（manifest.gate.overall = pass 且 evaluation.json r11 = pass）
- [x] Parquet 交付态全合同过闸（`--format parquet`，enforce 生效）
