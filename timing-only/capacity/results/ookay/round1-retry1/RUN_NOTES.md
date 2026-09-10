# Ookay round-1 coarse-scan record

The completed first round is `round1-retry1`: 39/39 configurations and 39,000,000 timed batches. Collection ran from 2026-09-10T16:52:52.918187+00:00 to 2026-09-10T16:55:42.304888+00:00, taking 169.39 seconds.

The shared `configs/common/round1.json` protocol is unchanged: random and sequential dependent chains at 19 powers-of-two footprints from 2 KiB to 512 MiB, plus an empty-timer control. Each configuration retains 1,000,000 timed batches, with 64 B spacing and 256 dependent loads per batch. Both rounds bind CPU 2 and memory to NUMA node 0. The C kernel, timing method, and `-O0` compiler flags are the same as the Artemisia experiments. CPU topology and activity were used to select the binding; cache geometry and PMU measurements were not consulted.

## Initial allocation failure and recovery

The initial attempt, `data/ookay/round1/`, completed four configurations, then stopped at the 512 MiB random configuration because `MADV_COLLAPSE` returned `Cannot allocate memory`. That directory, its manifest, and logs are preserved. The entire 39-point protocol was restarted under the new ID `round1-retry1`, with unchanged parameters, and completed successfully. The initial attempt's four million batches are excluded from the completed two-round study. There was no base-page fallback, system setting change, or intervention in another process. The underlying allocation failure was not isolated further. See [recovery.json](../../../data/ookay/recovery.json).

## Observations and second-round selection

The following intervals were selected from this completed run's random-chain curve. They select follow-up measurements and are not final capacity estimates or confidence intervals.

| Candidate | Lower endpoint median | Upper endpoint median | Refinement interval |
|---|---:|---:|---|
| L1D | 32 KiB: 3.9219 | 64 KiB: 10.7188 | 32–64 KiB |
| L2 | 256 KiB: 10.9531 | 512 KiB: 27.5703 | 256–512 KiB |
| LLC effective transition | 4 MiB: 32.9766 | 8 MiB: 170.6758 | 4–8 MiB |

Units are TSC ticks per dependent load. The empty-timer median is 42 ticks per interval. Random-chain medians from 16 MiB through 512 MiB range from 215.6641 to 235.7344, providing a slower large-footprint region without needing range extension. The 4 MiB distribution has a long upper tail despite its median remaining near the preceding plateau. Sequential access stays substantially faster at large footprints; these controls must be interpreted separately.

The generated [second-round configuration](../../../configs/ookay-round2.json) records this run's manifest/configuration hashes and every raw-input hash. It contains 57 configurations for dense measurements, new-seed repeats, sequential and compact-layout controls, longer-batch controls, and bounded LLC base-page controls.

## Validation and measurement conditions

All 39 raw files passed hash, positive-interval, and sample-count checks. Analysis recomputed statistics from all samples; no outliers were removed. The raw arrays total 312,000,000 bytes, compressed to 53,052,853 bytes. All measured mappings had complete huge-page coverage before and after timing and were local to NUMA node 0. CPU start/end checks both recorded CPU 2 for every point.

No measured minor faults, major faults, or voluntary context switches occurred. There were 42 involuntary switches in total, at most 5 at one point. CPU 6, the SMT sibling, had recorded busy percentages from 0 to 3.333% across subprocess intervals. These integrity checks do not establish an interference-free machine: other benchmarks were observed on CPUs 0 and 4 before collection, sharing machine resources. Their effects were not isolated.

- [Capacity curve](figures/capacity_s64_b256_huge.png), [per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Summary](summary.csv), [adjacent-point comparisons](transitions.csv), [temporal medians](temporal_medians.csv)
- [Validation](validation.json), [analysis provenance](provenance.json)
- [Raw data and snapshots](../../../data/ookay/round1-retry1/), [preparation record](../../../data/ookay/preparation.json)

For the completed two-round interpretation, see [combined12/RUN_NOTES.md](../combined12/RUN_NOTES.md).
