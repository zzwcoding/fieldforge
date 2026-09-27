# P1-T1 · 脏特征注入器家族（平台 9 类脏特征 → 交付物）

**状态**：done（2026-09-27） ｜ **上游**：docs/integration-requirements.md §⑤ P1；tpa/docs/business-setting.md §4 质量规则库

## 任务（实际落地）

- `fieldforge/inject.py` v2.0.0：统一注入器注册表（13 个注入器，签名 tables/entity/section/rng/schema），通用工况扰动（M2-T2 三类）与平台脏特征（P1 九类）同框架。
- 九类平台脏特征（每条注明消费它的规则）：
  1. `shift_duplicate` A/B 班重复行 → 规则 1
  2. `plan_dual_value` 配产版本切换日双值 → 规则 1 + 口径双值
  3. `unit_misentry` 液量漏折算密度 / 方桶混淆 ×6.29 → 规则 3
  4. `well_id_legacy` 井号旧写法 N2 / N-2 → 规则 7
  5. `stale_constant` 恒值 30 日（冻结窗口内量纲自洽） → 规则 10
  6. `late_batch` T-3 补录批次 → 规则 6
  7. `status_lag` 近 31 日全停但档案"生产中"（制造完整滞后态） → 规则 9
  8. `legacy_stop_code` 新旧编码并存（BELT↔R3 映射）+ 未知码 LEGACY-OLD → 规则 8
  9. `measure_missing` 措施缺效期缺失（schema `nullable: true` 承接）→ 完整性
  另：`lab_conflict` 化验 vs 计量打架 ±6–15pp → 规则 4。
- `check.py`：`nullable` 字段支持（缺失即脏特征，完整性交规则族统计）；`dirty_ok` 模式（配方声明 dirty_mode 时跳过 fk/enum——旧井号/旧编码按设计存在，日期/量程/缺失仍校验）。
- 演示配方 `recipes/tpa_s1_dirty.yaml`（与 tpa_s1_demo 同骨架同种子）。

## 验收

- [x] 注入账实相符（manifest counts 逐项 = 规则族检出的违例数，见 P1-T2 样例报告）
- [x] nullable 措施行存活于产物（约 30% 缺失）
- [x] 同 seed 字节级可复现
- [x] dirty 模式下符合性检查放行脏值、仍拦真缺陷

## 备注（坑存档）

- `status_lag` 初版语义反了（翻牌"仍有产量"的井），且停井窗口与规则 9 的 31 行尾窗差一行（差一天即漏检）——**注入器窗口必须与规则判据逐行对齐**，测试以"规则族必须逮住"为验收闭环。
- 产量改写类注入器（恒值冻结/强制停井）**必然联动破坏规则 12 月勾稽**——tpa 设定书 §3.1"指标不是独立数字"的活教材，测试预期如实标注。
