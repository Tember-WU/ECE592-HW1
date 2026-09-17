# Crux latency01-retry1: incomplete allocation attempt

This retry completed 11 of 30 configurations, including the 256 MiB
sequential control that failed in `latency01`. Point 12,
`llc_miss__alternate` at 512 MiB, failed with
`MADV_COLLAPSE: full THP backing unavailable: Cannot allocate memory`
before warm-up or timing. No base-page fallback or kernel change was made.

The 11 completed points retain 11,000,000 batches and 13,000,000 timer
intervals, including two paired configurations. All raw samples and failure
evidence remain in `../../../data/crux/latency01-retry1/`; its console log
is `../../../data/crux/latency01-retry1-console.log`.

This incomplete attempt is excluded from the formal seven-group analysis.
The complete, unchanged protocol was retried from the beginning under the
new ID `latency01-retry2`, on the same CPU 6 / NUMA node 0. Existing runs
were not overwritten, and no global memory settings were changed.
