# Sunbird：Section 8.3 PMU 验证记录

已按 **capacity → line_size → associativity** 串行完成三项实验，并生成各项统计、PMU 计数、PNG/PDF 图和验证记录。38 个不同工作负载各运行两个事件组，共 **76 次采集、7600 万批次**；每次均保留 100 万批次原始时间值。未合并不同事件组的时间分布，未删除异常值。正式采集均首次完成，无正式重跑。

| 实验 | Run ID | 不同工作负载 | 事件组运行数 | 保存批次 | Collector 耗时 |
|---|---|---:|---:|---:|---:|
| [capacity](../../../capacity/results/sunbird/capacity01/RUN_NOTES.md) | capacity01 | 14 | 28 | 28,000,000 | 260.79 s |
| [line_size](../../../line_size/results/sunbird/line_size01/RUN_NOTES.md) | line_size01 | 12 | 24 | 24,000,000 | 233.63 s |
| [associativity](../../../associativity/results/sunbird/associativity01/RUN_NOTES.md) | associativity01 | 12 | 24 | 24,000,000 | 59.17 s |

正式采集起止为 2026-09-14 **15:42:50–15:52:45 UTC**（Sunbird 当地 11:42:50–11:52:45 EDT），含各实验之间的分析间隔。原始 uint64 载荷共 608,000,000 bytes，gzip 共 79,866,562 bytes。详细时间与审计见 [run_summary.json](run_summary.json)。

## Phase-I 冻结与本机事件

在本轮首次 PMU 探测前，于 **15:30:00 UTC** 建立了 [Phase-I 冻结记录](../../../phase1-freeze/sunbird/freeze01/README.md)，锚定原有干净 Git 版本 `f86eecbb6fce590f3d40b64487620888b33dcd93`。769 个文件有 SHA256 记录，其中 694 个较小文件另有完整快照；大文件保留在原路径和对应 Git 版本。本次比较从冻结的统计读取，最后核对全部原文件及快照均未变化。

**此前 capacity 任务曾查看 `lscpu` 缓存规格，整个研究过程不能描述为盲测。** 本轮在冻结后读取本机 perf 事件；新的 sysfs 缓存规格采集时间为 15:43:08 UTC，随后查阅系统/Intel/Agner Fog 资料用于 Phase II 对照。没有根据这些规格改写冻结的 Phase-I 结论。

[本机事件清单](../../../events/results/sunbird/discovery01/EVENTS.md)保留完整 `perf list`/`--details`、事件描述、编码和探测输出。16 个单事件探测可用；原四事件组以及三 miss 事件组无法调度。按题目允许的相同负载分次采集方式，改成：

| Pass | 实际采集事件 | Raw config |
|---|---|---|
| `l1_l2` | `mem_load_uops_retired.l1_miss`、`mem_load_uops_retired.l2_miss` | `0x08d1`、`0x10d1` |
| `l3_loads` | `mem_load_uops_retired.l3_miss`、`mem_uops_retired.all_loads` | `0x20d1`、`0x81d0` |

每次单独启用两个 pinned counters，76 次全部满足 `time_enabled_ns == time_running_ns > 0`。四事件组失败的原始证据仍保留，未用缩放后的复用计数代替。事件含义是 retired load **uops**；沿用其他机器事件名并不可靠。本机 perf 描述中的 errata 提示也保留在清单。`perf list` 同时报 tracing 目录权限错误，但硬件事件枚举和用户态计数可用；没有调整 `perf_event_paranoid=2` 或系统权限。

## Timing / PMU / 系统及文献对照

计数均为每 1000 次已知链式读取的事件数，包含测量循环内的辅助读取，因此不是严格 miss probability。下面的时间单位是 **TSC ticks / timed dependent load**，没有转换为瞬时 core cycles。

