# Ookay — Section 8.3 PMU verification

2026-09-14，在 `ookay.ece.ncsu.edu` 上按 Artemisia 的 PMU 流程依次完成 capacity、line/stride、associativity；随后补查相联度，并完整重复一次 line/stride 稳定性检查。**59 个配置运行，每个 1,000,000 个 workload repetitions，共 59,000,000 个原始计时间隔。** 每次 repetition 是原实验的一批依赖加载，不是单次 load。

PMU 支持 L1D 约 32 KiB、L2 约 256 KiB 的容量边界，以及 L1 的 8 路冲突阈值。原先标为 L2 的 8→9 地址跳变实际主要来自 **L1 miss**。LLC 的旧 timing 跳变未完整重现；line/stride 结果与 64 B 候选相容，但不足以仅凭 PMU 唯一确定物理 line size。以下保留这些限制，不把系统规格当成独立实验推断。

## 采集顺序与证据

| 顺序 | Run | 配置 / repetitions | CPU / NUMA | 用途 |
|---|---|---|---|---|
| 1 | [capacity01](../../capacity/results/ookay/capacity01/RUN_NOTES.md) | 14 / 14 M | 2 / 0 | L1、L2、LLC 原边界附近 |
| 2 | [line_size01](../../line_size/results/ookay/line_size01/RUN_NOTES.md) | 12 / 12 M | 4 / 0 | 原 stride、offset、traversal controls |
| 3 | [associativity01](../../associativity/results/ookay/associativity01/RUN_NOTES.md) | 12 / 12 M | 4 / 0 | 原候选冲突布局；含 K=17、18 扩展 |
| 4 | [associativity02](../../associativity/results/ookay/associativity02/RUN_NOTES.md) | 9 / 9 M | 4 / 0 | Phase-I 已测过的 512 / 1024 candidate sets |
| 5 | [line_size02](../../line_size/results/ookay/line_size02/RUN_NOTES.md) | 12 / 12 M | 4 / 0 | 因第一轮时间波动，原参数完整重复 |

表中相对路径均指向各实验的结果；[总审计 JSON](verification_summary.json)保存准确 UTC 起止、样本数、质量指标和串行顺序检查。[对照表 CSV](comparison.csv)可直接用于后续报告。每个 run 的 `data/ookay/<run>/` 保存 gzip 原始 uint64 ticks、原始 PMU JSON、完整命令、有效 config、build log、环境和映射日志；`results/` 保存全量统计、PMU CSV、分段中位数、PNG/PDF 图及校验结果。未删除 outliers，也未拼接两次 line/stride 中较好的单点。

**冻结顺序：** 15:29:32 UTC 先保存 [Phase-I freeze](phase1-freeze01/manifest.json)，包含 18 份已有汇总/推断文件及 SHA-256；之后才发现 PMU 事件、查询系统几何参数和文献。最终审计同时检查副本及原文件哈希。已有 Phase-I 和 Artemisia 数据保持原样。该冻结是本次任务单独建立的 checkpoint，普通 runner 本身仍不自动创建冻结。

## 1. 本机事件发现与计数范围

本机的 [discovery02 inventory](../../events/results/ookay/discovery02/EVENTS.md) 解析了 270 个 cache/virtual-memory 相关条目，16 个单事件及一个四事件 group 的访问/调度探测全部成功。完整 `perf list`、`perf list --details`、probe 输出在 [events data](../../events/data/ookay/discovery02/)。`discovery01` 的原始输出也保留；其 CSV 编码列未识别本机 `default_core/` 前缀，修正解析器兼容 `cpu/` 和 `default_core/` 后以 discovery02 为准。

| 实际采集事件 | 本机验证的 raw config | 含义 |
|---|---|---|
| `mem_load_retired.l1_miss` | `0x08d1` | retired loads 的 L1 misses |
| `mem_load_retired.l2_miss` | `0x10d1` | retired loads 的 L2 misses |
| `mem_load_retired.l3_miss` | `0x20d1` | retired loads 的 L3 misses |
| `mem_inst_retired.all_loads` | `0x81d0` | retired loads 总量，揭示 helper 开销 |

这是本机实测可用事件，不假设不同处理器事件名称/编码相同。四事件通过 `perf_event_open` 按线程、user mode、pinned group 同时采集；所有点 `time_enabled == time_running > 0`，无需 multiplex scaling。计数覆盖整个百万次采样循环；初始化、warm-up、输出文件在计数窗口外。计数是每个配置的 aggregate totals，计时则逐 repetition 保存。Section 8.4 的八事件跨代研究不属于本次任务。

