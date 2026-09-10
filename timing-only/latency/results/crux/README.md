# Crux 七组 Hit / Miss / next-level latency 实验

已于 2026-09-10 在 CPU 6 / NUMA node 0 上，使用现有 `configs/crux.json`
和原 C 内核完成七组实验。执行顺序沿用 artemisia 的固定种子随机顺序，所有配置
逐点串行运行。正式运行编号为 **`latency01-retry2`**，耗时 **115.28 秒**。

| 实验组 | 完成配置数 | 工作集 |
|---|---:|---|
| calibration | 12/12 | 空计时、长批次、顺序访问、四独立流对照 |
| l1_hit | 3/3 | 8 / 16 KiB，加新种子重复 |
| l2_hit | 3/3 | 64 / 128 KiB，加新种子重复 |
| llc_hit | 3/3 | 1 / 2 MiB，加新种子重复 |
| l1_miss | 3/3 | 64 / 128 KiB，首次访问与立即重读 |
| l2_miss | 3/3 | 1 / 2 MiB，首次访问与立即重读 |
| llc_miss | 3/3 | 256 / 512 MiB，首次访问与立即重读 |

共 **30 个配置、3000 万批次、3900 万个计时间隔**。配对实验的两列分别分析，
全部原始样本和离群值保留；数据、源码快照、CPU/NUMA 绑定和大页检查全部通过。

单位均为 **TSC ticks / dependent load**，不是已验证的 CPU 核心周期：

| 实测类别 | 三个进程的中位数范围 |
|---|---:|
| L1 驻留候选 | 2.73047 |
| L2 驻留候选 | 7.79688 |
| LLC 驻留候选 | 25.77344–27.15625 |
| L1 miss / L2 候选首次访问 | 7.80078–7.94922 |
| L2 miss / LLC 候选首次访问 | 25.83594–27.16016 |
| LLC miss / 内存候选首次访问 | 205.25000–206.49609 |

空计时中位数为 30 ticks/interval。上述类别由工作集构造和时序对照支持，未由
PMU 逐次确认；大工作集的重读仍高于 L1 参考值，不能把所有样本视为纯 DRAM／
纯 L1 状态。CPU 0 在采集期间接近满载，完整实验记录包含负载与频率条件。

## 结果入口

- [完整实验记录](latency01-retry2/RUN_NOTES.md)
- [Hit 驻留分布图](latency01-retry2/figures/resident_distributions.png)
- [首次访问与立即重读图](latency01-retry2/figures/first_and_reread.png)
- [方法对照图](latency01-retry2/figures/method_controls.png)
- [统计 CSV](latency01-retry2/summary.csv)、[next-level 与配对差值](latency01-retry2/contrasts.csv)
- [估计 JSON](latency01-retry2/latency_estimates.json)、[校验结果](latency01-retry2/validation.json)
- [全部尝试清单](run_inventory.json)

正式原始数据、逐点日志、命令、二进制、汇编和源码快照位于
`../../data/crux/latency01-retry2/`。正式原始数据解压后为 312,000,000 字节，
压缩后为 48,646,666 字节。

最初两次尝试分别在 256 MiB 和 512 MiB 分配完整大页时失败；对应配置尚未计时。
它们分别保留 6 和 11 个已完成配置，未纳入正式分析。随后按相同参数从头重试
成功，未改变页面策略、源码或系统设置。
见 [首次失败记录](latency01/RUN_NOTES.md) 与 [第一次重试记录](latency01-retry1/RUN_NOTES.md)。

## 重建已有分析

```bash
cd /home/swu35/ECE592-HW1/timing-only/latency
.venv/bin/python scripts/analyze_latency.py --machine crux --run-id latency01-retry2
```

分析器会重新读取所有原始文件并核验，不重新采集。

## 本次执行命令

```bash
cd /home/swu35/ECE592-HW1/timing-only/latency
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PATH="/home/swu35/ECE592-HW1/timing-only/latency/.venv/bin:$PATH" \
  make MACHINE=crux all check
.venv/bin/python scripts/run_latency.py --machine crux --run-id latency01 --dry-run
.venv/bin/python scripts/run_latency.py --machine crux --run-id latency01
.venv/bin/python scripts/run_latency.py --machine crux --run-id latency01-retry1
.venv/bin/python scripts/run_latency.py --machine crux --run-id latency01-retry2
.venv/bin/python scripts/analyze_latency.py --machine crux --run-id latency01-retry2
```

以上采集命令是执行记录：前两次因大页分配失败退出，第三次成功。已有 run ID
受防覆盖保护；将来重新采集应使用新编号。依赖版本、自检日志、控制台日志和
汇编检查保存在 `../../data/crux/`。artemisia 的代码快照和结果未修改。
