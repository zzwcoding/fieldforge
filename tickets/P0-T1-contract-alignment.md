# P0-T1 · 数据合同对齐（tpa 生产域 8 表字典 → fieldforge schema）

**状态**：done（2026-09-27） ｜ **上游**：docs/integration-requirements.md §⑤ P0；tpa/docs/business-setting.md 附录 A + 20 条规则 + 主数据配比

## 任务（实际落地）

- `schemas/tpa-contract-v0.1.yaml`：与 core-v0 共存的合同 schema 包，11 实体 = **生产域 8 表**（well_info / oil_production_daily / water_injection_daily / well_overhaul / well_measures / fluid_test / equip_status / monthly_settlement，列名/类型/主键逐字段对齐字典）+ 井筒 / 传感器通道 / 传感器日度读数三辅助实体。
- 主数据 profile：`fieldforge/seeds/tpa_s1.json`（3 区块渤南/渤中/渤西带密度 0.86/0.89/0.91、5 平台 CEP-A…E、井号 {区块字母}-{序号} N-02 式、first_prod_date 2019–2020 档）+ `master_wells` 模型（**120 井 = 86 EW + 34 IW 精确配比**，井号唯一）。
- 引擎 8 个新模型：master_wells / tpa_daily_production（Arps+含水爬升+停机，liquid_output=油/((1−含水)×密度) 物质量纲自洽）/ tpa_water_injection（分层配注 P1:60,P2:40）/ tpa_overhaul（跨月案例 + T-1 批次）/ tpa_measures（主键防碰撞）/ tpa_fluid_test（化验含水 ±1.5pp 贴计量、密度落规则 3 区间、API°换算）/ tpa_equip_status（新编码）/ tpa_monthly_settlement（区块月勾稽 = 油量合计 × 0.98，输差 2% 在规则 12 的 3% 界内）。
- 兼容性：sensor 两个模型泛化（core/合同双列名兼容；读数 ledger 挂产油+注水双源，注水井停注日静稳）；既有 core schema/配方/测试零改动。
- 行业编码对照：seeds/tpa_s1.json `industry_code_map`（X_WELL_MASTER→well_info 等三条）。

## 验收

- [x] 一条命令产 11 表 175,842 行：oil_production_daily **31,390 行**（= 86×365，正对齐 W-F27-1 大结果锚点）、water_injection_daily 12,410、sensor_reading 131,400
- [x] 主数据：120 井 = 86+34、井号唯一且 ^[A-Z]-\d{2}$、区块/平台 ⊆ profile、first_prod_date 2019–2020
- [x] 规则可机判预埋：open_days∈[0,24]、water_cut∈[0,100]、density∈[0.82,0.98]、停机一致、月结算勾稽 ≤3%（测试逐条断言）
- [x] 同 seed 字节级可复现（well_info / oil_production_daily 双表验证）
- [x] manifest：schema=tpa-contract v0.1.0 + 合成数据红线声明
- [x] 全仓 26 测试 3 轮稳定全绿（core 既有 20 条零回归）

## 备注（P1 接续）

- 脏特征注入器家族（A/B 班重复、T-3 补录、单位误录、新旧编码并存、状态滞后、恒值 30 日、措施缺效期 30%、化验打架、计划双值）挂本合同的注入器。
- 20 条质量规则逐条翻闸门指标 + 过/挂双侧样本配比；evaluate 闸门适配合同表名（现 q2/q3/f1/f2 键名仍指 core 表）。
- 旧写法变体（N2/N-2）与"注入防御素材" remarks 属 P1 脏特征，干净基线不含。
