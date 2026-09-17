# Artemisia capacity PMU verification: capacity01

All 14 configurations completed in 226.30 seconds (about 3 minutes 46 seconds), from 2026-09-11T15:31:56.498762+00:00 to 2026-09-11T15:35:42.797812+00:00. Each point contains 1,000,000 timed batches of 256 dependent loads after warm-up: 14,000,000 batches and 3,584,000,000 chain loads in total. Four counters were collected together during each measurement loop.

## Findings

| Region | Working set | Median TSC ticks/load | Relevant misses / 1,000 chain loads |
|---|---:|---:|---:|
| L1 | 32 KiB | 5.1875 | 0.1193 |
| L1 | 44 KiB | 5.2344 | 6.1707 |
| L1 | 48 KiB | 5.9531 | 71.3938 |
| L1 | 52 KiB | 15.9766 | 977.9164 |
| L1 | 64 KiB | 16.0859 | 988.5790 |
| L2 | 2 MiB | 16.5156 | 22.0966 |
| L2 | 2.25 MiB | 34.2188 | 427.1920 |
| L2 | 3 MiB | 59.7656 | 959.6994 |
| L2 | 4 MiB | 62.0938 | 999.8352 |
| LLC | 32 MiB | 265.6953 | 999.7182 |
| LLC | 40 MiB | 264.2344 | 999.7267 |
| LLC | 48 MiB | 262.9219 | 999.7423 |
| LLC | 56 MiB | 263.9922 | 999.7414 |
| LLC | 64 MiB | 263.0938 | 999.7569 |

**L1: supports the approximately 48 KiB timing inference.** From 44 to 48 to 52 KiB, L1 misses rise from 6.17 to 71.39 to 977.92 per 1,000 chain loads, while medians rise from 5.23 to 5.95 to 15.98 ticks/load. This places the sharp change in the same 44–52 KiB neighborhood; these sparse points do not establish an exact byte-level threshold.

**L2: supports an onset near 2 MiB.** At 2 MiB the median is 16.52 ticks/load with 22.10 L2 misses per 1,000 chain loads; at 2.25 MiB it is 34.22 with 427.19 misses; at 3 MiB it is 59.77 with 959.70 misses. This agrees with the earlier 2–2.25 MiB onset interval.

**LLC: this run does not verify the earlier effective transition.** Every 32–64 MiB point has about 999.72–999.76 L3 misses per 1,000 chain loads and a median of 262.92–265.70 ticks/load. The earlier lower-latency region was not reproduced. These points establish predominantly L3-missing behavior for this run, not an exact physical LLC size or a proven pure-DRAM latency. Shared-cache/memory interference and workload residency changes are possible explanations; their causes were not isolated.

## Distribution and interference qualifications

**The 4 MiB point is temporally mixed.** Its median is 62.09 ticks/load, but its P95 is 274.23 and the largest/smallest temporal-block median ratio is 4.41. Its aggregate L3 misses are 148.05 per 1,000 chain loads. Do not describe this point as a stable pure LLC-hit distribution or use its median alone as a latency reference. The main curve shows P05–P95, and the temporal plot exposes the change. The box plot hides individual outlier markers while retaining every sample in the raw data.

The short preflight recorded CPU 32 at 100% busy and SMT sibling CPU 88 at 0%. CPU 88 stayed at 0% recorded average activity during all points. The run recorded 4,910 involuntary context switches, zero minor/major page faults, and zero voluntary switches. CPU activity during collection includes this benchmark and does not measure other-user activity separately. An idle SMT sibling does not exclude shared LLC or memory interference.

All mappings retained complete 2 MiB THP backing before and after measurement and remained on NUMA node 1. The worker remained on CPU 32. No machine-wide configuration was changed.

## Event scope and checks

The selected events were tested individually and as a group in the event-discovery experiment. Their raw encodings were checked against local `perf list --details` immediately before this run. All 14 pinned groups reported equal enabled/running times; no multiplex scaling was used.

Counts cover user-space execution of the million-batch loop, including helper/outer-loop loads. Retired loads measured approximately 1,062.50–1,062.63 per 1,000 chain loads, documenting about 6.25% additional loads. Thus the miss normalization is per known chain load, not an exact per-instruction or conditional cache miss probability. Counts are totals for each point, not a million separate PMU readings.

Five functional checks passed, including a live short counter-group test, rejection of multiplexed or wrongly normalized counts, and preservation of timing outliers. The timed dependency function is unchanged from the capacity implementation. Formal analysis verified all raw timing/count hashes and lengths, recomputed statistics, and matched every comparison point on the original workload parameters. These checks validate data integrity, not isolation of the memory hierarchy.

## Files

- [Capacity timing and PMU comparison](figures/capacity_pmu_validation.png) / [PDF](figures/capacity_pmu_validation.pdf)
- [Timing box plots](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Temporal stability](figures/temporal_stability.png) / [PDF](figures/temporal_stability.pdf)
- [Timing statistics](summary.csv), [raw and normalized PMU counts](pmu_counts.csv), [quality](quality.json), [validation](validation.json)

The matching data directory contains the effective config, raw gzip timing arrays, per-point PMU JSON, exact commands, logs, and environment. This work does not complete the literature/system comparison or the other Section 8.3 properties.
