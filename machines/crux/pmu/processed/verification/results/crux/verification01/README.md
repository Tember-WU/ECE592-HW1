# Crux：8.3 PMU 验证

2026-09-14 在 `crux.ece.ncsu.edu` 完成 capacity、line_size、associativity 三类代表性实验。沿用 Artemisia 的 PMU 测量流程，按 Crux 已冻结的 timing-only 结果选点，所有正式测量串行执行。

| 实验 | 完整运行 | 点数 | 每点重复次数 | 正式计时总数 | 运行耗时（含准备与保存） |
|---|---|---:|---:|---:|---:|
| capacity | [capacity05](../../../capacity/results/crux/capacity05/RUN_NOTES.md) | 14 | 1,000,000 | 14,000,000 | 53.80 s |
| line_size | [line_size01](../../../line_size/results/crux/line_size01/RUN_NOTES.md) | 12 | 1,000,000 | 12,000,000 | 50.77 s |
| associativity | [associativity01](../../../associativity/results/crux/associativity01/RUN_NOTES.md) | 12 | 1,000,000 | 12,000,000 | 15.02 s |

以上路径相对于本报告所在目录；每类结果保留统计 CSV、PMU 原始计数与归一化计数、质量记录、完整性校验，以及 PNG/PDF 图。对应 `data/crux/<run-id>/` 保留全部 gzip 原始计时、命令、配置、环境、大页/亲和性日志和源码/二进制快照。失败运行不参与上述 3,800 万次正式结果。

## 流程、冻结与事件

[Phase-I 检查点](../../../phase1/crux/freeze01/FREEZE.md) 创建于 `2026-09-14T15:31:22.812249+00:00`，早于本次任何 PMU probe。Git 基线为 `f86eecbb6fce590f3d40b64487620888b33dcd93`；manifest 记录 8,042 个已提交文件的 Git blob ID，并保存 171 个源码、配置及基线结果文件的副本与 SHA-256。原有 timing-only 文件和 Artemisia 结果未改动。

冻结保留了原始结论：L1 约 32 KiB、L2 约 256 KiB、LLC 有效变化区间 4–16 MiB；相联度选择器为 L1 9 路、L2 candidate 8 路。原 capacity 记录已经披露之前查看 `lscpu` 暴露了系统容量，因此这个检查点不能使先前实验追溯性地成为盲测。

[本机事件清单](../../../events/results/crux/discovery01/EVENTS.md) 包含 271 个解析条目；16 个单事件 probe 和一个四事件组 probe 全部通过。正式运行还重新核对本机 `perf list --details` 的编码：

| 事件 | Crux 原始编码 | 用途 |
|---|---|---|
| `mem_load_retired.l1_miss` | `0x08d1` | 退休 load 的 L1 miss |
| `mem_load_retired.l2_miss` | `0x10d1` | 退休 load 的 L2 miss |
| `mem_load_retired.l3_miss` | `0x20d1` | 退休 load 的 L3 miss |
| `mem_inst_retired.all_loads` | `0x81d0` | 记录已计数 load 总量及 helper 开销 |

Crux 的 perf 描述使用 `default_core/.../`，解析器现同时支持它和原有 `cpu/.../`。日志中 `failed to open tracing events directory` 是列举 tracing events 时的诊断；所需硬件事件描述存在，probe 与正式硬件组均成功。每点四个计数器同时计数，全部 `time_enabled == time_running`，没有 multiplex 缩放。计数是每个百万次循环的总量，并非每个样本单独读取四次 PMU。

capacity 固定 CPU 6 / NUMA node 0；line_size 和 associativity 固定 CPU 4 / node 0，与各自原 Crux 实际运行的 pinning manifest 一致。模板配置中的过时 CPU 字段不作为历史执行证据。机器无额外 SMT sibling。保留原 governor 和其他机器设置。

## 实验结论

**Capacity：L1/L2 转折复现，LLC 有效转折与 Phase I 有明显差异。** 32→36 KiB 时 L1 miss 从 39.13 增至 993.70 / 1,000 chain loads；256→288 KiB 时 L2 miss 从 10.76 增至 287.72。相应计时同时上升，支持原来的 32–36 KiB、256–288 KiB 转折邻域。

