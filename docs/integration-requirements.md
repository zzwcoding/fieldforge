# 对接调研 —— teach-petro-agent 真实化后对合成数据的要求 与 fieldforge 现状符合度

> **日期** 2026-09-27 · **性质** 调研报告（只评估，不改设计）
> **对照物**：teach-petro-agent（零代码教学项目，假想业务 = Petro-Agent 平台；其数据面 PRD/设定书即"真实化"的需求蓝本）× fieldforge（本仓库，合成数据生成器，schema 0.2.0 五表）。
> **证据纪律**：teach-petro-agent 侧引用格式 `tpa/<相对路径>:<行号>`（该仓自我定位为教学项目，含"教学演绎"标注的条目如实照引、不视为工程承诺）；fieldforge 侧引用本仓文件。
> **需求抽取方法**：探索 agent 通读 tpa 的数据面 PRD/架构、DP1–DP9 规格与 W-DP 断言、业务设定书 v3、湖仓技术分册（2026-09-27），以下为浓缩对照。

---

## ① TL;DR

1. **架构层合格**：fieldforge 的设计方向（schema 驱动、manifest 记账、种子可复现、物理一致性闸门、单位显式声明、合成数据红线、CSV 交付通道、GPL 组件容器隔离）与平台的对接要求**同构**，没有需要推倒重来的部分。
2. **内容层目前只覆盖 ~三成**：平台数据面以**生产域 8 表字典**为核心事实源（`tpa/docs/business-setting.md:32-34,139-156`），fieldforge 现有 5 表中只有生产日台账约 40% 列对齐，**缺 6–7 张表**（注水台账、检修、措施、化验、设备状态、月度结算、配产表）。
3. **最大的认知纠偏**：tpa 设定书里那些"脏特征"（A/B 班重复行、T-3 补录、单位误录、新旧编码并存、恒值 30 日…）**不是数据质量问题而是交付物**——每一条都被 W-DP 断言消费（`tpa/specs/walkthroughs-data-plane.md:27,41-42`）。fieldforge 的注入器架构正是生产它们的正确载体，但当前注入项与平台脏特征清单重合度低。
4. **对接不靠猜**：tpa 已有现成"数据合同"（附录 A 字段字典 + 20 条质量规则 + 15 条指标卡口径 + W-DP 断言），fieldforge 对接 = 把这份合同实现为 schema 0.3 与注入器家族，P0 即可启动。

---

## ② 对接要求清单（自 tpa 文档抽取，浓缩）

### A. 数据对象（平台核心事实源 = 生产域 8 表 + 外围）

| 对象 | 关键字段级要求 | 证据 |
|---|---|---|
| well_info 井档案 | well_id VARCHAR(8) 格式 `N-02`（旧写法 N2/N-2 并存）、well_type EW采油/IW注水、first_prod_date、platform（CEP-A/B）、block_name（渤南/渤中/渤西）、current_status、remarks | tpa/docs/business-setting.md:144-145 |
| oil_production_daily ★ | well_id+prod_date 主键；oil_output 吨 / liquid_output 方 / water_cut % / plan_output / open_days / oil_pressure MPa / report_shift A/B/C | tpa/docs/business-setting.md:147-149 |
| water_injection_daily 注水台账 | inj_volume 方 / pump_pressure MPa / layer_split 分层配注 | tpa/docs/business-setting.md:151 |
| well_overhaul 检修台账 | overhaul_start/end、affected_output、batch_id（T-3 补录） | tpa/docs/business-setting.md:152 |
| well_measures 措施台账 | measure_type（压裂/酸化/补孔/调剖）、effective_from/to（30% 缺失）、incr_oil_annual | tpa/docs/business-setting.md:153 |
| fluid_test 化验 | water_cut_lab / density / api_gravity，频次不齐 | tpa/docs/business-setting.md:154 |
| equip_status 设备状态 | equip_type / load / current / stop_reason_code（新旧编码并存） | tpa/docs/business-setting.md:155 |
| monthly_settlement 月度结算 | block_name / settle_date / net_weight（扣自用油与输差） | tpa/docs/business-setting.md:156 |
| 8 表未覆盖但本体要求 | 井筒段/射孔/防砂、区块、平台、设备、**受效关系**（注水井→受效油井多对多，劈分系数 Σ=1 + 响应起始日）、配产表（计划版本切换日双值） | tpa/docs/business-setting.md:45,48,88-89 |
| 文档语料 | Volve 钻井/完井报告 PDF（RAG 输入），入 MinIO reports 桶 | tpa/docs/prd.md:81,93 |
| 测井/岩性 | 按井+深度区间的测井曲线数据（FORCE 2020 复现） | tpa/docs/prd.md:135-136 |

