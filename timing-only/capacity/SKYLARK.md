# Skylark: two-round capacity experiment

Working directory: `/home/swu35/ECE592-HW1/timing-only/capacity`.

Skylark uses AMD EPYC 7532 processors and Linux x86-64, whereas the archived
Artemisia runs used Intel Xeon Gold 5420+. The original C source, Makefile,
collector, planner, analyzer, shared first-round protocol, and Artemisia
configurations/results are retained unchanged. `configs/skylark.json` selects
CPU 32 and NUMA node 1. This CPU has no enabled SMT sibling. CPU 32 was idle
in the short preflight observation; affinity is not an exclusive reservation.

## Compatibility checks

- `rdtscp`, `constant_tsc`, `nonstop_tsc`, and SSE2 are present. The original
  `LFENCE/RDTSC/LFENCE ... RDTSCP/LFENCE` timer and 16 dependent assembly loads
  compile and execute. The disassembly was inspected. Results remain in TSC
  ticks per load, not validated core cycles.
- AMD LFENCE ordering depends on processor/OS configuration. Linux 5.14's
  [AMD initialization code](https://github.com/torvalds/linux/blob/v5.14/arch/x86/kernel/cpu/amd.c#L894-L905)
  enables execution serialization. Retaining the timer relies on the normal
  Linux AMD initialization; the privileged DE_CFG register was not read directly.
- The running RHEL kernel is `5.14.0-611.38.1.el9_7.x86_64`. Actual probes show
  that `MADV_COLLAPSE` succeeds here despite the older upstream version number.
  Both 32 KiB and 512 MiB working sets had complete 2 MiB THP backing, and a
  32 MiB base-page probe had zero `AnonHugePages`. Memory binding to node 1
  succeeded. No THP fallback or C-source adaptation was needed.
- GCC, make, and objdump were available. Missing Python dependencies were
  installed in `.venv` with the original pinned requirements. Missing `numactl`
  was downloaded from the configured RHEL repository as
  `numactl-2.0.19-3.el9.x86_64.rpm`, its RPM signature/digests verified, and it
  was extracted under `build/skylark/tools`. The installed system libnuma is
  the same version. No system packages or global settings were changed.
- All 10 existing tests passed. Diagnostic probes use 1,000 samples and are
  excluded from the experiment; every formal configuration uses 1,000,000.

Compatibility evidence and dependency logs are in `data/skylark/preflight/`.
The initial `lscpu` inspection included OS-reported cache geometry as requested
for the platform check. Those reported capacities are not measurement evidence:
round-2 intervals and capacity interpretations are selected from Skylark's new
timings. No PMU counters are used. A single pinned core's curve must not be
interpreted as a measurement of aggregate cache across sockets/cache domains.

## Reproduction

```bash
cd /home/swu35/ECE592-HW1/timing-only/capacity
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
mkdir -p build/skylark/tools
rpm2cpio data/skylark/preflight/numactl-2.0.19-3.el9.x86_64.rpm | \
  (cd build/skylark/tools && cpio -idmu --quiet)
export PATH="$PWD/.venv/bin:$PWD/build/skylark/tools/usr/bin:$PATH"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
make MACHINE=skylark capacity assembly
make check

# Choose fresh run IDs when repeating; the collector rejects existing IDs.
taskset -c 0 python scripts/run_capacity.py --machine skylark --run-id round1
taskset -c 0 python scripts/analyze_capacity.py --machine skylark --run-id round1

# The actual evidence-based round-2 planning command is recorded in
# data/skylark/preflight/round2-plan-command.txt after round 1 finishes.
taskset -c 0 python scripts/run_capacity.py --machine skylark \
  --config configs/skylark-round2.json --sweep all --run-id round2
taskset -c 0 python scripts/analyze_capacity.py --machine skylark --run-id round2
taskset -c 0 python scripts/analyze_capacity.py --machine skylark \
  --run-id round1 round2 --output-id combined12 \
  --boundaries results/skylark/combined12/boundaries.json
taskset -c 0 python scripts/validate_capacity.py --machine skylark \
  --run-id round1 round2 --output-id combined12
```

The Python orchestration runs on CPU 0; each benchmark explicitly rebinds itself
to CPU 32 and first-touches memory under `numactl --membind=1`. Timing jobs run
serially. Source/executable snapshots, all compressed raw samples, per-point
logs, and manifests remain separate under `data/skylark/round1` and `round2`.
See `results/skylark/combined12/RUN_NOTES.md` for the final measurements and
their limitations.
