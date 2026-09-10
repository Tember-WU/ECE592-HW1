# Skylark latency experiment

The seven-group run is saved as `data/skylark/latency01/`, with analysis in
`results/skylark/latency01/`. It uses the existing `configs/skylark.json` and
the same original C source, timer header, Makefile, collector, analyzer, and
seven-group protocol as Artemisia. Existing source, configurations, and
Artemisia results are preserved.

The configuration selects footprints from the previously measured Skylark
capacity plateaus, rather than copying Artemisia's footprints:

| Candidate | Skylark footprints | Groups using them |
|---|---|---|
| L1 resident | 8 and 16 KiB | `l1_hit`; controls use 8 KiB |
| L2 resident | 128 and 256 KiB | `l2_hit`, `l1_miss`; controls use 128 KiB |
| LLC resident | 4 and 8 MiB | `llc_hit`, `l2_miss`; controls use 4 MiB |
| Memory-dominated | 256 and 512 MiB | `llc_miss`; controls use 256 MiB |

The SHA-256 of `../capacity/results/skylark/combined12/inference.json` was
verified against `capacity_basis` before collection. This is a timing-based
choice of residency candidates, not proof of the cache serving every load.

All seven groups run serially in the original fixed shuffled order
(`order_seed=59280`), with a new process for each of 30 configurations. Every
configuration records 1,000,000 batches after warm-up. The nine paired points
each save FIRST and REREAD, so the total is 30,000,000 batches and 39,000,000
recorded timer intervals. Each paired archive is an interleaved two-column
array, not a single distribution. Most batches contain 256 dependent loads;
the three long controls contain 1024. Four-stream values describe throughput.

## Local compatibility and dependencies

Skylark is Linux x86-64 on AMD EPYC 7532. The native x86 timer path is used,
retaining the capacity experiment's LFENCE/RDTSC/RDTSCP sequence and units of
TSC ticks. The previous [capacity compatibility record](../capacity/SKYLARK.md)
documents the Linux AMD timer assumptions; this run does not convert TSC ticks
to nominal core cycles.

CPU 32 is on NUMA node 1 and has no enabled SMT sibling. Its inherited affinity
mask was narrower, but an explicit bind to CPU 32 succeeded and the original
mask was restored before collection. Benchmark processes perform their own
binding under `numactl --membind=1`. Short CPU-load observations do not reserve
the CPU or establish exclusive access to shared resources.

The six existing tests passed, including actual execution of all five kernel
modes. Disassembly checks found the expected 16 register-addressed loads and
no stack references inside either timed assembly interval. Separate diagnostic
probes verified a 512 MiB paired workload and a 128 KiB four-stream workload
with complete THP backing and local NUMA placement. Their 1,000-sample arrays
are excluded from the formal experiment. No architecture adaptation was needed.

This run reuses the original pinned NumPy/Matplotlib environment and the local
`numactl` extraction prepared for the capacity experiments:

- Python: `../capacity/.venv/bin/python`
- numactl: `../capacity/build/skylark/tools/usr/bin/numactl`
- Dependency archive and installation evidence:
  `../capacity/data/skylark/preflight/`

No system package or kernel setting was changed. Preparation commands, test
output, assembly checks, capacity-basis verification, and preservation hashes
are saved under `data/skylark/preflight/`.

## Reproduction

From `/home/swu35/ECE592-HW1/timing-only/latency`:

```bash
export PATH="$PWD/../capacity/.venv/bin:$PWD/../capacity/build/skylark/tools/usr/bin:$PATH"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
make MACHINE=skylark all check

# latency01 contains this run; use a fresh ID for another collection.
LATENCY_RUN=latency02
python scripts/run_latency.py --machine skylark --run-id "$LATENCY_RUN" --dry-run
taskset -c 0 python scripts/run_latency.py --machine skylark --run-id "$LATENCY_RUN"
taskset -c 0 python scripts/analyze_latency.py --machine skylark --run-id "$LATENCY_RUN"
```

The Python controller is pinned to CPU 0 while each benchmark rebinds itself
to CPU 32. The original collector rejects an existing run ID. The analyzer
reopens every compressed archive, checks hashes and dimensions, recomputes
statistics and signed paired differences, and verifies snapshots and placement.

See the [completed run report](results/skylark/latency01/RUN_NOTES.md) for
measured latencies, next-level contrasts, figures, and limitations.
