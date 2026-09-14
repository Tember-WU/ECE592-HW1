# Ookay associativity02

Completed on 2026-09-14T15:36:55.200241+00:00 through 2026-09-14T15:37:07.667109+00:00 (UTC). 9 configurations, 1,000,000 measured workload repetitions each; total 9,000,000 acquisition-order timing intervals. Collection elapsed 12.467 seconds, excluding final analysis. Runs were collected serially.

Nine follow-up points revisit the original Phase-I 512/1024 candidate-set layouts (32/64 KiB spacing), selected after initial PMU results and system lookup. Larger spacing exposes L2 pressure earlier, but the 64 KiB K4→5 physical-L2 candidate transition is hidden by L1 hits. This rejects the original 8/9-way L2 labels without claiming a direct isolated measurement of 4 physical ways. All mappings retained 2 MiB THP backing.

## Method and evidence

Worker CPU 4, NUMA node 0; collector CPU 1. See the [effective configuration](../../../data/ookay/associativity02/config.json), [collection manifest and exact commands](../../../data/ookay/associativity02/manifest.json), and [raw data directory](../../../data/ookay/associativity02/). Original Phase-I files were frozen before event discovery/system lookup and remained unchanged.

All four per-thread user-mode events were scheduled simultaneously with time_enabled == time_running; no multiplexing or scaling. Counts include helper loads as well as known dependent-chain loads. Normalized misses are events per 1,000 known chain loads, not exact per-target miss probabilities. TSC ticks include original timer/loop overhead and are not calibrated core cycles. For associativity the actual timed batch is 129 loads and the counted preparation-plus-chain denominator is samples*(K+128); old plotted medians are multiplied by 128/129.

[summary.csv](summary.csv), [pmu_counts.csv](pmu_counts.csv), [temporal_medians.csv](temporal_medians.csv), and [PNG/PDF figures](figures/) contain the numerical evidence. All samples and outliers are retained. Final analysis recomputed statistics from raw data and validated hashes, lengths and load denominators: **passed**.

## Quality limits

| Metric | Observed |
|---|---:|
| Maximum ten-decile median max/min | 1.010710 (L2_sets1024_k9) |
| Maximum SMT sibling busy percentage | 3.125% |
| Minor / major faults during measurement | 0 / 0 |
| Involuntary context switches | 2 |

Full [quality.json](quality.json) and [validation.json](validation.json) distinguish integrity from interference. Host governor, Turbo, prefetch and global page/perf settings were not changed. Shared-machine effects remain possible.

See the [Section 8.3 report](../../../../results/ookay/SECTION_8_3_REPORT.md) for frozen timing inferences, PMU evidence, system/vendor values with sources/pages, and disagreements. Use a fresh run ID for another collection; analysis can be repeated using the existing raw files.
