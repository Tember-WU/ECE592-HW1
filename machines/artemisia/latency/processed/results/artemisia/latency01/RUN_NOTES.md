# Artemisia latency: complete seven-group run

Run `latency01` completed all 30 configurations in 302.31 seconds (about 5 minutes 2 seconds), from 2026-09-10T20:10:04.205037+00:00 to 2026-09-10T20:15:06.517681+00:00. Each configuration contains 1,000,000 batches after warm-up. Nine paired configurations save two timer intervals per batch; the complete run contains 39,000,000 recorded intervals. All seven groups were executed once with the configured alternate footprints and second-seed repeats. No follow-up round was needed to describe these observations.

Units below are **TSC ticks per dependent load**, not validated core cycles. Workload/state labels are timing-supported candidates, not PMU-confirmed hit/miss labels for every access.

## Resident candidates

| Group | Tested address spans | Median range across the three processes | Primary P05–P95 |
|---|---|---:|---:|
| l1_hit | 8 KiB, 16 KiB | 5.18750 | 5.17188–5.21094 |
| l2_hit | 512 KiB, 1 MiB | 16.21875 | 16.17969–16.25781 |
| llc_hit | 8 MiB, 16 MiB | 62.88281–62.92188 | 62.20312–63.53906 |

L1 and L2 medians agree across the alternate footprints and new-seed repeats. LLC medians also remain close, with a visibly broader within-point distribution. These results support three distinct residency timing classes under this measurement method.

## First pass versus immediate reread

| Pressure group | First-pass median range | Immediate-reread median range | First minus previous resident median |
|---|---:|---:|---:|
| l1_miss | 16.21094–16.21875 | 5.18750–5.19531 | 11.02344–11.03125 |
| l2_miss | 62.87500–62.92188 | 5.18750 | 46.65625–46.70312 |
| llc_miss | 248.53906–254.46094 | 10.46094–11.33594 | 185.65625–191.57812 |

The paired test times the next batch in a large random cycle, immediately rereads exactly that batch, and then advances to the next batch. Full-cycle reuse distance provides the working-set pressure. It does not flush or construct a congruent eviction set before each sample.

For L1-miss/L2 candidates and L2-miss/LLC candidates, first passes agree with the corresponding resident references, and immediate rereads return close to the L1 reference. This provides a clear same-address recency contrast.

For the 256/512 MiB memory candidates, immediate rereads remain around 10.46–11.34 ticks/load rather than the 5.19 L1 reference. Translation, conflicts, and other surrounding-workload effects were not isolated. The first-pass medians are also not monotonic in footprint: the 256 MiB primary is 254.46, its new-seed repeat is 248.54, and 512 MiB is 248.84. Report their observed range; do not claim a unique pure DRAM latency.

The last table column subtracts the separately measured primary previous-level resident median. It is an **empirical next-level access-cost contrast**, meaningful as a level-specific miss penalty only to the extent that the intended classes hold. It is not a measured pipeline stall count or a paired penalty distribution. `contrasts.csv` separately records the actual paired first-minus-reread distribution and first-slower fraction.

## Method controls and timer overhead

The empty timer has median 50 ticks/interval and P05–P95 of 48–54. No fixed timer minimum was subtracted from individual samples. At 1024 loads/batch, the L1/L2/LLC medians are 5.05664 / 16.08008 / 62.80078 ticks/load, close to the 256-load values; the slightly lower values are consistent with reduced per-load boundary overhead. Assembly inspection verifies no stack access within the timed instruction intervals, but the reported values still include the timer and loop instructions.

Four independent streams give about 1.46 / 4.22 / 16.59 ticks/load at the three resident footprints and 59.99 at the large footprint. These are throughput diagnostics, demonstrating why independent loads must not replace the dependent latency measurements.

Sequential controls are 5.19 / 16.04 / 61.70 ticks/load at the three resident footprints. At 256 MiB, the sequential median is 240.65 with a broad P05–P95 of 87.05–251.35. This control does not show a uniformly fast memory-region distribution. It does not establish that prefetching was absent, and it is not used to choose a preferred latency result.

## Placement, interference, and validation

All configurations ran on CPU 32 with memory local to NUMA node 1. All working mappings had complete 2 MiB THP backing before and after timing. The existing performance governor was retained. CPU 32 and SMT sibling CPU 88 both measured 0% busy in the short preflight; CPU 88 had 0% recorded average busy time during every subprocess. These averages do not prove uninterrupted exclusivity or the absence of shared-cache/memory interference.

The measured loops recorded 202 involuntary context switches in total, at most 46 per configuration, with zero minor faults, major faults, or voluntary switches. No first-pass point exceeded the descriptive 1.2 ratio between its ten temporal medians. All raw samples and outliers are retained.

The analyzer reopened all 30 archives, verified raw hashes and dimensions, recomputed all statistics including paired signed differences, checked manifest agreement, verified code/executable snapshots, and rechecked CPU/NUMA/page evidence. `validation.json` passes integrity checks; this is not a certificate of pure cache states.

Six functional tests passed. Both x86 timer loops contain the expected 16 register-addressed loads between timestamps, with no stack references in the interval. AArch64 dependent and four-stream timer assembly cross-compiled successfully with Clang; full AArch64 execution has not been tested as part of this Artemisia run.

The data directory preserves the collection-time code snapshot. `analysis_source/` preserves the analyzer and helper versions actually used for these outputs; a diagnostic unit-label correction made before analysis is thereby recorded without changing the collection snapshot.

## Files for subsequent reporting

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [First pass versus reread](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png) / [PDF](figures/method_controls.pdf)
- [Timer overhead](figures/timer_overhead.png) and [temporal stability](figures/temporal_stability.png)
- [Concrete access-method diagram](figures/method.png) / [PDF](figures/method.pdf)
- [Full statistics](summary.csv), [next-level and paired contrasts](contrasts.csv), [machine-readable estimates](latency_estimates.json)
- [Integrity validation](validation.json), [quality diagnostics](quality.json), [analysis provenance](provenance.json)
- [Recorded configuration](../../../data/artemisia/latency01/config.json), [run manifest](../../../data/artemisia/latency01/manifest.json), [raw arrays](../../../data/artemisia/latency01/raw/)

Raw payload: 312,000,000 bytes; gzip archives: 45,049,458 bytes. `summary.csv` includes derived signed-difference rows; those are not additional collected samples.
