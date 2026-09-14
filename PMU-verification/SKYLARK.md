# Skylark：Section 8.3 PMU 验证

已于 **2026-09-14** 在 Skylark 完成 capacity、line_size、associativity，按此顺序串行采集。共有 **14 + 12 + 12 = 38 个负载点**。每个点分别采集两组四事件，每组 **1,000,000 个 timed batches**，共 **76,000,000 个原始计时样本**、八个不同事件，所有计数均未 multiplex。两组采用完全相同的负载参数及 benchmark 二进制；计时分布分别保存，不混成一次实验的命中概率。

主要结论：容量证据支持 L1D 约 32 KiB、L2 约 512 KiB，以及 16–20 MiB 的 LLC 有效转换起点。L1 冲突边界支持 8 路；原 Phase-I 选择出的 **L2“11 路”不能成立为首个 miss 边界**，计数在 K=9 已增加，与系统的 8 路一致。64 B line-size 候选与系统值一致，但当前 stride PMU 曲线不足以独立、唯一确定 64 B。

## 结果入口

| 实验 | 分组 A / 分组 B | 综合图 | 八事件与原 timing 对照 |
|---|---|---|---|
| capacity | [capacity01](capacity/results/skylark/capacity01/) / [capacity02_refills](capacity/results/skylark/capacity02_refills/) | [PDF](skylark/results/capacity_combined.pdf) / [PNG](skylark/results/capacity_combined.png) | [CSV](skylark/results/capacity_eight_events.csv) |
| line_size | [line_size01](line_size/results/skylark/line_size01/) / [line_size02_refills](line_size/results/skylark/line_size02_refills/) | [PDF](skylark/results/line_size_combined.pdf) / [PNG](skylark/results/line_size_combined.png) | [CSV](skylark/results/line_size_eight_events.csv) |
| associativity | [associativity01](associativity/results/skylark/associativity01/) / [associativity02_refills](associativity/results/skylark/associativity02_refills/) | [PDF](skylark/results/associativity_combined.pdf) / [PNG](skylark/results/associativity_combined.png) | [CSV](skylark/results/associativity_eight_events.csv) |

每个实验的 `data/skylark/<run-id>/` 保存采集配置、命令、日志、PMU 原始计数、按采集顺序保存的 `.u64.gz`、源码/二进制/反汇编快照。对应 `results/` 保存完整分布统计、Tukey 箱线图、temporal medians、校验和 provenance。没有剔除 outlier。

完整六列表格见 [system_comparison.csv](skylark/results/system_comparison.csv)；计数定义见 [EVENTS.md](skylark/EVENTS.md)；最终完整性检查见 [final_audit.json](skylark/results/final_audit.json)。

## 平台检查与保留范围

本机为 AMD EPYC 7532，Family 17h / Model 31h，Zen 2，仍然是 Linux **x86_64**，可以复用已有的依赖指针链和 RDTSC/RDTSCP 计时内核。新增 Skylark 配置和 Python 运行/分析脚本；原 Artemisia C/C++、脚本、配置和结果均保留且未修改。沿用 `-O0`，计时单位始终是 **TSC ticks / timed chain load**，没有将它当成实际 core cycles，也没有减去固定计时开销。LFENCE 序列化沿用此前 Skylark 适配所依赖的标准 Linux AMD 初始化；没有读取特权 DE_CFG 寄存器。

正式采集前于 **15:32:11 UTC** 保存 [Phase-I 冻结清单](skylark/phase1_frozen.json)，涵盖 682 个已有 Skylark timing-only 文件；原 PMU 目录 264 个跟踪文件另有 [保留校验清单](skylark/original_pmu_sha256.json)。早期事件可用性探测先于此清单，正式 PMU 实验全部晚于清单。冻结的是已经存在的 Phase-I 结论，不是把此后读取的系统参数加入 timing-only 推断。

Skylark 没有活动 SMT 线程。新增分析处理了“没有 SMT sibling”的情况，不再套用 Artemisia 的 sibling 假设。未修改 perf 权限、频率 governor、预取器或 THP 全局设置。`perf_event_paranoid=2`；四事件 per-thread/user-only 组可用。系统没有 `numactl` 命令，复用此前 capacity 适配保存的本地 RPM 解包工具及 Python 虚拟环境。

## 事件发现与采集方式

已保存本机完整 [`perf list --details`](events/data/skylark/discovery02/perf-list-details.txt)、[110 个相关事件条目](events/results/skylark/discovery02/events.csv)、[逐项探测命令和结果](events/data/skylark/discovery02/probes.json)。每轮 runner 再次核对本机事件名与 raw encoding。

