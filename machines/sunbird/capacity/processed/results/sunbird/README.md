# Sunbird capacity experiment

The two-round experiment is complete: **96 configurations, 96,000,000 timed batches**, collected sequentially on CPU 32 / NUMA node 0 on September 10, 2026. All successful-run integrity and page/placement checks passed.

| Round | Formal run ID | Configurations | Collection time | Record |
|---|---|---:|---:|---|
| 1: coarse scan | `round1_retry1` | 39 | 179.06 s | [Round 1](round1_retry1/RUN_NOTES.md) |
| 2: refinement and controls | `round2` | 57 | 319.55 s | [Round 2](round2/RUN_NOTES.md) |

Read the [combined results and interpretation](combined12/RUN_NOTES.md). The timing data support approximate L1D and L2 capacities of **32 KiB** and **256 KiB**, with a broad LLC effective transition in the sampled **16–64 MiB** region. Exact physical LLC capacity remains unresolved.

- [Combined capacity curve](combined12/figures/capacity_s64_b256_huge.png)
- [Boundary zoom plots](combined12/figures/boundary_zoom.png)
- [Combined statistics](combined12/summary.csv), [validation](combined12/validation.json)
- Raw runs: [round1_retry1](../../data/sunbird/round1_retry1/), [round2](../../data/sunbird/round2/)
- [Machine configuration](../../configs/sunbird.json), [round-2 configuration](../../configs/sunbird-round2.json)
- [Dependencies and allocation preparation](../../data/sunbird/setup/README.md)

The initial [round1 attempt](../../data/sunbird/round1/) stopped on a huge-page allocation failure after three completed configurations. Those records remain preserved and are excluded from the formal results. The full coarse scan was rerun with the new ID `round1_retry1`. Existing Artemisia experiment files were preserved.
