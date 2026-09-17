# Crux capacity: capacity04 (failed)

This attempt completed 4 of 14 points, retaining 4 million timed batches. It is excluded from the formal capacity05 result; no partial arrays were pooled.

The next point `L1_w40960` failed before warm-up, PMU enable, or timing with `MADV_COLLAPSE: Cannot allocate memory`. See [allocation log](logs/L1_w40960.txt) and [manifest](manifest.json). No base-page fallback or machine-wide memory setting change was used.

Complete result: [capacity05](../../../../capacity/results/crux/capacity05/RUN_NOTES.md). The later runner permits only bounded retries of this specific premeasurement allocation error.