| 组 | 实际本机事件 | raw config | 使用范围 |
|---|---|---|---|
| A | `ls_mab_alloc.loads` | `0x0141` | load MAB allocation；保留异常响应，不将其视为 retired L1 misses |
| A | `l2_cache_req_stat.ls_rd_blk_c` | `0x0864` | L2 data-cache request misses，涵盖多个 request 类型 |
| A | `ls_refills_from_sys.ls_mabresp_lcl_dram` | `0x0843` | 来自本地 DRAM/IO 的 demand fills，作为 LLC 之外访问的间接证据 |
| A | `ls_dispatch.ld_dispatch` | `0x0129` | load dispatches，含辅助/推测操作 |
| B | `ls_refills_from_sys.ls_mabresp_lcl_l2` | `0x0143` | local L2 满足的 demand fills，检查 L1 refill 边界 |
| B | `ls_refills_from_sys.ls_mabresp_lcl_cache` | `0x0243` | 来自本地 cache domain 的 demand fills，不等同于纯 L3 hits |
| B | `l2_request_g1.rd_blk_l` | `0x8060` | L2 data-read requests，包含硬件/软件 prefetch |
| B | `ls_l1_d_tlb_miss.all` | `0xff45` | L1 DTLB misses/reloads，辅助检查地址翻译影响 |

