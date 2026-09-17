# Thunderbird：8.3 PMU 验证

已于 2026-09-14 依次完成 capacity、line_size、associativity，分别为 14、12、12 个配置，每个配置 1,000,000 次 timed batches。随后补充 2 个容量工作负载的 LL 事件诊断点，各 1,000,000 次。主实验共 38,000,000 次，含补充诊断共 40,000,000 次。

完整结论、规格对照表和差异说明见 **[REPORT.md](results/thunderbird/REPORT.md)**；文件保留与串行执行检查见 [audit.json](results/thunderbird/audit.json)。

| 实验 | 原始记录 | 统计与 PNG/PDF 图 |
|---|---|---|
| capacity | [capacity01](capacity/data/thunderbird/capacity01/) | [capacity01](capacity/results/thunderbird/capacity01/) |
| line_size | [line_size01](line_size/data/thunderbird/line_size01/) | [line_size01](line_size/results/thunderbird/line_size01/) |
| associativity | [associativity01](associativity/data/thunderbird/associativity01/) | [associativity01](associativity/results/thunderbird/associativity01/) |
| LL 事件补充诊断 | [ll_diagnostic01](capacity/data/thunderbird/ll_diagnostic01/) | [ll_diagnostic01](capacity/results/thunderbird/ll_diagnostic01/) |

原有 Artemisia 源码、脚本、Makefile、配置和结果均未修改。新增入口为 `scripts/thunderbird.py`；capacity 新增独立的 ARM 源文件，line_size 与 associativity 直接编译原有 PMU 源文件中的 ARM timer 分支。新入口处理 ARM 事件编码、原生反汇编、NUMA 绑定、计时单位、无 SMT 的质量记录和平台对应的图表标签。

本机 generic timer 为 25 MHz，1 tick = 40 ns；所有原始数据均为 `uint64` timer ticks。正式计数使用四个同时调度的用户态事件，不做 multiplex 缩放。运行目录保留 `manifest.json`、`config.json`、`environment.json`、原始样本、counts、日志、源码及二进制快照。结果目录有全部样本统计、PMU 计数、时间分块统计、质量记录和完整性验证。

复现实验时，在本目录执行以下命令；下面使用新 run ID，避免覆盖本次结果。虚拟环境和 numactl 沿用之前 capacity 实验安装的本地版本，入口自动设置 numactl 路径。

```bash
PY=/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin/python
taskset -c 0 "$PY" scripts/thunderbird.py run --experiment capacity --run-id capacity02
taskset -c 0 "$PY" scripts/thunderbird.py analyze --experiment capacity --run-id capacity02
taskset -c 0 "$PY" scripts/thunderbird.py run --experiment line_size --run-id line_size02
taskset -c 0 "$PY" scripts/thunderbird.py analyze --experiment line_size --run-id line_size02
taskset -c 0 "$PY" scripts/thunderbird.py run --experiment associativity --run-id associativity02
taskset -c 0 "$PY" scripts/thunderbird.py analyze --experiment associativity --run-id associativity02
```

`taskset -c 0` 限制控制/分析进程；实际 benchmark 仍按配置绑定 CPU 32（capacity）或 CPU 4（line_size、associativity），内存绑定 NUMA 0。各运行内采用固定种子的随机点顺序，与原有流程一致；三种实验互不并行。

如需复现补充诊断，使用 `--experiment capacity --run-id ll_diagnostic02 --config capacity/configs/thunderbird_ll_diagnostic.json`。`discover` 会重新生成本次 discovery01 的辅助清单；保留当前证据时无需重跑它。`check` 是已执行的原生内核检查，并拒绝覆盖现有 smoke01。`scripts/audit_thunderbird.py` 可重新核查本次四个 run 的冻结文件、快照和串行顺序。

特别注意：L1/L2 容量和相联度获得了 PMU 支持；line_size 的预取影响明显，核心 LL 事件未能独立验证 SLC 容量。CMN 系统级计数器的直接访问返回权限不足，未修改系统权限。
