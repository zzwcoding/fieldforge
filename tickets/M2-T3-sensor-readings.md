# M2-T3 · 传感器日度读数时序（M1-T3 遗留项）

**状态**：待开工（依赖 M2-T2 注入器） ｜ **上游**：charter §4 L2、PRD F4

## 任务

- schema 增 `sensor_reading` 时序实体（外键 → sensor_channel / production_daily）。
- 读数 = 生产骨架驱动（压力/温度随产量工况联动）+ M2-T2 注入。
- v0 粒度：**日度**（每井 × 3 通道 × 365 天）；亚日粒度（5min 采样 ≈ 10 万行/井/年）另票，避免 M2 范围膨胀。

## 验收草案

- [ ] 每井 3 通道日度读数，值在通道量程内，与通道注册表外键一致
- [ ] 停机日读数呈现静稳工况（与 production_daily 的 producing_hours=0 联动）
- [ ] 同 seed 可复现
