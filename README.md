# fieldforge

**油气领域专用合成数据生成工作台。**
A domain-specific synthetic data generator for oil & gas — production ledgers, sensor telemetry, injection connections and well logs, built around a schema contract, a physics engine backbone and a quality gate that refuses to ship data it cannot vouch for.

> 定位一句话：**Synthea 之于医疗 = fieldforge 之于油气。**
> 通用合成数据框架（SDV / mostlyai / synthcity…）没有油气 schema、单位制与物理约束；油气物理引擎（OPM Flow / MRST / devito…）能产"真物理"数据却没有面向 ML 的封装。fieldforge 补的就是中间这一层。

- **状态**：v0.x，单维护者。M0–M3 + P0–P3 + M5 共九个里程碑全部收口，48 个测试稳定全绿。
- **License**：Apache-2.0（详见下方数据声明）。

## 为什么是空白

2026-09 的 GitHub 生态调研（[docs/research/](docs/research/)，40+ 仓库逐一核实）确认：

- 通用表格/时序合成赛道成熟但头部已商业化收紧（SDV→BUSL-1.1，Gretel→NVIDIA 收购）；
- 油气领域只有活跃的**物理引擎**（OPM Flow、MRST、devito、neqsim），**不存在**任何框架级的"油田生产时序/设备传感器/钻井参数"合成数据项目——搜到的同类最高仅 2★；
- 缺的那一层（领域 schema + 物理一致性 + 脏特征交付）就是 fieldforge 的位置。

## 特性

| | 能力 | 说明 |
|---|---|---|
| 📐 | **schema 驱动双合同包** | `schemas/tpa-contract-v0.1.yaml`（Petro-Agent 生产域 8 表字典逐字段对齐）与 `schemas/core-v0.yaml`（通用油田域）并存；字段/单位/枚举/量程/主键全部声明式 |
| 🛢️ | **四类油气数据** | ① 生产域 8 表（120 井 = 86 采油 + 34 注水主数据配比，日产计量 31,390 行对齐全年锚点）② 注采受效关系（劈分系数 Σ=1）③ 测井曲线（FORCE 2020 记忆码 7 曲线 + 12 类岩性标签，288k 行）④ 传感器日度 + 15 分钟档亚日（分层采样 210k 行） |
| ⚙️ | **物理打底** | OPM Flow 独立容器扫参（SPE1 0.45s / Norne 全油田 164s，GPL 组件只经命令行与文件交换）；日度骨架 = Arps 递减 + 含水爬升 + 停机事件，物质量纲自洽 |
| 🧩 | **脏特征注入器家族** | 10+ 类平台脏特征（班报重复行、配产双值、单位误录、旧井号写法、恒值 30 日、T-3 补录批次、状态滞后、新旧编码并存、措施缺效期缺失、化验打架…）——**配方化、可复现、计数入 manifest**，是质量规则的挂样本生产线 |
| 🚦 | **评估闸门（未过闸不出库）** | 质量 / 隐私 / 物理一致性三族指标 + 平台规则 r1–r12 逐条机判；generate 自动过闸，`enforce: true` 时 fail 即 exit 1 |
| 📝 | **班报叙述化 + 机判回流** | 结构化事实 → 班报语料（模板 v0.1，LLM 接口已留），逐字段数值一致性机判，对不上台账的语料不得出库 |
| 🔁 | **确定性再生** | 同 seed 字节级复现（跨运行、跨表）；manifest 全程记账（seed / schema 版本 / 参数 / 单位表 / 闸门结论 / freshness） |
| 💾 | **CSV / Parquet 双载体** | Parquet 交付态下闸门同样生效 |

## 快速开始

依赖：Python ≥ 3.10 + PyYAML；可选 `pyarrow`（Parquet）、`resdata`（物理扫参汇总解析）。

```bash
# ① 一条命令产出平台数据合同全量（12 表 · 120 井 · ~46 万行，含自动过闸）
python3 -m fieldforge generate --recipe recipes/tpa_s1_demo.yaml --out out-tpa

# ② 脏特征交付物（质量规则的挂样本来源，闸门 report-only）
python3 -m fieldforge generate --recipe recipes/tpa_s1_dirty.yaml --out out-tpa-dirty

# ③ 评估闸门（质量/隐私/物理一致性三族 + 平台规则 r1–r12，JSON/HTML 报告）
python3 -m fieldforge evaluate --data out-tpa --html

# ④ 班报语料（数值一致性机判回流）
python3 -m fieldforge narrate --data out-tpa --well N-01 --days 7

# ⑤ 物理扫参（OPM Flow 容器；先 bash scripts/prepare_flow_image.sh）
python3 -m fieldforge sweep --sweep sweeps/spe1_orat.yaml

# 测试
python3 -m unittest discover -s tests -t .   # 48 个测试
```

