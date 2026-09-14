# Thunderbird：8.3 Performance-counter verification

2026-09-14，在 thunderbird.ece.ncsu.edu（AArch64、Neoverse N1 r3p1、80 核、单 socket、无 SMT）依次完成 capacity、line_size、associativity。L1D/L2 的容量和相联度推断获得计数证据支持；行大小实验存在预取影响；核心 LL 事件不能独立确认 SLC 容量边界。原始数据与这些限制均保留。

## 冻结、适配和执行

先于本次 PMU discovery 和新增系统/厂商对照，于 **15:31:35 UTC** 建立 [Phase-I 冻结清单](../../preflight/thunderbird/phase1_freeze.json)，覆盖 810 个已有文件；另对 264 个原有 PMU 文件记录 SHA-256。未改写旧推断或任何 Artemisia 文件。最终 [audit.json](audit.json) 检查文件哈希、源码/二进制快照及串行时间顺序。

| 顺序 | Run | 验证点 | 每点 timed batches | CPU / NUMA | 采集区间 UTC |
|---:|---|---:|---:|---|---|
| 1 | [capacity01](../../capacity/data/thunderbird/capacity01/) | 14 | 1,000,000 | 32 / 0 | 15:42:21–15:44:46 |
| 2 | [line_size01](../../line_size/data/thunderbird/line_size01/) | 12 | 1,000,000 | 4 / 0 | 15:45:18–15:46:22 |
| 3 | [associativity01](../../associativity/data/thunderbird/associativity01/) | 12 | 1,000,000 | 4 / 0 | 15:47:10–15:47:38 |
| 4 | [ll_diagnostic01](../../capacity/data/thunderbird/ll_diagnostic01/) | 2 | 1,000,000 | 32 / 0 | 15:48:46–15:49:21 |

三类主实验共 **38,000,000** 次，补充诊断 **2,000,000** 次；不是将总数分摊到不足一百万次的点上。工作集/地址序列、seed、batch、warm-up 与既有 Thunderbird Phase-I 对应点匹配。capacity 为 batch 256、64 B 间距、seed 59202、随机链、THP；line_size 为 256 KiB footprint、512 B grouping window、batch 1024，保留不同遍历模式及 seed；associativity 为 batch 参数 128、seed 701、max_k 16，使用既有 candidate256/candidate2048。

计时仍用 Phase-I 的 ARM `CNTVCT_EL0` 和相同屏障。实读 `CNTFRQ_EL0=25,000,000 Hz`，故 **1 tick = 40 ns**，不是一个 CPU cycle。capacity 的 timed assembly 与冻结源码逐字一致；两个 C++ timer header 也一致。原始源码差异已保存在 [preflight](../../preflight/thunderbird/) 的 `*_phase1_to_pmu.diff` 中。

沿用原有 Artemisia PMU 仪器化方式：计数只覆盖完整 sample loop，输出缓冲区预触页，最终文件输出在计数停止后。line_size 的 Phase-I 在相邻 timed intervals 之间写文本；既有 PMU 版本改为内存缓冲并使用 `posix_memalign`，因此相邻批次之间的活动和分配地址不能视为逐指令完全相同。计时区间内的指针追逐、布局、遍历顺序和 timer 不变；这种仪器化差异需纳入比较。

associativity 原有源码每次实际计时 **129** 次 load（第一次 `p->next` 加 128 次循环），而旧 CSV 除以 128。本次统计除以 129，旧 baseline 仅在展示时乘 128/129；旧数据未改动。PMU 包含 K−1 次准备访问，每点分母为 `1,000,000 × (K+128)`。因此报告的 rates 是每千次已知 chain load 的事件数，不是退休 load miss 百分比。

## 事件发现及支持范围

[事件清单与解释](../../events/results/thunderbird/discovery01/EVENTS.md) 附完整 `perf list`、108 个 core 事件的清单、全部本机 PMU sysfs 信息和实测探针。主实验同时收集 `l1d_cache_refill_rd` (0x42)、`l2d_cache_refill_rd` (0x52)、`ll_cache_miss_rd` (0x37)、`ld_spec` (0x70)。名称与编码均按本机验证，未使用 Intel 的 `mem_load_retired.*`。

