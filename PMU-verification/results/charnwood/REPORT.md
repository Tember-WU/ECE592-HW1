# Charnwood：Section 8.3 PMU 验证

2026-09-14 已按 **capacity → line_size → associativity** 串行完成三个实验：14 + 12 + 12 = **38 个测点、3,800 万次 workload repetitions**。每点 100 万次；四个事件同时采集，全部 `time_enabled == time_running > 0`。原始数据、计数、完整统计、PNG/PDF 图表均已保存。

| 实验 | 正式运行 | 测点 / repetitions | 报告与图表 |
|---|---|---|---|
| Capacity | `capacity03` | 14 / 14,000,000 | [运行记录](../../capacity/results/charnwood/capacity03/RUN_NOTES.md) · [图](../../capacity/results/charnwood/capacity03/figures/capacity_pmu_validation.png) |
| Line/stride | `line_size01` | 12 / 12,000,000 | [运行记录](../../line_size/results/charnwood/line_size01/RUN_NOTES.md) · [图](../../line_size/results/charnwood/line_size01/figures/line_size_pmu_validation.png) |
| Associativity | `associativity01` | 12 / 12,000,000 | [运行记录](../../associativity/results/charnwood/associativity01/RUN_NOTES.md) · [图](../../associativity/results/charnwood/associativity01/figures/associativity_pmu_validation.png) |

## 1. Phase-I 冻结与本机事件

采集前记录了 116 个 Phase-I 文件的 SHA-256 和 Git commit；结束后逐一复核，全部未变。[冻结记录](preparation/phase1-frozen.json)和[最终验证](preparation/post-run-validation.json)保留了证据。补充对照用的 latency/inclusion 文件也与采集前的 Git commit 一致。

本机为 Intel Core i7-6700。使用本机 `perf list --details`，再做权限和调度探测；没有直接假定 Artemisia 的事件一定适用。本机编码复核后恰好与原配置相同。[正式事件清单](../../events/results/charnwood/discovery02/EVENTS.md)包含 271 个解析条目，17 个单项/组合探测均可计数。

| 事件 | Raw config | 本次用途 |
|---|---|---|
| `mem_load_retired.l1_miss` | `0x08d1` | 判断 L1 miss 的转折 |
| `mem_load_retired.l2_miss` | `0x10d1` | 判断 L2 miss 的转折 |
| `mem_load_retired.l3_miss` | `0x20d1` | 判断 LLC miss 的转折 |
| `mem_inst_retired.all_loads` | `0x81d0` | 记录循环内总 retired-load 数量及辅助访问开销 |

计数范围为调用线程的 user-mode 采样循环；排除初始化、预热和结果写盘，包含循环/计时辅助访问。表中的 miss 数均按每 1,000 次已知 pointer-chain load 归一化，不是精确的目标 eviction probability。L3 miss 也不能单独证明由本地 DRAM 服务。本任务沿用 Artemisia 的四事件验证；截图提及可拆分八事件并不要求把独立的 Section 8.4 八事件研究加入本次运行。

## 2. Timing、PMU 与系统/文献对照

本表保留原 timing 推断，单列不同意之处。系统信息在 Phase-I 冻结后读取；未根据厂商参数重选 Phase-I 的 associativity candidate。容量以二进制 KiB/MiB 表示。

