# Upgrade capacity PMU verification: capacity02

All 14 configurations completed, with 1,000,000 timed batches per point. Collection took 26.88 seconds, from 2026-09-14T15:42:16.221947+00:00 to 2026-09-14T15:42:43.101643+00:00. Four user-mode events were counted simultaneously. The complete sequence was capacity → line_size → associativity.

The frozen timing inference was L1D approximately 32 KiB (32–36 KiB transition), L2 approximately 256 KiB (256–288 KiB transition), and an effective LLC transition around 7–8 MiB. The PMU evidence supports the first two boundaries: L1 misses rise from 38.91 to 994.21 per 1,000 chain loads at 32→36 KiB; L2 misses rise from 7.18 to 286.81 at 256→288 KiB.

The LLC result only partly reproduces Phase I. L3 misses rise from 0.59 at 6 MiB to 51.92 at 7 MiB and remain 51.42 at 8 MiB. Median latency rises from 27.04 to approximately 35.3 TSC ticks/load. This is an onset of mixed LLC-missing behavior between 6 and 7 MiB, not a sharp physical-capacity measurement. The older 7→8 MiB timing jump and high 8 MiB median are not reproduced in magnitude. The system reports 12 MiB shared LLC; the workload's effective residency threshold must not be substituted for that physical size. Shared occupancy, the streaming 8 MB timing-output buffer, replacement and address mapping are possible contributors whose individual effects were not isolated.

All fourteen points retained full 2 MiB THP backing and NUMA node 0 placement before and after measurement. CPU 2 was used throughout. The failed capacity01 attempt stopped at its first MADV_COLLAPSE call, before valid timing or PMU output. Its logs and executable/source snapshot are retained. A temporary process-private 1 GiB base-page allocation was touched and released, then capacity02 completed unchanged. No machine-wide memory or PMU setting was changed.

Counts are per-thread user-mode totals over the million-batch loop. Each sample times 256 dependent loads, so each denominator is 256,000,000 chain loads. Retired loads were 1,061.11–1,062.39 per 1,000 chain loads: helper/outer-loop loads are included, so miss counts are not exact per-target probabilities. Timing is TSC ticks/load with timer overhead retained.

## Measured points

| Region | Working set | Median TSC ticks/load | Relevant misses / 1,000 chain loads |
|---|---:|---:|---:|
| L1 | 32 KiB | 3.1719 | 38.9125 |
| L1 | 36 KiB | 8.4531 | 994.2104 |
| L1 | 40 KiB | 8.4727 | 996.8450 |
| L1 | 48 KiB | 8.5898 | 998.3579 |
| L1 | 64 KiB | 8.4727 | 1001.3088 |
| L2 | 256 KiB | 8.6484 | 7.1785 |
| L2 | 288 KiB | 13.9336 | 286.8052 |
| L2 | 384 KiB | 20.8672 | 646.4945 |
| L2 | 512 KiB | 22.4727 | 729.0681 |
| LLC | 4 MiB | 26.8984 | 0.3504 |
| LLC | 5 MiB | 27.2852 | 0.6251 |
| LLC | 6 MiB | 27.0391 | 0.5902 |
| LLC | 7 MiB | 35.3281 | 51.9206 |
| LLC | 8 MiB | 35.2227 | 51.4240 |

## Quality and preserved evidence

All raw-array lengths, SHA-256 hashes, counter denominators and recomputed statistics passed validation. Every pinned counter group had equal enabled/running time; no multiplex scaling was applied. Measurement logged zero minor and major faults, 153 involuntary context switches, and at most 1.37% average SMT-sibling activity. The largest ten-block median max/min ratio was 1.1042. Shared LLC/memory contention and frequency variation remain possible; these integrity checks do not prove isolation.

- [Timing/PMU comparison PNG](figures/capacity_pmu_validation.png) / [PDF](figures/capacity_pmu_validation.pdf)
- [Distribution PNG](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Full statistics](summary.csv), [raw/normalized counts](pmu_counts.csv), [temporal medians](temporal_medians.csv), [quality](quality.json), [validation](validation.json)
- [Run manifest](../../../data/upgrade/capacity02/manifest.json), [source/executable provenance](../../../data/upgrade/capacity02/source_provenance.json), [functional checks](../../../data/upgrade/capacity02/check.log)
- [Upgrade report and system/vendor comparison](../../../../reports/upgrade/README.md)

The data directory also retains compressed acquisition-order timing arrays, individual PMU JSON files, worker commands, effective configuration, build log, environment, source copies, executable and disassembly.