### B. 粒度与时序

- 生产数据原子粒度 = **井×日**，grain 未声明拒绝建模（tpa/docs/prd.md:297）。
- 传感器**秒级采样**（1 万 RTU、15 类关键指标）+ 15 分钟档入仓（tpa/docs/business-setting.md:30）。
- 历史跨度锚点：86 在产采油井 × 365 天 = 31,390 行全年明细（tpa/prototype/V2-page-spec.md:1493）；first_prod_date 2019–2020。
- 批/流双进料，每张湖表带新鲜度档位（realtime/nearline/offline + as_of）元数据（tpa/docs/prd-data-plane.md:49）。

### C. 量级

- 主数据配比：**3 作业区、120 口在产井（86 采油 + 34 注水）、5 平台**（tpa/docs/business-setting.md:12）。
- S1 档位（真实化的现实起点）：GB 级、≤百井（tpa/docs/prd-data-plane.md:23-27）。

### D. 存储与载体

- 湖 = MinIO + **Iceberg**（Parquet 落桶）；关系库 = PG/金仓；查询 S1=DuckDB；语义层 S1=静态 YAML 字典；T 层 S1=校验脚本直写、S2+=dbt（CSV 走 dbt seeds 通道）（tpa/docs/prd-data-plane.md:49-82；tpa/docs/tech-stack/dbt.md:32）。

### E. 质量与口径

- **20 条质量规则**是数据形状的硬约束：规则 1 (well_id,prod_date) 唯一；规则 2 oil_output 非空率 ≥99.5%；规则 3 折算密度 ∈[0.82,0.98] t/m³（区块密度 0.86/0.89/0.91）；规则 5 water_cut∈[0,100]、open_days∈[0,24]；规则 7 井号归一化 N2/N-2→N-02；规则 12 区块月物质平衡偏差 ≤3%…（tpa/docs/business-setting.md:68-82）。
- 单位制：吨/方混写为主流脏特征；吨↔方=质量/密度；桶↔m³=6.29（tpa/docs/business-setting.md:37）。
- 指标口径：15 条指标卡七件齐；"一数四源"权威源仲裁（差 3.2%）；合法 Join 白名单默认拒绝（注水需经受效关系）（tpa/docs/business-setting.md:41-90）。
- 传感器量程原型：井口压力 0–40 MPa、温度 −20–120 ℃、精度 0.5 级（tpa/references/extracts/indicators-and-data.md:140）。

### F. 摄取与契约

- "入湖必过质检"闸：20 条规则翻成 dbt tests，校验不合格行拦截、合格批带 provenance（tpa/docs/prd-data-plane.md:52）。
- Schema 即契约：列名/类型/注释/分区四件齐；Iceberg schema 演进只是元数据操作；快照化（结论绑 snapshot_id）（tpa/specs/data-plane/modules.md:35,181-183）。
- 新鲜度登记契约：register_freshness(table, tier, as_of)（tpa/specs/data-plane/modules.md:60-62）。
- 批次水位：≤T-1，T-3 补录作反例（tpa/docs/business-setting.md:75）。

### G. 安全合规

- 行级权限=作业区隔离（每行可归属 block）；导出审批+水位；国密 SM4/SM3；国产化（金仓+麒麟 aarch64）。
- **合成数据声明**：调研报告已点名 fieldforge 应"声明数据为合成、禁止用于储量申报等真实决策"，生成物 license 单独声明（tpa/docs/synthetic-data-github-survey.md:135,153）。

### H. W-DP 断言隐含的数据前提（样例）