所有 miss 数均归一化为 **每 1,000 次已知 chain loads 的事件数**。capacity 分母为 `1e6*256`，line_size 为 `1e6*1024`；associativity 的原循环实际有 129 次 timed loads，另有 K−1 次 preparation loads，因此计时除以 129，PMU 分母为 `1e6*(K+128)`。旧 associativity summary 除以 128，比较图将旧值乘 128/129，原文件不修改。

PMU 还计入 helper/stack loads：capacity 的 all-loads 约为已知 chain 的 1.06 倍，两个 C++ `-O0` 实验约 5 倍。因此归一化结果不是精确 miss probability，也不能直接从 L3 miss 认定由本地 DRAM 服务。计时单位是 **TSC ticks / timed chain load**，包含原 timer/loop 开销，未经 core-cycle 校准。

## 2. PMU 与 timing 转换位置

### Capacity

保持原依赖随机链、64 B spacing、seed 59202、batch 256、CPU 2/node 0 和 huge-page 路径。14 点都在原 combined12 中有参数完全匹配的 baseline。

| 点 | PMU-run median (TSC ticks/load) | L1 misses / 1000 | L2 misses / 1000 | L3 misses / 1000 |
|---|---:|---:|---:|---:|
| 32 KiB | 3.852 | 39.573 | 0.008 | 0.003 |
| 36 KiB | 10.422 | 994.720 | 0.017 | 0.012 |
| 256 KiB | 10.602 | 1000.277 | 10.131 | 0.014 |
| 288 KiB | 16.750 | 1000.442 | 285.726 | 0.010 |
| 4 MiB | 32.000 | — | 972.885 | 0.174 |
| 5 MiB | 32.109 | — | — | 1.013 |
| 6 MiB | 32.195 | — | — | 4.735 |
| 7 MiB | 32.297 | — | — | 7.980 |
| 8 MiB | 39.094 | — | — | 77.267 |

32→36 KiB 的 timing 增长伴随 L1 miss 急增；256→288 KiB 的增长伴随 L2 miss 急增，分别支持原 L1/L2 边界。完整数字见 [capacity summary](../../capacity/results/ookay/capacity01/summary.csv)。

LLC 与冻结数据存在明显分歧：原 7 / 8 MiB median 约 113.336 / 170.586，本次为 32.297 / 39.094。L3 misses 随 working set 增大，但没有建立完整的 miss plateau；不能声称复现了旧 5–8 MiB 的强烈转换或仅凭这些点测准物理容量。先前共享机器负载与现在不同，shared LLC occupancy、替换、输出缓冲占用等是可能解释，当前数据不能分离各因素的因果贡献。

### Line / stride

保持 256 KiB footprint、512 B grouping window、batch 1024、warm-up 1000、原四组 seeds，以及 CPU 4/node 0。窗口大小只是 traversal 参数。选点与 Artemisia 相同：random offset 0 的 32/56/64/72/96 B、offset 16 的 56/64/72 B、sequential 56/64/72 B 和 fully-random 64 B。

第一轮 random offset 0 的 median 随上述 stride 为 9.215、13.230、15.152、15.145、14.961；对应 L1 misses 为 100.345、228.629、318.877、341.688、472.461。计时在约 64 B 后趋平，但 miss 曲线仍继续增加，不能把它写成干净的 64 B miss 饱和点。64 B 下 sequential / random-window / fully-random 的 L1 misses 分别为 33.379 / 318.877 / 983.017，说明访问顺序显著影响结果。第二轮相同 stride 的 median 为 8.818、13.926、14.625、15.402、16.180，L1 misses 为 91.059、238.860、313.086、341.043、458.381：miss 上升趋势重现，64 B 之后的 timing 平台不够稳定。第二轮 64 B 的 sequential / random-window / fully-random L1 misses 为 66.825 / 313.086 / 1000.727，访问顺序的影响也重现。

与 Artemisia 相同的 256 KiB 工作集在 Ookay 恰好接近 L2 容量边界，因此 fully-random 第一轮还有约 404.288 次 L2 misses / 1000；不能沿用“大于 L1、完全驻留 L2”的解释。空间复用、prefetch、映射和 helper 污染可能共同影响曲线，本实验没有分别禁用/隔离它们。64 B 是有 timing 支持且与系统值一致的候选；本次计数不足以独立验证每一级 cache 的 line size。

