# Sunbird first-round coarse scan

The formal first round is `round1_retry1`: all 39/39 configurations completed, each retaining 1,000,000 timed batches, for 39,000,000 batches. Collection ran from 2026-09-10T16:31:11.730407+00:00 to 2026-09-10T16:34:10.790595+00:00, taking 179.06 seconds (2 minutes 59 seconds).

Measurements use CPU 32 / NUMA node 0, 64 B node spacing, 256 dependent loads per batch, complete huge-page backing, and the original `-O0` dependent-load kernel. Timing values are TSC ticks per dependent load, not validated core cycles. The empty-timer control has a median of 56 TSC ticks per interval.

The earlier run `data/sunbird/round1/` failed its fourth configuration during huge-page allocation after three completed configurations. Its data are preserved but excluded from this analysis. The entire coarse sweep was restarted after untimed allocation preparation; see the [setup record](../../../data/sunbird/setup/README.md).

## Observations and second-round selection

The new random-chain curve and box plots show three distinguishable low-latency residency regions, followed by a large-footprint memory-access region. The observed medians are approximately 4.16 ticks/load through 16 KiB, 12.1–12.6 at 64–256 KiB, 41.6–41.7 at 512 KiB–16 MiB, and 202.5–210.4 at 64–512 MiB. These timing regions motivate the follow-up measurements; they do not establish exact capacity boundaries.

| Candidate | Newly measured endpoints and evidence, TSC ticks/load | Second-round interval |
|---|---|---|
| L1D | 32 KiB: 4.40625; 64 KiB: 12.125 | 32–64 KiB |
| L2 | 256 KiB: 12.609375; 512 KiB: 41.609375 | 256–512 KiB |
| LLC effective transition | 16 MiB: 41.71875; 32 MiB: 98.1875; 64 MiB: 202.546875 | 16–64 MiB |

The LLC interval deliberately includes the observed rise from the third residency plateau to the large-footprint region. At 32 MiB, the random-chain Q1–Q3 range is 89.6094–122.8281 and the ten block medians range from 89.8906 to 162.4062 ticks/load. This substantial temporal variation calls for the bounded layout/repeat/base-page controls already provided by the original second-round procedure. The 128–512 MiB medians are close enough to the 64 MiB value that a larger-footprint extension is unnecessary for this two-round plan.

The [generated second-round configuration](../../../configs/sunbird-round2.json) records these reasons, measured endpoints, the source run, raw hashes, and the planner hash. It contains 57 configurations: 38 L1/L2 refinement and control configurations plus 19 bounded LLC configurations. The selected intervals are measurement regions, not confidence intervals or physical-capacity bounds.

## Validation

The analyzer recomputed all statistics from the raw data. The [supplementary audit](validation.json) independently checked all 39 raw-file hashes, counts, positive samples, source/executable hashes, manifest completion, analysis input provenance, CPU binding, NUMA placement, and page backing. All checks passed. Every mapping was fully huge-page backed and local to node 0 before and after measurement.

CPU 8, the SMT sibling, had 0% recorded busy time during every benchmark subprocess interval. The timed regions contained no minor faults, major faults, or voluntary context switches. Involuntary context switches totaled 47, with at most 7 at one point. These checks do not establish freedom from shared-machine or frequency effects; in particular, the 32 MiB temporal variation remains part of the evidence.

Raw arrays total 312,000,000 bytes, or 32,496,726 bytes after gzip compression. Every sample is retained, including outliers.

## Reproduce the analysis

From the capacity directory, with the [local environment](../../../data/sunbird/setup/README.md):

```bash
python3 scripts/analyze_capacity.py --machine sunbird --run-id round1_retry1
python3 data/sunbird/setup/audit_runs.py round1_retry1
```

- [Capacity curve](figures/capacity_s64_b256_huge.png) / [PDF](figures/capacity_s64_b256_huge.pdf)
- [Per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Statistics](summary.csv), [adjacent-point comparisons](transitions.csv), [time-block medians](temporal_medians.csv)
- [Analysis provenance](provenance.json), [validation](validation.json)
- [Raw data and collection logs](../../../data/sunbird/round1_retry1/)

See the [combined two-round record](../combined12/RUN_NOTES.md) for the interpretation after the second round.