| Property | Timing Inference | PMU Evidence | Published/System Value | Source/Page | Error/Agreement |
|---|---|---|---|---|---|
| L1D capacity | 约 32 KiB；原转折 32–36 KiB | 32→36 KiB：L1 miss 54.40→940.85 /1000；median 4.594→11.688 | 32 KiB | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 约值相符（32 KiB 对 32 KiB，0%）；测点间分辨率仍为 4 KiB |
| L2 capacity | 约 256 KiB；原转折 256–288 KiB | 256→288 KiB：L2 miss 25.77→993.77 /1000；median 12.578→41.625 | 256 KiB | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 约值相符（0%）；测点间分辨率 32 KiB |
| LLC capacity | 有效转折宽区间 16–64 MiB；未给物理容量点估计 | 16→28 MiB：L3 miss 0.743→986.460 /1000；本次转折提前 | 30 MiB/socket；Intel 写作 30 MB Smart Cache | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Intel E5-2680 v3, CPU Specifications](https://www.intel.com/content/www/us/en/products/sku/81908/intel-xeon-processor-e52680-v3-30m-cache-2-50-ghz/specifications.html) | 不能计算物理容量推断误差；28 MiB 的旧 median 49.953，本次 201.844，存在明显运行条件差异 |
| Line size | 原 stride 曲线在约 64 B 附近转缓 | 随机窗口 stride 32/56/64/72/96 的 L1 miss 为 81.94/230.82/267.65/281.03/372.41 /1000；未形成清晰平台 | L1D/L2/L3 均 64 B | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 64 B 候选与系统相符；PMU 只提供部分支持，不能独立精确确认各层 line size |
| L1D associativity | 冻结自动结果：9 ways；candidate_sets=64 | 4 KiB 间距：K=8/9/10 的 L1 miss 为 0.639/429.279/942.295；L2 miss 很低 | 8 ways | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 原 9 ways 高估 1 way（+12.5%）；PMU 支持测试布局下 8 ways 的冲突起点 |
| L2 associativity | 冻结自动结果：8 ways；candidate_sets=512 | 32 KiB 间距：K=8/9/10 的 L2 miss 为 0.062/813.244/942.035 | 8 ways | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 与 8 ways 相符（0%）；不等于验证所有物理 set 和替换状态 |
| L1D / L2 sets | 候选参数 64 / 512；L1 的 32KiB/(9×64B)=56.9，显示冻结推断内部不一致 | 按本次支持的 8 ways 及 64 B 候选，C/(A×B) 得 64 / 512 | 64 / 512 | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 推导值相符；sets 来自联合推导，未独立恢复物理索引函数 |
| LLC ways / sets | 没有可信的 timing-only 推断 | 本次 capacity sweep 不测 LLC associativity | 20 ways / 24576 aggregate sets | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json) | 未验证；Agner 泛化表的 LLC 12–16 ways 不适用于本机 sysfs 的 20 ways，不能直接套用 |
| Sharing scope | 没有独立跨核共享范围实验 | 本次固定 CPU 32，不提供跨核归属证明 | L1D/L2：CPU 8,32；LLC：socket 0 的 24 个 logical CPUs | [本机 sysfs](../../data/sunbird/system01/cache-sysfs.json)；[Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | 系统报告已记录；未宣称由本次 PMU 独立证明 |
| Hit latency | 既有 latency01：L1 4.156，L2 12.141–12.156，LLC 41.703–41.734 TSC ticks/load | capacity 中的逐级 miss 上升支持层次归属；未逐访问验证旧 latency 数据 | Agner 参考 L1 4、L2 12、L3 34 clocks；非此 SKU 的保证值 | [Agner Fog, §10.11 / Table 10.2, p.147](https://www.agner.org/optimize/microarchitecture.pdf#page=147) | L1/L2 数值接近、LLC 较高；TSC ticks 未校准为 core cycles，不能当成严格百分比误差 |
| LLC inclusion | 旧 inclusion_report.json 判为 NON-INCLUSIVE / exclusive-like；40000 trials | 本次三个 PMU 实验没有验证目标行先被 LLC 驱逐 | Haswell/Broadwell server LLC 为 inclusive | [Intel LBR Blueprint, p.4 / Figure 2](https://cdrdv2-public.intel.com/671449/runtimeoptblueprint-dclo.pdf#page=4) | 旧判词与文献冲突；旧报告所有 40000 目标区域均标记可能 L2 污染，驱逐前提不足，结论待定 |

[comparison.csv](comparison.csv)保存同一张表。本机 CPU 型号为 Intel Xeon E5-2680 v3；cache size、ways、sets、line size 和共享 CPU 列表的原始路径均记录在 [cache-sysfs.json](../../data/sunbird/system01/cache-sysfs.json)。Agner 文档采用 **2026-05-23** 版，引用其 §10.11、Table 10.2、印刷/PDF 第 147 页；它是代际参考，不能替代本机具体 SKU 的 LLC 组织。两份引用 PDF、来源 URL、页码及哈希保存在 [references](../../data/sunbird/system01/references/sources.json)。

## 分歧与可比性

**Capacity：** L1 32–36 KiB、L2 256–288 KiB 的原始转折得到相应层 miss 的强支持。LLC 在本次 16–28 MiB 间已出现大幅 miss 上升，28 MiB 时间显著高于旧数据。同期多个同 socket CPU 持续忙碌，见 [活动快照](../../data/sunbird/system01/during-capacity-activity.json)。共享缓存压力、分配布局和运行状态可能影响有效转折，但没有隔离出唯一原因。不能将其标成“物理 LLC 只有 16 或 28 MiB”，也不能宣称旧 LLC 曲线完全复现。

**Line size：** 随机窗口的时间曲线与原约 64 B 转折相容，但 miss 曲线没有清晰平台，PMU 支持有限。64 B 时 sequential/random-window/fully-random 的 L1 miss 为 33.238/267.645/1000.837，访问顺序是强影响因素。完全随机点的两个事件组时间为 **25.1875 / 36.7227**，相差约 45.8%；不能用一次的计数给另一时间分布作逐访问标签，也没有把两次数据合并。所有点的两次中位数见 [paired_pass_medians.csv](paired_pass_medians.csv)。

**Associativity：** L1 的冻结自动规则选“最大 eviction-probability 跳跃”，得到 9 ways；PMU 显示 K=9 已有明显 L1 miss，因此更支持冲突起点对应的 8 ways。L2 的 32 KiB 间距同样在 K=9 有 L2 miss 上升，支持原 8 ways。此结论针对所测布局，未恢复所有物理 set 或替换策略。

Associativity 延用原 `mmap/MADV_HUGEPAGE` 策略，23 次实际为完整 2 MiB THP，**`L1_k9__l3_loads` 一次为 base pages**；同点的 `l1_l2` 为 THP。这对运行的实际页状态不同，已在配对表和原始映射日志标记，不能当作完全相同的内存实现。L1 冲突结论取自 THP 的 L1/L2 计数组。没有隐藏页状态或覆盖原始结果。

既有 inclusion 判词只用于本次文献比较；本次 capacity/stride/conflict 三类计数并不检验“目标行先从 LLC 被驱逐”的前提，因此不能修补该旧实验的因果证据。旧判词保留在冻结快照，表中明确其与 Intel 描述的冲突和未决状态。

## 运行质量与实现记录

全部正式测量绑定 **CPU 32 / NUMA node 0**。这与旧 capacity 相同；旧 line_size / associativity 的 pinning 文件记录 CPU 4/node 0，本次因 CPU 4 忙碌改用同 socket 的另一个物理核。实际 SMT sibling 是 CPU 8，三个实验的预检及每个 worker 期间均为 0% 记录平均忙碌率；没有申请独占 socket。

Capacity 使用完整 THP；line_size 使用 base pages。测量区累计 **164 次 involuntary context switches、3 次 minor faults、0 次 major faults**。3 次 minor faults 均在 `random_s56_a16__l1_l2`。Capacity 的 32 KiB L1/L2 pass 十段中位数 max/min 为 1.33562，其他实验没有超过 1.2 的分段标记。全部尾部与异常值均保留。

采集期间的会话工具没有与测量 socket 隔离；其中一次只读 Phase-I 哈希审计读取了原文件及快照，可能增加背景活动，详见 [auxiliary-activity.json](../../data/sunbird/system01/auxiliary-activity.json)。最终完整审计在所有测量结束后执行。结果因此应解释为共享机器条件下的证据，不能声称无干扰。

计时核心和指针排列沿用既有 PMU 程序。为 Sunbird 新增了配置、实际事件发现配置，以及支持 1–4 个事件的 PMU helper 和分次运行/分析逻辑；未修改定时读取内核。保留了原流程相对于 timing-only 的缓冲输出等差异。Associativity 每批实际计时 **129 次**读取，旧摘要的 `/128` 仅在比较显示时乘 `128/129` 修正；计数分母包含 K−1 次准备读取，为 `samples×(K+128)`。原 Phase-I 文件保持原样。

[采集前 PMU 实现快照](../../data/sunbird/source01/manifest.json)含 37 个源文件、配置、脚本、可执行文件及反汇编的哈希；结束后均匹配。[Capacity 六项测试](capacity-tests.txt)与[共享六项测试](verification-tests.txt)全部通过，包括三个实际内核的两组硬件计数 smoke test、分组映射/分母校验和冻结 baseline 匹配。三个分析器重新打开原始 gzip 数据，核对哈希、长度及统计；[最终审计](run_summary.json)另验证串行顺序、事件组覆盖和冻结原件/快照。审计通过表示数据完整，不表示各个缓存状态均已独立证明。

## 文件与复现

- [Capacity 报告、全点表和图](../../../capacity/results/sunbird/capacity01/RUN_NOTES.md)
- [Line-size 报告、全点表和图](../../../line_size/results/sunbird/line_size01/RUN_NOTES.md)
- [Associativity 报告、全点表和图](../../../associativity/results/sunbird/associativity01/RUN_NOTES.md)
- 原始数据分别位于对应 `data/sunbird/<run-id>/`，含有效配置、命令、环境、计数、日志、raw gzip、manifest；`*-console.txt` 保存串行控制台输出。

在 `PMU-verification` 目录中使用已复用的 Python 环境和本地 numactl：

```bash
export PATH="/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:/home/swu35/ECE592-HW1/timing-only/capacity/build/sunbird/deps/usr/bin:$PATH"
python capacity/scripts/analyze_capacity.py --machine sunbird --run-id capacity01
python line_size/scripts/analyze_line_size.py --machine sunbird --run-id line_size01
python associativity/scripts/analyze_associativity.py --machine sunbird --run-id associativity01
python common/audit_sunbird.py
```

实际采集命令依次是 `run_capacity.py`、`run_line_size.py`、`run_associativity.py`，参数分别为 `--machine sunbird --run-id capacity01/line_size01/associativity01`，详见各 manifest 的完整命令。未来重新采集必须使用新的 run ID，脚本会拒绝覆盖现有数据。Artemisia 原始配置及结果保持不变。