- DP-W-D1-1/2/3：湖表 schema 四件齐、≥2 次快照、列级 min/max 统计。
- DP-W-D2-1：批数据须**含 A/B 班重复行样本**；DP-W-D3-1/2：须含重复行与"12.40 方"单位误录行——**脏特征是断言消费的测试夹具**。
- DP-W-D4-5：须能构造"一数四源"差值 3.2%。
- W-F27-1：全油田全年日产明细 3 万+行可达。
（tpa/specs/walkthroughs-data-plane.md:13-43,55-59,72；tpa/specs/walkthroughs.md:614）

---

## ③ fieldforge 现状逐条符合度

| # | 要求 | fieldforge 现状 | 判定 |
|---|---|---|---|
| 1 | 8 表字典对齐 | 仅 5 表；production_daily 列（oil_rate/water_rate/gas_rate/producing_hours）与字典（oil_output/liquid_output/water_cut/plan_output/open_days/oil_pressure/report_shift）约 40% 语义重叠；gas_rate 平台字典根本没有；**注水/检修/措施/化验/设备/月结/配产 7 表缺失** | ❌ 缺口（最大项） |
| 2 | 主数据配比（120 井=86+34、5 平台、3 区块、N-02 井号+旧写法） | 井数按 recipe 声明、名称虚构（BLZ-3-99 恰 8 字符但编码体系不同）、无 platform/block_name/first_prod_date/current_status 列、无旧写法变体 | ❌ 缺口（schema 0.3 可解） |
| 3 | 粒度（井×日 PK）与跨度（≥1 年、3 万+行） | ✅ grain=井×日、PK 一致；365 天 × N 井可扩（千行级/秒级生成，量级无压力） | ✅ 符合 |
| 4 | 传感器粒度（秒级 RTU/15 分钟档） | 仅日度读数；通道已声明 sample_interval_min 但未产亚日数据（T3 票明示另票） | ⚠️ 部分（框架已留位） |
| 5 | 单位制（吨/方混写、区块密度、桶换算、单位误录） | 单位显式声明 + 换算系数入 manifest ✅（底座好）；但无双单位脏行、无区块密度表、无"12.40 方"误录注入 | ⚠️ 部分（注入器加一类即得） |
| 6 | 脏特征即交付物（A/B 班重复、T-3 补录、状态滞后、恒值 30 日、新旧编码、措施缺效期、化验打架、计划双值） | 注入器架构 ✓（spike/gap/maintenance_window 三类，插件式、种子可复现、manifest 记账）——但与平台 9 类脏特征几乎零重合 | ⚠️ 载体对、内容缺（P1 主战场） |
| 7 | 20 条质量规则可机判（过/挂样本齐备） | 评估闸门 11 指标 ✓（物质平衡/停机/量程/静稳/递减率——恰是调研报告指出的"通用框架缺失的第三族"）；但规则集与平台 20 条不对齐，无逐规则挂样本配比控制 | ⚠️ 部分 |
| 8 | 物理自洽（区块月物质平衡 ≤3%、注采比、受效关系） | 单井级物理 ✓（Arps/含水/停机/静稳）；**注水侧整链缺失**（无注水台账→无注采比→无受效关系→无区块月勾稽） | ❌ 缺口（依赖 R1 补表） |
| 9 | CDC/新鲜度/快照就绪（稳定主键 ✓、行级作业区归属、freshness/批次水位元数据、不可变文件） | 主键稳定 ✓；文件确定性可再生 ✓（同 seed 字节级复现，天然满足"同快照重放"）；但无 freshness/批次/quality_status 元数据登记，无 block 行级归属列 | ⚠️ 部分（manifest 扩展即得） |
| 10 | 摄取形态（CSV/dbt seeds 通道、行业编码对照） | ✅ CSV+manifest 正是 dbt seeds 通道形态；编码对照表未做（X_OP_PROD_DAILY→oil_production_daily 等三条，映射表级工作量） | ✅ 基本符合 |
| 11 | 合规（合成声明、license 单独声明、禁止真实决策） | **fieldforge 领先项**：声明已强制写入 manifest/README/评估报告三处，Apache-2.0 已声明；"禁止储量申报"红线为验收项 | ✅ 符合 |
| 12 | 湖仓载体（Parquet/Iceberg） | CSV only（pyarrow 未装，Parquet 后端已留接口）；Iceberg 侧 platform 自建，生成器只需交付 Parquet/CSV | ⚠️ 部分（装 pyarrow 即通） |
| 13 | 文档语料/测井曲线（reports 桶、岩性识别） | M4（LLM 文档层）/M5（测井第二梯队）未开工 | ❌ 未开工（已在路线图） |

