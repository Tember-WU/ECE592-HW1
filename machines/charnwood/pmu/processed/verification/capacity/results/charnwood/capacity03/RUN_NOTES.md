# Charnwood capacity PMU verification: capacity03

Completed 2026-09-14, 15:40:17–15:40:59 UTC: **14 points, 1,000,000 timed batches per point**. Four simultaneous user-mode events were fully scheduled for every point. Collection took 42.94 seconds including build, initialization, logging and compression.

The Charnwood Phase-I workload is retained: random dependent chain, 64 B node spacing, seed 59202, batch 256, CPU 3 / NUMA node 0, full THP backing. The representative points are L1 32/36/40/48/64 KiB, L2 256/288/384/512 KiB, and LLC 4/5/6/7/8 MiB. Every point matches exactly one existing Phase-I primary-layout baseline in `combined12`. The original shuffled order is retained using order seed 59283. The C source and timed loop were unchanged.

| Transition | Median TSC ticks / load | Relevant misses / 1,000 chain loads | Interpretation |
|---|---|---|---|
| 32→36 KiB | 11.031→11.180 | L1: 916.034→992.666 | Already many L1 misses at 32 KiB; no clean onset reproduced |
| 256→288 KiB | 11.352→17.742 | L2: 12.609→289.583 | Supports Phase-I L2 onset |
| 6→7→8 MiB | 35.008→59.750→143.352 | L3: 23.058→131.730→495.801 | Growing LLC miss pressure; effective transition, not exact physical capacity |

The 32 and 40 KiB points coincided with CPU 7 sibling busy percentages of 98.889% and 98.925%. This materially limits the L1 conclusion. Across the run there were 2 minor faults, zero major faults, 207 involuntary switches, and a maximum decile-median ratio of 1.258 at 8 MiB. Shared workload and frequency effects were not isolated. All outliers remain in statistics and raw data. An L3 miss does not by itself establish local DRAM service.

`capacity01` and `capacity02` failed before sampling at the first 7 MiB point with `MADV_COLLAPSE: Cannot allocate memory`. Their logs and binaries remain separate. This successful run inherited `MALLOC_TRIM_THRESHOLD_=0` and `MALLOC_MMAP_THRESHOLD_=131072`; the runner additionally permitted up to six attempts only for the exact premeasurement allocation failure, with all failure logs retained. **No point required a retry in capacity03.** No page-policy fallback or timed-kernel modification was used; full backing was checked before and after every measurement. The exact reason allocation later succeeded was not established.

- [Raw data and acquisition manifest](../../../data/charnwood/capacity03/)
- [Statistics](summary.csv), [PMU counts](pmu_counts.csv), [temporal medians](temporal_medians.csv)
- [Validation](validation.json), [quality](quality.json)
- [Timing/PMU comparison](figures/capacity_pmu_validation.png) / [PDF](figures/capacity_pmu_validation.pdf)
- [Distributions](figures/latency_boxplots.pdf), [temporal stability](figures/temporal_stability.pdf)
- [Section 8.3 system/vendor comparison and disagreement analysis](../../../../results/charnwood/REPORT.md)

All timing is TSC ticks per dependent load, not calibrated core cycles. Counter normalization includes known chain loads only in the denominator; numerator counts also see loop/timer helper loads. Integrity/comparability checks passed and do not certify an uncontended cache state.
