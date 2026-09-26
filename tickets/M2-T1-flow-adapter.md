# M2-T1 · OPM Flow 独立进程适配器（F3）

**状态**：待开工（依赖 M2-T0 实测拍板运行形态：容器 or 二进制） ｜ **上游**：charter §4 L2、§5（GPL 红线）、Q3 拍板

## 任务

- `fieldforge/physics/flow_adapter.py`：**子进程**封装 flow（容器或二进制，按 T0 拍板）。
  - 输入：扫参方案 = schema 声明的参数域（如渗透率倍率、井底流压制度、生产制度档位）。
  - deck 变体：模板（Norne / SPE1）+ 参数替换，逐方案落盘为独立 deck 目录。
  - 输出：回收 WOPR/WWPR/WGPR/WTHP 等关键字汇总 → 归一为 `production_daily` 骨架表（沿用 M1 表结构，M1 的 Arps 骨架降级为 fallback 模型）。
- **GPL-3.0 红线**（charter §5）：只经命令行与文件交换，不链接源码、不二次分发其代码。
- 扫参编排：N 方案串行起步，是否并行等 T0 实测结论。

## 验收草案

- [ ] 一条命令对 1 口井跑 N 个方案并回收为 production_daily 骨架
- [ ] 宿主进程与 flow 进程隔离（超时/失败方案有明确退出码与日志，不拖垮宿主）
- [ ] 同一 deck + 同一 flow 版本结果可复现