| 项目 | Timing Inference | PMU Evidence | Published/System Value | Source/Page | Error/Agreement |
|---|---|---|---|---|---|
| L1D capacity | 约 32 KiB；原 32–36 KiB onset | 32/36 KiB 的 L1 miss 为 916.03/992.67，已大量 miss；32 KiB 同时遇到 98.89% SMT sibling activity | 32 KiB | [本机 sysfs](preparation/system-cache-geometry.json)，CPU 3/4 index0；Agner Table 11.2, p.160 | 原名义估计误差 0%；本次 PMU 未独立复现干净的 L1 onset |
| L2 capacity | 约 256 KiB；256–288 KiB onset | 256→288 KiB：L2 miss 12.61→289.58，时间 11.35→17.74 ticks/load | 256 KiB | [sysfs](preparation/system-cache-geometry.json)，index2；[CPUID leaf 4](preparation/cpuid-cache.txt) | 名义估计误差 0%；PMU 支持原 onset 区间 |
| LLC capacity | 有效过渡宽，约 4–8 MiB；未确定精确物理大小 | 4/5/6/7/8 MiB 的 L3 miss 为 2.34/5.48/23.06/131.73/495.80；本次主要增幅在 6–8 MiB | 8 MiB | [sysfs](preparation/system-cache-geometry.json)，index3；[Intel i7-6700 规格](https://www.intel.com/content/www/us/en/products/sku/88196/intel-core-i76700-processor-8m-cache-up-to-4-00-ghz/specifications.html) | 有效过渡与 8 MiB 物理容量相容；原区间不是物理容量置信区间，不能计算唯一百分比误差 |
| Line size | 64 B candidate；56→64 B 时间上升 | offset 0/16 的 L1 miss 分别 230.98→318.75 / 228.84→312.61；72/96 B 后仍会增加 | L1D/L2/L3 均 64 B | [sysfs](preparation/system-cache-geometry.json)，`coherency_line_size`；Agner Table 11.2, p.160 | 64 B 名义估计误差 0%；PMU 与空间复用相容，但非唯一、独立的各层 line-size 证明 |
| L1 associativity | 4 KiB spacing，K=8→9，推断 8 ways | L1 miss 2.82→978.37；L2 miss 0.010→0.011 | 8 ways | [sysfs](preparation/system-cache-geometry.json)，index0；Agner Table 11.2, p.160 | 同意，0% |
| L2 associativity | 原选 16 KiB spacing、candidate sets=256；把 K=8→9 判为 8 ways | K=8→9 的 L1 miss 1.98→980.38，L2 miss 0.009→0.013；K=16/17/18 的 L2 miss 才达到 0.245/181.70/296.24 | 4 ways，1,024 sets | [sysfs](preparation/system-cache-geometry.json)，index2；[Agner 的 Skylake 实测说明](https://agner.org/optimize/blog/read.php?i=415)，2015-12-26 | 原 8-way 估计比系统值高 100%；原跳变属于 L1。新的 K≈16 有效阈值也不能直接写成 L2 有 16 ways |
| Derived sets | L1：32 KiB/(8×64 B)=64；按原 L2 推断：256 KiB/(8×64 B)=512；实际旧 candidate 参数却为 256 | PMU 显示原 L2-way 归属错误；没有单独遍历并识别全部物理 sets | L1D 64；L2 1,024；LLC 8,192 | [sysfs](preparation/system-cache-geometry.json)、[CPUID](preparation/cpuid-cache.txt) | L1 相符；原 L2 算术推导值低 50%，candidate 参数低 75%；两者都不应当作已验证 sets |
| Hit latency | 既有 `latency03`：L1 5.281；L2 15.398–15.406；LLC 43.398–45.430 TSC ticks/load | 本次是三个代表性工作负载的 timing+PMU；没有重跑 latency 分类或逐样本标记服务层级 | Agner Skylake 表列 L1 4、L2 14、L3 34–85 clocks，含多个型号 | [原 latency 报告](../../../timing-only/latency/results/charnwood/latency03/RUN_NOTES.md)；Agner Table 11.2, p.160 | TSC ticks 未校准为 core cycles，循环/计时开销也不同；不计算数值误差，不声称 latency 已经 PMU 逐类验证 |
| Sharing scope | 旧 line/associativity pinning manifest 曾误写无 SMT sibling；本次三实验未独立推断 sharing scope | 单线程 counter scope 不能证明 cache sharing | CPU 3 与 7、CPU 4 与 0 各共享本核 L1/L2；L3 共享 CPU 0–7 | [sysfs](preparation/system-cache-geometry.json)、[CPU 拓扑](preparation/cpu-topology.txt)；Agner p.160 | 修正元数据解释；原 Phase-I 文件保持不变 |
| LLC inclusion | 既有 inclusion report 称 non-inclusive / exclusive-like，inner copy 存活约 92.77% | 本次未运行 inclusion PMU；capacity/stride/conflict 计数不能单独确认 back-invalidation | 本机 CPUID leaf 4 subleaf3：EDX=`0x6`，bit1=1，报告 LLC inclusive；L2 bit1=0 不等于 exclusive | [原 inclusion report](../../../timing-only/inclusion/data/charnwood/raw_data_inclusion/charnwood/inclusion_report.json)；[CPUID 输出](preparation/cpuid-cache.txt)；[Intel SDM](https://cdrdv2-public.intel.com/868137/325462-089-sdm-vol-1-2abcd-3abcd-4.pdf)，Vol.1 Table 21-14，EDX[1] | 不同意旧 inclusion verdict。原报告全部 40,000 trials 均标注可能 L2 contamination，且没有证明 target 真正从 LLC eviction；inner copy 存活不足以排除 inclusive |

Agner 参考为 [The microarchitecture of Intel, AMD, and VIA CPUs](https://www.agner.org/optimize/microarchitecture.pdf)，2026-05-23 版本，§11.12、Table 11.2、印刷 p.160（PDF 第 160 页），访问日期 2026-09-14。该表涵盖多个 Skylake 型号，故本机精确容量和 ways 以本机 sysfs/CPUID 为型号对应证据，不套用 Skylake-X/server 的组织。

## 3. 不一致与解释边界

**L2 associativity 的原归属错误是本次最明确的发现。** 两种候选 spacing 在 K=8→9 都产生大量 L1 miss，L2 miss 几乎不动。16 KiB spacing 的后续 K=16→17 才产生 L2 miss。结合系统报告的 1,024 sets、64 B line，在简单 set-index 模型下，16 KiB 间隔可轮转四个 L2 sets，四路乘四 sets 可产生约 16 条地址的有效容纳阈值。这是结合系统数据的解释，并非本实验独立恢复了物理地址映射。

**Capacity 的绝对时间和 LLC 过渡位置没有精确重现 Phase I。** 当前 32 KiB 与 40 KiB 点的 SMT sibling CPU 7 busy 接近 99%；32 KiB 的 miss 已很高，不能把本次曲线当作干净的 L1-capacity 复测。LLC 从原较早且更慢的过渡，变为本次 6–8 MiB 的主要增幅。CPU 频率、共享缓存/内存负载、计数代码的辅助访问和进程状态均可能影响结果，未分别隔离其因果贡献。保留全部样本和差异，没有通过筛选测点来强行获得一致结论。

**Line-size 的 PMU 证据是有限支持。** 64 B stride 下，顺序访问、随机窗口、完全随机的 L1 miss 分别为 33.16、318.75、983.74。窗口内仍顺序访问，未关闭预取器；因此不能把窗口实验描述为已经消除了预取。56→64 B 的转折与 64 B 空间复用相容，但 72/96 B 的 miss 仍增加，不能宣称获得了理想的 64 B 饱和平台。

## 4. 运行质量与复现

| 实验 | 测量 minor / major faults | involuntary switches | 最大 sibling busy | 最大十段 median max/min |
|---|---|---|---|---|
| capacity03 | 2 / 0 | 207 | 98.925% | 1.258 |
| line_size01 | 1 / 0 | 237 | 13.758% | 1.100 |
| associativity01 | 0 / 0 | 55 | 14.634% | 1.368 |

容量工作映射在测量前后均通过完整 THP 校验；line_size 为 base pages；associativity 每点前后均报告 2 MiB THP。所有四事件组完整调度，原始样本长度、正值、SHA-256 和重算统计通过校验；这不等于独占机器或无噪声保证。

`capacity01`、`capacity02` 都在首个测点的大页分配阶段失败，没有正式样本，已保留。正式 `capacity03` 保留相同 C 测时内核、工作负载、绑定和大页要求；启动时使用 allocator 环境设置，并允许仅对采样前的分配失败进行有限重试。实际成功运行的 14 点均第一次分配成功，没有发生点内重试，不能将成功归因于某一设置。

完整命令、软件版本、源代码快照、失败记录和校验见[准备与复现记录](preparation/README.md)。