### Associativity

保持原 shuffle、seed 701、warm-up、CPU 4/node 0 与 huge-page 路径。初次验证的候选间隔为 4 KiB 和 16 KiB，后者来自原选中的 `num_sets=256`，没有套用 Artemisia 的 128 KiB。

| 地址间隔 | K 转换 | L1 misses / 1000 | L2 misses / 1000 | 解释 |
|---|---|---|---|---|
| 4 KiB | 8→9 | 0.721→982.114 | 近零 | 支持 L1 的 8 地址阈值 |
| 16 KiB | 8→9 | 0.540→981.984 | 0.0019→0.0132 | 原 L2 标签实际是 L1 转换 |
| 16 KiB | 16→17→18 | 871.849→976.393→976.715 | 0.282→182.985→298.184 | 布局的后续 L2 压力，不能等同物理 16 路 |
| 32 KiB | 8→9→10 | 1.952→285.863→924.436 | 0.124→94.730→510.175 | 更大间隔带来更早 L2 压力 |
| 64 KiB | 4→5 | 0.0085→0.0317 | 0.0066→0.0167 | 仍命中 L1，L2 的阈值被遮蔽 |
| 64 KiB | 8→9→10 | 0.777→120.939→856.954 | 0.499→119.959→856.759 | L1 容不下后才显露大量 L2 misses |

associativity02 的 9 个点均有 Phase-I 512/1024 candidate-set baseline；它是在初次 PMU 和系统查询后选择的验证补查，不属于盲测 Phase I。K=17/18 是初次验证中的两个新扩展，没有原 baseline。

结合系统报告的 L2 1024 sets、4 ways，在简单 set-index 模型中，16/32/64 KiB stride 分别循环访问 4/2/1 个 L2 sets。16 KiB 布局的约 16 地址有效阈值与 `4 sets * 4 ways` 相容，但 PMU 本身没有直接给出所有物理 set 的映射证明。64 KiB 下 K=4→5 仍由 L1 服务，因此同一 workload 不能干净显露物理 4 路 L2 阈值。原 timing 的“8 路 L2”不成立，另两种候选的“9 路”也不能当作物理 ways。

## 3. Timing / PMU / Published-System 对照

