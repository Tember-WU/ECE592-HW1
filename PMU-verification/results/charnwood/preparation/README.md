# Charnwood PMU preparation and reproducibility

The [completed report](../REPORT.md) covers Section 8.3 capacity, line/stride and associativity. Collection was serial, with 38 million samples total. This directory preserves the preparation, launch and completion evidence.

## Phase-I checkpoint

`phase1-frozen.json` records SHA-256 for 116 relevant Phase-I files and Git commit `f86eecbb6fce590f3d40b64487620888b33dcd93` at 2026-09-14 15:29:15 UTC, before discovery/collection. The current files were read in place and never rewritten. `post-run-validation.json` verifies them after collection, all successful PMU raw/count hashes, sample totals and serial ordering. Supplemental latency/inclusion comparison files match that pre-run Git commit. These are provenance/integrity checks, not independent statistical replications.

`source/` and `source-hashes.json` preserve PMU configurations, implementations, helpers and build instructions as prepared for the initial attempts. `source-retry/` preserves the later capacity runner change adding bounded premeasurement allocation retries. The benchmark C/C++ sources did not change. Saved binaries, disassembly, effective configs, exact per-point commands and environment logs are in each data directory; successful runs also have `binary-sha256.json`.

## Build, probes and commands

Python was reused from `/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin/python` (NumPy 1.26.3, Matplotlib 3.9.4); see `python-environment.txt`. Build logs and the capacity/shared functional test logs are retained. Five capacity tests and five shared tests passed, including live four-counter smoke checks; the shared checks passed again after the CPU 4 binding was set. Dry runs validated the three point grids. Python compilation also checked the later retry adapter; the completed formal run exercised its successful first-attempt path.

From `/home/swu35/ECE592-HW1/PMU-verification`:

```bash
export PATH=/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:$PATH
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
make -C capacity MACHINE=charnwood all check
make -C line_size MACHINE=charnwood all
make -C associativity MACHINE=charnwood all
python common/test_verification.py -v
python events/scripts/discover_events.py --machine charnwood --run-id discovery02
python results/charnwood/preparation/run_pipeline.py capacity:capacity03 line_size:line_size01 associativity:associativity01
```

These are the recorded IDs; **choose fresh IDs to rerun**. Collectors refuse to overwrite data/results, and the pipeline refuses existing launch/log filenames. `run_pipeline.py` runs each collector and analyzer in order and preserves evidence on failure. It continues to later experiment types if an earlier collector fails; per-run manifests and analyzers, not the pipeline exit alone, establish success. All three final collectors and analyzers succeeded in this execution.

The helper/analysis processes use CPUs 1,5. Capacity pins itself to CPU 3; line_size and associativity use CPU 4 through the existing taskset/numactl sequence. All allocations bind node 0. `capacity03-launch.json`, `line_size01-launch.json`, `associativity01-launch.json` contain fresh process/command snapshots. The pipeline sets `MALLOC_TRIM_THRESHOLD_=0` and `MALLOC_MMAP_THRESHOLD_=131072` as inherited per-process environment; it does not change global VM settings. Earlier `launch-context-retry.json` inherited the original process-list snapshot and must not be treated as a fresh process census at its later timestamp.

The local perf build reports selected events under `default_core/event=...,period=...,umask=.../`. Discovery and runners now accept that PMU prefix in addition to the original `cpu/` spelling. The raw encoding and usable four-event group were rechecked on Charnwood. `discovery01` is retained with incomplete parsed encoding fields from the old parser; **discovery02 is the final complete inventory**. perf emitted a tracing-directory warning while listing selected hardware events; the hardware listing, live probes and formal groups succeeded. Raw warning output is preserved.

## Failed allocation attempts

`capacity01` and `capacity02` failed on the first shuffled 7 MiB workload before sampling, with `MADV_COLLAPSE: Cannot allocate memory`. Both have failed manifests, logs and binaries, no formal timing samples, and are excluded from analysis. The initial collector log is `capacity-collect.log`; the second is `capacity02-collect.log`.

`thp-diagnostic/` contains an excluded 16-sample allocation diagnostic: 2 MiB succeeded, the 7 MiB workload requiring an 8 MiB mapping failed. Free memory and buddy-list observations suggested transient large-page scarcity, but the exact cause was not isolated. No other user's processes were stopped and no global cache flush/VM reconfiguration was performed.

The later runner permits at most six attempts, separated by ten seconds, only when the log is exactly the premeasurement THP allocation error and neither raw samples nor counts exist. It archives each failed attempt. Measurement failures or partial samples are never retried/discarded by this mechanism. The successful `capacity03` completed all 14 points on their first attempt; hence this run does not establish the efficacy of the retry mechanism or allocator settings.

## System comparison

`lscpu.txt`, `cpu-topology.txt`, `system-cache-geometry.json` and the read-only `cpuid_cache.c` / `cpuid-cache.txt` record system organization after the Phase-I checkpoint. The CPUID utility was compiled with `gcc -O2 -Wall -Wextra -Werror` and executed on CPU 1; it is an inventory tool, not another benchmark. Leaf-4 maximum addressable sharers is not an actual online-CPU count; sysfs supplies actual sharing lists. External references and precise source locators are linked at their claims in the completed report.
