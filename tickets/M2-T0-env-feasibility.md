# M2-T0 · OPM Flow 环境可行性探测与算力实测

**状态**：路径 A 深度执行——被本机 Docker Desktop 故障阻断，**挂起等 Owner GUI 层处理** ｜ **上游**：charter Q3/Q8 ｜ 更新：2026-09-27

## 已定事实（本轮逐项核实）

### 官方安装渠道（结论性）

| 渠道 | 结论 | 证据 |
|---|---|---|
| Docker 官方镜像 | **不存在**（此前记忆中的 `openporousmedia/flow` 为检索摘要误导，已证伪） | [opm-project.org 安装页](https://opm-project.org/?page_id=36) 全文无 docker；镜像源按 registry API 逐名探测 `openporousmedia/flow`、`opmproject/flow`、`opm/flow` 等全部 404（对照组 `library/alpine` 同流程 200，证明探测路径有效） |
| macOS 二进制 | **不存在** | 安装页明示二进制仅覆盖 64 位 Ubuntu 与 RHEL 7；macOS 只支持源码编译；GitHub release（2026.04/2025.10/2025.04）assets 全空 |
| Ubuntu PPA | **存在且为本机唯一官方直达渠道** | `ppa:opm/ppa`（Ubuntu 26.04/24.04）——但只能在 Linux 环境（容器/虚机/服务器）内使用 |
| 算例 | 已核实 | [OPM/opm-data/spe1/](https://github.com/OPM/opm-data/tree/master/spe1)（SPE1CASE1.DATA 等）；Norne 随 opm-data `norne/` |

### 本机执行轨迹（A 路径）

1. **镜像源**：`~/.docker/daemon.json` 已配 `registry-mirrors`（docker.1ms.run / m.daocloud.io / xuanyuan.me，均探活；原文件备份 `daemon.json.bak-20260925`，还原 `cp ~/.docker/daemon.json.bak-20260925 ~/.docker/daemon.json`）。实测 daocloud 对本镜像白名单外（403 DENIED），1ms.run 的 token/manifest/blob API 全通。
2. **daemon 直拉挂死**：`docker pull`（含 `--debug`、含镜像源前缀、含 hello-world 对照）全部无输出挂死；`crane`（Go 栈）同样挂死；**宿主 curl（libcurl）对同一端点 IPv4/IPv6 均秒通**——Go 网络栈挂而 libcurl 通的根因待查（疑似 macOS DNS 解析路径差异）。
3. **绕行成功一半**：`scripts/docker-load-via-mirror.sh`（curl 逐 blob 下载 + sha256 校验 + OCI layout 组装 + `docker load`）已验证可行，`ubuntu:24.04`(arm64) 已入本地镜像库。
4. **容器子系统挂死（阻断点）**：干净重启后 `docker run -d` 连容器都未创建、`docker create` 纯元数据操作也挂死——runc/containerd 层故障，CLI 层无解。**需 Owner 打开 Docker Desktop GUI 检查**（可能有等密码/更新的对话框；或在 Troubleshoot 里做 Reset，注意 Reset 会清掉现有镜像，含 agentjiaotu 系列）。

## 解除挂起后的既定动作（零决策，直接跑）

1. `docker run --rm ubuntu:24.04 bash -c '...'` 网络通即继续；不通则 Docker Desktop 需重置。
2. 容器内换 TUNA 源 → `add-apt-repository ppa:opm/ppa && apt install flow`（PPA 不可达则从 `ppa.launchpadcontent.net/opm/ppa/ubuntu/pool/main/o/opm-simulators/` 直接 curl .deb）。
3. 宿主 `curl` 下载 SPE1 deck（github 直连可达）→ `flow SPE1CASE1.DATA` ×10 计时 + Norne ×1 计时。
4. 数字回填本票与 charter Q8 → 拍板 M2 扫参规模 N（M2-T1 编排器参数）。

## 并行选项（Owner 可任选替代）

- **路径 B**：GitHub Actions ubuntu runner 经 PPA 实测（需建远端仓，外发动作）。
- **路径 C**：任意可 SSH 的 Linux 服务器，跑本票第 2–3 步同样命令即可。

## 实测产出物（解除挂起后）

- [ ] SPE1 单次耗时 ×10 + Norne 单次耗时 ×1 记录入本票与 charter Q8
- [ ] 据此拍板 M2 扫参规模 N 与是否需要并行
