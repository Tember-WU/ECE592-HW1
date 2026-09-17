# Charnwood associativity PMU verification: associativity01

Completed 2026-09-14, 15:42:10–15:42:28 UTC, after line_size01: **12 points, 1,000,000 timed batches each**, all four-event groups fully scheduled. Collection took 17.31 seconds including setup and compression.

CPU 4 / NUMA node 0 and the original selected Charnwood conflict candidates were retained: L1 candidate 64 sets × 64 B = 4 KiB spacing, K=6/7/8/9/10; L2-labeled candidate 256 sets × 64 B = 16 KiB spacing, K=7/8/9/10/16/17/18. Seed 701, original `mt19937(seed + K*100)` shuffle, warmup 1000, and requested batch 128 are unchanged. The existing Artemisia PMU benchmark C++ source was reused without edits. K=17/18 are explicitly new extension points beyond the old K≤16 sweep; they have no Phase-I timing baseline.

| Spacing / K | Median ticks / timed load | L1 misses / 1,000 chain loads | L2 misses / 1,000 chain loads |
|---|---|---|---|
| 4 KiB / 8 | 9.752 | 2.818 | 0.010 |
| 4 KiB / 9 | 14.791 | 978.373 | 0.011 |
| 16 KiB / 8 | 8.496 | 1.983 | 0.009 |
| 16 KiB / 9 | 14.760 | 980.378 | 0.013 |
| 16 KiB / 16 | 14.574 | 997.946 | 0.245 |
| 16 KiB / 17 | 20.465 | 968.710 | 181.700 |
| 16 KiB / 18 | 23.256 | 969.112 | 296.243 |

Both K=8→9 transitions are L1 miss transitions; the original L2-labeled 8-way inference is not supported. L2 misses rise at K=16→17 in the tested 16 KiB layout. That is an effective address-count threshold, not a direct measurement of 16 physical ways. The [system comparison](../../../../results/charnwood/REPORT.md) explains its compatibility with four ways spread over multiple sets and the disagreement with the original inference. LLC associativity was not tested.

The timed loop performs **129 chain loads** (one initial load plus 128 loop loads); statistics divide by 129. The original displayed medians divided by 128, so comparison values are transparently multiplied by 128/129 without modifying old data. PMU scope also includes K−1 preparation loads, giving denominator `1,000,000 * (K + 128)`. C++ helper/stack loads are counted as well. Raw legacy summaries and the original divisor remain available. Calibration, warmup, sorting and output are outside PMU counting; the inherited prefaulted output-buffer/single-K-process implementation can affect absolute timing.

Every mapping reported 2048 KiB THP both before and after measurement. Zero minor/major faults, 55 involuntary switches, maximum sibling busy 14.634%. L1 K=8 has decile-median max/min 1.368: its elevated timing relative to Phase I does not coincide with a large miss count, so it is not evidence of a new cache threshold. CPU 0 is CPU 4's SMT sibling; the old no-SMT metadata statement is not relied upon. All samples and outliers were retained. Timing uses TSC ticks including loop/timer overhead, not calibrated core cycles.

- [Raw data, manifest, legacy summaries](../../../data/charnwood/associativity01/)
- [Statistics and corrected Phase-I medians](summary.csv), [PMU counts](pmu_counts.csv)
- [Validation](validation.json), [quality](quality.json), [temporal medians](temporal_medians.csv)
- [Timing/PMU figure](figures/associativity_pmu_validation.png) / [PDF](figures/associativity_pmu_validation.pdf)
- [Distributions](figures/latency_boxplots.pdf)
