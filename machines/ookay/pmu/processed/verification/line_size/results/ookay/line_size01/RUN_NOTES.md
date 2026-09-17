# Ookay line_size01

Completed on 2026-09-14T15:34:18.209081+00:00 through 2026-09-14T15:35:13.480972+00:00 (UTC). 12 configurations, 1,000,000 measured workload repetitions each; total 12,000,000 acquisition-order timing intervals. Collection elapsed 55.272 seconds, excluding final analysis. Runs were collected serially.

All 12 original stride/control points completed. A roughly 64 B timing plateau is accompanied by continuing L1 miss growth through 96 B, not a clean miss saturation point. Traversal controls differ strongly. The 256 KiB footprint is at this host's L2 capacity boundary. Base-page backing was observed. Temporal drift at random_s32_a0 and sibling activity motivated a complete line_size02 repeat; this run remains intact.

## Method and evidence

Worker CPU 4, NUMA node 0; collector CPU 1. See the [effective configuration](../../../data/ookay/line_size01/config.json), [collection manifest and exact commands](../../../data/ookay/line_size01/manifest.json), and [raw data directory](../../../data/ookay/line_size01/). Original Phase-I files were frozen before event discovery/system lookup and remained unchanged.

All four per-thread user-mode events were scheduled simultaneously with time_enabled == time_running; no multiplexing or scaling. Counts include helper loads as well as known dependent-chain loads. Normalized misses are events per 1,000 known chain loads, not exact per-target miss probabilities. TSC ticks include original timer/loop overhead and are not calibrated core cycles. For associativity the actual timed batch is 129 loads and the counted preparation-plus-chain denominator is samples*(K+128); old plotted medians are multiplied by 128/129.

[summary.csv](summary.csv), [pmu_counts.csv](pmu_counts.csv), [temporal_medians.csv](temporal_medians.csv), and [PNG/PDF figures](figures/) contain the numerical evidence. All samples and outliers are retained. Final analysis recomputed statistics from raw data and validated hashes, lengths and load denominators: **passed**.

## Quality limits

| Metric | Observed |
|---|---:|
| Maximum ten-decile median max/min | 1.165848 (random_s32_a0) |
| Maximum SMT sibling busy percentage | 18.909% |
| Minor / major faults during measurement | 25 / 0 |
| Involuntary context switches | 29 |

Full [quality.json](quality.json) and [validation.json](validation.json) distinguish integrity from interference. Host governor, Turbo, prefetch and global page/perf settings were not changed. Shared-machine effects remain possible.

See the [Section 8.3 report](../../../../results/ookay/SECTION_8_3_REPORT.md) for frozen timing inferences, PMU evidence, system/vendor values with sources/pages, and disagreements. Use a fresh run ID for another collection; analysis can be repeated using the existing raw files.
