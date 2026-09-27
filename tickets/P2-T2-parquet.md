# P2-T2 · Parquet 载体启用

**状态**：done（2026-09-27） ｜ **上游**：对接调研 D 节（湖表数据文件形态 Parquet 落桶）

## 任务

- pyarrow 25.0.1 以轮子直解方式装入宿主用户 site-packages（pip truststore 故障绕行，与 resdata 同法）。
- 既有 `--format parquet` 后端启用：emit.write_table 的 pyarrow 分支实测可用（M1 起预留的接口）。

## 验收

- [x] core 配方 `--format parquet` 一条命令：五表 .parquet 落盘、manifest output_format=parquet
- [x] pyarrow.parquet 回读 production_daily.parquet：365 行、列名齐
- [x] 合同 schema 同路径可用（emit 层与 schema 无关）

## 备注

- 湖表 Iceberg 化（MinIO+Iceberg catalog）属平台侧，生成器只需交付 Parquet 文件——对接形态已就位。
