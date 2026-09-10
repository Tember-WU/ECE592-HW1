# Crux latency: complete seven-group run

Run `latency01-retry2` completed all 30 configurations in **115.28 seconds**
(about 1 minute 55 seconds), from 2026-09-10T20:53:47.524199+00:00 to
2026-09-10T20:55:42.800698+00:00. Each configuration retains 1,000,000
batches after warm-up. Nine paired configurations record two intervals per
batch, giving **39,000,000 recorded timer intervals** in the complete run.
All seven groups, including their alternate footprints and new-seed
repeats, were executed serially in the same shuffled point order as the
Artemisia run.

The existing `configs/crux.json` was used unchanged, with CPU 6 / NUMA node 0.
Its capacity-basis hash matches the previously measured Crux inference.
Resident footprints are 8/16 KiB, 64/128 KiB, and 1/2 MiB. Large-footprint
controls use 256/512 MiB. The exact capacity inference is also preserved as
`../../../data/crux/latency01-retry2/capacity_inference.json`. The source
inference retains its original limitations and disclosure; this latency
run made no new cache-specification queries or PMU measurements.

All latency values below are **TSC ticks per dependent load**, not
validated core cycles. Candidate state labels are timing interpretations,
not verified hardware hit/miss labels for every access.

## Resident candidates

| Group | Address spans | Median range across three processes | Primary P05–P95 |
|---|---|---:|---:|
| l1_hit | 8 KiB, 16 KiB | 2.73047 | 2.71875–2.74219 |
| l2_hit | 64 KiB, 128 KiB | 7.79688 | 7.77344–7.96875 |
| llc_hit | 1 MiB, 2 MiB | 25.77344–27.15625 | 25.25000–27.17969 |

The L1 and L2 medians agree across the alternate footprints and second-seed
repeats, although the L1 repeat has a broader distribution. The LLC primary
and repeat at 1 MiB are 26.20312 and 25.77344; the 2 MiB alternate is
27.15625. These support a third residency timing class with measurable
footprint/process variation, rather than one exact LLC hit-latency value.

## First pass and immediate reread

| Pressure group | First-pass median range | Reread median range | First minus previous-level primary resident median |
|---|---:|---:|---:|
| l1_miss | 7.80078–7.94922 | 2.67578–2.92188 | 5.07031–5.21875 |
| l2_miss | 25.83594–27.16016 | 2.95312–3.03516 | 18.03906–19.36328 |
| llc_miss | 205.25000–206.49609 | 7.30859–8.57812 | 179.04688–180.29297 |

Each sample times the next 256 dependent loads in one random cycle, then
immediately rereads exactly those targets. The next sample advances to the
following batch, preserving the full-cycle reuse distance. This is the
original working-set pressure method; it does not freshly flush or
selectively evict every target.

L1-miss and L2-miss first passes are close to their destination resident
references. Their rereads are much faster, near but not always equal to
the small-footprint L1 reference. Across the nine paired configurations,
the first pass is slower in 99.9574%–99.9978% of samples.

At 256/512 MiB, first-pass medians are 205.25000, 205.25781, and 206.49609.
Rereads remain at 7.30859–8.57812, above the 2.73047 L1 reference. Possible
translation, conflict, and surrounding-workload effects have not been
isolated; these are memory-dominated candidates, not guaranteed pure DRAM
accesses or pure L1 rereads.

The last table column is a difference of medians measured in separate
processes. It is an empirical next-level access-cost contrast, not a paired
penalty distribution or a measured pipeline stall count. The actual
paired FIRST-minus-REREAD medians are 4.98438–5.14062, 22.80859–24.20312,
and 197.91016–197.92578 for the three pressure groups. Both quantities are
saved separately in [contrasts.csv](contrasts.csv).

## Calibration and controls

The empty timer has median **30 ticks/interval**, with P05–P95 of 28–32.
No fixed timer value was subtracted from individual samples. The 1024-load
controls yield 2.64453 / 7.71191 / 25.77930 ticks/load at the L1/L2/LLC
footprints, close to the corresponding 256-load residency results.

The four-independent-stream diagnostics yield 0.76172 / 2.17578 / 7.17578
ticks/load at the three resident footprints and 55.83203 at 256 MiB.
These are throughput measurements and are not substituted for dependent
latency. Sequential controls are 2.73047 / 4.29297 / 6.13672 at the three
resident footprints and 23.31250 at 256 MiB. Their lower latency shows
that traversal order matters; these controls do not isolate a unique
prefetching or overlap mechanism.

## Placement, interference, and validation

All 30 working mappings had complete 2 MiB THP backing before and after
measurement and remained local to node 0. CPU start/end records were 6,
and dependency-result checks passed throughout. CPU 6 has no other SMT
thread. Its one-second preflight busy percentage was 1.98%; CPU 0 was
100% busy then and 99.953%–100% busy during every benchmark subprocess.
The existing `powersave` governor was retained. Instantaneous frequency
readings are saved, but they were not used to convert TSC ticks to cycles.

There were **140 involuntary context switches**, at most 25 in one
configuration, and no recorded minor faults, major faults, or voluntary
switches during measurement. No first-pass point exceeded the descriptive
1.2 temporal-median ratio; the largest was 1.11404 at the L1 repeat. This
does not establish uninterrupted exclusivity or the absence of shared
cache/memory interference. All samples and outliers are retained.

The analyzer reopened all 30 archives, verified hashes and dimensions,
recomputed statistics including signed paired differences, and checked
manifest agreement, environment/source/executable snapshots, page backing,
CPU placement, and NUMA logs. [validation.json](validation.json) passes.
Six functional tests passed; both x86 timed loops contain the expected
16 register-addressed loads, with no stack accesses inside the timed
interval. The C kernel and timer header match the Artemisia snapshots.
See [implementation_checks.json](implementation_checks.json).

Two earlier attempts are preserved separately: `latency01` completed 6
points before a 256 MiB THP-allocation failure; `latency01-retry1` completed
11 before a 512 MiB failure. Both failures occurred before timing the
failing configuration. The full protocol was restarted with a new run ID
each time; there was no fallback, kernel change, or merging of partial
runs. The incomplete attempts' 21,000,000 recorded intervals are excluded
from the formal result and remain available as separate evidence.

## Files

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [First pass versus reread](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png) / [PDF](figures/method_controls.pdf)
- [Timer overhead](figures/timer_overhead.png), [temporal stability](figures/temporal_stability.png)
- [Access-method diagram](figures/method.png) / [PDF](figures/method.pdf)
- [Full statistics](summary.csv), [contrasts](contrasts.csv), [latency estimates](latency_estimates.json)
- [Validation](validation.json), [quality diagnostics](quality.json), [run summary](run_summary.json), [provenance](provenance.json)
- [Run inventory and reproduction commands](../README.md)

Formal raw payload: 312,000,000 bytes; gzip archives: **48,646,666 bytes**.
Derived signed-difference rows in `summary.csv` are not additional collected
intervals. The requested seven groups are complete; no follow-up measurements
were added to seek cleaner state labels.
