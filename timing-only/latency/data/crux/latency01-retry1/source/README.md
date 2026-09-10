# Timing-only latency: seven groups, one finite run

This directory covers assignment Section 8.2 items 5 and 6: hit latency and miss/next-level latency. It contains one Linux benchmark with x86-64 and AArch64 timer paths, one collector, and one analyzer. The capacity experiment remains a separate input source. No performance counters or cache-geometry queries are used.

## Experiment design

The supplied machine configurations contain **30 points in seven groups**. Every point collects 1,000,000 batches after warm-up. There are 21 single-column points and 9 paired points, so a complete run preserves 39,000,000 timer intervals (312,000,000 uncompressed bytes).

| Group | Points | Purpose |
|---|---:|---|
| `calibration` | 12 | Empty timer; long-batch, sequential, and four-independent-stream controls for three cache residency candidates; sequential and four-stream controls at a large footprint |
| `l1_hit` | 3 | Two small resident footprints and a second-seed repeat of the primary footprint |
| `l2_hit` | 3 | Two footprints beyond L1 and inside the observed L2 region, plus a second-seed repeat |
| `llc_hit` | 3 | Two footprints inside the observed third residency region, plus a second-seed repeat |
| `l1_miss` | 3 | Paired first/reread measurements at the L2 candidate footprints, plus a second-seed repeat |
| `l2_miss` | 3 | Paired first/reread measurements at the LLC candidate footprints, plus a second-seed repeat |
| `llc_miss` | 3 | Paired first/reread measurements at 256 and 512 MiB, plus a second-seed repeat |

The measurement order is shuffled once with the recorded `order_seed`. Each point runs in a fresh process with a fresh allocation and ring permutation. The repeat uses a different seed; the million consecutive batches within a point are not a million independent process experiments.

### Resident and method controls

Create one circular pointer chain through every node in a `bytes`-byte address span. Randomize the permutation except in the sequential control. Warm at least four complete traversals and at least 1,048,576 dependent loads. Time batches of 256 dependent loads; designated controls use 1024. The four-stream diagnostic uses four independent cursors in the same ring and executes the same total number of loads. Its throughput is never substituted for dependent-load latency.

Node spacing is a configurable access-layout parameter, initially 64 bytes to match the primary capacity measurements. It is **not a claimed measurement of cache-line size**. Measured line-size and associativity results can later motivate additional layout controls without changing the source.

### Paired first pass and immediate reread

For each sample, save the current cursor, time the next N dependent loads, then reset to the saved cursor and time exactly the same N loads again. Continue the next sample at the end of the first pass. The next N targets have not been read by the timed traversal since the previous full ring traversal; recently measured targets are revisited only after progressing around the whole ring. The immediate reread deliberately changes recency for the same addresses. Initial warm-up occurs before any samples are saved.

```text
one random cycle over W bytes: p0 -> p7 -> p3 -> ... -> p0
                             [ next N target loads ]
sample i:     time FIRST   -> reset -> time same N loads as REREAD
sample i + 1: continue at next N targets, preserving the large reuse distance
```

Changing W creates working-set eviction pressure without scanning a huge separate eviction buffer before every sample. Only FIRST and REREAD loads and the loop/timer instructions are timed; allocation, warm-up, file I/O, compression, and state bookkeeping are outside those intervals. Raw-output stores between intervals still form part of the surrounding workload.

This is the assignment's **working-set construction** option. It is not set-selective eviction, and it does not establish a particular hardware hit/miss state for every load. The same-address reread may include conflict or address-translation costs and is not automatically a pure L1-hit class. The large-footprint first pass is a memory-dominated candidate; residual cache hits and TLB effects can remain. Report overlap or mixed behavior honestly rather than forcing clean class labels.

## Run a machine

Paths below are relative to this directory. Requirements are GCC, make, objdump, numactl, Python with the pinned NumPy/Matplotlib dependencies, and Linux CPU affinity/NUMA interfaces.

```bash
python3 -m pip install -r requirements.txt
make MACHINE=artemisia all
make MACHINE=artemisia check
python3 scripts/run_latency.py --machine artemisia --run-id latency01 --dry-run
python3 scripts/run_latency.py --machine artemisia --run-id latency01
python3 scripts/analyze_latency.py --machine artemisia --run-id latency01
```

