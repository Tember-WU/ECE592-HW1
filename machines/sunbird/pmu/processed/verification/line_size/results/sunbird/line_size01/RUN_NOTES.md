# Sunbird line_size PMU verification

`line_size01` completed 12 selected workloads × 2 event passes = 24 million timed batches,
2026-09-14T15:47:35.882930+00:00 to 2026-09-14T15:51:29.508901+00:00, in 233.63 seconds.
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

The footprint is 256 KiB, grouping window 512 B, batch 1024, warm-up 1000; seeds
701/711/721/731 match the original initial/dense/fully-random/sequential sweeps.
The timer denominator is 1024 loads per batch. Counter rates divide by 1,024,000,000
known chain loads; helper/stack loads are included in PMU totals.

| Mode | Stride B | Offset B | Frozen median | L1/L2 pass median | L3/loads pass median | L1 miss/1000 | L2 miss/1000 | L3 miss/1000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fully_random | 64 | 0 | 32.574 | 25.188 | 36.723 | 1000.837 | 280.900 | 0.154 |
| random_lines | 32 | 0 | 12.598 | 12.316 | 12.855 | 81.935 | 16.315 | 0.001 |
| random_lines | 56 | 0 | 16.625 | 16.949 | 16.828 | 230.820 | 40.067 | 0.002 |
| random_lines | 64 | 0 | 19.535 | 18.387 | 18.180 | 267.645 | 47.017 | 0.008 |
| random_lines | 72 | 0 | 20.207 | 19.641 | 19.031 | 281.029 | 59.680 | 0.003 |
| random_lines | 96 | 0 | 19.773 | 19.301 | 18.352 | 372.408 | 68.014 | 0.002 |
| random_lines | 56 | 16 | 16.852 | 15.984 | 16.766 | 235.861 | 28.512 | 0.002 |
| random_lines | 64 | 16 | 20.273 | 18.824 | 19.777 | 261.272 | 48.270 | 0.001 |
| random_lines | 72 | 16 | 19.648 | 18.980 | 18.871 | 282.626 | 54.502 | 0.002 |
| sequential_lines | 56 | 0 | 10.852 | 10.859 | 10.883 | 24.303 | 0.375 | 0.000 |
| sequential_lines | 64 | 0 | 16.219 | 15.785 | 15.488 | 33.238 | 0.775 | 0.001 |
| sequential_lines | 72 | 0 | 16.203 | 15.805 | 16.004 | 30.705 | 3.802 | 0.000 |

Random-window timing rises through 32–64 B and is broadly similar at 64–96 B. However,
L1 misses continue to rise (about 268 at 64 B and 372 at 96 B) instead of forming a clean
one-miss-per-load plateau. At 64 B, sequential/random-window/fully-random L1 rates are
33.238 / 267.645 / 1000.837 per 1,000 loads. This demonstrates strong access-order and
spatial-reuse effects; prefetching is a plausible contributor but was not disabled or isolated.
The result is compatible with the frozen approximately 64 B interpretation and the system's
64 B line size, but does **not independently establish an exact 64 B line size from PMU**,
especially for deeper levels.

The fully-random 64 B point differs between passes: 25.1875 versus 36.7227 ticks/load
(max/min 1.45797), despite stable medians within each pass. These separate-run observations
must not be pooled or treated as the same instantaneous cache state. Allocation/physical
layout, translation, execution frequency and shared-machine state are possible contributors;
the data does not isolate one cause. Total retired load uops are about 5.024 per known
chain load, reflecting the preserved `-O0` helper/loop overhead.

All mappings used base pages before and after measurement. Three minor faults were recorded
in `random_s56_a16__l1_l2`; none were removed. Major faults were zero. The recorded
consecutive-block median max/min stayed below 1.005 for all 24 passes. During this collection,
one read-only Phase-I hash audit also read the original files and snapshots; session tooling
was not isolated from the measurement socket. The subsequent final audit ran after all
measurements. See the auxiliary-activity record linked by the cross-experiment notes.

Measurement regions recorded 64 involuntary context switches.
The SMT sibling CPU 8 had 0% recorded average busy time during all worker processes.
These are shared-host measurements, not exclusive-core/socket reservations. All raw samples,
outliers, count JSON, mapping logs and acquisition commands are retained. Analysis verified
hashes, dimensions, event encodings, denominators, full counter scheduling and recomputed
statistics. No formal collection retry was needed.

- [Timing and PMU evidence](figures/line_size_pmu_validation.png) / [PDF](figures/line_size_pmu_validation.pdf)
- [Distributions for both passes](figures/latency_boxplots.png) / [PDF](figures/latency_boxplots.pdf)
- [Statistics](summary.csv), [counts](pmu_counts.csv), [quality](quality.json), [validation](validation.json)
- [Raw files, mappings and manifest](../../../data/sunbird/line_size01/)
- [Full comparison, pass differences and provenance](../../../../common/results/sunbird/RUN_NOTES.md)

Recompute with `python line_size/scripts/analyze_line_size.py --machine sunbird --run-id line_size01`
from `PMU-verification`, using the Python environment in the full run notes.