LLC 在本次 4、7、10 MiB 时 L3 miss 为 1.82、3.02、12.67 / 1,000，13、16 MiB 时为 398.28、727.05。明显上升位于本次采样的 10–13 MiB 之间；Phase I 在 4–7 MiB 就已上升，7/10 MiB 的原中位数为 71.88/142.62，本次为 28.18/28.11 TSC ticks/load。因此不能写成“原 LLC 转折完全验证成功”。共享 LLC/内存竞争、驻留状态和运行间环境变化可能参与，未隔离唯一原因；13 MiB 的时间块中位数最大/最小比为 1.20，P95 为 143.58 ticks/load，也不是纯单一命中层级。系统 12 MiB 与本次明显上升的邻域相容，但本实验没有精确测得物理 LLC 字节数。

**Line size：支持空间复用和访问顺序影响，PMU 曲线没有干净的 64 B 饱和平台。** 256 KiB footprint、512 B 分组窗口下，offset 0 的 stride 32/56/64/72/96 B 对应 L1 miss 为 99.82/277.70/370.20/412.34/556.19 每千次 chain load。64 B 时，顺序、随机窗口、完全随机三种顺序分别为 49.42、370.20、985.62；窗口内的规则访问显著影响结果，预取是可能机制，未单独关闭或量化。该 footprint 同时接近 Crux L2 容量，完全随机控制的 L2 miss 达 345.32 / 1,000。因此保留“64 B 候选与系统规格相容”，不声称这些点独立且精确验证了每一级 cache line size，也不套用 Artemisia 的平台结论。

**Associativity：PMU 支持 L1 8 路；原 L2 的 8 个地址阈值不能直接解释为单个 L2 set 的 8 路。** L1 的 4 KiB 地址间隔下，K=8→9 时 L1 miss 为 0.333→984.504 / 1,000，L2 miss 仍接近零，支持 8 路边界。原选择器的 9 路标签高估 1 路（相对系统 8 路为 +12.5%）；旧的 timing-derived eviction probability/calibration 不能当作硬件 miss probability。

L2 candidate 使用 `512 * 64 B = 32 KiB` 间隔。K=8→9→10 时 L2 miss 为 0.019→93.189→515.644，同时 L1 miss 也上升；所以确有 L2 冲突参与，不能只归因于 L1。然而系统报告 L2 为 4 路、1,024 sets。在常规物理索引模型下，32 KiB 间隔交替访问两个 L2 sets，总共可容纳 `2 * 4 = 8` 个地址，这与观测阈值相容。所有本次 associativity 映射在测量前后均有完整 2 MiB THP，减少了基页物理映射不连续的混淆。这里的“两组”解释是依据系统几何的推断；没有额外逐地址物理 set 映射实验，不能声称 PMU 已独立测出所有 L2 sets 的 4 路。原始 candidate1024 也曾给出 8 路标签，本批未重跑该候选，不把它当作已消除的矛盾。

相联度绝对计时比 Phase I 明显下降，例如 L1 K=8 原值经分母修正为 10.76，本次 5.97 ticks/load。继承的 PMU 版本将循环内格式化输出改成 prefaulted 原始数组、在计数结束后写文件，并逐 K 启动进程；stack/helper 状态也可能变化。当前不能把差值归因于唯一因素，也不能只做纵轴平移后声称完全相同。保留同一依赖访存和计时函数，按层级 PMU miss 解释转折。

## 系统/文献对照

详细表见 [comparison.md](comparison.md)，可编辑数据为 [comparison.csv](comparison.csv)。本机 i7-9700 的 sysfs 报告：L1D 32 KiB / 8 路 / 64 sets；L2 256 KiB / 4 路 / 1,024 sets；LLC 12 MiB / 12 路 / 16,384 sets；均为 64 B line。L1/L2 每核心私有，LLC 的 shared CPU list 为 0–7。证据在选点和冻结之后读取的 [system-cache-reference.json](../../../events/data/crux/discovery01/system-cache-reference.json)。