The eight configurations use each machine's saved capacity inference, CPU, and NUMA node. `capacity_basis.inference_file` is relative to `timing-only/`; its hash records the evidence used to choose footprints. Configuration generation does not mean that latency has already been measured on that machine. Before running elsewhere, check actual CPU availability and dependencies. Timer assembly for an architecture must be validated there before treating its measurements as established.

Edit the machine's JSON to change per-group footprints, samples, batch lengths, node spacing, or seeds. Use `--config PATH` for an alternative configuration and `--groups l1_hit l1_miss` for a focused follow-up under a **new run ID**. The default executes all seven groups. The collector refuses to overwrite any existing run; a failed run stays in place and a retry gets a new ID. There is no automatic loop, resume, or merger of incompatible runs.

The benchmark pins the CPU, first-touches memory after binding, and runs under `numactl --membind`. Huge-page points require complete PMD-sized THP backing before and after timing. Existing full THP backing is accepted on older kernels; otherwise `MADV_COLLAPSE` is attempted. A failed allocation stops the run rather than silently changing page policy. Explicit `pages: "base"` configurations remain possible and must be identified as a different condition. CPU binding does not reserve the CPU, SMT sibling, cache, or memory bandwidth.

Both architectures compile at `-O0`; the timed dependency loops are inline assembly. x86 uses the capacity experiment's LFENCE/RDTSC/RDTSCP sequence. AArch64 uses CNTVCT_EL0 with the recorded barriers and calibrates CNTFRQ_EL0 against CLOCK_MONOTONIC_RAW. The empty timer may legitimately yield zero Arm ticks. TSC ticks and generic-timer ticks are not validated instantaneous core cycles. No nominal-GHz conversion is performed.

## Saved evidence and interpretation

```text
data/<machine>/<run-id>/
  config.json, manifest.json, environment.json, preflight.json
  commands.txt, build.log, disassembly.txt, latency_bench.bin
  source/                    # exact code, scripts, and methodology snapshot
  raw/<point>.u64.gz          # uint64 little-endian timer totals
  logs/<point>.json/.txt      # parameters, columns, hashes, stats, placement, events
results/<machine>/<run-id>/
  summary.csv, contrasts.csv, temporal_medians.csv
  latency_estimates.json, quality.json, validation.json, provenance.json
  figures/                   # resident, paired, controls, timer, time blocks, method
```

Single-column files contain one timer total per batch. Paired files contain interleaved rows `[first_total, reread_total]`; **do not analyze a paired archive as one flat distribution**. Divide each column by its recorded batch length. Empty timer values stay in ticks/interval. The analyzer reopens every archive and recomputes all statistics, checks sample counts and hashes, verifies snapshots and placement logs, and rejects incomplete runs.

Statistics retain all samples: n, mean, sample standard deviation, median, Q1/Q3, P05/P95/P99, min/max, Tukey outlier count, and ten temporal medians. Box plots omit individual outlier markers for readability; no outlier is removed from statistics or raw files. A >1.2 ratio between temporal medians is only a descriptive drift flag, not a significance test or sample-rejection criterion.

`contrasts.csv` distinguishes two quantities:

- `paired_first_minus_reread_median`: median of per-sample FIRST minus REREAD. This is an immediate-reread benefit, not automatically a particular level's miss penalty.
- `difference_of_medians`: first-pass median minus the primary resident median for the previous level, measured in a separate process. It is a candidate next-level incremental access cost, not a paired difference distribution, confidence interval, or total pipeline stall count. It is meaningful as a level-specific penalty only when the intended residency classes and controls support that interpretation.

For the report, show the resident and paired distributions, method controls, timer overhead, and relevant temporal stability evidence. Compare repeats and alternate footprints without pooling them into one distribution. LLC and memory may remain broad or mixed. The report must preserve the distinction between measured timing behavior, hypothesized cache state, and later Phase-II verification.

Commit configurations, source, compressed raw arrays, logs, snapshots, statistics, and figures. Working build files, uncompressed temporary arrays, and Python caches are ignored. `make check` uses small functional fixtures solely to validate code/data handling; these are not formal latency results.
