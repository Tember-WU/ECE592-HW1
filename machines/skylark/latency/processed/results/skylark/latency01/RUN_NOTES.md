# Skylark latency: complete seven-group run

Run `latency01` completed all **30 configurations in seven groups**, with 1,000,000 batches after warm-up per configuration. Collection took **177.19 seconds** (about 2 minutes 57 seconds), from 2026-09-10T20:53:22.920534+00:00 to 2026-09-10T20:56:20.108288+00:00. The nine paired configurations each save FIRST and REREAD, giving **30,000,000 batches and 39,000,000 recorded timer intervals**. All points ran serially in the original fixed shuffled order. All samples were retained.

Skylark's existing configuration uses its own measured capacity plateaus; its capacity-basis SHA-256 was verified before and after the run. Compared with Artemisia, the per-point parameters differ only in selected working-set sizes. Source, seeds, batch lengths, group counts, and point order remain the same. The original C code, timer header, scripts, configurations, and Artemisia results are unchanged.

Units below are **TSC ticks per dependent load**, not validated core cycles. The residency and next-level labels are timing-supported candidates, not verified hardware hit/miss states for every load.

## Resident candidates

| Group | Tested address spans | Median range across three processes | Primary P05–P95 |
|---|---|---:|---:|
| l1_hit | 8 KiB, 16 KiB | 3.18750 | 3.09375–3.18750 |
| l2_hit | 128 KiB, 256 KiB | 8.34375–8.81250 | 8.25000–8.62500 |
| llc_hit | 4 MiB, 8 MiB | 27.09375–27.75000 | 26.53125–27.65625 |

L1 medians agree exactly across both footprints and the new-seed repeat. The L2 primary/repeat at 128 KiB are 8.43750/8.34375, while the 256 KiB alternate is 8.81250. LLC primary/repeat at 4 MiB are 27.09375/27.18750, while the 8 MiB alternate is 27.75000. These are three distinct residency timing regions, with modest footprint/seed differences in the larger regions; the processes are not pooled into one distribution.

## First pass, immediate reread, and next-level contrasts

| Pressure group | FIRST median range | REREAD median range | FIRST minus previous resident median | Median of paired FIRST minus REREAD |
|---|---:|---:|---:|---:|
| l1_miss | 8.34375–8.81250 | 3.93750–4.31250 | 5.15625–5.62500 | 4.12500–4.96875 |
| l2_miss | 27.09375–27.75000 | 3.56250–3.65625 | 18.65625–19.31250 | 23.53125–24.18750 |
| llc_miss | 271.03125–276.18750 | 6.18750–7.40625 | 243.93750–249.09375 | 264.84375–268.68750 |

The paired method times the next batch in a large random cycle, resets the cursor, immediately rereads the same batch, and then continues at the next batch. The full-cycle reuse distance creates working-set pressure. There is no fresh flush or set-selective eviction before each sample.

The L1-pressure first passes are close to the L2 resident candidates, and the L2-pressure first passes match the corresponding LLC references. The immediate reread is faster in at least 99.954% of samples in each cache-pressure configuration and in 100% of samples in the three memory-pressure configurations.

**Reread is not a pure L1-hit reference here.** Its medians are 3.93750–4.31250 in the L1-pressure group, 3.56250–3.65625 in the L2-pressure group, and 6.18750–7.40625 in the memory-pressure group, all above the small-resident 3.18750 reference. Conflicts, address translation, and surrounding bookkeeping/output stores can affect the result; this experiment does not isolate their individual contributions. Report the observed same-address benefit without assigning every reread to a guaranteed cache level.

The 256 MiB primary and repeat FIRST medians both equal 271.03125; the 512 MiB alternate is 276.18750. These are memory-dominated access candidates, not a uniquely measured pure DRAM latency.

The fourth table column subtracts the separately measured **primary previous-level resident median**. It is an empirical next-level access-cost contrast, conditional on the intended residency classes; it is not a pipeline stall count or a paired difference distribution. The fifth column is computed from each sample's signed FIRST–REREAD difference. Median subtraction and the median of paired differences need not agree. All signed differences and outliers remain in the statistics.

## Method controls

The empty timer median is **72 ticks/interval**, with P05–P95 of 48–72. Timer overhead was not subtracted from individual observations. Long, 1024-load controls give L1/L2/LLC medians **2.97656 / 8.25000 / 26.92969** ticks/load. Their somewhat lower per-load values are consistent with amortizing timer/loop overhead over larger batches.

Four independent streams give **1.03125 / 2.71875 / 7.31250** ticks/load at the L1/L2/LLC candidate footprints and **73.96875** at 256 MiB. These are throughput diagnostics and are not substituted for dependent-load latency. Sequential controls give **3.18750 / 4.21875 / 4.68750**, and **11.15625** at 256 MiB (P05–P95 10.78125–14.15625). Access pattern strongly affects timings at the larger footprints; the dependent random-chain results remain the latency references.

## Placement, quality, and validation

All 30 configurations used **CPU 32 / NUMA node 1**, with complete 2 MiB THP backing before and after timing. CPU 32 has no enabled SMT sibling. Actual CPU binding was tested despite a narrower inherited affinity mask. The collector's short preflight measured CPU 32 at 0% busy; this does not establish exclusive access to shared resources. Frequency-governor files were unavailable for this CPU and no frequency policy was changed or assumed.

Measurement intervals recorded **zero minor faults, major faults, and voluntary context switches**. Involuntary switches totaled **374**, with a maximum of **88** per configuration. No FIRST point exceeded the descriptive 1.2 temporal-median-ratio threshold. The maximum ratio was **1.055556**, at `l1_miss__repeat`. Paired-column and signed-difference time blocks are also retained in `temporal_medians.csv`; the analyzer's drift flag specifically covers FIRST. These diagnostics do not prove uninterrupted exclusivity.

The analyzer reopened all 30 raw archives and verified hashes, dimensions, statistics (including signed paired differences), manifest agreement, executable/source snapshots, CPU/NUMA placement, and page backing. The supplemental run audit also confirms complete local NUMA page counts and nonoverlapping measurement windows. All six original functional tests passed. Native x86 disassembly checks verified 16 register-addressed loads and no timed stack accesses in both the dependent and four-stream loops. Separate 1,000-sample diagnostic probes are excluded from the formal results.

Raw arrays total **312,000,000 bytes**, compressed to **25,330,658 bytes**. The 48 rows in `summary.csv` include derived paired-difference rows; they are not 48 collected configurations. A preservation inventory verified all **151 pre-existing latency files** unchanged.

## Saved results

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [FIRST versus REREAD](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png), [timer overhead](figures/timer_overhead.png)
- [Temporal stability](figures/temporal_stability.png), [access-method diagram](figures/method.png)
- [Statistics](summary.csv), [contrasts](contrasts.csv), [machine-readable estimates](latency_estimates.json)
- [Integrity validation](validation.json), [quality](quality.json), [run audit](run_audit.json), [implementation checks](implementation_checks.json)
- [Analysis provenance](provenance.json), [analysis source](analysis_source/)
- [Recorded configuration](../../../data/skylark/latency01/config.json), [manifest](../../../data/skylark/latency01/manifest.json), [raw arrays](../../../data/skylark/latency01/raw/)
- [Platform checks and reproduction](../../../SKYLARK.md)

The requested seven groups are complete. No extra follow-up collection was run.
