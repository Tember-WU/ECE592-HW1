# Ookay line_size02

Completed on 2026-09-14T15:41:53.081708+00:00 through 2026-09-14T15:42:48.537484+00:00 (UTC). 12 configurations, 1,000,000 measured workload repetitions each; total 12,000,000 acquisition-order timing intervals. Collection elapsed 55.456 seconds, excluding final analysis. Runs were collected serially.

A complete repeat of line_size01 with the same config/order/placement, triggered by its temporal instability. The 32 B point stabilized, but random 56/72 B now show about 20.5%/21.2% decile-median spread and sibling activity reached 31.99%. Miss-versus-stride and traversal-control differences reproduce qualitatively; the timing plateau is not robust. Both whole runs are retained separately; no best-point mixture is formed. Base-page backing was observed. Collection finished all 12 points with exit code 0 per worker. The initial collection-plus-analysis shell later returned 143; final analysis was rerun successfully from the complete raw data, with a separate analysis-final.log.

## Method and evidence

Worker CPU 4, NUMA node 0; collector CPU 1. See the [effective configuration](../../../data/ookay/line_size02/config.json), [collection manifest and exact commands](../../../data/ookay/line_size02/manifest.json), and [raw data directory](../../../data/ookay/line_size02/). Original Phase-I files were frozen before event discovery/system lookup and remained unchanged.

All four per-thread user-mode events were scheduled simultaneously with time_enabled == time_running; no multiplexing or scaling. Counts include helper loads as well as known dependent-chain loads. Normalized misses are events per 1,000 known chain loads, not exact per-target miss probabilities. TSC ticks include original timer/loop overhead and are not calibrated core cycles. For associativity the actual timed batch is 129 loads and the counted preparation-plus-chain denominator is samples*(K+128); old plotted medians are multiplied by 128/129.

[summary.csv](summary.csv), [pmu_counts.csv](pmu_counts.csv), [temporal_medians.csv](temporal_medians.csv), and [PNG/PDF figures](figures/) contain the numerical evidence. All samples and outliers are retained. Final analysis recomputed statistics from raw data and validated hashes, lengths and load denominators: **passed**.

## Quality limits

| Metric | Observed |
|---|---:|
| Maximum ten-decile median max/min | 1.211568 (random_s72_a0) |
| Maximum SMT sibling busy percentage | 31.991% |
| Minor / major faults during measurement | 31 / 0 |
| Involuntary context switches | 32 |

Full [quality.json](quality.json) and [validation.json](validation.json) distinguish integrity from interference. Host governor, Turbo, prefetch and global page/perf settings were not changed. Shared-machine effects remain possible.

See the [Section 8.3 report](../../../../results/ookay/SECTION_8_3_REPORT.md) for frozen timing inferences, PMU evidence, system/vendor values with sources/pages, and disagreements. Use a fresh run ID for another collection; analysis can be repeated using the existing raw files.
