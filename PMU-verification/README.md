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

Crux's completed verification is indexed in [Crux verification01](results/crux/verification01/README.md):
14 capacity points, 12 line/stride points, and 12 associativity points, each with one million
timed batches. It includes the Phase-I checkpoint, local event discovery, system/Agner Fog
comparison, disagreement analysis, failed-attempt inventory, and reproduction commands.

| Directory | Purpose |
|---|---|
| [events](events/README.md) | Local `perf list` descriptions, event encodings, and access/scheduling probes. |
| [capacity](capacity/README.md) | Timing and hardware-miss evidence around selected capacity boundaries. |
| [line_size](line_size/README.md) | Machine-specific stride and traversal-order validation. |
| [associativity](associativity/README.md) | Machine-specific conflict validation with separate L1/L2 miss evidence. |

Each experiment uses `configs/<machine>.json`, `scripts/`, `data/<machine>/<run-id>/`, and
`results/<machine>/<run-id>/`. Capacity also contains its benchmark in `src/` and functional checks
in `tests/`. Every collection requires a new run ID. Data and results include failed attempts when
applicable. Build products and uncompressed temporary arrays are ignored by Git; compressed raw
samples, counter outputs, configurations, scripts, and figures are retained.

The current work covers event discovery and the three representative experiments on Artemisia,
Sunbird, Charnwood, Ookay, Upgrade and Crux required by Section 8.3: capacity, line/stride, and associativity. `common/`
holds shared helpers for the latter two. The unused latency/inclusion directories are optional
placeholders, not additional required runs.
Sunbird's system/vendor comparison is included in its run notes. Charnwood's
[completed report](results/charnwood/REPORT.md) includes the system/vendor comparison,
PMU evidence and disagreement analysis. Ookay's system/vendor comparison is complete in its
linked report; Artemisia's is pending.
Upgrade's [report and system/vendor comparison](reports/upgrade/README.md) records the frozen
Phase-I inferences, PMU evidence, disagreements, source pages, and reproducibility checks.
Crux's system/vendor comparison and disagreement analysis are included in its linked overview.
Section 8.4's eight-event cross-generation study is a separate task.

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
For Upgrade, a separate [Phase-I freeze](phase1_freeze/upgrade/freeze01/manifest.json) was saved before
formal PMU collection and before system/vendor cache-geometry comparison. It hashes all selected
original data and copies small results, configurations, and source files. Artemisia's historical runs
did not have this checkpoint.

For Crux, [freeze01](phase1/crux/freeze01/FREEZE.md) was explicitly created before PMU probes,
and each complete run has a post-collection `reproduction/` source/binary archive.
Capacity offers optional bounded retries only for THP allocation failures before measurement;
the default remains zero retries. Both `--allocation-attempts` (1–6 total attempts, 10-second
intervals) and `--allocation-retries` (0–30 retries, 2-second intervals) are supported; choose one.

Charnwood completed `capacity03` (14 points), `line_size01` (12 points) and `associativity01`
(12 points) serially on 2026-09-14, with one million samples per point and four simultaneous events.
The two earlier capacity allocation failures are preserved and excluded from formal analysis.
