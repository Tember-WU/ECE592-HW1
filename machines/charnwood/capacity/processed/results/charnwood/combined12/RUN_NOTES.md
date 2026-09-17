# Charnwood cache levels and capacity: two completed rounds

The two rounds completed serially on Charnwood: 39 configurations in round 1 and 57 in round 2, totaling **96 configurations and 96,000,000 timed batches**. Every configuration retained 1,000,000 samples. Round 1 took 241.406 seconds (4 minutes 1 second); round 2 took 310.749 seconds (5 minutes 11 seconds). Combined collection time was approximately 9 minutes 12 seconds, excluding setup and analysis.

Both rounds used the original C kernel, CPU 3 / NUMA node 0, and `-O0` flags. Round 1 reused `configs/common/round1.json` unchanged. Round-2 intervals were selected from Charnwood's new timing data. No cache specifications or PMU measurements were consulted. Existing Artemisia files and shared experiment code were retained.

## Timing-based interpretation

The data support **three distinguishable data-cache residency regions**, with **L1D approximately 32 KiB** and **L2 approximately 256 KiB**. The LLC has a broad effective transition across **4–8 MiB**; its exact physical capacity is not uniquely determined by these experiments.

| Region | Evidence, TSC ticks per dependent load | Interpretation |
|---|---|---|
| L1D | Two new-seed runs at 32 KiB: 5.9063 / 6.4453; round 1: 6.7734. At 36 KiB: 15.8906. | Approximately 32 KiB; 32–36 KiB brackets the sampled onset. |
| L2 | Two new-seed runs at 256 KiB: 18.0859 / 16.2734; round 1: 18.4688. At 288 KiB: 28.3984. At 384 KiB: 40.6328 / 40.5547. | Approximately 256 KiB; 256–288 KiB brackets the sampled onset. |
| LLC effective transition | Primary 64 B layout at 4/5/6/7/8 MiB: 58.2344 / 92.7969 / 240.7656 / 257.8984 / 280.8984. Compact 8 B repeats at 6 MiB: 111.2422 / 153.7578. | The transition is layout-, run-, and time-dependent; no exact physical LLC capacity is inferred. |

These intervals describe sampled onset or transition regions, not statistical confidence intervals. In particular, 4–8 MiB is not a bound on nominal physical LLC capacity. TSC ticks have not been validated as core clock cycles. Variations within the lower plateaus and different controls are not counted as additional cache levels.

The 1024-load controls measured 5.7324 TSC ticks/load at 32 KiB and 18.4063 at 256 KiB, supporting the lower residency regions. Sequential chains remain faster above those regions and are retained as prefetch/access-order controls. Compact 8 B layouts create different spatial-reuse opportunities, so they remain separate curves and are not pooled with 64 B layouts.

Base-page random controls at 4/6/8 MiB measured 81.3281 / 238.0859 / 310.2656 TSC ticks/load, versus 58.2344 / 240.7656 / 280.8984 with huge pages. These runs occurred at different times; the differences do not isolate a unique TLB or memory-system cause.

## Shared-machine activity and temporal variation

The prelaunch observations found CPU 3 / sibling CPU 7 approximately 1.672% / 1.003% busy before round 1, and 0.669% / 0.669% before round 2. Other users' benchmark processes were active throughout the preparation observations. CPU selection and affinity did not reserve or isolate the physical core, shared cache, or memory system.

Round 1 recorded 1,079 involuntary context switches, with at most 136 per configuration; round 2 recorded 1,619, with at most 149. Both rounds recorded zero minor/major page faults and zero voluntary context switches during the timed sampling loop.

**Two round-2 configurations coincided with substantial SMT sibling activity.** CPU 7's average busy percentage over the benchmark subprocess interval was 75.812% for the 384 KiB / 8 B random control and 97.945% for the 52 KiB / 64 B random point. The compact 384 KiB control's ten-block medians shifted from about 27.4 to 40 TSC ticks/load; it is not treated as a clean independent confirmation of the boundary. The logs establish concurrent activity, but do not isolate its causal effect on each sample. These two configurations and all their samples remain in the figures and statistics. The primary 32–36 KiB and 256–288 KiB onset evidence comes from other configurations.

CPU 7's recorded average busy percentage ranged from 0–12.5% in round 1 and 0–97.945% in round 2. Low values at other points do not rule out shared-cache or memory interference from other cores.

LLC uncertainty is also visible within individual measurements. The compact 5 MiB point has consecutive-block medians of approximately 103–105 early in the run and 56–64 later; the primary 5 MiB point's block medians range from about 71.6 to 157.8. At 6 MiB the compact new-seed medians differ by about 38%. The 8 MiB primary-layout median changed from 258.8750 in round 1 to 280.8984 in round 2. Layout, shared workloads, frequency behavior, and translation effects are possible contributors whose individual effects were not isolated.

## Validation and outputs

All 96 raw-file hashes, sample counts, and positive timing intervals were verified. The analyzer recomputed every statistic from raw samples, and the supplemental validator checked each round's CSV against another recomputation. Configuration/manifest/analysis point sets agree, source and binary snapshot hashes match, and both rounds satisfy the analyzer's compatibility checks. All mappings were local to node 0 and matched the configured page policy before and after measurement: 93 huge-page configurations and 3 explicit base-page controls. Passing these checks confirms data integrity and the logged settings; it does not certify absence of interference.

- [Boundary zoom](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf)
- [Boundary box plots](figures/boundary_boxplots.pdf)
- [Primary capacity curve](figures/capacity_s64_b256_huge.png) / [PDF](figures/capacity_s64_b256_huge.pdf)
- [Layout comparison](figures/layout_comparison_b256_huge.png), [temporal stability](figures/temporal_stability.pdf)
- [All statistics](summary.csv), [adjacent comparisons](transitions.csv), [temporal medians](temporal_medians.csv)
- [Machine-readable inference](inference.json), [boundary annotations](boundaries.json), [validation](validation.json), [analysis provenance](provenance.json)
- [Round-1 record](../round1/RUN_NOTES.md), [round-2 record](../round2/RUN_NOTES.md), [preparation and reproducible commands](../preparation/README.md)
- Raw data: [round1](../../../data/charnwood/round1/) and [round2](../../../data/charnwood/round2/)

The raw arrays contain 768,000,000 bytes before compression. Exact compressed sizes and per-round counts are recorded in `validation.json`. Source, executable, disassembly, build/measurement logs, and environment snapshots are preserved with each raw run. No outliers were removed.

The requested two-round protocol is complete. A third round has not been executed. The approximate L1/L2 capacities and LLC uncertainty can be reported with the caveats above. If narrower onset brackets or a quieter confirmation are required later, a bounded third round could refine 32–36 KiB and/or 256–288 KiB; the current evidence does not warrant an unbounded search for an exact LLC value.
