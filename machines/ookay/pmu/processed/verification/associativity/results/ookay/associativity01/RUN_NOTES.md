# Ookay associativity01

Completed on 2026-09-14T15:35:15.964836+00:00 through 2026-09-14T15:35:30.519571+00:00 (UTC). 12 configurations, 1,000,000 measured workload repetitions each; total 12,000,000 acquisition-order timing intervals. Collection elapsed 14.555 seconds, excluding final analysis. Runs were collected serially.

The 4 KiB-spaced K8→9 transition supports the L1 8-way threshold. The original L2 candidate uses 16 KiB spacing: its K8→9 transition is also L1, while L2 misses increase at K16→17→18. K17/18 are new Phase-II extension points without old baselines. Do not interpret this layout threshold as physical 16-way L2. All mappings retained 2 MiB THP backing.

## Method and evidence

Worker CPU 4, NUMA node 0; collector CPU 1. See the [effective configuration](../../../data/ookay/associativity01/config.json), [collection manifest and exact commands](../../../data/ookay/associativity01/manifest.json), and [raw data directory](../../../data/ookay/associativity01/). Original Phase-I files were frozen before event discovery/system lookup and remained unchanged.

All four per-thread user-mode events were scheduled simultaneously with time_enabled == time_running; no multiplexing or scaling. Counts include helper loads as well as known dependent-chain loads. Normalized misses are events per 1,000 known chain loads, not exact per-target miss probabilities. TSC ticks include original timer/loop overhead and are not calibrated core cycles. For associativity the actual timed batch is 129 loads and the counted preparation-plus-chain denominator is samples*(K+128); old plotted medians are multiplied by 128/129.

[summary.csv](summary.csv), [pmu_counts.csv](pmu_counts.csv), [temporal_medians.csv](temporal_medians.csv), and [PNG/PDF figures](figures/) contain the numerical evidence. All samples and outliers are retained. Final analysis recomputed statistics from raw data and validated hashes, lengths and load denominators: **passed**.

## Quality limits

| Metric | Observed |
|---|---:|
| Maximum ten-decile median max/min | 1.006441 (L2_candidate_k17) |
| Maximum SMT sibling busy percentage | 8.108% |
| Minor / major faults during measurement | 0 / 0 |
| Involuntary context switches | 8 |

Full [quality.json](quality.json) and [validation.json](validation.json) distinguish integrity from interference. Host governor, Turbo, prefetch and global page/perf settings were not changed. Shared-machine effects remain possible.

See the [Section 8.3 report](../../../../results/ookay/SECTION_8_3_REPORT.md) for frozen timing inferences, PMU evidence, system/vendor values with sources/pages, and disagreements. Use a fresh run ID for another collection; analysis can be repeated using the existing raw files.
