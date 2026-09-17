# Sunbird：8.5 软件 L1D 命中率估计

`hitrate01` 已依照 Artemisia 的流程完成全部 **54 次百万样本采集**。采集与数据完整性检查通过；但原算法在 Sunbird 上出现明显的准确率问题：同次执行对照的平均绝对误差为 **26.882 个百分点**，最差 **96.692 个百分点**。独立软件执行与配对 PMU 执行相比，平均绝对误差为 **25.748 个百分点**。`validation.json` 的 `passed` 表示完整性及参考计数检查通过，不代表命中率估计准确。

正式采集时间为 **2026-09-14 20:43:01–20:43:27 UTC**（Sunbird 当地 16:43:01–16:43:27 EDT），耗时 26.35 秒，不含准备、编译和结果分析。没有正式重跑，没有根据 PMU 结果调整阈值或挑选更好的一轮。

## 执行的实验

| 阶段 | 配置与重复 | 计时样本 |
|---|---|---:|
| 纯软件校准 | 空计时器；8 KiB expected-hit 和 512 KiB expected-miss；两个独立 seed 的校准检查 | 5,000,000 |
| PMU 空循环对照 | 冻结阈值之后执行 | 1,000,000 |
| 验证 | 8 种负载 × 3 个 seed/repeat × 软件版、PMU 版 | 48,000,000 |
| 合计 | 54 次独立串行执行 | 54,000,000 |

这里共 5200 万个单目标读取计时区间，以及 200 万个空循环控制区间。每次测量保留 100 万条原始 uint64 时间；暖机另计。原始载荷共 **432,000,000 bytes**，gzip 共 **20,685,687 bytes**。软件与 PMU 每对使用相同 seed/参数，第 2 次重复倒置两者执行顺序，沿用原来的确定性打乱顺序。

`configs/sunbird.json` 保留 Artemisia 的校准负载、8 种验证负载、spacing、reuse、seed、重复数和容许误差门限，仅适配 CPU 32/node 0、CPU identity 以及 PMU 名称/资料链接。`src/`、计时内核和 `scripts/estimator.py` 与 Artemisia 采集快照完全一致。报告代码只修正了不同机器的事件出处、文字及空控制样本的表述。

## 纯计时校准与阈值冻结

| 项目 | 本次值 |
|---|---:|
| 空计时器 median | 58 ticks |
| 8 KiB expected-hit median | 56 ticks |
| 512 KiB expected-miss median | 88 ticks |
| 分类规则 | 单次原始时间 ≤ **70 ticks** 判为 L1 hit |
| Balanced training error | 3.7001% |
| 独立 seed 的 balanced check error | 3.0777% |
| Hit calibration false-negative rate | 6.9754% |
| Miss calibration false-positive rate | 0.4249% |
| 阈值敏感性范围 | 70–75 ticks |

阈值由两类 timing 分布的等权分类错误最小化得到，沿用原规则处理并列最优点。训练和独立 seed 检查均低于原设定的 15% 门限，因此流程继续验证。`model.json` 和带 SHA256 的 `threshold-checkpoint.json` 在所有正式 PMU 测量之前保存；审计重新从纯计时校准 raw 拟合，结果仍为同一模型。PMU 计数没有进入拟合或分类。

计时包含 fence、分支和读时钟开销，单位是原始 TSC ticks，不能直接当成纯 load latency 或 core cycles；没有减去空计时器的某一个最小值。校准 hit/miss 标签表示强烈预期的驻留类别，没有单访问硬件标签。

## 与 PMU 的对照

下表是每种负载三次重复的平均值；误差先逐次计算，再平均。软件同次执行列使用 PMU 版保存的时间值进行冻结规则分类，避免独立运行的漂移混进主对照。独立软件版的结果另列。

| 负载 | Reuse | 软件同次命中率 % | PMU 命中率 % | 独立软件命中率 % | 平均绝对误差 pp |
|---|---:|---:|---:|---:|---:|
| resident_16k | 1 | 94.963 | 99.780 | 95.372 | 4.816 |
| boundary_48k | 1 | 96.312 | 0.157 | 95.952 | 96.155 |
| nonresident_128k | 1 | 93.518 | 0.072 | 92.826 | 93.446 |
| reuse2_256k | 2 | 59.301 | 49.992 | 60.109 | 9.308 |
| reuse4_256k | 4 | 71.053 | 74.981 | 75.608 | 3.928 |
| reuse8_256k | 8 | 80.109 | 87.476 | 85.798 | 7.367 |
| deeper_8m | 1 | 0.019 | 0.009 | 0.013 | 0.010 |
| large_128m | 1 | 0.000 | 0.027 | 0.000 | 0.027 |

最差点是 **boundary_48k，repeat 2**：软件命中率 96.8102%，PMU 为 0.1187%，绝对误差 96.6915 pp。

绝对误差计算为 `100 × abs(H_software − H_PMU)`，单位是百分点；相对误差为 `100 × abs(H_software − H_PMU) / H_PMU`。24 对完整结果，包括逐次相对误差、95% 区间和阈值敏感性，见 [comparison.csv](comparison.csv)。当 PMU 命中率接近零时，相对误差会极大；本次最高约 1,370,762.6%，不能把它当成稳定的跨负载评分。平均汇总另见 [case_summary.csv](case_summary.csv)。

