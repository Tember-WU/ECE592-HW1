# Upgrade round-1 coarse scan

The completed first round is `round1-retry2`: 39/39 configurations and 39,000,000 timed batches. Collection started at 2026-09-10T16:54:31.128053+00:00 and finished at 16:57:04.075465+00:00, taking 152.95 seconds. Every configuration retained all 1,000,000 samples.

The shared `configs/common/round1.json` protocol and original C kernel were used unchanged: CPU 2, NUMA node 0, 64 B spacing, 256 dependent loads per batch, complete huge-page backing and `-O0`. Units are TSC ticks per dependent load; the empty-timer median is 34 ticks per interval. No cache geometry or PMU measurements were consulted.

## Follow-up intervals selected from this scan

| Candidate | Lower point: random median | Upper point: random median | Round-2 interval |
|---|---:|---:|---|
| L1D | 32 KiB: 3.3398 | 64 KiB: 8.8477 | 32–64 KiB |
| L2 | 256 KiB: 8.9336 | 512 KiB: 23.2617 | 256–512 KiB |
| LLC effective transition | 4 MiB: 27.9414 | 8 MiB: 114.5898 | 4–8 MiB |

These intervals choose follow-up measurements; they are not established capacities or confidence intervals. The coarse curve shows three residency regions at approximately 3, 9 and 26–28 ticks/load before the memory-access region. Large-footprint medians rise toward approximately 205 ticks/load. The 512 MiB endpoint adequately covers this region, so no extension was selected.

## Integrity and operating conditions

All raw hashes, sample counts and recomputed statistics passed validation. CPU start/end values were 2, and before/after mapping logs show complete huge-page backing entirely on node 0 at all 39 points. No measurement page faults or voluntary context switches occurred. Involuntary context switches totaled 276, with a maximum of 35 per point. CPU 8, the SMT sibling, recorded 0–3.98% average busy time over individual benchmark subprocess intervals.

Another `cache_bench` process was observed on CPU 0 before the first attempt. It was not interrupted. This is a shared-machine measurement; the checks do not establish absence of shared-cache or scheduling interference, and all outliers are retained.

Two earlier attempts, `round1` and `round1-retry1`, each stopped after 4/39 points when the 512 MiB random point failed `MADV_COLLAPSE` with `Cannot allocate memory`. Both incomplete directories remain preserved and are excluded from this analysis. A separate page-only diagnostic achieved 492 MiB of huge-page coverage on a 512 MiB scratch mapping despite three collapse calls. A bounded 1 GiB anonymous allocation/touch/release was then performed before this fresh full sweep. The successful sweep used the unchanged collector and required full backing at every point; no fallback to base pages or system-setting changes were made.

The project-local `.venv` contains Python 3.10.12, NumPy 1.26.3 and Matplotlib 3.9.4. Ubuntu's `numactl` 2.0.14-3ubuntu2 package was extracted under `.venv/native/root`; no system installation was needed. The existing 10 tests passed before collection. Exact Python package versions, build/test logs, commands, source/executable snapshots and preparation records are saved with the raw run.

## Files

- [Capacity curve](figures/capacity_s64_b256_huge.png), [box plots](figures/boxplots_s64_b256_huge.pdf)
- [Statistics](summary.csv), [transitions](transitions.csv), [validation](validation.json), [provenance](provenance.json)
- [Raw run and preparation records](../../../data/upgrade/round1-retry2/)
- [Generated second-round configuration](../../../configs/upgrade-round2.json)
- [Combined two-round record](../combined12/RUN_NOTES.md)
