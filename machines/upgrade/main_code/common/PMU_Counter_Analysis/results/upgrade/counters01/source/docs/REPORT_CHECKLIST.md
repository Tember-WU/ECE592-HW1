# Section 8.4 requirement → evidence

| Requirement | Produced evidence | Final action |
|---|---|---|
| Same three microbenchmarks, eight events, all ECE machines (3 points) | `src/bench.cpp`, per-host `metadata.json`, `selected_events.json`, `raw/`, `records.json`, `coverage.csv` | Run all eight native hosts; inspect size/domain choices and event behavior |
| Normalize with a stated denominator (1 point) | `raw_counts.csv`, `normalized_summary.csv`, methodology/README | Explain count × 1000 / exact chain loads; separate timing instrumentation |
| Rank each workload by all eight events (2 points) | `rankings.csv`, three `ranked_*.pdf` panels, three `rank_matrix_*.pdf`, compact `REPORT.md` tables | Combine one complete run per host |
| Compare Intel/AMD/Arm and older/newer generations (2 points) | `event_semantics.csv`, `generations_*.pdf`, mapping review and source evidence | Write evidence-based comparisons and explain noncomparable proxies |
| At least one million timed samples per tested configuration | Raw compressed uint64 batches and `timing_statistics.csv` | Verify `coverage.csv`; exclude smoke data |
| Distribution statistics and boxes | Mean, median, population SD, Q1/Q3, P5/P95, Tukey outlier count, `box_*.pdf` | Explain batching, whiskers, overhead and timer units |
| Main source listings and experimental logic diagram | Complete portable `src/bench.cpp`, `docs/figures/methodology.pdf` | Include listing/diagram in the report body |
| Reproduction and provenance | README, source/binary/disassembly snapshots, hashes, command/error logs and Slurm template | Preserve final Git commit and identify final run directories |
| Contributor attribution and AI disclosure | `--contributor` labels and report draft reminders | Supply actual people/accounts and disclose actual assistance |

A generated plot or complete single-host run is not proof that the eight-machine section is finished. The analysis explicitly lists missing hosts. Counter access on AMD/Arm and generic-event semantic differences are real limitations to report, not values to replace with invented measurements.
