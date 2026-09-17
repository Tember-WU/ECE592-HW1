# Charnwood line-size PMU verification: line_size01

Completed 2026-09-14, 15:41:04–15:42:07 UTC, after capacity03: **12 points, 1,000,000 timed batches each**, all four-event groups fully scheduled. Collection took 63.61 seconds including setup and compression.

The Artemisia verification workflow was applied to the existing Charnwood Phase-I points: 256 KiB footprint, 512 B grouping window, batch 1024, warmup 1000, original seeds, CPU 4 / NUMA node 0. The selected strides are 32/56/64/72/96 B at offset 0, 56/64/72 B at offset 16, sequential 56/64/72 B, and fully random 64 B. CPU 0 is the actual SMT sibling; the old timing-only pinning manifest's no-SMT statement is incorrect. The old data remains unchanged.

| Access mode / offset | Stride | Median ticks / load | L1 misses / 1,000 chain loads |
|---|---|---|---|
| Random windows / 0 B | 32 B | 10.018 | 94.763 |
| Random windows / 0 B | 56 B | 14.217 | 230.980 |
| Random windows / 0 B | 64 B | 15.451 | 318.747 |
| Random windows / 0 B | 72 B | 15.262 | 348.092 |
| Random windows / 0 B | 96 B | 16.758 | 464.235 |
| Random windows / 16 B | 56 B | 14.299 | 228.842 |
| Random windows / 16 B | 64 B | 15.723 | 312.608 |
| Sequential / 0 B | 64 B | 13.340 | 33.162 |
| Fully random / 0 B | 64 B | 22.533 | 983.741 |

The 56→64 B increase recurs at both offsets and is consistent with the prior 64 B candidate. Miss counts continue increasing above 64 B, and the access-order controls differ strongly. The randomized-window kernel still traverses sequentially within windows; prefetching was not disabled. Thus this supports spatial reuse visible in L1 but does not uniquely prove a 64 B line or independently identify every deeper level's line size.

The same existing PMU C++ implementation was used without changes. It retains Phase-I pointer construction and the timed loop, while the inherited PMU workflow moves formatted per-sample output to a prefaulted raw-tick vector and postmeasurement binary output. These I/O, allocation and compiled-layout differences are not a bit-for-bit Phase-I replay. All 12 points match existing timing-only summaries; the graph retains those baselines.

Working mappings reported base pages before and after every measurement. There was 1 minor fault, zero major faults, 237 involuntary switches, maximum sibling busy of 13.758%, and maximum decile-median ratio 1.100. Preflight CPU 0 activity was 90%, which subsided during measurement; it is retained in the environment record. User-mode counters include C++ stack/helper loads and normalize by `1,000,000 * 1024` chain loads. TSC units include `-O0` loop/timer overhead and are not calibrated core cycles.

- [Raw data and manifest](../../../data/charnwood/line_size01/)
- [Full statistics and Phase-I medians](summary.csv), [PMU counts](pmu_counts.csv)
- [Validation](validation.json), [quality](quality.json), [temporal medians](temporal_medians.csv)
- [Comparison figure](figures/line_size_pmu_validation.png) / [PDF](figures/line_size_pmu_validation.pdf)
- [Distribution figure](figures/latency_boxplots.pdf)
- [Section 8.3 system/vendor comparison](../../../../results/charnwood/REPORT.md)
