# Artemisia round-2 collection record

All 57/57 configurations completed, with 1,000,000 timed batches per point and 57,000,000 batches in total. Collection took approximately 8 minutes 2 seconds. The round included L1/L2 refinement, repeats with new seeds, sequential/layout/longer-batch controls, and bounded LLC layout/base-page controls.

Raw data are located in `../../../data/artemisia/round2/`; the round configuration is `../../../configs/artemisia-round2.json`. Checks of raw-data integrity, CPU/NUMA binding, and actual page backing passed; see [validation.json](validation.json). **This round experienced substantial scheduling interference: 115,454 involuntary context switches in total, with up to 16,359 at one point. Passing validation does not establish the absence of interference.** All samples have been retained.

For the full interpretation and discussion of whether a third round is needed, see the [combined two-round experiment record](../combined12/RUN_NOTES.md). Statistics and figures for round 2 alone remain in this directory. Final comparisons should also use round 1 and the [combined statistics](../combined12/summary.csv).
