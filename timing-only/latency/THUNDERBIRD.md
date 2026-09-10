# Thunderbird latency: native AArch64 execution

The seven-group experiment uses the existing `configs/thunderbird.json` and the existing AArch64 kernels in `src/timing.h` and `src/latency_bench.c`. The benchmark source, machine configurations, collector, analyzer, and all Artemisia data/results are retained without changes. The seven groups comprise 30 configurations; the original `order_seed=59280` shuffles their order, and each process executes serially under CPU 32 / NUMA node 0 binding.

## Capacity evidence and native checks

The configuration's capacity-inference hash was checked against `../capacity/results/thunderbird/combined12/inference.json` and matches exactly. The working sets therefore use this host's measured plateaus: L1 candidates 16/32 KiB, L2 candidates 256/512 KiB, LLC candidates 4/8 MiB, and large-footprint candidates 256/512 MiB. A copy of the capacity inference used for the check is archived under `data/thunderbird/preflight/`.

The dependent and four-stream AArch64 kernels each have 16 load instructions between counter reads. The former uses one pointer dependency stream and the latter four. Native disassembly inspection found no stack accesses or calls between counter reads. Both use the existing `DSB/ISB/CNTVCT_EL0` timing sequence. The timer frequency is 25 MHz, so one tick is 40 ns; generic-timer ticks are not core cycles. Frequency calibration against CLOCK_MONOTONIC_RAW passed the existing 1% tolerance.

Six functional tests and eight native smoke configurations passed. Smoke configurations cover every mode, 1024-load timing, full THP backing up to the 512 MiB paired case, and an explicit base-page paired check. These small functional/smoke runs are excluded from the formal 30 configurations and their sample counts.

One test-only change was needed: the native kernel fixture originally used 16 loads/batch. On this ARM host, the four-independent-stream fixture produced zero intervals at that size; a diagnostic on the original test CPU observed 5,726 zero intervals among 100,000 four-stream intervals. The ARM fixture now uses the formal 256-load batch length, while the x86 fixture remains at 16. The original test is preserved at `data/thunderbird/preflight/source_before/tests/test_latency.py`, alongside the initial failing test log and the passing rerun. Neither the benchmark kernel nor the formal experiment parameters were changed to resolve this fixture issue. Empty-timer zero intervals remain allowed; nonempty formal intervals must remain positive.

## Dependencies and commands

The run reuses the working Python environment and locally extracted `numactl` from the preceding capacity experiment. No system package or governor changes are needed.

```bash
cd /home/swu35/ECE592-HW1/timing-only/latency
export PATH="$PWD/../capacity/.venv/bin:$PWD/../capacity/build/thunderbird/deps/usr/bin:$PATH"
make MACHINE=thunderbird all
make MACHINE=thunderbird check
python3 scripts/run_latency.py --machine thunderbird --run-id latency01 --dry-run
python3 scripts/run_latency.py --machine thunderbird --run-id latency01
python3 scripts/analyze_latency.py --machine thunderbird --run-id latency01
```

The collector refuses to overwrite an existing run ID. Use a new ID for a new collection; analysis can be rerun for the same completed input. The formal data and exact collection-time code snapshots are in `data/thunderbird/latency01/`. Analysis snapshots, plots, statistics, and interpretation are in `results/thunderbird/latency01/`.

Preflight evidence is in `data/thunderbird/preflight/`: `original_files_sha256.json`, `native_checks.json`, inspected `.dis` files, smoke logs/arrays, `tests.initial.log`, `tests.log`, and `plan.log`. The original file hashes cover 151 files present before this run; the only modified original file is the backed-up test fixture. All other original files are checked again when writing the final preservation record.

## Completed run

`latency01` completed all 30 configurations and 39,000,000 timer intervals in 223.41 seconds. See the [Chinese results and interpretation](results/thunderbird/latency01/RUN_NOTES.md), [integrity validation](results/thunderbird/latency01/validation.json), and [plan/preservation/runtime audit](results/thunderbird/latency01/run_audit.json). Three descriptive temporal-drift flags are retained and explained in the report.