系统值取自冻结后保存的 [sysfs cache organization](system-reference01/sysfs-cache-organization.json) 与 [CPUID leaf 4](system-reference01/cpuid-leaf4.json)，不是 Phase-I 输入。处理器为 Intel Core i7-7700；Intel 的 [SKU specifications](https://www.intel.com/content/www/us/en/products/sku/97128/intel-core-i77700-processor-8m-cache-up-to-4-20-ghz/specifications.html)确认 Kaby Lake、4 cores/8 threads 和 8 MB Smart Cache。

Agner Fog 的 [The microarchitecture of Intel, AMD, and VIA CPUs](https://www.agner.org/optimize/microarchitecture.pdf)（2026-05-23 版）p.152 的第 11 章覆盖 Kaby Lake；p.160 §11.12 Table 11.2 提供相关架构族的缓存/延迟参考。该表 L2/LLC 是架构族范围，精确 SKU 值以本机记录为准。以下 “Agner p.160” 均指该表。

| Property | Timing Inference | PMU Evidence | Published/System Value | Source/Page | Error/Agreement |
|---|---|---|---|---|---|
| L1D capacity | 约 32 KiB | 32→36 KiB 的 L1 misses 急增 | 32 KiB | [sysfs](system-reference01/sysfs-cache-organization.json), index0；[Agner](https://www.agner.org/optimize/microarchitecture.pdf), p.160 | 一致；点估计相对系统值 0%，扫描分辨率仍有限 |
| L2 capacity | 约 256 KiB | 256→288 KiB 的 L2 misses 急增 | 256 KiB | [sysfs](system-reference01/sysfs-cache-organization.json), index2；[CPUID](system-reference01/cpuid-leaf4.json), subleaf2 | 一致；点估计误差 0%，不是精确逐字节边界 |
| LLC capacity | 有效转换约 5–8 MiB | L3 misses 增加，原强 timing 跳变未重现 | 8 MiB | [sysfs](system-reference01/sysfs-cache-organization.json), index3；[Intel SKU](https://www.intel.com/content/www/us/en/products/sku/97128/intel-core-i77700-processor-8m-cache-up-to-4-20-ghz/specifications.html), Cache | 物理值位于原区间上端；有效区间相对物理值 −37.5% 至 0%，二者不可直接等同 |
| L1D ways | 8 | 4 KiB 间隔 K8→9 的 L1 miss 急增 | 8 | [sysfs](system-reference01/sysfs-cache-organization.json), index0；[Agner](https://www.agner.org/optimize/microarchitecture.pdf), p.160 | 一致，ways 误差 0% |
| L2 ways | 原 selected candidate 推断 8；其他候选 9 | 原 8→9 是 L1；大 stride 补查也受 L1 遮蔽 | 4 | [sysfs](system-reference01/sysfs-cache-organization.json), index2；[CPUID](system-reference01/cpuid-leaf4.json), subleaf2 | 原 selected ways 高估 100%；9 路高估 125%；PMU 未独立直接测出 4 |
| LLC ways | 未得到可信 timing 推断 | 未开展 LLC associativity PMU sweep | 16 | [sysfs](system-reference01/sysfs-cache-organization.json), index3 | 仅系统参考，实验未验证 |
| Derived sets | L1: 32768/(8*64)=64；L2: 262144/(8*64)=512，与原选中 candidate256 本身不一致 | PMU 否定将 candidate stride 当成真实 L2 set 数 | L1D 64；L2 1024；LLC 8192 | [sysfs](system-reference01/sysfs-cache-organization.json)；[CPUID](system-reference01/cpuid-leaf4.json) | L1 一致；旧 L2 derived512 低估 50%，candidate256 低估 75%；LLC 无独立 timing 推断 |
| Line size | stride 曲线的约 64 B 候选 | 趋势与候选相容，miss 无唯一饱和点，controls 差异大 | 各级 64 B | [sysfs](system-reference01/sysfs-cache-organization.json)；[Agner](https://www.agner.org/optimize/microarchitecture.pdf), p.160 | 候选数值误差 0%；PMU 证据部分支持，不构成逐级独立验证 |
| L1 hit latency | 冻结 latency median 3.672 TSC ticks/load | capacity 小工作集 3.852；不同 workload | 参考 latency 4 core clocks | [Agner](https://www.agner.org/optimize/microarchitecture.pdf), p.160；冻结 latency_estimates.json | 单位/开销不同，不计算百分比误差 |
| L2 hit / L1 miss-next latency | 10.711–10.719 TSC ticks/load | capacity L1 溢出时约 10.42–10.60，L2 misses 较低 | 参考 latency 14 core clocks | [Agner](https://www.agner.org/optimize/microarchitecture.pdf), p.160；冻结 latency_estimates.json | 层级关系相容，未经 core-cycle 校准 |
| LLC hit / L2 miss-next latency | 30.883–32.391 TSC ticks/load | 4 MiB median 32.000，L2 misses 高、L3 misses 低 | 架构族参考 34–85 core clocks | [Agner](https://www.agner.org/optimize/microarchitecture.pdf), p.160；冻结 latency_estimates.json | 支持该工作集以 LLC 服务为主；不能用不同单位算误差 |
| Sharing scope | 容量/单线程 latency 未独立定位；旧 CPU4 manifest 错写无 SMT sibling | 记录到 CPU0 的 sibling 活动；未做 sharing sweep | L1/L2 按 core 共享给 SMT pair；L3 shared CPUs0–7 | [sysfs](system-reference01/sysfs-cache-organization.json), shared_cpu_list | CPU4 的 sibling 是 CPU0，CPU2 的是 CPU6；旧 placement 文字不正确 |
| Inclusion / exclusion | 原报告 NON-INCLUSIVE / exclusive-like | 本次未采 inclusion PMU；旧实验未证明 LLC target eviction | L3 CPUID EDX=6，bit1=1：inclusive of lower levels | [CPUID](system-reference01/cpuid-leaf4.json), subleaf3；[Intel CPUID reference](https://cdrdv2-public.intel.com/671368/architecture-instruction-set-extensions-programming-reference.pdf), Table1-3 p.1-5 | 原 verdict 与系统报告矛盾；不能据此认定 exclusive |
| L1 instruction cache | 数据依赖链未测 instruction capacity | 无指令缓存 PMU 验证 | 32 KiB、8 ways、64 sets、64 B | [sysfs](system-reference01/sysfs-cache-organization.json), index1 | 仅列参考，避免把 data-cache 结果套到 instruction cache |

## 4. 分歧、质量与可比较性

**LLC inclusion 分歧：** 原 inclusion 报告用 stride 256 B、K=32 的 pressure，地址跨度约 8 KiB，且全部 40,000 trials 被其自身标为 possibly L2 contaminated。它没有证明目标 LLC 副本被逐出；观察内层副本仍在，不能推出 exclusive/non-inclusive。CPUID leaf4 subleaf3 的 EDX=6 还设置 bit2，报告 complex cache indexing，简单 stride 不能直接当成 LLC congruent-set 证明。bit1/bit2 的解释来自 Intel [CPUID Table 1-3, p.1-5](https://cdrdv2-public.intel.com/671368/architecture-instruction-set-extensions-programming-reference.pdf)。本次记录矛盾，未额外声称完成 inclusion PMU 实验。

**稳定性：** 原始数据完整性通过与无干扰不是同一件事。capacity 的最差十段 median max/min 为 1.0391（8 MiB）；associativity01 为 1.0064，followup 为 1.0107。line_size01 的 random 32 B 为 1.1658，同期 SMT sibling 忙碌度 18.91%；还有 25 次 minor faults，未出现 major faults。line_size02 的 32 B 点降至 1.0033，但 random 56/72 B 分别达到 1.2053/1.2116，最高 sibling activity 为 31.99%，另有 31 次 minor faults。因此补跑也不是无干扰基准；两轮均完整保留、分别分析，不继续选择性重测直到得到预期平台。全部五轮均无 major faults。每轮详细质量见 RUN_NOTES 和 quality.json，不将 integrity passed 当成无噪声保证。

**页面与放置：** capacity 验证 full huge-page backing，两个 associativity runs 的工作映射在测前/后均为 2 MiB THP；line_size 使用 base pages。collector 绑定 CPU1，worker 分别使用 CPU2 或 CPU4，保持 Ookay 原实验 CPU/node。未改变 governor、Turbo、prefetch、THP 全局配置或 perf 权限，也未停止其他用户进程；共享缓存和 OS 活动仍可能影响实验。

**同 workload 的具体边界：** 重用 Artemisia PMU kernels；此次只增加 Ookay configs，修正本机 event 编码解析和图标题/地址间隔，以及让已有硬件检查选择本机配置。capacity 的 timed assembly 和 chain 构造不变。line_size/associativity 沿用此前 PMU 版的 prefaulted binary-output buffer，把原 Phase-I 循环内 CSV 输出移到计数之后；line_size 使用原 PMU 版 `posix_memalign`；associativity 为单 K 进程并修正 128/129 divisor。这些保留依赖链、timer 和顺序算法，但编译后 stack layout、输出行为可改变绝对 timing，不能声称 bit-for-bit Phase-I replay。

已有 10 项功能检查（包括本机 kernel/counter smoke checks）通过，日志在 [preparation](preparation/)。五轮分析均从 raw 重新计算统计并检查 hash、长度、actual-load 分母和 PMU 调度。最终 [reproduction archive](reproduction01/manifest.json)保存本次 source、binary/disassembly 的事后副本与哈希；这些 binary hashes 是采集之后记录，不能当成采集前 provenance。每轮配置和命令仍以 run data 为准。

## 复跑

在 `PMU-verification/` 下，使用已有环境 `../timing-only/capacity/.venv/bin/python`，逐条执行，每次 collection 必须选择新的 run ID：

```bash
taskset -c 1 ../timing-only/capacity/.venv/bin/python capacity/scripts/run_capacity.py --machine ookay --run-id capacity02
taskset -c 1 ../timing-only/capacity/.venv/bin/python capacity/scripts/analyze_capacity.py --machine ookay --run-id capacity02
taskset -c 1 ../timing-only/capacity/.venv/bin/python line_size/scripts/run_line_size.py --machine ookay --run-id line_size03
taskset -c 1 ../timing-only/capacity/.venv/bin/python line_size/scripts/analyze_line_size.py --machine ookay --run-id line_size03
taskset -c 1 ../timing-only/capacity/.venv/bin/python associativity/scripts/run_associativity.py --machine ookay --run-id associativity03
taskset -c 1 ../timing-only/capacity/.venv/bin/python associativity/scripts/analyze_associativity.py --machine ookay --run-id associativity03
```

若重复 supplemental layout，collection 加 `--config associativity/configs/ookay-followup.json` 并另选 run ID。在当前保存结果上执行 `python3 results/ookay/finalize_results.py` 可重建总审计、事后 reproduction archive 和 comparison.csv，不重新采集 PMU。
