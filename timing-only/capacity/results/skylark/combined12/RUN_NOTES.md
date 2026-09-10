# Skylark capacity results from two rounds

The measurements support three distinguishable data-cache residency regions, with approximate L1D capacity **32 KiB** and L2 capacity **512 KiB**. The LLC curve has a low-latency point at **16 MiB** and rises sharply by **20 MiB**, with a broader layout-dependent transition through 32 MiB. This is an effective transition for the pinned core; a unique nominal physical LLC capacity or aggregate cache capacity is not established.

Both requested rounds completed serially on Skylark, using CPU 32 / NUMA node 1 and the original unmodified x86-64 C kernel. Round 2 was generated from Skylark round-1 timings. The OS cache geometry inspected during the requested compatibility check was not used as measurement evidence or to select the follow-up endpoints. No PMU measurements were used.

| Round | Configurations | Timed batches | Collection time |
|---|---:|---:|---:|
| Round 1, shared coarse sweep | 39 | 39,000,000 | 187.55 s |
| Round 2, refinement and controls | 57 | 57,000,000 | 318.45 s |
| Total | 96 | 96,000,000 | 506.00 s |

Each configuration retains 1,000,000 timed batches after warm-up. The usual batch contains 256 dependent loads; the two longer-batch controls contain 1024. The empty-timer control has no timed loads. Diagnostic compatibility probes are separate and excluded from these totals. Timing jobs did not overlap; elapsed collection time excludes the pause for analysis/planning between rounds.

## Capacity evidence

All numbers below are TSC ticks per dependent load, not calibrated processor core cycles.

| Region | Measured evidence | Interpretation |
|---|---|---|
| L1D | 2–16 KiB: 3.1875; 32 KiB: 3.4688 in the coarse run and both round-2 seeds; 36 KiB: 5.0625 (P05–P95 4.8750–5.3438) | Approximately 32 KiB; sampled onset bracket 32–36 KiB |
| L2 | 512 KiB: 9.1875 in all three primary runs; 576 KiB: 15.7500 (P05–P95 14.7188–17.2500); 1 MiB repeats: 23.2500–23.3438 | Approximately 512 KiB; sampled onset bracket 512–576 KiB |
| LLC/L3 effective region | Primary 64 B layout: 16 MiB 29.9063 in both rounds, 20 MiB 137.4375, 24 MiB 184.4063, 32 MiB 211.9688 in both rounds | Observed onset 16–20 MiB; broader transition 16–32 MiB; nominal physical capacity unresolved |

These are empirical sampling intervals, not statistical confidence intervals. The random-chain coarse curve shows a third low-latency region at 2–16 MiB (25.8750–29.9063 ticks/load) before the large increase. Larger random footprints approach 276.0938 ticks/load at 512 MiB. The intermediate L1/L2 transition points are mixed-residency behavior, not extra cache levels.

## Controls and repeatability

- The 1024-load controls give 3.2578 ticks/load at 32 KiB and 8.9766 at 512 KiB, supporting the two low-latency regions with reduced per-load timer overhead. The empty-timer median is 72 ticks/interval. It is reported separately and was not subtracted from the data.
- Compact 8 B layout medians at 16 MiB are 28.6875 for both seeds. At 20 MiB the median is 84.7500; at 24 MiB repeat medians are 120.0000–120.1875; at 32 MiB they are 157.2188–157.3125. Repeats support a stable increase, while absolute latency differs from the 64 B layout. Compact layout changes spatial reuse; its curve is not pooled with the primary layout.
- Base-page controls at 16/24/32 MiB give 182.8125/225.1875/219.8438 ticks/load, versus 29.9063/184.4063/211.9688 with huge pages. Page policy materially changes this curve, and the base-page points are not monotonically increasing. Translation costs, allocation/cache conflicts, and shared activity remain possible contributors; these measurements do not isolate a unique cause.
- Sequential controls remain much faster than random chains beyond the small cache region. For example, round-2 16/24/32 MiB sequential medians are recorded separately in [summary.csv](summary.csv). Sequential performance alone is not used to infer cache capacity.
- Run medians are not pooled. The original fixed selection priority chooses the targeted round before the coarse round, then the smaller seed; black error bars show the range of separate run medians. Consecutive timed batches are not independent experiments.

## Validation and runtime quality

All 96 configurations passed the [independent validation](validation.json): raw SHA-256 hashes, sample counts, positive timing intervals, recomputed statistics, source/executable hashes, CPU binding, NUMA locality, and actual page backing. Round 1 contains 39 huge-page configurations; round 2 contains 54 huge-page configurations and 3 explicit base-page controls. Every working mapping remained local to node 1 and retained the requested page policy before and after measurement. CPU start/end values were 32 in every case. CPU 32 has no enabled SMT sibling.

Both rounds recorded zero measurement minor faults, major faults, and voluntary context switches. Involuntary switches totaled **430** in round 1 (maximum 78 per point) and **787** in round 2 (maximum 71 per point). All samples were retained. The maximum ratio between a point's ten temporal-block medians was 1.003145 in round 1 and 1.058824 in round 2; the latter occurred at 640 KiB. The key 32 KiB and 512 KiB repeat medians remained consistent. Passing these checks does not prove that this shared server had no interference.

The two rounds used identical source and executable hashes:

- Source: `5cf5653625c28888dbf907e2120088cb8145c2248ac49ac26e172d1be4893c6d`
- Executable: `1812acb1265cf7b491677c33058b76a7c8547091e4c60d619436a7e36b9d8bd1`

The raw arrays total **768,000,000 bytes**, or **81,038,899 bytes** in gzip archives. Individual raw arrays, commands, source/binary snapshots, compiler logs, and environment metadata remain in `../../../data/skylark/round1/` and `../../../data/skylark/round2/`. The final preservation check confirms that all **396** original files covered by the preflight hash inventory, including Artemisia code/data/results and the shared protocol, are unchanged.

## Files

- [Boundary zoom](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf)
- [Boundary box plots](figures/boundary_boxplots.pdf)
- [Primary capacity curve](figures/capacity_s64_b256_huge.png)
- [Layout comparison](figures/layout_comparison_b256_huge.png)
- [Base-page controls](figures/capacity_s64_b256_base.png)
- [Temporal stability](figures/temporal_stability.pdf)
- [Statistics](summary.csv), [transitions](transitions.csv), [inferences](inference.json), [boundaries](boundaries.json)
- [Validation](validation.json), [analysis provenance](provenance.json)
- [Round-1 notes](../round1/RUN_NOTES.md), [round-2 notes](../round2/RUN_NOTES.md)
- [Platform checks and reproduction instructions](../../../SKYLARK.md)

The requested two-round experiment is complete. No third round was run. The present L1/L2 estimates and LLC uncertainty can be reported at the measured resolution.
