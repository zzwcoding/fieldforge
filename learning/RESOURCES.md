# RESOURCES —— 信源清单（讲解论断的出处，不凭记忆）

> 规则：课程里的每个关键论断都应能回指到这里。分两类：知识（官方文档/源码/标准）、智慧（社区实践/内部经验沉淀）。

## 知识类（官方与源码）

| 信源 | 用在哪些课 |
|---|---|
| 本仓源码 `fieldforge/fieldforge/`（engine/transform/inject/narrate） | S1–S3、S6 全部行为的第一真源 |
| 本仓源码 `fieldforge/schemas/`、`recipes/` | S1：表结构与配方怎么声明 |
| tpa-data-plane 源码 `app/data_plane/`（dp1–dp9）+ `specs/modules.md` | S4–S5：四道闸、五工具、治理 |
| 教学仓 teach-petro-agent `docs/business-setting.md` §3/§4/§6/§8 | S2：20 条规则判据；S4：15 指标卡与术语 |
| fieldforge `docs/research/2026-09-25-*.md` | S1 开场：生态调研、选型依据 |
| FastAPI 官方文档 https://fastapi.tiangolo.com/ | S7：两个 API 面的框架 |
| DuckDB 官方文档 https://duckdb.org/docs/ | S3/S4：直读 CSV/Parquet 的查询引擎 |
| PyIceberg 文档 https://py.iceberg.apache.org/ | S7：湖表格式（S1 用替身，真链路挂起项） |
| nginx beginner guide https://nginx.org/en/docs/beginners_guide.html | S7：转发规则 |
| 《Fundamentals of Analytics Engineering》（Castillo 等，dbt Labs 系）
  本地：/Users/divh/Downloads/资料/技术书籍/Fundamentals of Analytics Engineering/原书提取/（ch1–ch14 提取文本）
  本书 = tpa 数据面那套概念的行业源头：staging/intermediate/marts 分层、质量测试、语义层、分析工程角色分工。
  用在：S2（质量闸 = 书中 data quality tests）、S2-02（marts 分层建模）、S4（语义层/指标）、S7（数据栈全景） |

## 智慧类（实践与内部经验）

| 信源 | 用在哪些课 |
|---|---|
| Arps 递减模型（石油工程标准产量递减公式） | S3：产量骨架的数学依据 |
| fieldforge `learning/` 各课闯关错题 | 持续累积，错题即缺口 |
| 部署实测记录（本会话：Docker Hub 不可达→镜像加速、pip 轮子直解等） | S7：环境坑与绕行 |
| Synthea（https://github.com/synthetichealth/synthea） | S1 开场：领域专用生成器的对标项目 |
