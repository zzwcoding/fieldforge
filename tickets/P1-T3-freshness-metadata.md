# P1-T3 · freshness/批次元数据（平台新鲜度契约的生成侧）

**状态**：done（2026-09-27，v0） ｜ **上游**：tpa/specs/data-plane/modules.md（register_freshness 契约）

## 任务（实际落地）

- 配方声明 `freshness: {tier, watermark}` → manifest 落 `freshness: {tier: offline, watermark: T-1, as_of: <期末日>}`——对齐平台"每张湖表带新鲜度档位 + 截至时点"的登记契约（register_freshness(table, tier, as_of)）。
- tpa 两配方（tpa_s1_demo / tpa_s1_dirty）均已声明 offline/T-1。

## 验收

- [x] manifest.freshness 三件齐（tier/watermark/as_of），测试断言
- [x] tier 取值对齐平台三档（realtime/nearline/offline）词汇

## 备注（后续票）

- 生成侧 v0 只落元数据；register_freshness 的平台侧登记 API、T-3 补录的新鲜度语义（late-arriving 与 watermark 的关系）在平台真实化时对齐。
- "生成时自动过闸（emit 内嵌 gate）+ 未过闸不出库"的流程级强制仍挂后续集成票。
