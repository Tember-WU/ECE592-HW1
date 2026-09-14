# Crux 两轮 Cache levels and capacity 实验

已于 2026-09-10 按原有流程依次完成粗扫描和第二轮加密扫描。固定 CPU 6 /
NUMA node 0，每个配置保留 100 万次计时；原 C 内核、`-O0` 编译参数、种子规则、
采样次数和页面策略保持一致。

| 阶段 | Run ID | 完成配置 | 计时样本 | 采集耗时 |
|---|---|---:|---:|---:|
| 第一轮完整粗扫描 | `round1-retry1` | 39/39 | 3900 万 | 156.60 秒 |
| 第二轮加密与对照 | `round2` | 57/57 | 5700 万 | 204.07 秒 |
| 合并分析 | `combined12` | 96 | 9600 万 | 两轮采集共 360.67 秒 |

实测支持三个数据缓存驻留区间：L1D 约 **32 KiB**（采样边界 32–36 KiB），
L2 约 **256 KiB**（起始过渡区间 256–288 KiB）。LLC 仅报告 **4–16 MiB 的
有效过渡区间**，不能据此确定物理容量。CPU 0 和 CPU 3 在采集期间持续满载，
布局、页面策略对 LLC 延迟也有明显影响。

最初的 `round1` 在第 5 个配置（512 MiB）分配大页失败；保留了前 4 个配置和
失败日志，随后用相同参数从头运行 `round1-retry1`。失败尝试未纳入正式合并结果。
原 artemisia 结果未修改。

另有流程偏差：最初环境检查的 `lscpu` 输出显示了系统报告的缓存容量，因此不能
把此次实验描述为事先未知规格的盲测。第二轮选点及报告中的数值均列出本次计时
证据；未采集 PMU 数据。

## 结果入口

- [两轮完整实验记录](combined12/RUN_NOTES.md)
- [边界放大图](combined12/figures/boundary_zoom.png)、[箱线图 PDF](combined12/figures/boundary_boxplots.pdf)
- [完整容量曲线](combined12/figures/capacity_s64_b256_huge.png)、[布局对照](combined12/figures/layout_comparison_b256_huge.png)
- [合并统计 CSV](combined12/summary.csv)、[推断 JSON](combined12/inference.json)
- [合并校验结果](combined12/validation.json)、[分析来源记录](combined12/provenance.json)
- [第一轮记录](round1-retry1/RUN_NOTES.md)、[第二轮记录](round2/RUN_NOTES.md)、[失败尝试记录](round1/RUN_NOTES.md)

原始样本、逐点命令、源代码快照、二进制、汇编及运行日志位于
`../../data/crux/round1-retry1/` 和 `../../data/crux/round2/`。
正式两轮压缩原始数据共 141,486,652 字节；全部样本和离群值均已保留。
额外的启动负载记录、控制台日志、依赖版本与自检日志位于 `../../data/crux/`。

## 重建已有分析

在 capacity 目录执行；这些命令只重新分析保存的数据，不重新采集：

```bash
cd /home/swu35/ECE592-HW1/timing-only/capacity
.venv/bin/python scripts/analyze_capacity.py --machine crux --run-id round1-retry1
.venv/bin/python scripts/analyze_capacity.py --machine crux --run-id round2
.venv/bin/python scripts/analyze_capacity.py --machine crux \
  --run-id round1-retry1 round2 --output-id combined12 \
  --boundaries results/crux/combined12/boundaries.json
.venv/bin/python results/crux/validate_runs.py round1-retry1 round2
```

## 本次成功采集的命令记录

以下是已执行命令，已有 run ID 和生成配置会受到防覆盖保护。将来重新采集时应使用
新的 run ID 和第二轮配置路径，并从当次第一轮数据重新选区间。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PATH="/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:$PATH" \
  make MACHINE=crux capacity assembly check
.venv/bin/python scripts/run_capacity.py --machine crux --run-id round1-retry1
.venv/bin/python scripts/analyze_capacity.py --machine crux --run-id round1-retry1
.venv/bin/python scripts/plan_capacity.py --machine crux --from-runs round1-retry1 \
  --round 2 --l1 32KiB:64KiB --l2 256KiB:512KiB --llc 4MiB:16MiB \
  --output configs/crux-round2.json
.venv/bin/python scripts/run_capacity.py --machine crux \
  --config configs/crux-round2.json --sweep all --run-id round2 --dry-run
.venv/bin/python scripts/run_capacity.py --machine crux \
  --config configs/crux-round2.json --sweep all --run-id round2
```

规划命令的完整选点说明保存在 `configs/crux-round2.json` 的 `planning.note`；上方省略
长说明以便阅读。每轮 `manifest.json`、`commands.txt` 与合并 `provenance.json` 保存
实际使用的采集、构建、逐点与分析命令。第三轮未执行。
