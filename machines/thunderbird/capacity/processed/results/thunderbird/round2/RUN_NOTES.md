# Thunderbird 第二轮：加密扫描与对照

本轮已完成 57 个配置、57,000,000 个计时批次，采集耗时 422.04 秒（约 7 分 2 秒），在第一轮采集及校验完成之后启动。每个配置独立运行并保存 1,000,000 个批次。配置来自 Thunderbird 第一轮的新随机访问曲线，没有套用 Artemisia 的容量结论。

加密范围为 64–128 KiB、1–2 MiB 和 32–64 MiB。保持原有规划器流程，使用新种子 59202/59203，加入随机链重复、顺序链、8 B 紧凑布局、1024-load 长批次和基础页对照。54 个配置使用完整 THP，3 个使用基础页。两轮的源码、二进制、计时器频率、编译选项及 CPU 32 / NUMA node 0 绑定相同。

结果支持 L1D 约 64 KiB、L2 约 1 MiB；可报告末级/系统缓存的 32–64 MiB 有效转换区域，但没有唯一确定物理容量。详细数值、边界含义、重复稳定性和对照分析见 [两轮合并说明](../combined12/RUN_NOTES.md)。

本轮全部数组的哈希、样本数、重新计算的统计量、源码/二进制快照及 CPU/NUMA/页策略均已验证。所有映射在计时前后均位于 node 0 并满足对应页策略。计时区间小缺页、大缺页和主动切换为 0；非主动切换共 4,897 次，单点最多 256 次。保留默认 schedutil governor，所有原始样本及时间块中位数均保留。

原始数组共 456,000,000 字节，gzip 后 37,192,814 字节。记录见 [validation.json](validation.json)。

[本轮主曲线](figures/capacity_s64_b256_huge.png)、[布局对照](figures/layout_comparison_b256_huge.png)、[统计表](summary.csv)、[时间稳定性](figures/temporal_stability.pdf)、[配置及规划证据](../../../configs/thunderbird-round2.json)。
