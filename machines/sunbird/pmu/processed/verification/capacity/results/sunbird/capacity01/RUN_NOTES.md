# Sunbird capacity PMU verification

`capacity01` completed 14 unchanged workloads × 2 event passes = 28 million timed batches
in 260.79 seconds, 2026-09-14T15:42:50.535127+00:00 to 2026-09-14T15:47:11.326410+00:00.
Each pass saves one million acquisition-order uint64 intervals; each batch has 256 dependent
loads. CPU 32/node 0, 64 B pointer spacing, random traversal, seed 59202 and complete THP
backing match the selected frozen Phase-I workloads. The capacity kernel is unchanged from
the existing PMU version; the PMU helper accepts smaller pinned event groups.

The two pass medians and counters are separate observations. A blank event in summary.csv
means **not measured in that pass**, not zero. The largest median ratio between passes is
1.00538. Counters cover the calling thread's entire user-mode sample loop, including helper
loads; rates are per 1,000 known chain loads, not exact probabilities. L3 miss does not prove
local DRAM service. All timings are TSC ticks per dependent load.

| Region | Footprint | Frozen timing median | PMU median, L1/L2 pass | PMU median, L3/loads pass | L1 miss/1000 | L2 miss/1000 | L3 miss/1000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| L1 | 32 KiB | 4.445 | 4.594 | 4.594 | 54.398 | 0.008 | 0.004 |
| L1 | 36 KiB | 11.688 | 11.688 | 11.625 | 940.854 | 0.016 | 0.010 |
| L1 | 40 KiB | 12.094 | 12.094 | 12.125 | 990.449 | 0.017 | 0.011 |
| L1 | 48 KiB | 12.125 | 12.156 | 12.156 | 997.300 | 0.019 | 0.018 |
| L1 | 64 KiB | 12.141 | 12.141 | 12.141 | 998.077 | 0.024 | 0.018 |
| L2 | 256 KiB | 12.969 | 12.578 | 12.531 | 999.769 | 25.767 | 0.001 |
| L2 | 288 KiB | 41.516 | 41.625 | 41.641 | 1000.519 | 993.773 | 0.036 |
| L2 | 384 KiB | 41.688 | 41.734 | 41.734 | 1000.578 | 999.093 | 0.030 |
| L2 | 512 KiB | 41.688 | 41.672 | 41.672 | 1000.331 | 998.846 | 0.022 |
| LLC | 16 MiB | 41.719 | 41.781 | 41.781 | 1000.681 | 1000.309 | 0.743 |
| LLC | 28 MiB | 49.953 | 202.703 | 201.844 | 1000.992 | 1000.588 | 986.460 |
| LLC | 40 MiB | 156.375 | 203.766 | 204.266 | 1000.983 | 1000.597 | 999.078 |
| LLC | 52 MiB | 194.938 | 203.906 | 203.906 | 1001.138 | 1000.681 | 999.415 |
| LLC | 64 MiB | 202.188 | 204.969 | 205.547 | 1000.967 | 1000.581 | 999.630 |

The L1 rise at 32–36 KiB and L2 rise at 256–288 KiB agree with the frozen timing transitions.
L1 misses are already nonzero at exactly 32 KiB; fitting the nominal data capacity does not
reserve every cache way for the chain. This observation is consistent with helper/cache
competition but does not identify a unique cause.

The LLC result differs materially from Phase I. At 28 MiB, median time changes from 49.953
in the frozen seed-59202 run to 201.844 in the L3-counting pass, with 986.460 L3 misses per
1,000 chain loads. At 16 MiB the corresponding L3 rate is only 0.743. The current effective
transition is therefore sampled between 16 and 28 MiB, earlier than the old broad transition.
This is not an estimate of the physical LLC size: the system reports 30 MiB per socket.
Several other logical CPUs on this socket were 100% busy in a contemporaneous activity
snapshot. Shared-cache interference, placement/allocation and run state are plausible causes;
this run does not isolate them or establish that PMU instrumentation alone caused the shift.
The original Phase-I inference explicitly left nominal LLC capacity unresolved.

All 28 groups have `time_enabled_ns == time_running_ns > 0`; raw hashes, lengths and
statistics were independently recomputed. Both mapping observations in every worker show
complete THP backing and memory on node 0. The measurement regions recorded zero page faults,
zero voluntary switches, and 74 involuntary switches. CPU 8, the SMT sibling, had 0% recorded
average busy time during every worker. At 32 KiB in the L1/L2 pass, consecutive-block median
max/min is 1.33562; this variability is retained, as are every raw sample and outlier. Integrity
checks do not certify an uncontended machine.

- [Timing/counter comparison](figures/capacity_pmu_validation.png) and [PDF](figures/capacity_pmu_validation.pdf)
- [All-pass distributions](figures/latency_boxplots.png), [temporal stability](figures/temporal_stability.png)
- [Statistics](summary.csv), [counts](pmu_counts.csv), [quality](quality.json), [validation](validation.json)
- [Raw data and manifest](../../../data/sunbird/capacity01/)
- [Cross-experiment comparison and provenance](../../../../common/results/sunbird/RUN_NOTES.md)

Recompute with `python capacity/scripts/analyze_capacity.py --machine sunbird --run-id capacity01`
from `PMU-verification`, using the Python environment and PATH in the cross-experiment notes.
Use a new run ID for any future collection. No formal retry was needed.
