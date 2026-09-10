# Charnwood experiment preparation and reproduction

Working directory: `/home/swu35/ECE592-HW1/timing-only/capacity`.

The two collection rounds run serially on CPU 3 / NUMA node 0, with SMT sibling CPU 7 monitored. CPU topology and a brief load observation were used for CPU selection; cache specifications were not consulted. The runner and analysis processes inherit affinity to CPUs 1 and 5; the benchmark explicitly binds itself to CPU 3 before first-touch allocation. Other users' active processes were left running and are documented in the preflight JSON records.

System Python lacked `pip` and `ensurepip`. A local `.venv` was created with `python3 -m venv --without-pip .venv`; pip was bootstrapped there from `https://bootstrap.pypa.io/get-pip.py`. The exact NumPy 1.26.3 and Matplotlib 3.9.4 versions in the existing `requirements.txt` were installed in that environment. System packages were not changed. [python-environment.txt](python-environment.txt) records the resolved Python dependencies. Python was 3.12.3; the compiler and kernel are recorded in each raw run's `environment.json`.

## Commands

The following shows the substantive commands used. Existing run IDs and generated planning configurations are protected against overwrite; use new IDs/output paths for any future collection. Wrapper code saved stdout/stderr to the logs in this directory and captured a 3-second `/proc/stat` observation plus a process snapshot immediately before each round.

```bash
source .venv/bin/activate
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
taskset -c 1,5 make MACHINE=charnwood capacity assembly
taskset -c 1,5 make check
taskset -c 1,5 python scripts/run_capacity.py --machine charnwood --run-id round1 --dry-run
taskset -c 1,5 python scripts/run_capacity.py --machine charnwood --run-id round1
taskset -c 1,5 python scripts/analyze_capacity.py --machine charnwood --run-id round1

# Intervals selected after inspecting the new round-1 curve and statistics.
# The exact rationale supplied through --note is preserved in the generated config.
taskset -c 1,5 python scripts/plan_capacity.py --machine charnwood --from-runs round1 \
  --round 2 --l1 32KiB:64KiB --l2 256KiB:512KiB --llc 4MiB:8MiB \
  --output configs/charnwood-round2.json
taskset -c 1,5 python scripts/run_capacity.py --machine charnwood \
  --config configs/charnwood-round2.json --sweep all --run-id round2 --dry-run
taskset -c 1,5 python scripts/run_capacity.py --machine charnwood \
  --config configs/charnwood-round2.json --sweep all --run-id round2
taskset -c 1,5 python scripts/analyze_capacity.py --machine charnwood --run-id round2
taskset -c 1,5 python scripts/analyze_capacity.py --machine charnwood \
  --run-id round1 round2 --output-id combined12 \
  --boundaries results/charnwood/combined12/boundaries.json
taskset -c 1,5 python results/charnwood/preparation/validate_runs.py round1 round2
```

## Records

- [Build output](build.log), [10 passing existing checks](check.log)
- [Round-1 dry run](dry-run-round1.log), [preflight](preflight-round1.json), [collection](collection-round1.log), [analysis](analysis-round1.log)
- [Round-2 dry run](dry-run-round2.log), [preflight](preflight-round2.json), [collection](collection-round2.log), [analysis](analysis-round2.log)
- [Combined analysis](analysis-combined12.log), [supplemental validation script](validate_runs.py), [validation output](validation.log)

The original benchmark, runner, planner, analyzer, common protocol, and Artemisia data were retained. The supplemental validator recomputes statistics from compressed samples and checks them against each round's CSV, checks manifest/config/analysis agreement and snapshot hashes, and validates before/after CPU/NUMA/page-backing logs. Passing these checks does not establish absence of interference.
