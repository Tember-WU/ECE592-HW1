# Skylark round-1 collection record

Completed 39/39 configurations, each with 1,000,000 timed batches: 39,000,000 batches in 187.55 seconds. This is the same shared 2 KiB–512 MiB powers-of-two protocol used for Artemisia, with random/sequential chains and one empty-timer control. CPU 32 / NUMA node 1, 64 B node spacing, 256 loads per batch, seed 59201, and verified huge pages were used throughout.

The original C source is unchanged (SHA-256 `5cf5653625c28888dbf907e2120088cb8145c2248ac49ac26e172d1be4893c6d`). All statistics use TSC ticks per dependent load; the empty control uses TSC ticks per timer interval. No samples or outliers were removed.

## Evidence for round 2

| Selected interval | Lower/upper random medians (ticks/load) | Ratio |
|---|---:|---:|
| 32–64 KiB | 3.46875 / 7.3125 | 2.108 |
| 512 KiB–1 MiB | 9.1875 / 23.34375 | 2.541 |
| 16–32 MiB | 29.90625 / 211.96875 | 7.088 |

The earlier plateaus are approximately 3.1875 ticks/load at 2–16 KiB, 8.4375–9.1875 at 128–512 KiB, and 25.875–29.90625 at 2–16 MiB. The largest random footprints approach 276.09375 ticks/load at 512 MiB; no larger extension is needed for this bounded two-round plan. The selected intervals are follow-up sampling regions, not final capacity estimates. They were selected from the new timing curve, not the OS-reported cache sizes inspected during platform checks.

## Validation and runtime quality

All raw hashes, sample counts, positive intervals, and stored statistics passed independent verification. The source/executable snapshots match the recorded hashes. All 39 mappings were completely huge-page backed and local to node 1 before and after measurement. CPU start/end values were 32 throughout. The measurement intervals recorded zero minor faults, major faults, and voluntary switches. Involuntary switches totaled 430, with at most 78 per point. The maximum ratio of ten temporal-block medians within a point was 1.003145. These checks do not exclude all shared-machine interference.

The raw arrays total 312,000,000 bytes, compressed to 24,014,237 bytes.

- [Capacity curve](figures/capacity_s64_b256_huge.png)
- [Per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Statistics](summary.csv), [adjacent transitions](transitions.csv), [validation](validation.json)
- [Final two-round interpretation](../combined12/RUN_NOTES.md)

The compatibility probes are separately identified in `../../../data/skylark/preflight/` and are not included in these 39 configurations.
