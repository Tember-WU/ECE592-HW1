# Upgrade：两轮 Cache levels and capacity 实验

已按原有流程依次完成两轮：先用共享配置做全范围扫描，再根据 upgrade 的新曲线生成第二轮加密和对照配置。有效结果共 **96 个配置、96,000,000 个计时批次**，固定 CPU 2 / NUMA node 0。

| 轮次 | 有效 run ID | 配置数 | 采集时间 | 结果 |
|---|---|---:|---:|---|
| 第一轮 | `round1-retry2` | 39 | 152.95 秒 | [实验记录](round1-retry2/RUN_NOTES.md) |
| 第二轮 | `round2` | 57 | 120.17 秒 | [实验记录](round2/RUN_NOTES.md) |
| 合并分析 | `combined12` | 96 | — | [完整报告](combined12/RUN_NOTES.md)、[容量曲线](combined12/figures/capacity_s64_b256_huge.png)、[边界图](combined12/figures/boundary_zoom.png) |

当前计时证据支持 L1D 约 **32 KiB**、L2 约 **256 KiB**。LLC 在 **7–8 MiB** 出现有效转折；共享机器上存在其他负载，且布局对照有差异，因此未把该区间解释为精确物理容量。

最初的 `round1` 和 `round1-retry1` 均在 512 MiB 测点因大页分配失败而停止，每次完成 4 个配置。失败记录及部分原始数据完整保留，未计入最终结果。临时内存准备后，`round1-retry2` 使用未修改的内核和原参数完成了全部 39 个配置。详见合并报告。

## 配置与原始数据

- [机器配置](../../configs/upgrade.json)：引用原有 `common/round1.json`。
- [第二轮配置](../../configs/upgrade-round2.json)：由第一轮新数据生成，细化 32–64 KiB、256–512 KiB、4–8 MiB。
- [有效第一轮原始数据](../../data/upgrade/round1-retry2/)、[第二轮原始数据](../../data/upgrade/round2/)。
- [合并统计](combined12/summary.csv)、[校验结果](combined12/validation.json)、[推断记录](combined12/inference.json)。

## 重新生成分析

依赖保存在项目本地 `.venv`。系统原先缺少 pip、numactl、NumPy 和 Matplotlib；已用 `get-pip.py` 引导本地虚拟环境，安装 `requirements.txt`，并通过 `apt-get download numactl` / `dpkg-deb -x` 将 numactl 提取至 `.venv/native/root`。各轮 `python-packages.txt` 记录完整 Python 依赖版本。无需修改系统安装。

```bash
cd /home/swu35/ECE592-HW1/timing-only/capacity
export PATH="$PWD/.venv/bin:$PWD/.venv/native/root/usr/bin:$PATH"

python3 scripts/analyze_capacity.py --machine upgrade --run-id round1-retry2
python3 scripts/analyze_capacity.py --machine upgrade --run-id round2
python3 scripts/analyze_capacity.py --machine upgrade \
  --run-id round1-retry2 round2 --output-id combined12 \
  --boundaries results/upgrade/combined12/boundaries.json
python3 results/upgrade/validate_runs.py \
  --run-id round1-retry2 round2 --output-id combined12
```

以上命令只读取原始样本并重新生成分析与校验。实际采集的命令、源码、二进制和反汇编在每个原始数据目录内；重新采集必须使用新的 run ID。此次未运行第三轮。