所有组均 pinned、per-thread、user mode，要求 `time_running_ns == time_enabled_ns > 0`，全部通过。L1/L2 refill 与 speculative-load 事件具有不同于 Intel retired-load 事件的语义；helper/stack、结果缓冲区和推测活动会进入计数。不得要求不同层 rates 必然构成严格递减的概率序列。事件的条件与语义依据 [Arm Neoverse N1 PMU Guide，pp. 33、38、40–44、52](https://documentation-service.arm.com/static/66ace6ee0469d5197d40c93e)。

## Timing / PMU / system-vendor 对照

厂商参考采用本平台的 [Ampere Altra Datasheet，Issue 1.30，pp. 8–9](https://amperecomputing.com/assets/Altra_Rev_A1_DS_v1_30_20220728_8170025756.pdf)。本机不是 Intel/AMD，题目关于适用代际的 Agner Fog 条件不适用。PDF、本地提取文本、来源及 SHA-256 保存在 [vendor](../../preflight/thunderbird/vendor/)。系统值来自冻结之后采集的 [CPU 4/32 cache sysfs](../../events/data/thunderbird/discovery01/hardware.json)；两核一致。容量单位以下按 KiB/MiB 表示，datasheet 使用 KB/MB 标记。

| 项目 | Timing Inference（冻结 Phase-I） | PMU Evidence（每 1000 chain loads） | Published/System Value | Source/Page | Error/Agreement |
|---|---|---|---|---|---|
| L1D 容量 | 约 64 KiB，64–72 KiB 发生变化 | 64/72/80 KiB 的 L1 refill 为 17.11/570.74/998.44；L2 refill 约 0.49 | 64 KiB | sysfs；Altra §2.3.1 p.9 | 标称容量一致；边界附近已受冲突/辅助数据影响 |
| L2 容量 | 约 1 MiB；1–1.125 MiB 明显上升 | 1/1.125/1.5/2 MiB 的 L2 refill 为 48.44/298.04/791.50/998.97 | 1 MiB | sysfs；Altra §2.4 p.9 | 近似推断一致；不是理想的阶跃 |
| SLC 有效容量 | 32–64 MiB 的有效转变区间，非精确物理容量 | `0x37` 在此区间约 1001，未随 timing 同步给出新边界 | 32 MiB、socket 共享 | Altra §2.1 p.8、§2.5 p.9；sysfs 未列 SLC | 32 MiB 落在旧推断区间端点；PMU 验证不成立，不能报告 64 MiB 物理容量 |
| L1D 相联度 | candidate256、16 KiB 间距，K=4→5，推断 4 ways | K4→5：L1 refill 0.12→977.45，L2 refill 0.95→0.94 | 4 ways | sysfs；Altra §2.3.1 p.9 | 一致，4→5 是 L1 冲突 |
| L2 相联度 | candidate2048、128 KiB 间距，K=8→9，推断 8 ways | K8→9：L2 refill 19.06→271.02；K10/12 为 501.78/953.04 | 8 ways | sysfs；Altra §2.4 p.9 | 一致；增长渐进，K5 的更早跃升属于 L1 |
| L1D / L2 sets | 64 KiB/(4×64 B)=256；1 MiB/(8×64 B)=2048 | 对应候选的层级归因得到上述计数支持 | 256 / 2048 | sysfs；由容量/ways/line 计算 | 一致；推导依赖 64 B 行大小，并非独立测出物理索引映射 |
| 行大小 | 64 B 候选；原 timing 未给出干净平台 | offset0、32/56/64/72/96 B 的 L1 refill 为 173.33/288.48/339.74/418.86/1001.02；64 B 完全随机约 1000.69 | L1D、L2 均 64 B | sysfs；Altra §2.3.1、§2.4 p.9 | 候选数值相符，但本工作负载 PMU 曲线不足以独立精确确认 64 B |
| SLC ways / sets | 未在本次冻结候选中独立确定 | 本次无有效 CMN 几何证据 | SLC 16 ways；具体 slice/set 映射未验证 | Altra §2.5 p.9 | 仅列厂商值，不将其写回 Phase-I；不从分布式总容量直接声称已测 sets |
| Hit / next-level latency | 既有 latency01：L1/L2/SLC 候选 hit 中位数约 1.406/4.688/38.438 ns；memory 候选约 94–97 ns | 本次只验证代表性容量/冲突工作负载，没有重新计数七组 latency | 未找到可直接同条件对照的确定 latency 规格 | 冻结 latency01；datasheet p.9 给几何而非同条件实测时延 | 不计算虚假的 cycle 误差；C++ -O0 loop timing 不能直接替代纯依赖链 hit latency |
| 共享范围 | 本次单线程候选未独立验证跨核共享 | per-thread 计数不能单独证明共享拓扑 | L1/L2 每核私有，SLC 全 80 核共享 | sysfs；Altra §2.1 p.8、§2.5 p.9 | 系统/厂商一致，实验范围有限 |
| Inclusion / exclusion | 本目录下没有可归属 Thunderbird 的有效已冻结结论 | 本次三个实验不构成 inclusion 专项验证 | L2 严格包含 L1D/L1I；SLC mostly exclusive with L2 | Altra §2.4、§2.5 p.9 | 仅记录厂商属性，尚无本次独立实验确认 |

最后一行的证据归属需要特别说明：已有 `timing-only/inclusion/data/thunderbird/raw_data_inclusion/artemisia/inclusion_report.json` 内部写的是 `machine: artemisia`，仅 40,000 trials。它虽位于 thunderbird 路径下，不能据此作为 Thunderbird 的 inclusion 结果；文件保留原样。

## 差异与限制

**L1/L2 结果吻合。** capacity 的 L1/L2 median 基本复现原 timing：72 KiB 为 3.281 ns（原 3.125 ns），1 MiB 为 6.25 ns，2 MiB 为 38.281 ns。结合 refill 跃升，可以把两个局部转变分别归为 L1 与 L2。associativity 的 128 KiB 地址间距同时冲突 L1，K=4→5 的时延增长不可误算成 L2 只有 4 ways；L2 refill 在 K=8→9 才大幅增加。

**SLC 尚未由 PMU 验证。** 主实验在 2 MiB 时 L2 refill≈998.97、`0x37`≈999.07，32–64 MiB 两者也接近 1000。补充两个相同容量工作负载，改收集 `0x36/0x37/0x2a/0x52`：2 MiB 的前三者均约 998.96，64 MiB 均约 1000.56–1000.57。核心 LL read、LL miss 与 cluster refill 几乎同数，不能区分该机器上的 SLC hit/miss。我们未读取或修改特权 EXTLLC 配置，也不能确定固件/返回数据源标记的原因。

CMN `hnf_cache_miss` 在本机列表中存在，但 perf 的用户态过滤探针显示 `<not supported>`；进一步通过不启用事件的直接 `perf_event_open`、取消 user/kernel 过滤，得到 **EACCES (13)**。这确认当前账户不能打开所需 system-wide CMN 事件。保留失败探针，没有伪造 SLC miss 证据或调整系统权限。

**LLC 区间有明显时间变化。** 新 PMU timing 在 32 MiB 为 67.81 ns，而冻结 baseline 为 39.38 ns；40 MiB 为 80.47 vs 57.34 ns；64 MiB 为 89.22 vs 75.00 ns。32 MiB 的十个时间块 median 最大/最小比为 1.65，40 MiB 为 1.45。相同绑核和完整 THP 并不隔离共享缓存、内存、其他用户活动或动态频率。期间观察到其他计算/分析进程活动，但没有证据把全部差异归因于某一个因素。因此保留非平稳分布，不用一次 PMU 曲线改写已冻结的 SLC 容量区间。

**行大小受到遍历/预取影响。** offset0 的 grouped-random 64 B 约 340 L1 refills/1000，而 fully-random 64 B 约 1001、sequential 64 B 约 76。说明 grouped-random 仍保留局部连续访问，不能套用“stride 达到 line size 就一次访问一次 miss”的理想模型。96 B 的陡升不能解释为 96 B 行大小；分组规则、复用与预取共同影响曲线。sequential64 的 L2 refill≈18.39、`0x37`≈43.90 也是计数作用域/推测请求的异常提示，不能由这些总量直接构造嵌套 miss 概率。64 B 目前是与系统值一致的候选。

**质量记录如实保留。** 三个主 run 的计数组全部无 multiplex，测量区间 minor/major faults 均为 0，NUMA 均为 0；非自愿切换数分别为 945/1821/1614。line_size 开始前 CPU4 一秒 busy 检查为 100%，因此不能称该 run 在空闲机器上采集；其各点十个时间块的 median 比仍不超过 1.010，未删除异常值。associativity 最大时间块比为 1.25。所有 raw 样本、离群值和顺序均保留，不将一百万相邻批次当作一百万独立进程重复。

capacity 每点完整 THP backing 在测量前后得到核查；associativity 映射保持 2/4 MiB THP。line_size 的 malloc 区域可能与其他分配合并，smaps 中 AnonHugePages 从 0 到 6 MiB 不等；这是包含工作负载的整个映射，不能推断每个 256 KiB 工作集都具有相同页类型。遵循原有分配流程并记录此限制。

## 结果入口

- [capacity 图](../../capacity/results/thunderbird/capacity01/figures/capacity_pmu_validation.png) · [统计](../../capacity/results/thunderbird/capacity01/summary.csv) · [质量](../../capacity/results/thunderbird/capacity01/quality.json)
- [line_size 图](../../line_size/results/thunderbird/line_size01/figures/line_size_pmu_validation.png) · [统计](../../line_size/results/thunderbird/line_size01/summary.csv) · [质量](../../line_size/results/thunderbird/line_size01/quality.json)
- [associativity 图](../../associativity/results/thunderbird/associativity01/figures/associativity_pmu_validation.png) · [统计](../../associativity/results/thunderbird/associativity01/summary.csv) · [质量](../../associativity/results/thunderbird/associativity01/quality.json)
- [LL 补充诊断计数](../../capacity/results/thunderbird/ll_diagnostic01/pmu_counts.csv)
- [运行方法](../../THUNDERBIRD.md) · [完整性审计](audit.json)

每个结果目录另有相同图的 PDF、真实样本箱线图、每个事件的原始计数与 enabled/running 时间、十个时间块统计、分析源码副本和 SHA-256。