输出带 `manifest.json`（seed / schema 版本 / 单位表 / 符合性结论 / 闸门结论 / 合成数据声明）。

## 部署（单机 Docker Compose）

```bash
cd deploy && docker compose up -d --build   # fieldforge-api + postgres + redis + nginx(80)
curl http://<服务器IP>/healthz
```

- API：`POST /api/generate` · `GET /api/runs` · `POST /api/evaluate/{run_id}` · `POST /api/narrate/{run_id}` · `GET /api/runs/{id}/download/{file}`（白名单文件名）
- 生成任务互斥限流（并发第二个 429）；每个响应带 `X-Synthetic-Data` 头
- 服务器首次初始化：[deploy/init-server.sh](deploy/init-server.sh)（Docker + 4G swap）
- 路线：单机 compose → tpa 前后端加入 → 流量上来再迁容器服务

## 数据红线

**所有产出均为合成数据**，仅可用于算法研发、测试、演示与教学；
**禁止用于储量申报、生产决策等任何真实业务场景。**
该声明强制写入 README、输出 manifest 与评估报告三处，缺失即验收不通过。

## 架构（L0–L5）

```
L0 领域 schema（合同包 + 通用包，声明式：字段/单位/枚举/量程/主键）
L1 规则+随机打底（实体字典、字段填充——faker/mimesis 同思路的油气 locale）
L2 物理引擎产数（OPM Flow 独立容器扫参 + 噪声/工况注入）
L3 统计/深度生成补分布（接口已留，fg-data-synthetic / mostlyai 同接口可插拔）
L4 LLM 文档层（模板叙述化已落地，LLM 叙述化接口已留）
L5 评估闸门（质量 / 隐私 / 物理一致性三族指标插件 + 平台规则族，未过闸不出库）
```

设计取舍与选型依据详见 [docs/charter.md](docs/charter.md)（含九个里程碑的决策记录）与 [docs/research/](docs/research/)（合成数据生态调研）。

## 文档地图

| 路径 | 内容 |
|---|---|
| [docs/charter.md](docs/charter.md) | 立项稿：定位 / 技术路线 / 里程碑 / 决策记录与开放问题 |
| [docs/prd.md](docs/prd.md) | PRD（F1–F10 功能域骨架） |
| [docs/integration-requirements.md](docs/integration-requirements.md) | 对接调研：目标平台数据面需求抽取 × fieldforge 符合度 |
| [docs/licenses-real-anchor.md](docs/licenses-real-anchor.md) | 真实锚点数据 license 审阅备忘（NLOD 2.0 / Equinor ODL） |
| [docs/reports/](docs/reports/) | 评估闸门样例报告（干净 pass / 脏特征 fail）与班报语料样例 |
| [tickets/](tickets/) | 全部施工票（含验收记录与坑存档） |
| [schemas/](schemas/) · [recipes/](recipes/) · [sweeps/](sweeps/) | schema 合同包 / 场景配方 / 物理扫参配方 |

## 坑存档（踩过的都在票里）

- OPM 官方**没有** Docker 镜像与 macOS 二进制，Ubuntu PPA 是唯一直达渠道，PPA 二进制包名是 `libopm-simulators-bin`；
- SPE1 deck 实为 FIELD 单位制（第 46 行 `FIELD`），单位换算按此定；
- Docker Desktop 曾出现容器子系统挂死（`docker create` 卡死），需 GUI 层排查；
- Go 网络栈（docker/crane）在本机曾极慢而 libcurl 秒通——绕行方案见 [scripts/docker-load-via-mirror.sh](scripts/docker-load-via-mirror.sh)（curl 逐 blob + sha256 校验 + OCI 组装 + docker load）；
- 本机 pip 因 truststore/macOS 26 兼容 bug 不可联网安装，依赖以轮子直解方式就位。

## License

[Apache-2.0](LICENSE)。

**数据声明**：本项目生成的全部数据为合成数据。种子字典与岩石物理图版值为虚构/教学典型值（取形自内部教学设定，其自身标注虚构），不代表任何真实油田；FORCE 2020 / Volve 等真实数据集**未**被使用。OPM Flow 经 Ubuntu PPA 在独立容器内运行，宿主仅做命令行与文件交换（GPL-3.0 合规集成）。
