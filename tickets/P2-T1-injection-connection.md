# P2-T1 · 注采受效关系（本体域硬要求）

**状态**：done（2026-09-27） ｜ **上游**：tpa/docs/business-setting.md §5 Ontology 域草案（受效关系：注水井→受效油井多对多，劈分系数 Σ=1、响应起始日）

## 任务（实际落地）

- `schemas/tpa-contract-v0.1.yaml` 增 `injection_connection` 实体：injector_well_id / producer_well_id 双外键 + split_coefficient [0,1] + response_start_date，PK=(注水井, 受效油井)。
- 引擎模型 `tpa_injection_connection`：每口注水井连 1–3 口**同区块**受效油井（合法 Join 白名单语义：注采关系经本实体，不直连），劈分系数用整数百分比分摊 + 取整损耗补最大份——**合计恰为 1**（浮点 Σ 偏差 < 1e-6）。
- 闸门增 `r_eff` 指标（本体域约束：Σ=1 / 注水井），干净合同数据自动通过。

## 验收

- [x] 65 组受效关系（34 注水井 × 1–3 受效油井），PK 唯一、双侧外键实存、同区块
- [x] 每注水井劈分系数合计 = 1（±1e-6），闸门 r_eff pass
- [x] 为注采比口径与"措施/注水事件增油劈分"（王飞系数劈分）备好数据前提

## 备注

- 受效关系的**动态演化**（响应起始日随措施/注水制度变化）与"注采比"指标卡对接属 P2 后续/平台侧。
