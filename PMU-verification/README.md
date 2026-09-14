# Section 8.3: PMU verification

Keep each verification experiment separate, with machine-specific configurations and outputs.

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

The current work covers event discovery and the three representative Artemisia experiments required
by Section 8.3: capacity, line/stride, and associativity. `common/` holds shared helpers for the latter
two. The unused latency/inclusion directories are optional placeholders, not additional required runs.
System/vendor comparison tables are not yet completed here. Section 8.4's
eight-event cross-generation study is a separate task.

No pre-run code/result snapshot or freeze checkpoint is created by these scripts. The existing
timing-only files are read in place for comparison and are not changed.
