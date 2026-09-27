# M5-T1 · 测井曲线合成（收窄版：对齐 tpa 岩性识别的数据前提）

**状态**：done（2026-09-27） ｜ **上游**：tpa/docs/prd.md F9（identify_lithology(well_id, depth_range)，FORCE 2020 复现，不训练新模型）、W-F9-1/3；Owner 决策：M5 收窄为测井曲线（地震不做——tpa 无需求），不接真实数据

## 任务（实际落地）

- `schemas/tpa-contract-v0.1.yaml` 增 `well_log_curve` 实体（PK (well_id, depth_md)）：FORCE 2020 记忆码 7 条曲线（GR/RHOB/NPHI/RDEP/DTC/CALI/PEF）+ 12 类岩性编码（30000 Sandstone … 99000 Tuff，字符串型）。
- 引擎模型 `well_log_curves`：岩性分区（厚度 5–50m 随机，加权自 seeds `lithology_weights`）+ 图版典型值（seeds `lithology_chart`，典型测井响应）+ 逐列噪声 + **按 schema 量程截断**。深度 1400–2600m × 0.5m 采样。
- 合成声明纪律：无真实数据（Owner 决策）；图版值为典型测井响应的教学值，seeds 头注已声明取形不借实。

## 验收

- [x] 120 井 × 2401 采样点 = 288,120 行；PK 唯一、井内深度单调
- [x] 七条曲线全部落物理量程（泄漏点经 schema 截断修复）
- [x] 岩性分区结构成立（存在 ≥10m 连续段，非逐采样点噪声）
- [x] 同 seed 字节级可复现
- [x] 全仓 48 测试 3 轮全绿（既有零回归）

## 备注

- tpa 平台的 identify_lithology（XGBoost）若要在合成数据上服务/评测：训练与推理属平台侧；fieldforge 保证曲线+标签的数据前提（对齐 FORCE 记忆码，模型文件可直接复用 FORCE 方案的特征集）。
- 曲线光滑化/过渡带/井眼扩径响应属增强项，另票再议。
