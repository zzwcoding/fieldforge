# P3-T1 · 生成时自动过闸（未过闸不出库）

**状态**：done（2026-09-27） ｜ **上游**：PRD F7"任何生成物必须过闸才能出库"；P1-T1 备注

## 任务（实际落地）

- 配方声明 `gate: {enabled, enforce}`；generate 在 emit 后自动跑 evaluate：
  - `evaluation.json` 落输出目录；manifest 回填 `gate: {overall, summary, enforce}`；
  - `enforce: true` 且 overall=fail → **exit 1**（未过闸不出库语义）；
  - `enforce: false` = report-only（脏特征交付物按定义含违例，挂样本正是其交付价值，不能被自己的闸门拦死）。
- `_load_data` 支持 Parquet 交付态——闸门在 Parquet 交付上同样生效。
- tpa_s1_demo：enabled+enforce（干净基线必须过闸）；tpa_s1_dirty：enabled+report-only。

## 验收

- [x] 干净基线生成 rc=0，manifest.gate.overall=pass，evaluation.json 随目录
- [x] 脏配方 enforce=true 时 rc=1（测试以改写配方式样验证 enforce 语义）
- [x] Parquet 交付态全合同（12 表，含 210,240 行亚日表）过闸 rc=0
