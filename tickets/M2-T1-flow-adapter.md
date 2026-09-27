# M2-T1 · OPM Flow 独立进程适配器（F3）

**状态**：done（2026-09-27） ｜ **上游**：charter §4 L2、§5（GPL 红线）、Q3/Q8 拍板

## 任务（实际落地）

- `scripts/prepare_flow_image.sh`：从 ubuntu:24.04 构建 `fieldforge/flow:2026.04` 镜像（TUNA 源 + OPM PPA + libopm-simulators-bin），可重复执行。
- `fieldforge/physics/flow_adapter.py`：扫参编排器——
  - 扫参配方 YAML（`sweeps/spe1_orat.yaml`）：deck 模板（SPE1 已入库 `fieldforge/physics/templates/`）+ **声明式正则参数替换**（每参数必须恰好命中一次，否则报错）+ 单位换算表（FIELD → schema：stb/d→t/d、Mscf/d→10^4 m³/d、psia→MPa，系数入 manifest）+ 容器/超时声明；
  - 每方案：渲染 deck 变体落盘 → `docker run --rm -v` 挂载方案目录独立容器跑 flow（超时强杀容器、失败有 rc 与日志）；
  - 回收：宿主侧 `parse_summary.py`（resdata 可选依赖）读 SMSPEC/UNSMRY → 速率列非负截断 → production_daily **同构骨架表**（+bhp_mpa 信息列），行粒度 = deck DATES 步长，producing_hours 恒 24（停机扰动归 T2 注入器）；
  - 汇总 `sweep_results.csv`（带 solution_id）+ `manifest.json`（flow 版本/镜像/模板 sha/逐方案 rc·耗时·行数）。
- `fieldforge/cli.py` 新增 `sweep` 子命令：`python3 -m fieldforge sweep --sweep ... [--out ...]`。
- **GPL-3.0 红线**：flow 只在独立容器内运行，宿主仅命令行 + 文件交换；容器镜像逐脚本可重建。

## 验收

- [x] 一条命令对 1 口井跑 N 个方案并回收为 production_daily 同构骨架（实测 spe1-orat N=3：3/3 rc=0，每方案 1.1–1.3s，123–124 行/方案）
- [x] 宿主进程与 flow 进程隔离（容器边界）；超时/失败方案有明确退出码与日志
- [x] 同 deck + 同 flow 版本可复现（deck 渲染确定性 + 模板 sha256 记账）
- [x] 单测 4 条（渲染恰好命中一次 / 零命中报错 / 配方缺模板缺 values 报错）全过

## 备注（工程坑存档）

- PPA 二进制包名 `libopm-simulators-bin`（不叫 flow）；SPE1 deck 实为 FIELD 单位制（第 46 行），units 换算按此定。
- 宿主 pip 因 truststore/macOS 26 兼容 bug 无法联网安装，resdata 6.3.5 以轮子直解到用户 site-packages 方式就位（resdata/cwrap/numpy/pandas/typing_extensions/tzdata/pytz/python-dateutil/six）。
- resdata 无 linux-arm64 轮子 → 解析放宿主侧（macOS arm64 轮子存在），容器只跑 flow——恰与 GPL 进程隔离同向。
- 精扫（Norne 级 N=50）复用同一配方结构，换 template 与参数域即可（M2-T0 实测 164s/次）。
