# P1-T2 · 平台质量规则族机判（20 条规则 → 闸门指标）

**状态**：done（2026-09-27，机判子集 1–10+12） ｜ **上游**：tpa/docs/business-setting.md §4（判据原文）

## 任务（实际落地）

- `fieldforge/evaluate.py` 增**规则族**：manifest schema 名为 `tpa-contract` 时自动启用，r1–r12 逐条机判：
  - r1 (well_id,prod_date) 唯一性；r2 oil_output 非空率 ≥99.5%；r3 折算密度带 [0.82,0.98]；r4 计量 vs 化验 ≤5pp（井号+日期双键）；r5 water_cut/open_days 值域；r6 批次水位（-T3=超窗）；r7 井号归一化 ^[A-Z]-\d{2}$；r8 停机原因码映射全命中；r9 状态滞后（档案生产中 + 近 31 日全停）；r10 恒值 30 日（告警级 warn）；r12 区块月物质平衡 ≤3%。
  - r11 传感器零值 2 小时 = skipped（实时域规则，tpa 自标教学演绎；日粒度不可判，15 分钟档接入后启用）。
  - r13–20（引用完整/跨表一致/枚举合法/正则格式/极值/波动率/钩稽/scrub）= skipped，注明由既有指标覆盖的映射（枚举合法=符合性、极值/波动率=q2/f5、引用完整=fk、钩稽=r12），专条待提取件二核对后启用。

## 样例报告（随仓 docs/reports/）

| 样例 | overall | 要点 |
|---|---|---|
| [p1-rules-clean.json](../docs/reports/p1-rules-clean.json)（+.html） | **pass**（17 pass + 7 skipped） | 干净基线：12 条规则全部通过、零误报 |
| [p1-rules-dirty.json](../docs/reports/p1-rules-dirty.json)（+.html） | **fail**（9 fail + 1 warn） | 脏特征全数被逮：383 主键重复、12 密度越带、18 化验打架、6 超 T-1 批次、21 旧井号、1 未知编码、3 口滞后井、30 日恒值告警、r12 联动破坏 7.73% |

## 验收

- [x] 干净基线零误报（12 条机判规则全 pass）
- [x] 脏特征逐条被对应规则逮住，违例计数与注入账吻合
- [x] 判据逐字对齐 tpa 设定书 §4 原文（阈值 99.5%/0.82–0.98/5pp/≤T-1/≤3%/30 日）
- [x] 全仓 33 测试稳定全绿（core/P0 零回归）
