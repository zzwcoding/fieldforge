# Q5 备忘 —— 真实锚点数据 license 审阅（Volve / FORCE 2020）

> **日期** 2026-09-27 · **性质** 法务初筛备忘（非法律意见；正式商用前建议法务复核）
> **结论先行**：**FORCE 2020（NLOD 2.0）条款干净，可作第一个真实锚点**，合成数据"上游合规"叙述成立；**Volve（Equinor Open Data Licence）有用途限定词，需补读 User Guide PDF 再定**。

## 1. FORCE 2020（NLOD 2.0）—— ✅ 建议首选

数据：挪威海 118 口井测井+岩性（Zenodo record 4351156 直接下载，许可 NLOD 2.0）。
NLOD 2.0 全文（data.norge.no/nlod/en/2.0）关键条款：

- **§2 使用与衍生**：licensee "may use the information for any purpose and in all contexts, by: copying … and distributing the information to others, **modifying the information and/or combining the information with other information, and copying and distributing such changed or combined information**"——**明确允许修改+组合+再分发修改后的信息**，用其做分布先验/评估锚点并分发合成数据落在授权范围内。
- **§5 署名**：须署名 licensor 并附许可链接；"**If the information has been changed, the licensee must clearly indicate that changes have been made**"——合成数据即"changed information"，fieldforge 的 manifest/README 合成声明恰好满足"清晰指明已改动"。
- **§6 正当使用**：不得以误导方式使用、不得用 licensor 名义背书——README 声明"合成数据、非真实井"符合。
- **§9 许可兼容**：与 CC-BY 4.0 兼容——生成物（Apache-2.0）与署名链可并存。
- **§7 免责**：as-is，无担保——标准条款。

**落地动作**：下载 FORCE 2020（Zenodo 4351156）→ README/manifest 增补署名行："Contains data under the Norwegian licence for Open Government data (NLOD 2.0) distributed by [NPD/Force licensor]，changes made by fieldforge (synthetic)"→ `--real` 接口接 FORCE 测井曲线作 q3 参照与 anonymeter 输入。

## 2. Volve（Equinor Open Data Licence）—— ⚠️ 缓一步

Equinor 官方页（equinor.com/energy/volve-data-sharing）核实到的措辞：

- 授权对象："all **academic institutions, students and researchers**"；用途："available for **research, study and development purposes**"；"without any need for further written permission from us"。
- **页面未含许可全文**（分发/衍生/署名条款在 Databricks Marketplace 或 User Guide PDF 内，页明示"该页即为许可文档"）。

**风险点**："research, study and development purposes" 的用途限定词——若 fieldforge 产出物未来作为开源工具分发给企业使用，"衍生自 Volve 的合成数据"是否越出 research/study/development 存在解释空间。
**落地动作**：暂以 FORCE 2020 为唯一锚点；如需 Volve，先取 User Guide PDF 全文审阅，必要时仅限内部实验用途。

## 3. 决策与下一步

1. 真实锚点 = **FORCE 2020（NLOD 2.0）**；署名模板随锚点接入票落地。
2. `--real` / anonymeter / q3 真质量评估在锚点数据下载后接通（接口已留）。
3. 本备忘为工程初筛；仓库 README 增补"上游数据来源与许可"小节时引用本文。