Intel 的 [i7-9700 产品规格](https://www.intel.com/content/www/us/en/products/sku/191792/intel-core-i79700-processor-12m-cache-up-to-4-70-ghz/specifications.html) 确认 Coffee Lake、8 核/8 线程和 12 MB Smart Cache。Agner Fog 的 [The microarchitecture of Intel, AMD and VIA CPUs](https://www.agner.org/optimize/microarchitecture.pdf) 第 11 章印刷页 152 包含 Coffee Lake；§11.12、表 11.2（印刷页 160）给出该 Lake 家族的 cache 参数。它的 L2/L3 数值包含多个型号范围，不能代替本机 SKU 的准确规格。PDF、页图和来源 hash 已存入 [references](../../../events/data/crux/discovery01/references/sources.json)。

本次报告对照这三类实验，并列明 derived sets、sharing scope 的证据范围。未新增独立的 hit-latency、跨核心共享或 inclusion/exclusion PMU 实验；未获得证据的属性在表中明确标为未验证。TSC ticks 包含计时/循环开销，不等同于 Agner Fog 的 core clocks，不计算两者的伪百分比误差。

## 数据质量、失败记录与实现适配

38 个正式点均通过 raw/count SHA-256、原始长度、正计时间隔、统计量重算、真实 chain-load 分母及无 multiplex 检查，见 [最终校验记录](validation.json)。全部 outliers 保留。capacity 每次计时 256 个 chain loads；line_size 为 1,024 个；associativity 实际计时 129 个，PMU 还包含 K−1 个准备 load，因此分母是 `samples * (K + 128)`。原相联度 CSV 的 `/128` 仅在对比时乘 `128/129`，旧文件未改写。

计数覆盖 user-mode、当前线程的测量循环，也包含 helper/stack load。每千次已知 chain loads 的 retired-load 总数范围分别为 capacity 1062.50–1062.52、line_size 5027.34–5027.35、associativity 5368.06–5388.06。因此 miss/1,000 是归一化工作量指标，不能直接解释为条件 miss probability 或逐目标 eviction probability。L3 miss 也不能单独证明访问由本地 DRAM 服务。

| 实验 | minor faults | major faults | involuntary switches | 映射 |
|---|---:|---:|---:|---|
| capacity05 | 1 | 0 | 189 | 全部工作集前后完整 THP，node 0 |
| line_size01 | 6 | 0 | 278 | 全部基页，前后状态不变 |
| associativity01 | 0 | 0 | 39 | 全部前后 2 MiB THP，node 0 |

主机有其他用户负载，未隔离共享 cache/内存竞争。测量期间 CPU busy 包含本 benchmark，不能当作其他进程的活动率。少量缺页和上下文切换已计入统计，未剔除对应样本。

capacity01–04 因 `MADV_COLLAPSE: Cannot allocate memory` 在分配阶段中断，分别完成 0、4、0、4 个点；共 800 万次部分结果保留但不合并。见 [run_inventory.csv](run_inventory.csv) 和各失败目录的 `RUN_NOTES.md`。之后只为 capacity 启动脚本增加可选 `--allocation-retries`：日志必须是已知的计时前 THP ENOMEM，且没有 timing/count 输出，才允许间隔 2 秒重启同一点；其他错误立即失败。capacity05 从头完成全部 14 点，首点有 5 个未计时的分配失败日志，没有从旧运行取数据。没有更改测量 C/C++、测量顺序、seed、样本数、大页要求或机器级内存设置。

其他兼容性修改为 perf 事件别名、无 SMT 时的质量汇总、原 CSV 字段空格清理，以及图标题/地址间隔/CPU 说明按配置生成。7 个 capacity 检查（含 allocation retry 边界和真实 PMU 短测）及 6 个共用检查（含两个 C++ kernel 的真实 PMU 短测）通过。日志位于 [discovery01](../../../events/data/crux/discovery01/)。每个完整运行的 `reproduction/` 是采集后的保留源码与可执行文件快照，附 SHA-256；不混称为自动采集前快照。

## 重现命令

在 `PMU-verification/` 下，使用本机 `.venv`（NumPy 1.26.3、Matplotlib 3.9.4）。已有 run ID 不可覆盖。以下按顺序产生新的运行：

```bash
.venv/bin/python capacity/scripts/run_capacity.py --machine crux --run-id capacity06 --allocation-retries 30
.venv/bin/python capacity/scripts/analyze_capacity.py --machine crux --run-id capacity06
.venv/bin/python line_size/scripts/run_line_size.py --machine crux --run-id line_size02
.venv/bin/python line_size/scripts/analyze_line_size.py --machine crux --run-id line_size02
.venv/bin/python associativity/scripts/run_associativity.py --machine crux --run-id associativity02
.venv/bin/python associativity/scripts/analyze_associativity.py --machine crux --run-id associativity02
```

重现会受到运行时共享主机状态影响。完整运行的逐点实际命令、UTC 起止、CPU/频率和原始计数以各自 `data/.../manifest.json` 为准。
