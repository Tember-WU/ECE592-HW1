# Crux latency01: incomplete allocation attempt

The first attempt completed 6 of the 30 planned configurations. Point 7,
`calibration__memory_sequential` at 256 MiB, failed with
`MADV_COLLAPSE: full THP backing unavailable: Cannot allocate memory`
before warm-up or timing. The collector stopped as required by the page
policy; no fallback to base pages was used.

The six completed points retain 6,000,000 batches and 8,000,000 timer
intervals, including the two paired configurations. Their raw arrays,
logs, source/executable snapshots, and failed manifest are preserved in
`../../../data/crux/latency01/`. The complete console log is
`../../../data/crux/latency01-console.log`.

This incomplete run is excluded from the formal seven-group analysis.
The same configuration, CPU 6 / NUMA node 0, point order, seeds, batch
counts, and page policy were retried from the beginning under the new ID
`latency01-retry1`. No other user's processes or global memory settings
were changed.
