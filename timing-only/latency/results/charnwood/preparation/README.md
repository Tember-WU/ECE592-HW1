# Charnwood latency preparation

Working directory: `/home/swu35/ECE592-HW1/timing-only/latency`.

The existing `configs/charnwood.json` defines all seven groups and 30 configurations. Its capacity-inference SHA-256 matched the saved Charnwood two-round inference before collection; see [capacity-basis-check.json](capacity-basis-check.json). Resident footprints are 8/16 KiB, 64/128 KiB, and 1/2 MiB. Paired memory candidates use 256/512 MiB. The configuration, source, and fixed-seed shuffled measurement order were retained.

The existing virtual environment at `../capacity/.venv` supplies Python 3.12.3, NumPy 1.26.3, and Matplotlib 3.9.4, matching `requirements.txt`. [python-environment.txt](python-environment.txt) records all installed versions.

The runner and supporting processes inherit affinity to CPUs 1 and 5. Each measurement subprocess binds itself to CPU 3 before allocation and runs under `numactl --membind=0`. CPU 7 is the SMT sibling. A short initial observation found CPU 3 approximately 0.334% busy and CPU 7 1.0% busy; another user's benchmark was active on CPU 6. The collector's own immediate preflight and per-point observations are preserved in the raw run. No CPU reservation or exclusive machine access was established.

## Commands

```bash
source ../capacity/.venv/bin/activate
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
taskset -c 1,5 make MACHINE=charnwood all check
taskset -c 1,5 python scripts/run_latency.py --machine charnwood --run-id latency01 --dry-run
taskset -c 1,5 python scripts/run_latency.py --machine charnwood --run-id latency01
# After the failed attempt and successful allocation diagnostic:
taskset -c 1,5 python scripts/run_latency.py --machine charnwood --run-id latency02 --dry-run
taskset -c 1,5 python scripts/run_latency.py --machine charnwood --run-id latency02
# After latency02 also failed, release large temporary allocations more readily:
export MALLOC_TRIM_THRESHOLD_=0
export MALLOC_MMAP_THRESHOLD_=131072
taskset -c 1,5 python scripts/run_latency.py --machine charnwood --run-id latency03 --dry-run
taskset -c 1,5 python scripts/run_latency.py --machine charnwood --run-id latency03
taskset -c 1,5 python scripts/analyze_latency.py --machine charnwood --run-id latency03
```

All measurement subprocesses execute serially in the original shuffled point order. The seven groups are part of one finite run, as in Artemisia. `latency01` and `latency02` each stopped after 11 configurations when the 512 MiB mapping could not obtain complete THP backing. A separate 16-sample diagnostic between them succeeded with full 512 MiB backing. The complete seven-group plan succeeded as **`latency03`**, with the glibc allocator environment shown above inherited by the collector and benchmark subprocesses. These settings change allocation/release behavior outside the timed loops; the exact failure cause and the allocator adjustment's individual effect were not isolated. No global memory setting, page policy, measurement configuration, or timing source was changed. Both incomplete attempts and the diagnostic are excluded from formal results. Every run ID is preserved and protected against overwrite.

## Checks and logs

- [Build and six passing functional tests](build-check.log), [dry-run plan](dry-run.log)
- [Dependent-loop assembly](time_batch.dis), [four-stream assembly](time_independent.dis), [implementation checks](implementation_checks.json)
- First attempt: [launch context](launch-context.json), [collector output](collector.log), [incomplete-run record](../latency01/RUN_NOTES.md)
- Allocation diagnostic: [command and scope](thp-probe.json), [before/after mapping log](thp-probe.txt)
- Second attempt: [dry-run plan](dry-run-latency02.log), [launch context](launch-context-latency02.json), [collector output](collector-latency02.log), [incomplete-run record](../latency02/RUN_NOTES.md)
- Complete retry: [dry-run plan](dry-run-latency03.log), [launch context](launch-context-latency03.json), [collector output](collector-latency03.log), [analysis output](analysis.log)
- [Formal run report](../latency03/RUN_NOTES.md), [raw run](../../../data/charnwood/latency03/)

On this x86-64 build, each timed loop contains 16 register-addressed loads and no stack references between timestamps. The dependent loop uses one cursor register; the independent diagnostic uses four. The C source and timing header match Artemisia's collection snapshots. The collector additionally checks final cursor progression, full huge-page backing, and CPU/NUMA evidence at every point. Architecture validation here covers execution on Charnwood's x86-64 path.
