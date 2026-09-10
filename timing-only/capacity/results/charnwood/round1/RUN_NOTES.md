# Charnwood round-1 coarse scan

Run `round1` completed all 39 configurations and retained 39,000,000 timed batches (1,000,000 per configuration). Collection started at 2026-09-10T16:52:02.194784+00:00 and finished at 2026-09-10T16:56:03.600832+00:00: 241.406 seconds, approximately 4 minutes 1 second.

The unchanged common round-1 protocol scanned 19 powers-of-two footprints from 2 KiB to 512 MiB, with random and sequential chains plus an empty-timer control. The original C kernel used `-O0`, CPU 3 / NUMA node 0, 64 B spacing, 256 dependent loads per batch, and full transparent-huge-page backing. No cache specifications or PMU measurements were used to select points or interpret capacity.

## Observations and second-round selection

| Candidate | Lower endpoint, TSC ticks/load | Upper endpoint, TSC ticks/load | Round-2 interval |
|---|---:|---:|---|
| L1D | 32 KiB: 6.7734 | 64 KiB: 16.0000 | 32–64 KiB |
| L2 | 256 KiB: 18.4688 | 512 KiB: 45.4141 | 256–512 KiB |
| LLC effective transition | 4 MiB: 57.7109 | 8 MiB: 258.8750 | 4–8 MiB |

These are measured endpoint intervals for further sampling, not exact capacities or confidence intervals. Three cache-residency regions are distinguishable in the random-chain curve. The 16–512 MiB measurements already reach a much slower region, with medians approximately 290–318 TSC ticks/load, so the scan does not need an extension. The empty-timer median is 62 TSC ticks/interval.

The low-footprint medians differ between measurements: 2/8 KiB are approximately 5.4844, while 4/16 KiB are approximately 6.20 TSC ticks/load. Most corresponding within-point temporal medians are stable. This demonstrates between-measurement variation; frequency changes or other causes were not isolated. Round-2 repeats and controls should be considered before interpreting absolute latency.

The [generated round-2 configuration](../../../configs/charnwood-round2.json) records these intervals, their rationale, source-run hashes, and all 57 follow-up configurations.

## Integrity and runtime observations

The analyzer verified all 39 raw-file SHA-256 hashes, sample counts, and positive timing intervals, and recomputed statistics without removing outliers. CPU binding, local NUMA placement, and configured page backing are checked in [validation.json](validation.json).

Measurement intervals recorded zero minor/major page faults and zero voluntary context switches. Involuntary context switches totaled 1,079, ranging from 0 to 136 per configuration. SMT sibling CPU 7's average busy percentage ranged from 0% to 12.5% over benchmark subprocess intervals. This is not a measure of isolation from shared-cache or memory interference.

The 3-second prelaunch observation found CPU 3 1.672% busy and CPU 7 1.003% busy. Other users' benchmark processes were active on the machine. Full observations and collection output are preserved in [preparation](../preparation/). All 39 configurations used complete huge-page backing, including the small footprints whose allocation is rounded to 2 MiB.

## Outputs

- [Capacity curve](figures/capacity_s64_b256_huge.png) / [PDF](figures/capacity_s64_b256_huge.pdf)
- [Per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Statistics](summary.csv), [adjacent comparisons](transitions.csv), [temporal medians](temporal_medians.csv)
- [Validation](validation.json), [analysis provenance](provenance.json)
- [Raw data, logs, source and executable snapshots](../../../data/charnwood/round1/)

This document records the coarse-scan evidence used for planning. Final two-round interpretation is in [combined12/RUN_NOTES.md](../combined12/RUN_NOTES.md).
