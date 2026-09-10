# Sunbird latency results

All seven groups completed under run ID **`latency01`**: 30 configurations, 30,000,000 batches, and 39,000,000 recorded timer intervals. Collection took **169.26 seconds** on CPU 32 / NUMA node 0, with full huge-page backing. Data, snapshots, and recorded placement passed validation.

Read the [complete experiment record](latency01/RUN_NOTES.md), including calibration results, hit/next-level timing evidence, preparation history, and limitations.

| Candidate | Observed median range, TSC ticks/dependent load |
|---|---:|
| L1 hit | 4.15625 |
| L2 hit | 12.14063–12.15625 |
| LLC hit | 41.70313–41.73438 |
| L1 miss / L2 first pass | 12.12500–12.17188 |
| L2 miss / LLC first pass | 41.70313–41.71875 |
| LLC miss / memory first pass | 209.79688–211.00000 |

These are timing-supported candidate classes, not per-access hardware-state verification or validated core-cycle counts. Two calibration points have flagged temporal variation; all samples are retained.

- [Resident distributions](latency01/figures/resident_distributions.png)
- [First pass versus reread](latency01/figures/first_and_reread.png)
- [Full statistics](latency01/summary.csv), [next-level and paired contrasts](latency01/contrasts.csv)
- [Validation](latency01/validation.json), [run summary](latency01/run_summary.json)
- [Raw data and collection evidence](../../data/sunbird/latency01/)

This latency execution made no new cache-specification lookup. Earlier specification exposure during the capacity task is explicitly recorded in the complete experiment notes.
