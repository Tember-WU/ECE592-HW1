# Upgrade associativity PMU verification: associativity01

All 18 configurations completed, with 1,000,000 timed batches per point. Collection took 21.21 seconds, from 2026-09-14T15:43:40.295721+00:00 to 2026-09-14T15:44:01.503712+00:00. Four user-mode events were counted simultaneously. The complete sequence was capacity → line_size → associativity.

The original Upgrade timing-only associativity outputs were absent. Before formal PMU collection or system cache-geometry lookup, the unchanged timing-only benchmark was built locally and the original four candidate sweeps plus boundary repeats were completed on CPU 2/node 0. Their 70 million timed batches, source/executable, logs and plots are retained under timing-only/associativity/data/upgrade and results/upgrade. The results and existing capacity/line-size/latency evidence were then frozen. The automatic candidate labels were retained, including the inconsistent L2 labels; they were not rewritten using the later hardware information.

The PMU run contains the same twelve-point design used on Artemisia, adapted to Upgrade's frozen candidates: five points at 4 KiB spacing (K=6,7,8,9,10), and seven at 16 KiB spacing (K=7,8,9,10,16,17,18). Six extra controls repeat K=8,9,10 at the already measured 32 KiB and 64 KiB candidate spacings. These controls were selected before formal PMU collection to explain disagreements among Phase-I candidates. K=17 and K=18 are bounded extensions beyond the original K≤16 sweep and have no original timing-only comparator.

At 4 KiB spacing, K=8→9 increases the median from 6.37 to 11.49 TSC ticks/timed load and L1 misses from 0.53 to 984.54 per 1,000 counted chain loads; L2 misses remain below 0.001. This supports the L1 eight-address conflict threshold and agrees with the system's eight L1D ways.

At 16 KiB spacing, the frozen L2-labeled K=8→9 edge is actually an L1 transition: L1 misses rise from 0.59 to 984.39 while L2 misses remain about 0.008. The later K=16→17→18 sequence raises L2 misses from 0.13 to 182.64 to 297.13, and medians from 11.28 to 15.68 to 18.09. Thus the original label is rejected as a physical L2-way estimate.

The system later reports L2 as 256 KiB, four ways, 1,024 sets, with 64 B lines. Under the usual simple set-index model, 16 KiB spacing visits four L2 sets, allowing sixteen resident lines across those sets. This conditionally explains the later edge; it does not mean the cache is sixteen-way. L1 residency masks lower-level evictions when K≤8. The 32 KiB control has L2 misses 0.02→94.70→513.08 at K=8→9→10, and the 64 KiB control has 0.38→119.07→865.26. Their timing jumps therefore contain L2 misses, but neither constitutes an unbiased four-way threshold measurement. The set-index explanation is an inference using the separately recorded geometry, not independent proof of address mapping or replacement policy. LLC associativity was not measured.

The kernel still performs 129 timed loads per requested batch of 128, plus K−1 preparation loads. New timing summaries divide by 129; legacy values and the original baseline are preserved, with baseline figures transparently rescaled by 128/129. The PMU denominator is 1,000,000 × (K+128), including preparation. Across all eighteen points there are 2,322,000,000 timed chain loads and 2,483,000,000 counted chain loads. Retired loads were 5,390.31–5,417.89 per 1,000 known chain loads because helper/stack loads are also counted. These are per-loop normalized totals, not exact eviction probabilities.

The existing C++ benchmark is unchanged. The original timing-only summaries sort samples; this PMU runner additionally saves raw ticks in acquisition order. All points retained 2 MiB THP backing and NUMA node 0 placement; CPU 2 affinity was verified. No outliers were removed.

## Measured points

| Point | Phase-I median¹ | PMU median¹ | L1 misses² | L2 misses² | L3 misses² |
|---|---:|---:|---:|---:|---:|
| L1_k6 | 6.6279 | 6.3721 | 0.0153 | 0.0004 | 0.0000 |
| L1_k7 | 6.3953 | 6.3876 | 0.0291 | 0.0004 | 0.0000 |
| L1_k8 | 6.3953 | 6.3721 | 0.5348 | 0.0003 | 0.0001 |
| L1_k9 | 11.2791 | 11.4884 | 984.5411 | 0.0005 | 0.0003 |
| L1_k10 | 11.2480 | 11.2791 | 942.4644 | 0.0005 | 0.0002 |
| L2_candidate_k7 | 6.5271 | 6.4651 | 0.0313 | 0.0014 | 0.0000 |
| L2_candidate_k8 | 6.3566 | 6.4806 | 0.5926 | 0.0007 | 0.0001 |
| L2_candidate_k9 | 11.2946 | 11.5116 | 984.3876 | 0.0081 | 0.0001 |
| L2_candidate_k10 | 11.4496 | 11.3101 | 942.4377 | 0.0073 | 0.0001 |
| L2_candidate_k16 | 11.2791 | 11.2791 | 999.8874 | 0.1263 | 0.0001 |
| L2_candidate_k17 | New extension | 15.6822 | 979.2378 | 182.6393 | 0.0000 |
| L2_candidate_k18 | New extension | 18.0930 | 977.8350 | 297.1287 | 0.0001 |
| L2_sets1024_k8 | 6.3876 | 6.6667 | 0.5133 | 0.3844 | 0.0001 |
| L2_sets1024_k9 | 9.6822 | 9.5581 | 119.7914 | 119.0670 | 0.0000 |
| L2_sets1024_k10 | 32.9457 | 32.8062 | 865.3638 | 865.2589 | 0.0001 |
| L2_sets512_k8 | 6.3721 | 6.4031 | 0.5333 | 0.0245 | 0.0000 |
| L2_sets512_k9 | 9.8527 | 9.6357 | 287.0572 | 94.7039 | 0.0000 |
| L2_sets512_k10 | 23.6511 | 23.4806 | 928.3430 | 513.0842 | 0.0000 |

¹ TSC ticks per timed chain load. ² Per 1,000 counted chain loads, including the disclosed helper-load scope.

## Quality and preserved evidence

All raw-array lengths, SHA-256 hashes, counter denominators and recomputed statistics passed validation. Every pinned counter group had equal enabled/running time; no multiplex scaling was applied. Measurement logged zero minor and major faults, 64 involuntary context switches, and at most 0.76% average SMT-sibling activity. The largest ten-block median max/min ratio was 1.0706. Shared LLC/memory contention and frequency variation remain possible; these integrity checks do not prove isolation.

- [Timing/PMU comparison PNG](figures/associativity_pmu_validation.png) / [PDF](figures/associativity_pmu_validation.pdf)
- [Distribution PNG](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Full statistics](summary.csv), [raw/normalized counts](pmu_counts.csv), [temporal medians](temporal_medians.csv), [quality](quality.json), [validation](validation.json)
- [Run manifest](../../../data/upgrade/associativity01/manifest.json), [source/executable provenance](../../../data/upgrade/associativity01/source_provenance.json), [functional checks](../../../data/upgrade/associativity01/check.log)
- [Upgrade report and system/vendor comparison](../../../../reports/upgrade/README.md)

The data directory also retains compressed acquisition-order timing arrays, individual PMU JSON files, worker commands, effective configuration, build log, environment, source copies, executable and disassembly.
