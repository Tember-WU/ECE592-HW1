# Section 8.3: PMU verification

Keep each verification experiment separate, with machine-specific configurations and outputs.

Sunbird's Section 8.3 execution and system/reference comparison are documented in
[common/results/sunbird/RUN_NOTES.md](common/results/sunbird/RUN_NOTES.md).
The run order is capacity, line size, then associativity. Sunbird uses two separately
pinned counter pairs per unchanged workload because the original four-event group
cannot be scheduled on this host. Each pass retains one million timed batches.

Ookay's completed experiments and Section 8.3 timing/PMU/system comparison are in
[the Ookay report](results/ookay/SECTION_8_3_REPORT.md): 59 million repetitions across capacity,
line/stride (two complete runs), and associativity (including a nine-point follow-up).
The report preserves the LLC/line-size limits and the incorrect original L2 associativity label.

| Directory | Purpose |
|---|---|
| [events](events/README.md) | Local `perf list` descriptions, event encodings, and access/scheduling probes. |
| [capacity](capacity/README.md) | Timing and hardware-miss evidence around selected capacity boundaries. |
| [line_size](line_size/README.md) | Stride validation with access-order controls. |
| [associativity](associativity/README.md) | Conflict validation that distinguishes L1 misses from L2 misses. |

Each experiment uses `configs/<machine>.json`, `scripts/`, `data/<machine>/<run-id>/`, and
`results/<machine>/<run-id>/`. Capacity also contains its benchmark in `src/` and functional checks
in `tests/`. Every collection requires a new run ID. Data and results include failed attempts when
applicable. Build products and uncompressed temporary arrays are ignored by Git; compressed raw
samples, counter outputs, configurations, scripts, and figures are retained.

The current work covers event discovery and the three representative experiments on Artemisia,
Sunbird, Charnwood and Ookay required by Section 8.3: capacity, line/stride, and associativity. `common/`
holds shared helpers for the latter two. The unused latency/inclusion directories are optional
placeholders, not additional required runs.
Sunbird's system/vendor comparison is included in its run notes. Charnwood's
[completed report](results/charnwood/REPORT.md) includes the system/vendor comparison,
PMU evidence and disagreement analysis. Ookay's system/vendor comparison is complete in its
linked report; Artemisia's is pending. Section 8.4's eight-event cross-generation study is a separate task.

Legacy configurations read timing-only files in place. Sunbird configurations reference
the pre-PMU [Phase-I freeze](phase1-freeze/sunbird/freeze01/README.md); the analyzers read
its copied summaries. A separate [PMU implementation snapshot](common/data/sunbird/source01/manifest.json)
records the scripts, kernels, configurations, executables and disassemblies used for this run.
Phase-I files and Artemisia results are preserved.

The core collectors do not create Phase-I freeze checkpoints. Charnwood's
[preparation workflow](results/charnwood/preparation/README.md) separately records source snapshots,
a pre-run Phase-I hash checkpoint and its post-run verification. Existing timing-only files are read
in place for comparison and are not changed.
For Ookay, a separate [pre-discovery Phase-I freeze](results/ookay/phase1-freeze01/manifest.json)
was created before event discovery and system/vendor lookup; the original hashes were checked again afterward.

Charnwood completed `capacity03` (14 points), `line_size01` (12 points) and `associativity01`
(12 points) serially on 2026-09-14, with one million samples per point and four simultaneous events.
The two earlier capacity allocation failures are preserved and excluded from formal analysis.
