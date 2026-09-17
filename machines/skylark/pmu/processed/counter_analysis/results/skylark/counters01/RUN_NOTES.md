# Skylark section 8.4 run notes

Completed natively on skylark.ece.ncsu.edu using the existing suite and Skylark profile. Full protocol: three workloads × three repetitions × (one timing pass + eight single-event passes). All 81 passes completed: 9,000,000 timing samples and 72 PMU passes. Each pass executes 64,000,000 dependent chain loads; counts are normalized per 1,000 chain loads. Initialization and two warm-up traversals are excluded.

## Results

| Workload | Footprint | Median of three timing medians (TSC ticks/access) | Local-cache fills / 1,000 loads | Local DRAM/IO fills / 1,000 loads |
|---|---:|---:|---:|---:|
| L1-resident | 16 KiB | 4.125 | 0.000266 | 0 |
| LLC-sized | 16 MiB | 113.625 | 775.532 | 270.627 |
| Beyond LLC | 64 MiB | 279.375 | 122.982 | 873.215 |

L1-resident timing and negligible deeper traffic support the intended residency. The LLC-sized workload receives substantial local-cache service but also local DRAM/IO fills; it is not an isolated LLC-hit measurement. Beyond LLC, local-cache fills fall and local DRAM/IO fills rise, alongside higher timing medians. These are separate-pass counts, not simultaneous mutually exclusive hit/miss probabilities. TSC ticks are not core cycles.

The 16 MiB LLC is the pinned CPU's sysfs sharing domain, not the 512 MiB machine-wide sum. CPU 4, socket 0, NUMA node 0; no enabled SMT sibling (thread_siblings_list=4). Allocation follows pinning and requests base pages. No exclusive CPU/cache reservation was made. Activity snapshots are retained. Across the 81 measured intervals there were 20 minor faults, zero major faults, and 382 involuntary context switches. All 72 PMU passes had positive equal enabled/running times, with no multiplex scaling. All timing samples and outliers remain included.

## Event interpretation and repeat anomaly

Five generic slots worked. Unsupported generic stores, LLC loads, and LLC misses used the existing profile's documented raw alternatives: local-L2 fills (0x143), local-cache fills excluding local L2 (0x243), and local DRAM/IO fills (0x843). These are not stores, total LLC accesses, or direct LLC misses. Exact selections, meanings and probe errors are in selected_events.json and probes/. Generic AMD names also require the mapping caveats in source/docs/generic_mapping_review.md; matching Intel spellings do not establish matching cache levels or request scope. Counts above 1,000 per 1,000 loads must not be clamped into probabilities.

The original LLC-sized dTLB result spans 0.010797–509.298641 events per 1,000 loads, with median 508.646984. Three targeted full-length diagnostic reruns, using the original snapshotted binary, CPU, footprint, event, and each repetition's seed, returned 507.934203, 508.525391, and 509.280594. Each diagnostic interval was fully scheduled. Exact commands and raw results are in diagnostics/. The near-zero original result did not recur; its cause remains unresolved. Diagnostics are supplemental and do not replace any original sample or enter the rankings. Treat that original TLB ranking as unstable despite the consistent follow-up.

LLC-sized local DRAM/IO fills also vary (236.634641–487.439172 per 1,000 loads), and timing medians range from 105 to 123 TSC ticks/access. Preserve these ranges rather than claiming an uncontended or precisely isolated cache latency.

## Artifacts and validation

- analysis/REPORT.md: all eight normalized event tables and interpretation caveats.
- analysis/workload_comparison_skylark.pdf: compact eight-event workload panel; PNG also supplied.
- analysis/: 19 PDF plots and PNG counterparts, timing distributions, ranked panels, rank matrices, generation plots, coverage and raw/normalized CSVs.
- raw/: original per-pass counts, logs and nine compressed timing arrays.
- source/, source_sha256.json: reproducible source, binary, disassembly, configuration and evidence snapshot; all 50 archived file hashes verified.
- ../../comparison_artemisia_skylark01/: combined full-run rankings and plots for the two available machines. Six ECE hosts remain uncollected here; this is not the completed eight-machine section.

Validation: make test passed all six tests; preflight and smoke collection/analysis passed; full coverage audit reports 81/81 and full_sample_coverage=True. The workload plot was visually checked. No benchmark/configuration changes or system settings changes were needed.

Contributor label: Preet Patel, following the existing Artemisia run notes. AI assistance: Codex executed collection, checked results, generated plots through the existing analyzer, and wrote these notes. Review the interpretation and include the project's AI-assistance disclosure in the final submission.
