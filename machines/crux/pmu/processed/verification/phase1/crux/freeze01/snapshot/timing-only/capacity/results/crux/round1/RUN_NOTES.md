# Crux initial round-1 attempt: incomplete

This attempt completed 4 of 39 configurations. Configuration 5, the 512 MiB
random chain, failed at `MADV_COLLAPSE` with `Cannot allocate memory`, before
warm-up or timed sampling. The runner stopped as required by the huge-page
policy. No fallback to base pages or measurement-kernel change was made.

The original manifest, four complete raw arrays, source/executable snapshots,
and failure log remain in `../../../data/crux/round1/`. The console log is
`../../../data/crux/round1-console.log`.

The complete first-round protocol was retried under the fresh ID
`round1-retry1`, with the same CPU 6, NUMA node 0, seeds, order, sample counts,
and page policy. This incomplete attempt is excluded from point selection
and the final combined analysis. Its four million timed batches are retained
as separate evidence and are not counted in the intended two-round total.
