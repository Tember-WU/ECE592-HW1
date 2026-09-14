# Artemisia line size PMU verification: line_size01

Completed 12 configurations, each with 1,000,000 timed batches after warm-up, in 110.38 seconds. Collection ran from 2026-09-14T15:03:52.592325+00:00 to 2026-09-14T15:05:42.976263+00:00. All four events were measured simultaneously in user mode without multiplexing.

## Main finding

**The timing and L1 miss curve support approximately 64 B spatial granularity visible in L1.** The below-boundary points retain spatial reuse; at 64 B and above the median and L1 miss count plateau. L2/L3 misses remain negligible for this 256 KiB workload. This is not an independent line-size measurement for every deeper cache.

| Stride | Median TSC ticks/timed load | L1 misses / 1,000 chain loads |
|---:|---:|---:|
| 32 B | 10.6113 | 498.783 |
| 56 B | 14.8477 | 884.949 |
| 64 B | 16.1211 | 999.744 |
| 72 B | 16.1152 | 1000.434 |
| 96 B | 16.1152 | 999.999 |

At a 32 B stride, approximately half of the chain loads miss L1; at 56 B the miss count is approximately 885 per 1,000; at 64/72/96 B it is approximately 1,000. The 16 B base-offset controls show the same onset. This supports the inferred transfer/spatial-reuse boundary, rather than a new change in working-set capacity.

At 64 B, randomized-window, fully random, and sequential traversals have medians around 16.12, 16.13, and 15.96 ticks/load. The sequential control is slightly faster and has slightly fewer L1 misses. These controls do not prove prefetching is absent. The grouping window is fixed at 512 B, so 64 B is not mechanically imposed as the window size.

## Scope and comparability

The existing pointer-chain construction, timer, footprint, batch, grouping window, seeds, and selected strides/offsets were retained. Formatting/output moved outside the counting loop into one final binary write; samples are stored in prefaulted memory. Allocation uses posix_memalign while retaining the original allocation alignment. The original run used CPU 4/node 0, while this validation uses CPU 32/node 1 because CPU 4 was occupied. Absolute timing differences are not solely attributable to enabling PMU counting.

The mapping containing the workload used base pages before and after every point. Each point times 1,024 dependent chain loads per sample; normalization uses 1,024,000,000 known chain loads. Counters also include helper/stack loads, which explains counts slightly above 1,000 misses per 1,000 chain loads. Do not relabel these values as exact miss probabilities.

## Quality and evidence

CPU 32 and its actual SMT sibling CPU 88 were idle in the short preflight; CPU 88 remained at 0% recorded average busy time throughout the points. This run recorded 41 involuntary switches and zero minor/major page faults or voluntary switches during the measured loops. These records do not establish exclusive access to shared caches or memory. The old pinning manifest incorrectly stated there was no SMT sibling; the new environment records the observed topology.

All raw timing and count hashes/lengths were verified, full statistics and temporal medians were recomputed, and every counter group had equal enabled/running times. Five functional checks passed, including both live kernels and rejection of invalid normalization/multiplexing. Timing units are TSC ticks per timed chain load, including the existing timer/loop overhead; they are not calibrated core cycles.

- [PMU comparison figure](figures/line_size_pmu_validation.png) / [PDF](figures/line_size_pmu_validation.pdf)
- [Timing distributions](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Full statistics](summary.csv), [raw/normalized PMU counts](pmu_counts.csv), [temporal medians](temporal_medians.csv)
- [Quality](quality.json), [validation](validation.json)

All sample arrays, per-point count JSON, effective configuration, commands, build logs, and environment remain in the matching data directory. System/vendor reference comparison is a separate remaining Section 8.3 task.
