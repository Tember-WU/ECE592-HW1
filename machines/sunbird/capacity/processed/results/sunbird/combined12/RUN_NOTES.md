# Sunbird cache levels and capacity: two completed rounds

The requested two-round procedure is complete. The formal inputs are `round1_retry1` (39 configurations) and `round2` (57 configurations), totaling **96 configurations and 96,000,000 timed batches**. Each configuration retained 1,000,000 samples. The first round took 179.06 seconds and the second 319.55 seconds, totaling 8 minutes 18.61 seconds of collection, excluding preparation and analysis.

Both rounds used CPU 32 / NUMA node 0, the same executable and C source, the original `-O0` compiler flags, and the original dependent-load timing method. Round 1 used the shared coarse-scan configuration. The second-round intervals were selected from the new Sunbird curve and box plots, with the original planner generating the dense points, seed repeats, sequential/layout/longer-batch controls, and bounded LLC page/layout controls. The generated [second-round configuration](../../../configs/sunbird-round2.json) preserves the source run and raw-data hashes.

## Findings

The measurements support three distinguishable data-cache residency regions. **L1D is approximately 32 KiB and L2 approximately 256 KiB.** The sampled major transitions are 32–36 KiB and 256–288 KiB respectively. **LLC is reported as a broad effective transition within the sampled 16–64 MiB region; exact physical capacity is unresolved.**

All latency values below are TSC ticks per dependent load, not validated core cycles. Intervals describe empirical sampling regions, not statistical confidence intervals. The LLC interval is not a bound on nominal physical cache capacity.

| Region | New second-round evidence | Interpretation |
|---|---|---|
| L1D | 32 KiB repeat medians: 4.6250 / 4.7188; 36 KiB: 11.6875; 40 KiB: 12.0938 | Approximately 32 KiB; major sampled transition at 32–36 KiB |
| L2 | 256 KiB repeat medians: 12.5312 / 12.7500; 288 KiB: 41.5156; 320 KiB: 41.5781 | Approximately 256 KiB; major sampled transition at 256–288 KiB |
| LLC, primary 64 B layout | 16 MiB: 41.7188; 28 MiB: 49.9531; 40 MiB: 156.3750; 52 MiB: 194.9375; 64 MiB: 202.1875 | A broad rise, with a clear increase between 28 and 40 MiB, approaching the large-footprint region by 64 MiB |
| LLC, compact 8 B layout | 16 MiB repeats: 41.2969 / 41.3125; 28 MiB: 47.0312; 40 MiB repeats: 95.4531 / 97.4844; 64 MiB repeats: 138.4062 / 138.1094 | Repeats support a similar broad region, while absolute latency depends strongly on layout |

At the L1 boundary, the round-2 32 KiB P05–P95 ranges end below 5.02 ticks/load, while the 36 KiB range starts at 11.4062. At the L2 boundary, the 256 KiB repeat ranges end below 13.65, while the 288 KiB range starts at 40.6094. The main distribution changes are therefore readily distinguishable at the current sample spacing. The coarse 32 KiB median was 4.4062 and coarse 256 KiB was 12.6094, supporting the same broad boundary interpretation while showing some variation between runs.

## Controls and variability

The longer-batch controls used 1024 dependent loads per batch: 4.4453 ticks/load at 32 KiB and 12.9688 at 256 KiB. These support the two low-latency residency regions. Sequential controls and compact layouts have their own curves; compact layout allows more spatial reuse, so lower latency above a transition does not directly imply a different cache capacity. Runs and controls have not been pooled into extra cache levels.

The three base-page controls measured 59.9219, 181.5000, and 232.8906 ticks/load at 16, 40, and 64 MiB, compared with 41.7188, 156.3750, and 202.1875 for the corresponding primary-layout huge-page points. The differences demonstrate sensitivity to page policy in this measurement. They do not isolate a unique cause such as TLB behavior or shared-cache contention.

The coarse 32 MiB point had substantial temporal variation: its ten block medians ranged from 89.8906 to 162.4062 ticks/load. That point is retained in the combined data. In contrast, the primary 64 MiB medians were close across the two rounds, 202.5469 and 202.1875. Compact-layout repeats are also fairly consistent at the measured anchors. These observations support reporting the broad LLC region, while the controls and coarse temporal variation prevent a unique physical-capacity conclusion.

## Validation and preparation history

All data-integrity and placement checks passed; see [combined validation](validation.json) and the linked per-run records. The analyzer verified raw hashes and sample counts, checked compatibility between rounds, and recomputed all statistics from raw samples. The supplementary [audit script](../../../data/sunbird/setup/audit_runs.py) independently checked raw data, source/executable hashes, completed manifests, analysis input provenance, CPU binding, NUMA placement, and actual page backing before and after timing.

The 93 huge-page configurations had complete huge-page backing; the 3 explicit base-page controls had none. Every measured mapping was local to NUMA node 0. CPU 8, the SMT sibling of CPU 32, had 0% recorded busy time in all benchmark subprocess intervals. Timed regions had no minor faults, major faults, or voluntary context switches. Involuntary context switches totaled 47 in round 1 and 91 in round 2, with at most 7 at any configuration. This does not prove the absence of shared-machine or frequency effects.

The initial `data/sunbird/round1/` attempt failed its fourth configuration during `MADV_COLLAPSE` allocation. Its three completed configurations and failure logs remain preserved and are excluded from these 96 configurations. After untimed process-local allocation preparation and five successful complete 512 MiB huge-page checks, the entire first round was restarted as `round1_retry1`. The benchmark never silently switched page policy. See the [setup record](../../../data/sunbird/setup/README.md), including the local NUMA executable, Python dependencies, allocation diagnostics, and CPU preflight observation.

Host inspection with `lscpu` included cache specifications. The follow-up intervals and conclusions here are supported by the new timing measurements; this execution should not be described as blind to hardware specifications. No PMU measurements were used.

The successful runs contain 768,000,000 bytes of uncompressed raw arrays, or **89,527,017 bytes after gzip compression**. Every sample, including outliers, is retained. Consecutive batches are not independent experiment repetitions.

## Files and reproduction

- [Boundary zoom plots](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf)
- [Boundary box plots](figures/boundary_boxplots.pdf)
- [Primary capacity curve](figures/capacity_s64_b256_huge.png)
- [Layout comparison](figures/layout_comparison_b256_huge.png)
- [Temporal stability](figures/temporal_stability.pdf)
- [Statistics](summary.csv), [adjacent-point comparisons](transitions.csv), [time-block medians](temporal_medians.csv)
- [Machine-readable inferences](inference.json), [boundary annotations](boundaries.json), [analysis provenance](provenance.json)
- [First-round record](../round1_retry1/RUN_NOTES.md), [second-round record](../round2/RUN_NOTES.md)
- Raw data: [round1_retry1](../../../data/sunbird/round1_retry1/), [round2](../../../data/sunbird/round2/)

From the capacity directory, with the local `.venv` activated:

```bash
python3 scripts/analyze_capacity.py --machine sunbird \
  --run-id round1_retry1 round2 --output-id combined12 \
  --boundaries results/sunbird/combined12/boundaries.json
python3 data/sunbird/setup/audit_runs.py round1_retry1 round2
```

The two requested rounds are sufficient to report these approximate L1/L2 capacities and the LLC uncertainty. No third round was run. If finer empirical boundaries are needed later, a bounded third round can refine 32–36 KiB and/or 256–288 KiB using already measured endpoints; the present workflow does not require an ongoing search for exact LLC capacity.
