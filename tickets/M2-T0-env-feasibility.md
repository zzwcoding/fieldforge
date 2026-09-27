# M2-T0 · OPM Flow 环境可行性探测与算力实测

**状态**：✅ done（2026-09-27，路径 A 打通并完成实测） ｜ **上游**：charter Q3/Q8

## 实测结果（本机 macOS arm64 · Docker 容器原生 arm64 · flow 2026.04）

| 算例 | 规模 | 结果 | 单次耗时 |
|---|---|---|---|
| SPE1CASE1（[OPM/opm-data/spe1](https://github.com/OPM/opm-data/tree/master/spe1)） | 教学级（437 行自包含 deck） | ×10 全部 rc=0 | **0.44–0.53 s** |
| NORNE_ATW2013（opm-data/norne，30 MB 完整 INCLUDE 树） | 全油田（1323 Newton / 2320 Linear 迭代） | rc=0 | **164.4 s（≈2.7 min）** |

## 环境配方（可复现）

1. 宿主 `ubuntu:24.04`(arm64) 入库（官方无 OPM Docker 镜像；经 `scripts/docker-load-via-mirror.sh` curl 组装或镜像源直拉均可）。
2. 容器内换 TUNA apt 源 → `add-apt-repository ppa:opm/ppa` → `apt install libopm-simulators-bin`（PPA 二进制包名不叫 flow；noble 有 **arm64 原生构建**，Apple Silicon 免转译）→ `/usr/bin/flow`（版本 2026.04）。
3. 常驻容器 `flowbox`（sleep infinity）保留作 M2-T1 开发环境；deck 经 `docker cp` 注入。
4. 官方渠道定论存档：OPM 无 Docker 镜像、无 macOS 二进制（安装页 + registry API 逐名探测证伪，对照 alpine 200）；daemon 直拉非黑洞——cache-miss 代理极慢后返回 not found。

## 排障存档（已收口）

- 镜像加速三源已配 `~/.docker/daemon.json`（备份 `daemon.json.bak-20260925`；daocloud 白名单外 403，1ms.run 可用）。
- Docker Desktop 曾出现容器子系统挂死（`docker create` 卡死），Owner 于 GUI 层修复后恢复。
- Go 栈（daemon/crane）慢而 libcurl 快的现象随环境恢复消失，未再复现，根因未深究。

## 扫参规模结论（喂给 M2-T1 编排器）

- **Norne 级精算：N=50 串行 ≈ 2.2 h（一夜档）**；本机 4–8 路并行可压至 0.5 h 内。
- 建议扫参**分两档**：粗扫用 SPE1 级简模型（千次 ≈ 8 min）定参数域，精扫用 Norne 级 N=50 复核——M2-T1 按此设计编排器参数。
- 验收：~~SPE1 单次耗时 ×10 + Norne ×1 记录~~ ✅；~~拍板扫参规模 N~~ ✅（50，分粗/精两档）
