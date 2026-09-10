# Ookay latency results

The requested seven-group experiment is complete. Use **`latency01-retry2`**, which contains all 30 configurations, 30,000,000 batches, and 39,000,000 recorded timer intervals. Collection took 120.22 seconds on CPU 2 / NUMA node 0, and all integrity checks passed.

Start with the [complete experiment record](latency01-retry2/RUN_NOTES.md), [resident distributions](latency01-retry2/figures/resident_distributions.png), and [first-pass/reread distributions](latency01-retry2/figures/first_and_reread.png).

The L1/L2/LLC resident median ranges are 3.67188, 10.71094–10.71875, and 30.88281–32.39062 TSC ticks per dependent load. The report distinguishes next-level first-pass latency, same-address reread benefit, and differences against separately measured resident references. These are timing-supported candidates, not hardware-confirmed hit/miss labels or validated core cycles.

`latency01` and `latency01-retry1` are preserved incomplete attempts that stopped at a large-page allocation failure. They are excluded from the formal results. Non-timed memory-allocation preparation preceded the successful full restart; see the [recovery record](../../data/ookay/recovery.json).

To regenerate the successful run's analysis from the latency directory, using the pinned Python environment prepared for the earlier capacity experiment:

```bash
../capacity/.venv/bin/python scripts/analyze_latency.py --machine ookay --run-id latency01-retry2
```

The existing [Ookay configuration](../../configs/ookay.json) and measurement/analysis source were used unchanged. [Raw data, snapshots, and logs](../../data/ookay/latency01-retry2/) preserve the complete successful run; [preparation.json](../../data/ookay/preparation.json) records dependencies and the checked capacity basis. All six existing functional tests passed before formal collection.
