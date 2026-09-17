# Artemisia associativity PMU verification: associativity02

Completed 12 configurations, each with 1,000,000 timed batches after warm-up, in 30.33 seconds. Collection ran from 2026-09-14T15:02:44.354117+00:00 to 2026-09-14T15:03:14.680360+00:00. All four events were measured simultaneously in user mode without multiplexing.

## Main findings

**L1: the tested conflict cycle supports an effective threshold of 12 ways.** At K=12, L1 miss counts are near zero; at K=13 they increase sharply while L2 miss counts remain near zero.

**The original L2-labeled 12-way inference is not supported by the counters.** The 128 KiB address spacing also causes L1 conflicts. Its K=12 to K=13 timing jump coincides with L1 misses, not L2 misses. A candidate spacing and a latency step alone do not identify the missed cache level.

**The extension supports an L2 threshold near 16 ways for this layout.** L2 misses remain near zero through K=16, then increase at K=17 and K=18. These two points were not present in the original sweep and must be described as new verification measurements.

| Candidate spacing | K | Median TSC ticks/timed load | L1 misses / 1,000 chain loads | L2 misses / 1,000 chain loads |
|---|---:|---:|---:|---:|
| 4 KiB | 10 | 6.2016 | 0.053 | 0.000 |
| 4 KiB | 11 | 6.1860 | 0.073 | 0.000 |
| 4 KiB | 12 | 6.2791 | 0.200 | 0.000 |
| 4 KiB | 13 | 16.7287 | 921.875 | 0.000 |
| 4 KiB | 14 | 16.7287 | 985.889 | 0.000 |
| 128 KiB | 11 | 5.8450 | 5.488 | 0.000 |
| 128 KiB | 12 | 6.7752 | 0.193 | 0.000 |
| 128 KiB | 13 | 16.7132 | 922.005 | 0.000 |
| 128 KiB | 14 | 16.7287 | 985.891 | 0.000 |
| 128 KiB | 16 | 16.7287 | 999.970 | 0.013 |
| 128 KiB | 17 | 26.7752 | 935.772 | 167.907 |
| 128 KiB | 18 | 36.0155 | 981.954 | 329.219 |

For the L2 candidate, L2 misses are approximately 0.013 per 1,000 chain loads at K=16, 167.91 at K=17, and 329.22 at K=18. The corresponding medians are 16.73, 26.78, and 36.02 ticks/timed load. L3 misses remain negligible. This is a gradual increase after the threshold, not a requirement that every K=17 access must miss.

A geometry cross-check is consistent with the existing capacity results: 64 B * 64 candidate sets * 12 ways = 48 KiB for L1, and 64 B * 2,048 candidate sets * 16 ways = 2 MiB for L2. This is a consistency check using the tested candidates, not independent proof of indexing or physical set counts. The results apply to these layouts; no LLC associativity is claimed.

## Correct normalization and limits

Each timed interval has one initial pointer load plus 128 loop loads, for 129 actual timed chain loads. The original summary divided by 128. New statistics use 129, keep the original-divisor value as legacy_median, and rescale the old plotted median by 128/129 for a fair unit comparison. Original timing-only files were not modified.

The PMU counting window also contains K-1 preparation loads per sample. Miss normalization therefore uses 1,000,000 * (K + 128) known chain loads for each point. Stack/helper loads remain in the counters. The original threshold-derived eviction_probability is retained only as legacy output; it is neither a hardware miss probability nor sufficient evidence of an L2 threshold.

The current C++ chain construction and timed loop are retained. Storage is prefaulted and raw ticks are saved in acquisition order before sorting. One K runs per process, and CPU 32/node 1 replaces the occupied CPU 4/node 0. Compiled stack layout and preparation state can differ, so this is not a claim of identical absolute timing. All conflict mappings retained complete 2 MiB THP backing, with 2 MiB allocated for L1 points and 4 MiB for L2-candidate points.

Several below-threshold timing distributions drift within their run: the largest/smallest temporal-block median ratio reaches approximately 1.26. They should not be used as precision L1-latency measurements. The cache-specific counter transitions still separate the L1 conflict threshold from the later L2 onset. No post-hoc sample filtering was performed.

## Earlier failed start

associativity01 failed before collecting any samples because numactl rejected CPU 32 based on the inherited affinity mask. Its failure log and manifest are retained. Switching to taskset followed by numactl allowed the kernel to apply the intended CPU and memory bindings; associativity02 is the complete run used here.

## Quality and evidence

CPU 32 and its actual SMT sibling CPU 88 were idle in the short preflight; CPU 88 remained at 0% recorded average busy time throughout the points. This run recorded 8 involuntary switches and zero minor/major page faults or voluntary switches during the measured loops. These records do not establish exclusive access to shared caches or memory. The old pinning manifest incorrectly stated there was no SMT sibling; the new environment records the observed topology.

All raw timing and count hashes/lengths were verified, full statistics and temporal medians were recomputed, and every counter group had equal enabled/running times. Five functional checks passed, including both live kernels and rejection of invalid normalization/multiplexing. Timing units are TSC ticks per timed chain load, including the existing timer/loop overhead; they are not calibrated core cycles.

- [PMU comparison figure](figures/associativity_pmu_validation.png) / [PDF](figures/associativity_pmu_validation.pdf)
- [Timing distributions](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Full statistics](summary.csv), [raw/normalized PMU counts](pmu_counts.csv), [temporal medians](temporal_medians.csv)
- [Quality](quality.json), [validation](validation.json)

All sample arrays, per-point count JSON, effective configuration, commands, build logs, and environment remain in the matching data directory. System/vendor reference comparison is a separate remaining Section 8.3 task.
