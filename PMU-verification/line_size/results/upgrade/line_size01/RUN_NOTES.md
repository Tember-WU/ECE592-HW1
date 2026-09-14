# Upgrade line_size PMU verification: line_size01

All 12 configurations completed, with 1,000,000 timed batches per point. Collection took 51.05 seconds, from 2026-09-14T15:42:46.600562+00:00 to 2026-09-14T15:43:37.654719+00:00. Four user-mode events were counted simultaneously. The complete sequence was capacity → line_size → associativity.

The twelve points retain the original 256 KiB footprint, 512 B grouping window, 1,024 dependent loads per timed batch, 1,000 warm-up batches, traversal seeds, and CPU 4/node 0 placement. The actual SMT sibling is CPU 10; the historical baseline pinning file incorrectly says there is no SMT sibling. That original file is preserved in the freeze and the correction is recorded here.

The result is compatible with the frozen 64 B spatial-granularity candidate but does not establish a clean plateau. For random windows at offset 0, L1 misses per 1,000 chain loads are 110.73, 240.85, 324.57, 338.85 and 479.89 at strides 32, 56, 64, 72 and 96 B. The increase from 56 to 64 B is accompanied by a median rise from 10.50 to 12.01 TSC ticks/load. Offset 16 B produces similar behavior at 56/64/72 B. Misses continue rising at 96 B, so a statement that all strides at or above 64 B plateau would be false.

Traversal order strongly affects the result. At 64 B stride the L1 miss counts are 37.25 for sequential traversal, 324.57 for random windows, and 998.78 for fully random traversal; corresponding medians are 9.80, 12.01 and 17.75. Within-window spatial reuse and prefetching are plausible contributors; prefetchers were not disabled. At this 256 KiB footprint, L2 misses also vary with order (5.84, 63.21 and 338.81 for these controls), so timing changes are not solely an L1 line-size effect. Deeper-level line sizes are system-reported, not separately inferred by this workload.

The existing Artemisia PMU implementation is reused unchanged: the pointer-order construction and timed loop match Phase I, while raw samples are buffered and written after counting rather than formatted inside every sample iteration. This difference, and helper/stack layout, can shift absolute timings. Retired loads were 5,024.96–5,027.25 per 1,000 known chain loads, exposing substantial -O0 helper loads. Each PMU denominator is 1,000,000 × 1,024. Counts are totals for the complete user-mode sample loop, not one reading per sample, and are not pure per-address miss probabilities.

All working mappings used base pages and stayed on NUMA node 0; CPU 4 affinity was verified. Timing units remain TSC ticks per timed chain load, including loop/timer overhead. No outliers were removed.

## Measured points

| Point | Phase-I median¹ | PMU median¹ | L1 misses² | L2 misses² | L3 misses² |
|---|---:|---:|---:|---:|---:|
| fully_random_s64 | 19.0254 | 17.7510 | 998.7818 | 338.8117 | 0.0164 |
| random_s32_a0 | 7.8604 | 7.5703 | 110.7314 | 23.8159 | 0.0003 |
| random_s56_a0 | 10.3457 | 10.4990 | 240.8466 | 35.5960 | 0.0004 |
| random_s64_a0 | 12.3193 | 12.0088 | 324.5716 | 63.2115 | 0.0039 |
| random_s72_a0 | 12.1250 | 12.6758 | 338.8491 | 79.9582 | 0.0009 |
| random_s96_a0 | 13.0264 | 12.8740 | 479.8933 | 86.2397 | 0.0001 |
| random_s56_a16 | 10.9580 | 10.4014 | 237.1848 | 37.2203 | 0.0008 |
| random_s64_a16 | 12.6338 | 11.7861 | 322.0155 | 58.6470 | 0.0003 |
| random_s72_a16 | 12.4414 | 12.8701 | 347.0058 | 83.1705 | 0.0005 |
| sequential_s56 | 8.0527 | 7.8203 | 29.4123 | 6.4318 | 0.0000 |
| sequential_s64 | 10.0498 | 9.8027 | 37.2458 | 5.8351 | 0.0002 |
| sequential_s72 | 10.3516 | 10.1797 | 51.6824 | 9.1281 | 0.0005 |

¹ TSC ticks per timed chain load. ² Per 1,000 counted chain loads, including the disclosed helper-load scope.

## Quality and preserved evidence

All raw-array lengths, SHA-256 hashes, counter denominators and recomputed statistics passed validation. Every pinned counter group had equal enabled/running time; no multiplex scaling was applied. Measurement logged zero minor and major faults, 308 involuntary context switches, and at most 1.00% average SMT-sibling activity. The largest ten-block median max/min ratio was 1.0631. Shared LLC/memory contention and frequency variation remain possible; these integrity checks do not prove isolation.

- [Timing/PMU comparison PNG](figures/line_size_pmu_validation.png) / [PDF](figures/line_size_pmu_validation.pdf)
- [Distribution PNG](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Full statistics](summary.csv), [raw/normalized counts](pmu_counts.csv), [temporal medians](temporal_medians.csv), [quality](quality.json), [validation](validation.json)
- [Run manifest](../../../data/upgrade/line_size01/manifest.json), [source/executable provenance](../../../data/upgrade/line_size01/source_provenance.json), [functional checks](../../../data/upgrade/line_size01/check.log)
- [Upgrade report and system/vendor comparison](../../../../reports/upgrade/README.md)

The data directory also retains compressed acquisition-order timing arrays, individual PMU JSON files, worker commands, effective configuration, build log, environment, source copies, executable and disassembly.