**量化印象**：对象覆盖 5/12+（其中生产台账列对齐 ~40%）；脏特征家族 0/9（注入载体已就绪）；质量规则对齐 0/20（闸门插件已就绪）；合规与交付通道基本达标。**综合：架构合格、内容 ~三成、全部缺口都有已验证的扩展点承接。**

---

## ④ 结论：目前的设计是否符合要求？

**符合——作为底座**。四项"不需要改"的底座恰好是对接最贵的部分：

1. **schema 驱动 + manifest 记账**：平台"Schema 即契约"（列名/类型/注释）与"逐批 provenance"要求，fieldforge 的 manifest（schema 版本/seed/单位表/参数/闸门结论）就是同构物，只差平台侧字段（freshness/批次水位）。
2. **确定性再生**：同 seed 字节级复现，直接满足 W-DP"同快照重放逐行一致"与金标供数（W-F15-1）——这是随机生成器普遍做不到的硬能力。
3. **注入器 = 脏特征生产线**：平台的脏特征清单本质是"带配方的缺陷注入"，与 T2 架构完全同构，P1 是填内容不是改架构。
4. **物理一致性闸门**：tpa 调研报告明言这是通用框架缺失、油气刚需（tpa/docs/synthetic-data-github-survey.md:68）——fieldforge 已自研落地，方向被独立验证。

**不符合——作为可直接入湖的数据源**：现在把 fieldforge 输出喂给平台，数据面 8 表有 7 张是空的，列名对不上，质量规则 20 条跑不出既有过样本又有挂样本的双侧样本。**结论：架构不需要返工，需要一轮"P0 内容对齐"才有对接资格。**

---

## ⑤ 建议路线

- **P0 数据合同对齐（schema 0.3，1 个里程碑）**：按 tpa 设定书附录 A 字典重写生产域 schema——8 表全建、列名/类型/PK 逐字段对齐、主数据 profile（120 井=86+34、5 平台、3 区块、N-02+旧写法变体、first_prod_date 2019 起）、区块密度表、well 表补 platform/block_name/current_status。交付物自带"行业编码对照表"。
- **P1 脏特征注入器家族（1–2 个里程碑）**：把平台 9 类脏特征逐条实现为注入器（A/B 班重复、T-3 补录批次、状态滞后、恒值 30 日、单位误录"12.40 方"、新旧编码并存、措施缺效期、化验打架、计划双值），配比入配方；20 条质量规则逐条翻成闸门指标（每条有过/挂双侧样本）；闸门/manifest 增补 freshness 档位、批次水位、quality_status 元数据。
- **P2 对接深化**：注采受效关系生成（劈分系数 Σ=1 + 响应起始日）+ 区块月物质平衡 ≤3% 勾稽；Parquet 输出启用（装 pyarrow）；亚日传感器粒度（15 分钟档对齐 nearline）；M4 LLM 文档层对接 reports 桶（完井报告 PDF 叙述化）；测井曲线（M5）对接岩性识别。
- **真实锚点（并行线）**：Volve/FORCE license 审阅（charter Q5）后接入 `--real`，隐私族 anonymeter 三类攻击激活，质量族 q3 变真质量评估。

**双向责任提醒**：tpa 侧真实化也不是只等数据——需要把"演示假数/教学演绎"标注清理为真实供数声明、S1 档位落地（DuckDB+dbt seeds 通道）、外部表审批等机制对合成数据同样生效；两仓对接的胶水（dbt seeds 目录约定、编码对照、freshness 登记）建议在 P0 时一次性定稿。
