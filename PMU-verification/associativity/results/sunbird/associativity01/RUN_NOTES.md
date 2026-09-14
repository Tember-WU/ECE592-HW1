# Sunbird associativity PMU verification

`associativity01` completed 12 selected workloads × 2 event passes = 24 million timed batches,
2026-09-14T15:51:46.705210+00:00 to 2026-09-14T15:52:45.871593+00:00, in 59.17 seconds.
Each pass retains one million acquisition-order raw timer intervals and its own statistics.
L1/L2 misses are counted in `l1_l2`; L3 misses and total retired load uops in `l3_loads`.
Counters from different passes are separate observations; blank summary fields are unmeasured,
not zero. Both pairs were pinned and fully scheduled for every completed pass.

CPU 32/node 0 was used. The frozen Phase-I pinning record used CPU 4/node 0, which was occupied
at preparation; this changes the physical core but preserves the socket and NUMA node.
The timer and pointer-order construction follow the existing PMU implementation. The recorded
seeds, batch and layout parameters match the corresponding frozen timing-only points. As in
Artemisia's PMU workflow, output is buffered outside measurement; this and stack/layout state
limit bit-for-bit timing comparability with Phase I. No Phase-I file was changed.

Selected K values are 6,7,8,9,10,12 at both 4 KiB (`num_sets=64`) and 32 KiB
(`num_sets=512`) candidate spacings, with line-size parameter 64 B, `max_k=16`, seed 701,
requested batch 128 and warm-up 1000. There are no new K extension points.

Each timed interval actually contains **129 dependent loads**: one initial dereference
and 128 further dereferences. The frozen median below is rescaled by 128/129; the original
file is retained unchanged, and `legacy_median` preserves the old divisor. Counters include
K−1 preparation loads, so their denominator is **1,000,000 × (K+128)**. They also include
helper/stack loads, and are not per-target eviction probabilities.

| Candidate spacing | K | Frozen median (corrected divisor) | L1/L2 pass median | L3/loads pass median | L1 miss/1000 | L2 miss/1000 | L3 miss/1000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 4 KiB | 6 | 10.760 | 10.760 | 10.760 | 0.053 | 0.014 | 0.011 |
| 4 KiB | 7 | 10.760 | 10.760 | 10.760 | 0.068 | 0.015 | 0.010 |
| 4 KiB | 8 | 10.760 | 10.760 | 10.791 | 0.639 | 0.014 | 0.011 |
| 4 KiB | 9 | 15.721 | 13.922 | 13.271 | 429.279 | 0.018 | 0.013 |
| 4 KiB | 10 | 17.643 | 17.705 | 17.705 | 942.295 | 0.022 | 0.016 |
| 4 KiB | 12 | 17.643 | 17.705 | 17.364 | 943.291 | 0.022 | 0.016 |
| 32 KiB | 6 | 10.760 | 10.760 | 10.760 | 0.095 | 0.016 | 0.011 |
| 32 KiB | 7 | 10.729 | 10.760 | 10.760 | 0.068 | 0.019 | 0.011 |
| 32 KiB | 8 | 10.760 | 10.760 | 10.760 | 0.630 | 0.062 | 0.013 |
| 32 KiB | 9 | 36.186 | 41.054 | 41.178 | 820.438 | 813.244 | 0.038 |
| 32 KiB | 10 | 51.659 | 48.496 | 46.667 | 942.457 | 942.035 | 0.025 |
| 32 KiB | 12 | 50.791 | 48.186 | 48.186 | 943.264 | 942.871 | 0.089 |

At 4 KiB spacing, L1 misses increase from 0.639 at K=8 to 429.279 at K=9 and 942.295
at K=10, while L2 misses remain around 0.02. This identifies the onset as an **L1 conflict**,
consistent with an effective 8-way boundary in the tested layout. The frozen automatic
selection instead reported 9 ways because its largest thresholded eviction-probability
jump was K=9→10. Partial conflict was already present at K=9; choosing the largest jump
can therefore overestimate the associativity. The frozen result is preserved and the
one-way (+12.5% against system-reported 8 ways) disagreement is explicitly recorded.

At 32 KiB spacing, L2 misses increase from 0.062 at K=8 to 813.244 at K=9 and 942.035
at K=10. L1 also misses, while L3 misses remain low. This supports the frozen L2 effective
8-way threshold. Address spacing alone is not proof of a physical set mapping or every
set's replacement policy. LLC associativity was not tested.

Twenty-three passes had 2 MiB THP backing. **`L1_k9__l3_loads` had base-page backing**,
whereas the matching L1/L2 pass had 2 MiB THP. Both were stable within their own run and
used the same original mmap/MADV_HUGEPAGE policy, which does not require successful THP
allocation. This pair has different observed page backing and must not be treated as a
strictly identical memory realization. Its medians are 13.9225 versus 13.2713; the
L1-conflict conclusion above uses the full-THP L1/L2 pass and is not inferred by combining
its timing with the other pass's counts. No page fallback was imposed or hidden, and the
original output remains available. Minor and major faults were zero across all 24 passes.

Measurement regions recorded 26 involuntary context switches.
The SMT sibling CPU 8 had 0% recorded average busy time during all worker processes.
These are shared-host measurements, not exclusive-core/socket reservations. All raw samples,
outliers, count JSON, mapping logs and acquisition commands are retained. Analysis verified
hashes, dimensions, event encodings, denominators, full counter scheduling and recomputed
statistics. No formal collection retry was needed.

- [Timing and PMU evidence](figures/associativity_pmu_validation.png) / [PDF](figures/associativity_pmu_validation.pdf)
- [Distributions for both passes](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Statistics](summary.csv), [counts](pmu_counts.csv), [quality](quality.json), [validation](validation.json)
- [Raw files, mappings and manifest](../../../data/sunbird/associativity01/)
- [Full comparison, pass differences and provenance](../../../../common/results/sunbird/RUN_NOTES.md)

Recompute with `python associativity/scripts/analyze_associativity.py --machine sunbird --run-id associativity01`
from `PMU-verification`, using the Python environment in the full run notes.