本机实际使用 `mem_load_uops_retired.l1_miss`（`0x08d1`）和 `mem_uops_retired.all_loads`（`0x81d0`），参考比率是 `1 − L1_misses / retired_load_uops`。它们在本机 `perf list --details` 中核实，并通过成组调度预检；本次正式 25 个 PMU 执行（含空控制）全部满足 enabled time = running time > 0。[Intel Haswell Server 事件定义](https://perfmon-events.intel.com/platforms/haswellx/core-events/core/)说明这些是 retired **load uops**，并列有相关 errata。实际内核每个目标读取为单条对齐 load，反汇编检查和计数分母检查均通过；不能将这种比率直接套用到其他架构的 refill/dispatch 事件。

PMU 空循环记录 382 个辅助 load uops；验证执行相对已知 100 万目标读取最多多出 972 个，满足原来 0.1% 容许限。辅助读取带来的参考界限最大为 **0.0972 pp**，远小于 48/128 KiB 的约 92–97 pp 误差，不能解释这些大误差。此界限以事件本身正确计数为前提，不覆盖 PMU errata。低命中率时，参考中的少量命中可能主要来自辅助读取；原脚本保留 `pmu_target_hit_bound_low/high`，没有擅自减掉辅助计数。

## 失败原因与不确定性

**直接观察到的是分布覆盖失败。** 48/128 KiB 在 PMU 上几乎全为 L1 miss，但其计时大量落在 70 ticks 以下，与 expected-hit 校准重叠；512 KiB miss 校准却主要在更慢的区间。选择能分开 8 KiB 与 512 KiB 的阈值，不能保证能识别所有 L1 miss 的服务状态。见新增的 [held-out 分布重叠图](figures/heldout_overlap.png) / [PDF](figures/heldout_overlap.pdf)。

较快的下一层服务、运行时机、频率和仪器开销都可能影响这种重叠；本次没有 L2 事件或逐访问 PMU 标签，不能逐访问断定具体数据来源。8 KiB hit 校准自身还有约 6.98% 的阈值外样本，所以小 resident 负载也被低估约 4–6 pp。Reuse=4/8 的部分运行还呈现明显分类比例变化，单一阈值不能消除这些状态差异。

原有 block bootstrap 使用 100 个连续块、2000 次重采样，报告的是**在冻结分类器下**的抽样不确定性，需要近似可交换块假设；它不覆盖校准类别不全和系统性分类偏差。本次仅 **3/24** 个同次软件 95% 区间包含对应 PMU 点估计。例如最差的 48 KiB repeat 2，区间约 [94.96%, 98.50%]，与约 0.12% 的 PMU 参考相距很远。这个对照说明窄区间不等于正确估计；它不是在独立同分布真值标签下进行的正式覆盖率检验。

70–75 ticks 的敏感性范围来自训练误差距最优值不超过 1 pp 的阈值集合，并非另一个置信区间。把阈值升高会进一步把这些较快的 miss 判为 hit；本次没有用验证 PMU 数据选择新阈值。当前结果如实展示原估计器在 Sunbird 上的泛化局限，不能宣称复现了 Artemisia 的低误差，也不能把它重新命名成另一个已经验证的 cache metric。

## 运行质量与证据

所有测量 CPU 起止均为 **32**，内存显式绑定 **node 0**，使用 prefaulted base pages。计数前记录了 chain/output 的全部页位于 node 0；16 次运行中相邻 mmap 合并为一个 VMA，审计按页数总和验证，不能误认为少记录了一块内存。每个 interval 对目标读取一次；输出存储在停止计时之后，但其缓存影响属于保留原始数据的仪器化工作负载。

CPU 8 是同核 SMT sibling，本次所有 worker 期间记录的平均忙碌率为 **0%**。测量区有 **0 minor faults、0 major faults、0 voluntary switches、2 involuntary switches**。机器其他核仍有工作负载；这些观察不证明独占或无共享缓存干扰。没有修改全局缓存、THP、调速器或 perf 权限设置。

5 项原有功能检查全部通过，包括纯软件程序无 PMU 接口、软件/验证二进制测量循环一致、分类重建和污染分母/复用拒绝检查。原分析器重读全部 raw，重算统计、C/Python 分类数量及参考误差；补充审计核对完整串行计划、3 次重复覆盖、模型纯计时重拟合、页数及 NUMA、当前与快照内核/二进制，结果见 [execution_audit.json](execution_audit.json)。206 个原 Artemisia 文件及原始内核/估计器文件的哈希保持不变。

此前 capacity/8.3 任务已经查看过缓存规格，这段历史没有被当成盲测。本轮 8.5 没有以规格或 PMU 结果修改校准参数；估计器保持 timing-only 输入。PMU 调度的预检是单独的能力检查，不参与正式校准或误差计算。

## 文件与复现

- [原流程生成的报告](RUN_NOTES.md)、[完整统计](statistics.csv)、[逐重复误差及区间](comparison.csv)、[按负载汇总](case_summary.csv)
- [命中率/误差图](figures/hit_rate_comparison.png)、[校准图](figures/calibration.png)、[分布箱线图](figures/validation_boxplots.png)、[流程图](figures/methodology.png)、[失败分布图](figures/heldout_overlap.png)；均有 PDF
- [原始数据与源代码/可执行文件快照](../../../data/sunbird/hitrate01/)、[冻结模型](../../../data/sunbird/hitrate01/model.json)、[冻结时间及哈希](../../../data/sunbird/hitrate01/threshold-checkpoint.json)
- [准备、构建检查、事件核实及完整控制台](../../../preparation/sunbird/setup01/)

在 `software-hit-rate` 下重新分析已有数据：

```bash
export PATH="/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:/home/swu35/ECE592-HW1/timing-only/capacity/build/sunbird/deps/usr/bin:$PATH"
python scripts/analyze.py --machine sunbird --run-id hitrate01
python preparation/sunbird/setup01/audit_run.py
```

实际采集命令是 `python -u scripts/run_experiment.py --machine sunbird --run-id hitrate01`。将来再次采集需要新 run ID；现有运行、旧 Artemisia 结果和冻结模型均保留。
