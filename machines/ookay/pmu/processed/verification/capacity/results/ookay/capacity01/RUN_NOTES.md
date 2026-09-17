# Ookay capacity01

Completed on 2026-09-14T15:33:46.477986+00:00 through 2026-09-14T15:34:14.775708+00:00 (UTC). 14 configurations, 1,000,000 measured workload repetitions each; total 14,000,000 acquisition-order timing intervals. Collection elapsed 28.298 seconds, excluding final analysis. Runs were collected serially.

L1D 32→36 KiB and L2 256→288 KiB timing steps coincide with the corresponding miss increases. The old strong LLC timing transition did not reproduce; L3 misses increase toward 8 MiB, but exact physical LLC capacity is not independently established. All 14 points match the frozen Phase-I workload. Full huge-page backing was verified.

## Method and evidence

Worker CPU 2, NUMA node 0; collector CPU 1. See the [effective configuration](../../../data/ookay/capacity01/config.json), [collection manifest and exact commands](../../../data/ookay/capacity01/manifest.json), and [raw data directory](../../../data/ookay/capacity01/). Original Phase-I files were frozen before event discovery/system lookup and remained unchanged.

All four per-thread user-mode events were scheduled simultaneously with time_enabled == time_running; no multiplexing or scaling. Counts include helper loads as well as known dependent-chain loads. Normalized misses are events per 1,000 known chain loads, not exact per-target miss probabilities. TSC ticks include original timer/loop overhead and are not calibrated core cycles. For associativity the actual timed batch is 129 loads and the counted preparation-plus-chain denominator is samples*(K+128); old plotted medians are multiplied by 128/129.

[summary.csv](summary.csv), [pmu_counts.csv](pmu_counts.csv), [temporal_medians.csv](temporal_medians.csv), and [PNG/PDF figures](figures/) contain the numerical evidence. All samples and outliers are retained. Final analysis recomputed statistics from raw data and validated hashes, lengths and load denominators: **passed**.

## Quality limits

| Metric | Observed |
|---|---:|
| Maximum ten-decile median max/min | 1.039140 (LLC_w8388608) |
| Maximum SMT sibling busy percentage | 0.000% |
| Minor / major faults during measurement | 3 / 0 |
| Involuntary context switches | 18 |

Full [quality.json](quality.json) and [validation.json](validation.json) distinguish integrity from interference. Host governor, Turbo, prefetch and global page/perf settings were not changed. Shared-machine effects remain possible.

See the [Section 8.3 report](../../../../results/ookay/SECTION_8_3_REPORT.md) for frozen timing inferences, PMU evidence, system/vendor values with sources/pages, and disagreements. Use a fresh run ID for another collection; analysis can be repeated using the existing raw files.
