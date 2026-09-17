# upgrade: machine-organized experiment evidence

Platform: **x86_64**. This is a byte-preserving export of the repository material for Sections 8.2–8.5. Large raw CSV files are stored as lossless gzip; their hashes refer to the original uncompressed bytes. Packaging does not rerun experiments, correct measurements or certify scientific conclusions.

| Folder | Contents |
|---|---|
| `main_code/x86_64`, `main_code/aarch64`, `main_code/common` | Architecture-specific native code, portable code, scripts/configs, and per-run source snapshots; original paths distinguish versions |
| `build` | Existing compiler/build logs, archived executables/disassembly, and an index of exact recorded commands |
| `capacity`, `line_size`, `associativity`, `inclusion_policy`, `latency` | Section 8.2; raw measurements/provenance versus derived statistics/figures |
| `pmu/raw/verification`, `pmu/processed/verification` | Section 8.3 events, capacity/stride/conflict verification, references and reports |
| `pmu/raw/counter_analysis`, `pmu/processed/counter_analysis` | Section 8.4 per-machine eight-event measurements and analysis |
| `software_hit_rate/raw`, `software_hit_rate/processed` | Section 8.5 estimator calibration, frozen parameters, PMU comparison and uncertainty |

## Exact provenance and commands

[manifest.jsonl](manifest.jsonl) maps every packaged file to its repository-relative original path, SHA-256, compression method and byte count. [build/recorded_commands.jsonl](build/recorded_commands.jsonl) indexes original build/run command values and compiler descriptions with the source file and JSON pointer. Original absolute paths are evidence; they have not been rewritten or presented as commands that can be executed verbatim on another host.

Environment and pinning may differ between experiments and runs. Read the archived per-run `environment.json`, `metadata.json`, pinning manifests and build logs rather than assuming one CPU/NUMA binding for every experiment. The current shared source and older per-run source snapshots are both preserved; the latter identifies the implementation used by an existing run. Match report listings to the appropriate snapshot before submission.

## Restore a runnable original layout

The classification intentionally separates source, build records and data. Existing scripts and report links expect their original relative layout. The restoration tool copies files and decompresses CSVs into a **new** directory without depending on the four original experiment directories:

```bash
# Run from ECE592-HW1; choose a new output directory
python3 machines/tools/restore_layout.py --machine upgrade --output /tmp/ece592-upgrade-restored
cd /tmp/ece592-upgrade-restored
```

Restoration starts no experiments. Typical entry points below use the restored layout. Native collection must run on **upgrade**, using its saved configs and a new run ID. For exact historical arguments and compilers, follow the command index above. Some collectors require a Git checkout for provenance; when collecting outside the original repository, initialize and commit the restored source/configs in a new repository first. The export records the original commit but does not embed Git history.

```bash
make -C timing-only/capacity MACHINE=upgrade
(cd timing-only/capacity && python3 scripts/run_capacity.py --machine upgrade --run-id NEW_RUN)
make -C timing-only/latency MACHINE=upgrade
(cd timing-only/latency && python3 scripts/run_latency.py --machine upgrade --run-id NEW_RUN)
# Section 8.4 (uses the actual host and its configuration)
make -C PMU_Counter_Analysis
(cd PMU_Counter_Analysis && python3 scripts/run.py --run-id NEW_RUN)
```

Line-size/associativity/inclusion scripts have legacy working-directory assumptions; their exact source and configs are supplied. See the original script headers and archived run commands. Do not blindly run the copied line-size Makefile: its current default target references the associativity source. The direct compile command/source record is the appropriate entry point. Missing historical compiler/command evidence is not reconstructed by guessing.

Section 8.3 uses host-specific workflows. In the restored `PMU-verification/`, start with `README.md`, `SKYLARK.md` (AMD), or `THUNDERBIRD.md` (Arm), and the relevant per-host run notes. Do not transfer raw PMU event encodings between architectures.

## Coverage and preserved limitations

| Source experiment | Existing evidence files |
|---|---:|
| capacity | 386 |
| line_size | 89 |
| associativity | 25 |
| latency | 114 |
| inclusion | 83 |
| pmu_verification | 244 |
| counter_analysis | 519 |
| software_hit_rate | 0 |

Counts indicate material present, not a passing experiment. Failed/retried/preflight runs are retained with their original status. Association sweep files containing only medians/eviction probabilities are classified as processed data; packaging cannot recreate missing raw distributions. Inclusion verdicts and low sample counts remain unchanged and require the limitations documented in the experiment/PMU reports.

**Section 8.5: no machine-specific configuration/run was found in the supplied source tree.** The raw/processed folders are placeholders; shared estimator code is included for later adaptation. No results from another host have been substituted.

Cross-machine Section 8.4 comparisons, including historical partial comparisons and the final eight-host comparison, are under `../cross_machine/pmu/processed/counter_analysis/`. Restore with `--machine all` to reproduce their multi-host analysis.

Exported files: 2208; categories: {'code': 394, 'raw': 1507, 'processed': 280, 'build': 27}.
