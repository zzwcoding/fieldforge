> **快照说明**：本文件为调研报告的快照副本，原件存放于 teach-petro-agent 仓库 `docs/synthetic-data-github-survey.md`（2026-09-25 生成）。若原件更新，以原件为准；本副本仅为让新仓库自包含。

# 合成数据（Synthetic Data）开源生态 GitHub 调研

> **调研日期**：2026-09-25
> **调研范围**：GitHub 上的合成数据开源生态——通用表格合成框架、时序合成、LLM 驱动合成、隐私/质量评估、石油/地球科学领域特有项目（地震/测井/油藏模拟/公开数据集）。
> **调研方法**：所有仓库均通过 GitHub API（`api.github.com/repos/{owner}/{repo}`）或 GitHub 搜索 API 在 2026-09-25 当天逐一核实存在性、stars、最近提交时间（pushed_at）、语言与 license；无法核实或已 404 的条目如实标注，未凭记忆收录。**本报告所有 stars/活跃度数据均截至 2026-09-25。**
> **调研目的**：为新项目"石油行业（油气田）合成数据生成"（拟覆盖测井曲线、生产时序、设备传感器、钻井、地震等）提供选型与架构设计参考。

---

## ① TL;DR（一屏结论）

1. **通用表格合成赛道已经成熟且出现"商业化收紧"**：SDV 全家桶（SDV 3.6k★ + CTGAN 1.6k★）仍是事实标准，但 **SDV/CTGAN 已改用 Business Source License 1.1（DataCebo, Inc.）**，禁止拿它做对外的"合成数据服务"；Apache-2.0 的替代品是 MOSTLY AI SDK（802★）与 synthcity（685★）。[SDV](https://github.com/sdv-dev/SDV)、[CTGAN](https://github.com/sdv-dev/CTGAN)、[mostlyai](https://github.com/mostly-ai/mostlyai)、[synthcity](https://github.com/vanderschaarlab/synthcity)
2. **Gretel 开源体系已死**：gretelai 组织下全部仓库（gretel-synthetics、gretel-blueprints、gretel-python-client 等）已于 2025 年 6–9 月陆续归档，`gretelai/synthetic` 数据集仓库已 404；NVIDIA 于 2025 年 3 月收购 Gretel 并入 NeMo 数据生态。**不要选型 Gretel。**[gretel-synthetics（archived）](https://github.com/gretelai/gretel-synthetics)
3. **ydata 系已改名迁移**：`ydataai/ydata-synthetic`（1.7k★，MIT，表格+时序）与 `ydataai/ydata-profiling`（13.7k★）已整体转移至 Data-Centric-AI-Community 组织，更名为 `fg-data-synthetic` / `fg-data-profiling`，仍在活跃维护；引用时务必用新地址。[fg-data-synthetic](https://github.com/Data-Centric-AI-Community/fg-data-synthetic)
4. **油气领域只有"物理引擎"，没有"合成数据框架"**：油藏模拟（OPM Flow、MRST、DuMux、openDARTS）、地震正演（devito）、测井工具（welly/bruges）、工艺/流体（neqsim）都是活跃的物理仿真或工具库；但 GitHub 上**不存在**任何成型的"油田生产时序/设备传感器/钻井参数合成数据生成"开源项目——搜索到的同类项目全是 0–2★ 的个人课程作业。**这是新项目的明确空白与定位。**
5. **架构上有 4 种可借鉴模式**：SDV 的"schema→变换→生成→评估"流水线、synthcity 的"插件化生成器+统一评测面板"、Synthea 的"领域模块状态机+标准交换格式"（医疗界标杆，最值得油气效仿）、物理引擎打底+随机场景扫描（OPM/devito）。新项目建议走"**规则+物理模拟打底、统计/深度生成补分布、LLM 造文档类语料**"的三层混合路线，并用公开真实数据集（Volve / FORCE 2020 / Norne）做分布先验与评估锚点。

---

## ② 通用表格合成框架对比

| 仓库 | Stars¹ | 最近 push¹ | 语言 | License¹ | 技术路线 | 备注/优缺点 |
|---|---|---|---|---|---|---|
| [sdv-dev/SDV](https://github.com/sdv-dev/SDV) | 3,565 | 2026-09-24（活跃） | Python | **BUSL-1.1**（DataCebo） | 统计（Gaussian Copula）/ GAN（CTGAN）/ TVAE 多合成器全家桶 + RDT 可逆变换 | 生态最全（RDT/Copulas/SDMetrics/DeepEcho）；**license 已收紧：不得作为对外"合成数据服务"使用** |
| [sdv-dev/CTGAN](https://github.com/sdv-dev/CTGAN) | 1,567 | 2026-09-14（活跃） | Python | **BUSL-1.1** | 条件 GAN（Conditional Tabular GAN） | 表格 GAN 经典基线；同上 license 限制 |
| [sdv-dev/SDMetrics](https://github.com/sdv-dev/SDMetrics) | 263 | 2026-09-24（活跃） | Python | MIT | 质量诊断+机器学习效能指标 | 评估事实标准，可独立于 SDV 使用 |
| [sdv-dev/RDT](https://github.com/sdv-dev/RDT) | 135 | 2026-09-23 | Python | NOASSERTION（未核实） | 可逆数据变换（预处理层） | SDV 生态的编码/解码层 |
| [sdv-dev/Copulas](https://github.com/sdv-dev/Copulas) | 652 | 2026-09-21 | Python | NOASSERTION（未核实） | 多元统计（Copulas） | 轻量统计路线 |
| [sdv-dev/DeepEcho](https://github.com/sdv-dev/DeepEcho) | 125 | 2026-09-21 | Python | NOASSERTION（未核实） | 混合型多变量时序合成（PAR） | SDV 时序分支，见 ③ |
| [mostly-ai/mostlyai](https://github.com/mostly-ai/mostlyai) | 802 | 2026-09-23（活跃） | Python | Apache-2.0 | Synthetic Data SDK（生成式 tabular LLM 路线） | MOSTLY AI 公司开源 SDK；license 友好，SDV 的主要替代 |
| [Data-Centric-AI-Community/fg-data-synthetic](https://github.com/Data-Centric-AI-Community/fg-data-synthetic)（**原 ydataai/ydata-synthetic**） | 1,658 | 2026-09-03（活跃） | Python/Jupyter | MIT | GAN（TVAE/CTGAN）+ 扩散 + TimeGAN 时序 | **仓库已改名迁移**，原地址会重定向；ydataai 组织现只剩商业平台 Fabric 的 SDK（22★） |
| [vanderschaarlab/synthcity](https://github.com/vanderschaarlab/synthcity) | 685 | 2026-04-21（放缓） | Python | Apache-2.0 | 插件化生成器（GAN/扩散/统计十余种）+ 隐私/公平评估 | 学术（van der Schaar Lab）；评测面板强，2026-04 后更新节奏下降 |
| [yandex-research/tab-ddpm](https://github.com/yandex-research/tab-ddpm)（**原 rotot0/tab-ddpm**） | 566 | 2024-07-13（停滞） | Python | MIT | **扩散模型**（TabDDPM，ICML 2023 官方实现） | 表格扩散的代表；研究代码，工程化程度低，近两年无提交 |
| [worldbank/REaLTabFormer](https://github.com/worldbank/REaLTabFormer) | 244 | 2026-01-04 | Python | MIT | **Transformer 自回归**（表格+关系表/Seq2Seq） | 世界银行出品，强项是关系型数据库合成（父表→子表外键一致） |
| [joke2k/faker](https://github.com/joke2k/faker) | 19,411 | 2026-09-15（活跃） | Python | MIT | 规则/随机（fake data） | 通用假数据事实标准；无统计学习、无列间依赖建模 |
| [lk-geimfari/mimesis](https://github.com/lk-geimfari/mimesis) | 4,840 | 2026-09-23（活跃） | Python | MIT | 规则/随机，多语言 locale，性能优于 faker | 中文 locale 支持好，适合打底字段 |
| [gretelai/gretel-synthetics](https://github.com/gretelai/gretel-synthetics) | 683 | **已归档**（2025-06-24） | Python | NOASSERTION（未核实） | 差分隐私 LSTM/Transformer（结构化+文本） | **弃选**：NVIDIA 2025-03 收购 Gretel（约 $320M，科技媒体报道），并入 NeMo 数据生态；gretelai 组织全部仓库已归档，[gretelai/synthetic](https://github.com/gretelai/synthetic) 已 404 |
| [synthetichealth/Synthea](https://github.com/synthetichealth/synthea) | 3,358 | 2026-08-18（活跃） | Java | Apache-2.0 | 领域模块状态机（疾病模块）→ 患者生命轨迹 → FHIR | 医疗领域专用合成数据**标杆**；"领域专用生成器"路线可行性的最强证据，见 ⑤ |

¹ 截至 2026-09-25，经 GitHub API 核实。NOASSERTION = 仓库 license 文件非标准 SPDX（SDV/CTGAN 经解码核实为 Business Source License 1.1；同家族 RDT/Copulas/DeepEcho 未逐一解码，选型前请自行确认）。

---

## ③ 分赛道详情：时序 / LLM 驱动 / 隐私评估

### 3.1 时序合成（对"生产时序/传感器数据"最直接相关）

- [Data-Centric-AI-Community/fg-data-synthetic](https://github.com/Data-Centric-AI-Community/fg-data-synthetic)（原 ydata-synthetic，1,658★，MIT，2026-09 仍活跃）：自带 time-series 模块（TimeGAN、模拟器），是开源里"表格+时序"二合一最顺手的 MIT 选项。
- [jsyoon0823/TimeGAN](https://github.com/jsyoon0823/TimeGAN)（1,059★，NeurIPS 2019 官方实现，2026-02 有 push，**无 license 标注**）：时序 GAN 的祖师爷级参考实现，embedding + 自监督 + 对抗三阶段；适合做原理参考与基线，不适合直接工程化（无 license 即默认保留所有权利，商用前需联系作者）。
- [sdv-dev/DeepEcho](https://github.com/sdv-dev/DeepEcho)（125★，2026-09 活跃）：混合型（数值+分类+日期）多变量时序的 PAR（Probabilistic AutoRegressive）路线，对"传感器+事件日志"混合流有参考价值；license 未核实（DataCebo 家族）。
- [AlexanderVNikitin/tsgm](https://github.com/AlexanderVNikitin/tsgm)（227★，Apache-2.0 系，2026-03 活跃）：时序生成+**内置时序评估指标+数据增强+可视化**一体，"生成-评估"同框架的典范。
- [TimeSynth/TimeSynth](https://github.com/TimeSynth/TimeSynth)（385★，2023-10 后停滞）：统计信号过程（噪声/分形/调和过程）合成库——**物理打底思路**（白噪声+趋势+周期叠加）的最简实现参考。
- 结论：**时序合成没有一家独大**。ydata（MIT）可用；工业级多传感器时序+异常注入场景均需自研封装。

### 3.2 LLM 驱动的合成数据（对"完井报告/班报/故障工单"等文档类语料直接相关）

- [argilla-io/distilabel](https://github.com/argilla-io/distilabel)（3,397★，Apache-2.0，2026-09-21 活跃）：LLM 合成/标注流水线框架（多 LLM 编排 + AI 反馈 + 质量过滤），argilla 被 Hugging Face 收购后仍是活跃主线。
- [argilla-io/synthetic-data-generator](https://github.com/argilla-io/synthetic-data-generator)（590★，Apache-2.0，2025-09 后更新放缓）：基于 distilabel 的"用自然语言造数据集"上层封装（表格/问答/文本三类，与 HF Space 集成）。
- [Magpie-Align/Magpie](https://github.com/Magpie-Align/Magpie)（886★，MIT，ICLR 2025）：不写提示词、直接从对齐 LLM 采样合成指令数据（两段采样法）；造指令微调语料的高效套路，2025-03 后放缓。
- 结论：LLM 造**结构化油气台账**应优先走"schema 约束 + distilabel 式管线 + 规则校验"，纯 LLM 自由生成不适合数值时序（易产生物理上不成立的组合），只适合文档类与字段填充。

### 3.3 隐私与质量评估（合成数据的"验收闸门"）

- [sdv-dev/SDMetrics](https://github.com/sdv-dev/SDMetrics)（263★，MIT，活跃）：列形状/成对相关/边际分布/κ-way、以及 TSTR（Train-Synthetic-Test-Real）效能指标，事实标准。
- [statice/anonymeter](https://github.com/statice/anonymeter)（109★，2026-07 活跃）：按 GDPR 视角量化合成数据隐私风险的三类攻击评估——Singling Out / Linkability / Inference，隐私评估的少数专门开源实现（license 未核实）。
- [Baukebrenninkmeijer/table-evaluator](https://github.com/Baukebrenninkmeijer/table-evaluator)（93★，MIT）：真实 vs 合成数据集的快速对比评估，轻量辅助。
- [vanderschaarlab/synthcity](https://github.com/vanderschaarlab/synthcity)（Apache-2.0）：其 `metrics` 模块把 privacy / performance / detection 三族指标与生成器放在同一插件框架内，是"生成+评估闭环"的最佳架构参考。
- 结论：评估侧工具足够（质量+隐私+效能三族），**缺的是物理一致性校验**——没有任何通用框架检查"合成数据是否符合物理规律"（如注采平衡、压力-流量关系），这恰好是油气场景的刚需，需要自研。

---

## ④ 石油/地球科学领域现状与空白

### 4.1 物理模拟与正演引擎（活跃、可当"产数引擎"）

| 仓库 | Stars¹ | 最近 push¹ | License¹ | 定位 |
|---|---|---|---|---|
| [devitocodes/devito](https://github.com/devitocodes/devito) | 714 | 2026-09-24（极活跃） | MIT | 有限差分 DSL/编译器，波动方程正演——**合成地震（炮集/FWI/RTM 输入）首选引擎**，被大量地震 ML 论文用作数据生成器 |
| [OPM/opm-simulators](https://github.com/OPM/opm-simulators)（OPM Flow） | 167 | 2026-09-24（极活跃） | GPL-3.0 | 工业级开源油藏数值模拟器（黑油/组分，Eclipse 数据格式兼容）；油藏组织名核实为 **OPM**（无 opm-flow 独立仓库，Flow 就在 opm-simulators 内） |
| [SINTEF-AppliedCompSci/MRST](https://github.com/SINTEF-AppliedCompSci/MRST) | 138 | 2026-09-24（极活跃） | GPL-3.0 | MRST（MATLAB Reservoir Simulation Toolbox）官方仓库；含 CO₂ 储存、聚合物驱、聚合粗化等模块，适合快速产生产方案扫描数据 |
| [dumux/dumux](https://github.com/dumux/dumux) | 47 | 2026-09-24（活跃） | GPL-3.0（镜像同源） | DuMux——多孔介质流动/传质 DUNE 框架（GitHub 为官方镜像，上游在斯图加特大学 GitLab） |
| openDARTS（[官网](https://darts.citg.tudelft.nl/) / [PyPI](https://pypi.org/project/open-darts/) / [GitLab 主仓库](https://gitlab.com/open-darts/open-darts)） | — | v2.0.0 发布于 2026-09-10 | GPL-3.0-or-later | DARTS（TU Delft, Voskov 组）——算子线性化油藏/地热/CO₂ 模拟器；**GitHub org `open-darts` 存在但无公开仓库，主仓库在 GitLab**（已核实），`pip install open-darts` 可用；JOSS 2024 有同行评审记录 |
| [equinor/neqsim](https://github.com/equinor/neqsim) | 155 | 2026-09-25（极活跃） | Apache-2.0 | 流体相平衡/工艺流程模拟（Java）——可产 PVT、分离器/压缩机工况等"工艺侧"合成数据 |
| [equinor/ert](https://github.com/equinor/ert) | 161 | 2026-09-24（极活跃） | GPL-3.0 | 集合式油藏工具（历史拟合/集成工作流）——"模拟器批量扫参"工作流的成熟参照 |

### 4.2 井/测井/地震工具生态

- [agilescientific/welly](https://github.com/agilescientific/welly)（376★，Apache-2.0，2025-07 有更新）：测井曲线加载（LAS）、质量检查、基础数据科学；配合 bruges 可生成**合成地震记录（synthetic seismogram）**。
- [agilescientific/bruges](https://github.com/agilescientific/bruges)（316★，Apache-2.0，**2023-12 后停滞**）：地学公式库（Ricker 子波、反射系数、岩石物理），"物理合成测井/地震小样"的现成积木。
- [agilescientific/striplog](https://github.com/agilescientific/striplog)（228★，2023-10）：岩性地层柱状图工具。
- 注意：`agilescientific/synthetic` 与 `agilescientific/welleng` **经核实不存在（404）**；Agile 旗下没有专门的合成测井生成器仓库。
- **合成测井曲线专门仓库：只有个人项目级**——[andymcdgeo/Synthetic_Log_Generator](https://github.com/andymcdgeo/Synthetic_Log_Generator)（7★，2020，基于简单 Earth Model）、[abhishekdbihani/synthetic_well-log_polynomial_regression](https://github.com/abhishekdbihani/synthetic_well-log_polynomial_regression)（38★，2020，曲线重建）、[tobi-ore/Synthetic-Well-Logs-Using-Neural-Networks](https://github.com/tobi-ore/Synthetic-Well-Logs-Using-Neural-Networks)（12★，2020）。**无活跃、无框架级项目。**
- 合成地震：除 devito 外，仅有 [zhangxp90/synthetic-seismic-data-generation-program](https://github.com/zhangxp90/synthetic-seismic-data-generation-program)（13★，2019，Ricker 子波程序）等玩具级仓库；配套 I/O 用 [equinor/segyio](https://github.com/equinor/segyio)（583★，LGPL-3.0，2025-12 有更新，附 [segyio-notebooks](https://github.com/equinor/segyio-notebooks) 146★）。

### 4.3 已知公开油气数据集（真实数据，用作分布先验与评估基准）

- **Equinor Volve**（官方入口 [equinor.com/energy/volve-data-sharing](https://www.equinor.com/energy/volve-data-sharing)）：北海 Volve 油田 2008–2016 生产期约 4 万个文件的完整地下+运营数据（地震/测井/生产/模拟）；经 Databricks Marketplace 申请获取，免费学术使用，**Equinor Open Data Licence**。GitHub 无官方镜像（第三方如 [f0nzie/volve_eclipse_reservoir](https://github.com/f0nzie/volve_eclipse_reservoir) 37★ 仅部分模拟数据）。
- **FORCE 2020 ML Well Log Challenge**（官方结果仓 [bolgebrygg/Force-2020-Machine-Learning-competition](https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition)，195★，2022-12 后冻结）：挪威海 118 口井的测井+岩性数据；**数据可在 [Zenodo record 4351156](https://zenodo.org/records/4351156) 直接下载**，许可 NLOD 2.0。
- **Norne**：基准油藏数据随 [OPM/opm-data](https://github.com/OPM/opm-data)（71★，2026-08 仍维护）仓内 `norne/` 目录分发（已核实），与 OPM Flow 基准测试配套。

### 4.4 空白确认：油田生产时序/设备传感器合成数据 = 无人区

在 GitHub 搜索 API 上以 `synthetic data oil gas`、`synthetic well log`、`synthetic seismic data` 等关键词检索（2026-09-25），全部结果中与"油田生产/设备/钻井"相关的最大仓库仅有：

- [caioazevedo-mdm/Hybrid_VFM_Slugging](https://github.com/caioazevedo-mdm/Hybrid_VFM_Slugging)（2★，2026-02）：用深度学习生成多相流**严重段塞**合成数据（课程/研究级）；
- [leoxthomas/K-Pipelines](https://github.com/leoxthomas/K-Pipelines)（1★，2026-01）：管道腐蚀分类合成数据；
- [jayanthbagare/synthetic_oil_gas](https://github.com/jayanthbagare/synthetic_oil_gas)（0★）：油气厂维护场景合成数据（概念验证）；
- [shankartiwary/Drilling-monitoring-](https://github.com/shankartiwary/Drilling-monitoring-)（1★）：钻井看板（数据 synthetic）。

**结论：不存在任何框架级的"油田生产时序/设备传感器/钻井参数"合成数据开源项目。** 通用表格/时序框架（SDV、ydata、synthcity 等）没有油气 schema、单位制、物理约束的概念；物理引擎（OPM/MRST/devito）能产"真物理"但没有面向 ML 的 schema 化、噪声注入、评估闭环封装。两件事之间缺一层，就是新项目的定位。

---

## ⑤ 可借鉴的架构模式归纳

1. **"Schema→可逆变换→生成→评估"流水线**（来源：[SDV](https://github.com/sdv-dev/SDV) + [RDT](https://github.com/sdv-dev/RDT) + [SDMetrics](https://github.com/sdv-dev/SDMetrics)）
   把生成拆成四段：领域 schema/元数据声明 → 可逆变换把异构列规整到数值空间 → 可插拔合成器（统计/GAN/扩散/LLM 同接口）→ 统一指标报告。新项目的油气 schema（井/井筒/传感器通道/生产台账/单位制）就落在这个骨架的第一段。
2. **插件化生成器 + 统一评测面板（生成-评估同框架闭环）**（来源：[synthcity](https://github.com/vanderschaarlab/synthcity)、[tsgm](https://github.com/AlexanderVNikitin/tsgm)）
   生成器是插件、指标也是插件，任何新方法都能接入同一套隐私/效能/检测评测。油气版应把"物理一致性"做成第三族指标插件（物质平衡、压力-流量可行性、传感器量程/采样率合法性）。
3. **领域模块状态机 → 标准交换格式**（来源：[Synthea](https://github.com/synthetichealth/synthea)）
   医疗界用"疾病模块（模块化状态机）+ 人群统计先验 + FHIR 标准输出"做成 3.4k★ 的领域标杆。油气完全可类比：生产制度模块（定产/递减/措施增产）、设备退化模块（结蜡/结垢/泵磨损/传感器漂移）、事件模块（停机/修井/检泵），输出对齐 WITSML/PRODML/常见 SCADA 点表——**这是油气版 Synthea 的设计蓝本**。
4. **物理引擎打底 + 随机场景扫描 + 噪声注入**（来源：[OPM/opm-simulators](https://github.com/OPM/opm-simulators)、[SINTEF-AppliedCompSci/MRST](https://github.com/SINTEF-AppliedCompSci/MRST)、[devito](https://github.com/devitocodes/devito)、[neqsim](https://github.com/equinor/neqsim)、[ert](https://github.com/equinor/ert)）
   先用物理模拟器在参数空间（渗透率/井距/生产制度）批量扫描出"物理上必然成立"的骨架数据（ert 就是干扫参这活的成熟工具），再叠加传感器噪声、漂移、缺测、坏点等真实工况扰动。devito 之于合成地震同理：正演炮集 + 噪声 + 检波器响应。
5. **LLM 管线只用在"文档层"**（来源：[distilabel](https://github.com/argilla-io/distilabel)、[synthetic-data-generator](https://github.com/argilla-io/synthetic-data-generator)、[Magpie](https://github.com/Magpie-Align/Magpie)）
   数值时序不交给 LLM；LLM 负责把结构化事实"叙述化"（完井报告、班报、故障工单），并接受 schema/规则校验回流——distilabel 的管线+AI 反馈是现成壳。

---

## ⑥ 给新项目的建议

### 6.1 定位

- **不要做"第 N+1 个通用表格合成器"**——该赛道成熟且头部已商业化（SDV→BUSL、Gretel→NVIDIA 闭源）。做**油气领域专用的合成数据工作台**，第一主攻空白点：**生产时序+设备传感器+钻井参数**；测井曲线（借 welly/bruges 物理合成起步）与合成地震（借 devito 正演）为第二梯队。
- 参照物明确写进 README：「Synthea 之于医疗 = 我们之于油气」。领域专属 schema、物理约束、单位制，是通用框架替代不了的三样东西。
- 数据侧用 Volve（[Equinor Open Data Licence](https://www.equinor.com/energy/volve-data-sharing)）+ FORCE 2020（[Zenodo](https://zenodo.org/records/4351156)，NLOD 2.0）+ Norne（[OPM/opm-data](https://github.com/OPM/opm-data)）做分布先验与评估锚点；**注意这些是真实数据，其许可条款决定合成数据的"上游合规"叙述，生成物 license 应单独声明。**

### 6.2 技术路线组合（分层混合，而非单一路线）

| 层 | 干什么 | 选型参考 |
|---|---|---|
| L0 领域 schema 层 | 井/井筒/传感器/生产台账的本体与单位制；场景配方（yield script）声明式描述"生成什么场景" | 自研；Schema 声明格式参考 SDV metadata / Synthea 模块参数 |
| L1 规则+随机打底 | 实体字典（井名/设备型号/故障代码）、字段填充 | [faker](https://github.com/joke2k/faker) / [mimesis](https://github.com/lk-geimfari/mimesis)（均 MIT），扩展油气 locale |
| L2 物理引擎产数 | 生产时序骨架（OPM Flow/MRST 扫参）、地震正演（devito）、PVT/工艺（neqsim） | 均活跃维护；**OPM/MRST 是 GPL-3.0——用"命令行/独立进程"集成，不直接链接源码**；devito 是 MIT 可放心依赖 |
| L3 统计/深度生成补分布 | 在物理骨架上学习残差分布、注入真实感噪声、丰富场景多样性 | 时序首选 [fg-data-synthetic（ydata，MIT）](https://github.com/Data-Centric-AI-Community/fg-data-synthetic)；表格备选 [mostlyai（Apache-2.0）](https://github.com/mostly-ai/mostlyai) 或 [synthcity（Apache-2.0）](https://github.com/vanderschaarlab/synthcity)；扩散思路参考 [tab-ddpm](https://github.com/yandex-research/tab-ddpm)（研究级）；**SDV/CTGAN（BUSL-1.1）仅可用于内部实验，不可作为对外服务内核** |
| L4 LLM 文档层 | 完井报告/班报/工单等非结构化语料 | [distilabel](https://github.com/argilla-io/distilabel)（Apache-2.0）+ [synthetic-data-generator](https://github.com/argilla-io/synthetic-data-generator) 模式，Magpie 的无提示采样可借鉴 |
| L5 评估闸门 | 质量（SDMetrics 式指标）+ 隐私（[anonymeter](https://github.com/statice/anonymeter) 三类攻击）+ **物理一致性（自研：物质平衡/量程/递减率/压力-流量关系）** | 前两类有现成开源；物理一致性是新项目的差异化卖点 |

### 6.3 License 与工程注意

- **License 红绿灯**（截至 2026-09-25 已核实）：可放心集成（Apache/MIT）——mostlyai、synthcity、fg-data-synthetic、REaLTabFormer、faker、mimesis、devito、SDMetrics、neqsim、Synthea、distilabel、Magpie；**传染型 GPL-3.0 需进程外集成**——OPM Flow、MRST、DuMux、openDARTS、ert；**BUSL-1.1 限制商用服务**——SDV、CTGAN（及 DataCebo 家族）；**已死勿选**——Gretel 全系。
- **改名陷阱**：ydata-synthetic→`Data-Centric-AI-Community/fg-data-synthetic`、tab-ddpm→`yandex-research/tab-ddpm`、DARTS→GitLab `open-darts`——写文档/依赖时用新地址。
- **开源 license 建议**：新项目本体选 **Apache-2.0**（与 mostlyai/synthcity/devito 同族，方便下游企业采用；GPL 组件以外部进程/插件形式对接）。
- **命名参考**：领域工具命名走"短词+功能"风格（welleng、welly、bruges、segyio、Synthea），建议同类风格（如 "rigsynth / fieldforge / prodgen" 一类），并在 agent-card/文档中声明数据为合成、禁止用于储量申报等真实决策。

---

## ⑦ 参考链接清单

**通用框架**
- https://github.com/sdv-dev/SDV ｜ https://github.com/sdv-dev/CTGAN ｜ https://github.com/sdv-dev/SDMetrics ｜ https://github.com/sdv-dev/RDT ｜ https://github.com/sdv-dev/Copulas ｜ https://github.com/sdv-dev/DeepEcho
- https://github.com/mostly-ai/mostlyai
- https://github.com/Data-Centric-AI-Community/fg-data-synthetic （原 https://github.com/ydataai/ydata-synthetic ）
- https://github.com/vanderschaarlab/synthcity
- https://github.com/yandex-research/tab-ddpm （原 https://github.com/rotot0/tab-ddpm ）
- https://github.com/worldbank/REaLTabFormer
- https://github.com/joke2k/faker ｜ https://github.com/lk-geimfari/mimesis
- https://github.com/gretelai/gretel-synthetics （archived；NVIDIA 2025-03 收购 Gretel，并入 NeMo 数据生态）

**时序 / LLM / 评估**
- https://github.com/jsyoon0823/TimeGAN ｜ https://github.com/AlexanderVNikitin/tsgm ｜ https://github.com/TimeSynth/TimeSynth
- https://github.com/argilla-io/distilabel ｜ https://github.com/argilla-io/synthetic-data-generator ｜ https://github.com/Magpie-Align/Magpie
- https://github.com/statice/anonymeter ｜ https://github.com/Baukebrenninkmeijer/table-evaluator

**油气领域**
- https://github.com/devitocodes/devito
- https://github.com/OPM/opm-simulators ｜ https://github.com/OPM/opm-data （含 Norne）
- https://github.com/SINTEF-AppliedCompSci/MRST ｜ https://github.com/dumux/dumux
- openDARTS：https://darts.citg.tudelft.nl/ ｜ https://gitlab.com/open-darts/open-darts ｜ https://pypi.org/project/open-darts/ （GitHub org open-darts 无公开仓库，已核实）
- https://github.com/equinor/neqsim ｜ https://github.com/equinor/ert ｜ https://github.com/equinor/segyio ｜ https://github.com/equinor/segyio-notebooks
- https://github.com/agilescientific/welly ｜ https://github.com/agilescientific/bruges ｜ https://github.com/agilescientific/striplog
- https://github.com/andymcdgeo/Synthetic_Log_Generator （个人项目级）
- 领域标杆类比：https://github.com/synthetichealth/synthea

**数据集**
- Volve：https://www.equinor.com/energy/volve-data-sharing （Equinor Open Data Licence，Databricks Marketplace 获取）
- FORCE 2020：https://github.com/bolgebrygg/Force-2020-Machine-Learning-competition ｜ https://zenodo.org/records/4351156
- 油气合成数据同类（均为个人项目级，佐证空白）：https://github.com/caioazevedo-mdm/Hybrid_VFM_Slugging ｜ https://github.com/leoxthomas/K-Pipelines ｜ https://github.com/jayanthbagare/synthetic_oil_gas

---

*报告完。所有仓库存活性、stars、活跃度、license 均于 2026-09-25 经 GitHub API / 搜索 API / 仓库页面直接核实；未核实到的信息（个别 NOASSERTION license 的具体条款）已在文中显式标注。*