分组 B 是发现 MAB allocation 不跟随 L1 timing 转换后增加的补充验证。完整保留 A 的结果和这项分歧，没有用 B 覆盖 A。八事件拆成两个 pinned 四事件组；PMU 在整个 sample loop 前后启停，初始化、warm-up、排序和文件输出不在计数窗口内。计数包含用户态辅助和 stack 操作，因此归一化值不是目标 load 的精确 miss 概率。Linux 的 [Zen 2 memory 事件定义](https://raw.githubusercontent.com/torvalds/linux/master/tools/perf/pmu-events/arch/x86/amdzen2/memory.json)及 [cache 事件定义](https://raw.githubusercontent.com/torvalds/linux/master/tools/perf/pmu-events/arch/x86/amdzen2/cache.json)也用于交叉核对；实际采集以保存的本机列表为准。

**直接 L3 计数限制：** `amd_l3` 的 per-thread 和 system-wide 探测在当前 kernel/perf/account 配置下返回 `<not supported>`。这里没有取得直接 L3 miss 计数，也没有将 local DRAM fills 改名为 L3 misses。`discovery01` 中两个 system-L3 raw modifier 有语法错误，已在 `discovery02` 改正并重测，两次记录都保留。`perf list` 的 tracefs permission warning 仅涉及不可读的 tracepoint 列表；硬件事件是否可用有独立探测和正式计数结果。

## 与原流程一致的负载

| 实验 | 点选择 | 保留参数 | 本次 CPU / NUMA |
|---|---|---|---|
| capacity | L1：32/36/40/48/64 KiB；L2：512/576/768/1024 KiB；LLC：16/20/24/28/32 MiB | 随机依赖链；spacing=64 B；batch=256；seed=59202；huge pages；顺序 seed=59283 | 32 / 1，与 Skylark Phase-I round2 相同 |
| line_size | random offset0：32/56/64/72/96 B；offset16：56/64/72 B；sequential：56/64/72 B；fully_random：64 B | footprint=256 KiB；batch=1024；warmup=1000；group_window=512 B；各 sweep 原 seed | 0 / 0，依据已有配置；旧数据未保存可验证的实际 pinning manifest |
| associativity | L1 K=6/7/8/9/10；L2 candidate K=7/8/9/10/11/12/13 | candidate sets=64/1024，即4/64 KiB spacing；line_size=64；max_k=16；batch=128；warmup=1000；seed=701 | 4 / 0，与保存的 candidate-sweep pinning manifest 相同 |

capacity 的每个点均匹配已有 Skylark `combined12/summary.csv` 的 size、samples、batch、spacing、seed、pages、mode。line_size 匹配已有 `stats/all_stats.csv`；原 worker seeds 来自已归档脚本的 701/711/721/731 分组。associativity 使用有 candidate selection 和 pinning 记录的 `raw_data/raw_data/` 内层数据，未混用外层另一批结果。

沿用 Artemisia PMU 版本已有的实现差异：line_size 把逐样本格式化 CSV 输出改为 prefaulted buffer，计数结束后写二进制；使用 `posix_memalign` 和初始化的配置结构。associativity 按单个 K 运行，保存排序前原始样本并 prefault 输出。依赖链构造与 timed traversal 保留，但这些差异、stack layout 和运行状态会影响绝对 timing，不能宣称是与 Phase-I 的逐字节重放。

associativity 原代码实际计时 **1 + 128 = 129 次**依赖 load，旧 summary 除以 128。本次保留 `legacy_median`，正式统计除以 129；图中旧值同步乘 128/129，原文件不修改。计数还包含 K−1 次 preparation loads，分母为 `1,000,000 × (K + 128)`。capacity 和 line_size 的计数分母分别是 `1,000,000 × 256`、`1,000,000 × 1024`。

## 实验发现和分歧

所有下列事件率均为 **每 1,000 个已知 chain loads 的事件数**。

- **Capacity：** 32→36 KiB 时，local-L2 demand fills 从 **47.62→325.58**，计时约 **3.47→5.06**；512→576 KiB 时，L2 DC request misses 从 **21.53→368.39**，计时 **9.19→15.84**。16→20 MiB 时，本地 DRAM/IO demand fills 从 **9.14→437.22**，计时 **30.09→141.56**；到32 MiB时该事件为738.61。这支持此前三个转换区域，但 LLC 的结果指向一个共享域的有效容量，不能当成整个 socket 的总 LLC。
- **L1 associativity：** 4 KiB spacing 的 K=8→9，local-L2 fills 从 **66.20→983.09**；L2 request misses 仍约0.01–0.02，支持 L1 冲突。K=9 的计时18.79高于K=10的10.23，说明延迟曲线并非随K单调，不能仅取最大延迟来判 ways。K=8已有少量 refill，也不应将边界描述成绝对零 miss。
- **L2 associativity：** 64 KiB spacing 的 K=8/9/10/11/12/13，L2 misses 分别为 **0.108/228.805/442.876/594.099/846.209/977.741**；补充组的 local-cache fills 显示类似趋势。最初“11 路”由 timing eviction probability 的最大跳变选出，却漏掉K=9已开始的 L2 miss。系统8路与最早的显著计数边界一致，旧11路比8路高37.5%。替换策略、冲突布局以及固定阈值会使转换分布在多个K；本次不把其中某一种原因当作已证实的唯一解释。
- **Line size：** offset0、stride32/56/64/72/96 B 的 local-L2 fills 为 **120.79/219.21/248.73/286.70/309.07**。64 B处没有清晰的 refill plateau。64 B时 sequential/random-window/fully-random 的同一事件为 **4.84/248.73/956.04**，表明遍历和预取影响很强。L1 DTLB 事件也随模式变化，例如 random-window64约8.92、fully-random64约34.09。结果支持空间复用的存在，64 B候选与系统值相容，但未独立排除其他解释，也没有分别测出L2/L3 line size。
- **Counter disagreement：** A组 MAB allocations 在32→36 KiB反而从19.52降至0.236，而同处延迟和B组 refill增加；该事件不能直接替代 Intel retired-load misses。line_size A组部分L2 request misses较大，B组对应cache-domain fills却很低；两者语义和采集时刻不同，不作相减/求和。没有证据把这些不一致归因为某个具体硬件 erratum。

## Timing / PMU / System 对照

系统值来自正式验证阶段保存的 [sysfs cache 记录](skylark/system/cache-sysfs.json)和 [lscpu](skylark/system/lscpu.txt)。Agner Fog 的 *The microarchitecture of Intel, AMD, and VIA CPUs*，2026-05-23版，**§22.16，Table22.3，p.237** 给出通用 Zen2 参数；已保存 [PDF](skylark/references/agner-microarchitecture.pdf)和[核对页](skylark/references/agner-page237.png)。[官方 Agner Fog 来源](https://www.agner.org/optimize/microarchitecture.pdf#page=237)。

| 属性 | Timing Inference | PMU Evidence | Published/System Value | Source/Page | Error/Agreement |
|---|---|---|---|---|---|
| L1D capacity | 约32 KiB，32–36 KiB起变 | local-L2 fills明显增加 | 32 KiB | sysfs index0；Fog p237 | 近似值一致；采样括区宽4 KiB |
| L2 capacity | 约512 KiB，512–576 KiB起变 | L2 request misses明显增加 | 512 KiB | sysfs index2；Fog p237 | 近似值一致；采样括区宽64 KiB |
| LLC capacity | 16–20 MiB起变，16–32 MiB过渡 | DRAM/IO fills增加 | 每共享域16 MiB | sysfs index3 | 相容；没有直接L3 miss计数或唯一物理容量估计 |
| L1可见line size | 64 B候选 | 有空间复用，64 B处无干净拐点 | 64 B | sysfs index0；Fog p237 | 数值一致；PMU独立确认不足 |
| L2/L3 line size | 未分层隔离 | 此负载不足以分别确认 | 均64 B | sysfs indices2/3；Fog p237 | 系统报告值 |
| L1 ways | 8 | K8→9出现L1 refill | 8 | sysfs index0；Fog p237 | 支持，数值误差0% |
| L2 ways | 原选11 | K9已有L2 miss，非等到K12 | 8 | sysfs index2；Fog p237 | 旧估计+37.5%；新计数边界与8一致 |
| L1 sets | 32 KiB/(8×64 B)=64 | 上述capacity/ways证据 | 64 | sysfs index0；Fog p237 | 推导一致 |
| L2 sets | 候选1024；旧11路反推却是744.7 | 用8路边界得到1024 | 1024 | sysfs index2；Fog p237 | 旧ways/size/sets不能同时成立 |
| LLC ways/sets | 本次代表子集未验证 | 没有新增LLC冲突测试 | 16 /16384 | sysfs index3 | 系统值，不宣称PMU确认 |
| Latency | 原latency01：L1约3.19；L2约8.34–8.81；LLC约27.09–27.75 TSC ticks/load | 本次未对独立latency workload采PMU | 通用Zen2参考4/12/40 core clocks | [原latency结果](../timing-only/latency/results/skylark/latency01/RUN_NOTES.md)；Fog p237 | 单位不同，不能直接算百分比误差 |
| Sharing | 单worker未独立推断 | 仅记录placement | L1/L2私有；本机L3域分别含CPU0–1、4–5、32–33；无活动SMT | sysfs、lscpu | 以实际启用CPU列表为准 |
| Inclusion/exclusion | 本次三个负载未验证 | 无受控eviction/coherence证据 | 未从sysfs确定 | 不作额外来源断言 | 保留为未确定 |

7532 的厂商表给出每socket **256 MB L3**，本机双socket系统汇总为512 MiB；这与单个16 MiB共享域是不同范围，不能拿总数直接比较单worker容量拐点。[AMD EPYC 7002 datasheet，p.2，7532行](https://www.amd.com/content/dam/amd/en/documents/products/epyc/amd-epyc-7002-series-datasheet.pdf#page=2)。完整对照CSV额外列出memory候选延迟、误差说明和全部来源定位。

## 质量与复现

六个正式run均通过原始长度、正计时值、SHA-256、重新计算的统计、实际load分母、计数event ID映射、CPU/NUMA placement 和 `time_enabled == time_running` 检查。测量窗口内 **minor/major faults均为0**；involuntary switches合计917，样本全部保留。capacity/associativity 工作区在测量前后有完整2 MiB THP backing；line_size工作区为base pages。无SMT不代表没有共享cache/内存竞争；机器未独占。

两组之间单点中位数最大变化：capacity **4.18%**，line_size **16.31%**（random stride96），associativity **21.13%**（L2 candidate K9）。associativity A组K11的分段中位数最大/最小比约1.158。变化点附近的分布、预取/替换状态、分组之间状态以及共享机器干扰均限制绝对latency比较，不把不同计数组拼成精确命中率。短样本native probe独立保存在events目录，没有计入上述76M样本。

源码适配检查通过：原capacity检查4项通过、1项Artemisia专用live检查跳过；共用非live检查4项通过；新增Skylark测试验证3个native kernel和被冻结的baseline点。保留测试日志于`skylark/test-*.log`。三个综合图已检查，并提供PNG与PDF。

在本目录使用以下环境。重新采集必须使用新的run ID；现有数据不会被覆盖。

```bash
cd /home/swu35/ECE592-HW1/PMU-verification
export PATH="$PWD/../timing-only/capacity/.venv/bin:$PWD/../timing-only/capacity/build/skylark/tools/usr/bin:$PATH"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

# 分组 A：依次执行，使用新的 run ID
taskset -c 1 python skylark/run_capacity.py --machine skylark --run-id capacity03
taskset -c 1 python skylark/run_verification.py --experiment line_size --machine skylark --run-id line_size03
taskset -c 1 python skylark/run_verification.py --experiment associativity --machine skylark --run-id associativity03

# 分组 B：相同负载；改用补充事件配置
taskset -c 1 python skylark/run_capacity.py --machine skylark --config capacity/configs/skylark-refills.json --run-id capacity04_refills
taskset -c 1 python skylark/run_verification.py --experiment line_size --machine skylark --config line_size/configs/skylark-refills.json --run-id line_size04_refills
taskset -c 1 python skylark/run_verification.py --experiment associativity --machine skylark --config associativity/configs/skylark-refills.json --run-id associativity04_refills

# 仅重新分析本次已经保存的六个run
python skylark/analyze_capacity.py --machine skylark --run-id capacity01
python skylark/analyze_capacity.py --machine skylark --run-id capacity02_refills
python skylark/analyze_verification.py --experiment line_size --machine skylark --run-id line_size01
python skylark/analyze_verification.py --experiment line_size --machine skylark --run-id line_size02_refills
python skylark/analyze_verification.py --experiment associativity --machine skylark --run-id associativity01
python skylark/analyze_verification.py --experiment associativity --machine skylark --run-id associativity02_refills
python skylark/combine_results.py
```

既有README描述的是Artemisia流程；Skylark请使用本文件中的新增脚本，避免旧分析脚本里的Intel事件标签和SMT假设。原Artemisia代码及Phase-I数据的保留校验结果记录在`final_audit.json`。
