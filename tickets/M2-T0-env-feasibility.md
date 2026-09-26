# M2-T0 · OPM Flow 环境可行性探测与算力实测

**状态**：探测完成（2026-09-25）／ **实测挂起——两条候选路径待 Owner 拍板** ｜ **上游**：charter Q3/Q8

## 已探测结论（本机 macOS arm64，2026-09-25 逐路实测）

| 路径 | 结论 | 证据 |
|---|---|---|
| Homebrew | **不可行** | brew 7.0.2 无 opm-flow 公式；OPM 官方 tap [github.com/OPM/homebrew-opm](https://github.com/OPM/homebrew-opm) 已停更（pushed_at 2018-12-04，仅老 opm-core 等公式，无 flow） |
| Docker | **本机不可行（网络）** | Docker 29.4.1 已装但 daemon 未启动；`~/.docker/daemon.json` 无镜像加速配置；Docker Hub 网络不可达（curl 与 ZCode 抓取双通道均超时，同刻 api.github.com 返回 200）——直拉官方镜像不可行 |
| conda-forge | **不可行** | api.anaconda.org/package/conda-forge/opm → 404（无该包）；本机也未装 conda/mamba |
| GitHub release 二进制 | **无 macOS 产物** | opm-simulators 最新 release（release/2026.04/final）assets 为空 |
| 算例 | ✅ 已核实 | [OPM/opm-data/spe1/](https://github.com/OPM/opm-data/tree/master/spe1) 有 SPE1CASE1.DATA 等（仓库 pushed_at 2026-08 活跃）；Norne 随 opm-data `norne/` 分发 |

## 两条候选实测路径（待 Owner 拍板）

- **路径 A（本机 Docker）**：启动 Docker Desktop + 在 daemon.json 配置镜像加速后拉 `opmproject/flow`（镜像名/tag 在 Hub 不可达期间无法核实，拉到后确认），`docker run -v $PWD:/data opmproject/flow flow /data/SPE1CASE1.DATA` 计时。优点：数据不出本机；代价：需改 daemon.json、第三方镜像源完整性自负。
- **路径 B（GitHub Actions 远端）**：建 GitHub 仓库，ubuntu-latest runner 上 `add-apt-repository ppa:opm/ppa && apt install flow`（或 runner 内拉镜像——runner 网络直连 Hub 无碍），workflow 跑 SPE1×10 + Norne×1 计时。优点：零本机改动、结果随仓可复现；代价：属外发动作（SPE1/Norne 均为公开数据，无合规问题）。

## 实测产出物（解除挂起后）

- [ ] SPE1 单次耗时 ×10 + Norne 单次耗时 ×1 记录入本票与 charter Q8
- [ ] 据此拍板 M2 扫参规模 N（M2-T1 编排器参数）与是否需要并行
