# Section 8.3: PMU verification

Keep each verification experiment separate, with machine-specific configurations and outputs.

Sunbird's Section 8.3 execution and system/reference comparison are documented in
[common/results/sunbird/RUN_NOTES.md](common/results/sunbird/RUN_NOTES.md).
The run order is capacity, line size, then associativity. Sunbird uses two separately
pinned counter pairs per unchanged workload because the original four-event group
cannot be scheduled on this host. Each pass retains one million timed batches.

| Directory | Purpose |
|---|---|
| [events](events/README.md) | Local `perf list` descriptions, event encodings, and access/scheduling probes. |
| [capacity](capacity/README.md) | Timing and hardware-miss evidence around selected capacity boundaries. |
| [line_size](line_size/README.md) | Completed Artemisia stride validation; supports 64 B spatial granularity visible in L1. |
| [associativity](associativity/README.md) | Completed Artemisia conflict validation; distinguishes the L1 threshold from the L2 threshold. |

Each experiment uses `configs/<machine>.json`, `scripts/`, `data/<machine>/<run-id>/`, and
`results/<machine>/<run-id>/`. Capacity also contains its benchmark in `src/` and functional checks
in `tests/`. Every collection requires a new run ID. Data and results include failed attempts when
applicable. Build products and uncompressed temporary arrays are ignored by Git; compressed raw
samples, counter outputs, configurations, scripts, and figures are retained.

The current work covers event discovery and the three representative experiments on Artemisia and Sunbird required
by Section 8.3: capacity, line/stride, and associativity. `common/` holds shared helpers for the latter
two. The unused latency/inclusion directories are optional placeholders, not additional required runs.
Sunbird's system/vendor comparison is included in its run notes. Section 8.4's eight-event
cross-generation study is a separate task.

Legacy configurations read timing-only files in place. Sunbird configurations reference
the pre-PMU [Phase-I freeze](phase1-freeze/sunbird/freeze01/README.md); the analyzers read
its copied summaries. A separate [PMU implementation snapshot](common/data/sunbird/source01/manifest.json)
records the scripts, kernels, configurations, executables and disassemblies used for this run.
Phase-I files and Artemisia results are preserved.
