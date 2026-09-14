# Upgrade：七组 Hit / Miss latency 实验

`latency01` 已按原流程串行完成七组、30 个配置，正式采集用时 **111.82 秒**。每个配置保留 100 万批次，共 **3000 万批次、3900 万个计时间隔**，原始数据校验通过。

使用现有 `configs/upgrade.json`，固定 CPU 2 / NUMA node 0。测点来自此前 upgrade 的容量实验，执行顺序沿用原脚本的固定随机排列。正式运行一次完成；采集前的大页准备记录已保存。

| 实验组 | 配置数 | 首次访问中位数范围（TSC ticks/load） |
|---|---:|---:|
| calibration | 12 | 计时器、长批次、顺序访问和四流对照；单位按对照类型区分 |
| l1_hit | 3 | 3.03125–3.03516 |
| l2_hit | 3 | 8.84766–8.85547 |
| llc_hit | 3 | 26.10938–27.44141 |
| l1_miss / L2 candidate | 3 | 8.85547–8.86328 |
| l2_miss / LLC candidate | 3 | 26.19531–27.36719 |
| llc_miss / memory candidate | 3 | 204.75781–206.13672 |

以上是计时支持的候选访问类别，单位不等同于核心周期。首次访问、立即重读及两种延迟差值分别保存。L2 顺序访问对照出现时间波动；共享机器上另有测试负载。完整报告保留这些限制及全部原始样本。

- [完整实验报告](latency01/RUN_NOTES.md)
- [命中分布图](latency01/figures/resident_distributions.png)、[首次访问与重读图](latency01/figures/first_and_reread.png)
- [完整统计](latency01/summary.csv)、[延迟差值](latency01/contrasts.csv)、[校验结果](latency01/validation.json)
- [原始数据、日志与源码快照](../../data/upgrade/latency01/)

重新生成分析：

```bash
cd /home/swu35/ECE592-HW1/timing-only/latency
export PATH="$PWD/../capacity/.venv/bin:$PWD/../capacity/.venv/native/root/usr/bin:$PATH"
python3 scripts/analyze_latency.py --machine upgrade --run-id latency01
```

重新采集需要新的 run ID；已有 `latency01` 不会被覆盖。本次没有追加其他测量组或改变原实验内核。
