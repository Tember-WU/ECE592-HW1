# Cache levels and capacity: two main rounds and an optional third round

This directory is the entry point for rerunning the Artemisia experiment: `/home/swu35/ECE592-Project1/ECE592-HW1/timing-only/capacity`. It covers only cache levels and capacity, corresponding to assignment §8.2. Linux x86-64 is currently the only supported platform.

Crux has also completed the two-round workflow using `configs/crux.json`
(CPU 6 / NUMA node 0). Its complete runs are `round1-retry1` and `round2`;
the initial incomplete `round1` is preserved separately. See the
[Crux run inventory and reproduction commands](results/crux/README.md) and
[combined interpretation](results/crux/combined12/RUN_NOTES.md).

`src/cache_bench.c` is identical to `timing-only-V2/cache_bench.c`. The V2 dependent-load kernel and timing method are retained, while configuration, point selection, analysis, and record keeping have been updated. Historical V2 data and reports remain in their original location. This directory does not read the old capacity conclusions or assume that there must be three cache levels.

Upgrade uses `configs/upgrade.json` (CPU 2 / NUMA node 0). Its run IDs, local dependency setup, results and reproduction commands are recorded in [the Upgrade experiment record](results/upgrade/README.md).

## Experiment plan

| Round | Configuration source | Measurements | Configurations |
|---|---|---|---:|
| Round 1 | `configs/common/round1.json`, referenced by the machine config | A powers-of-two sweep from 2 KiB to 512 MiB; random and sequential chains at each of 19 sizes, plus an empty-timer control | 39 |
| Round 2 | `configs/artemisia-round2.json`, generated from the new results | For each of L1/L2: 9 dense points, 3 repeats with a new seed, 3 sequential points, 3 compact-layout controls, and 1 longer-batch control; bounded LLC refinement with layout and base-page controls | Usually 57 |
| Round 3, optional | `configs/artemisia-round3.json`, generated from round 2 | Only for unresolved boundaries: 5 dense points, 3 repeats with a new seed, and 3 sequential controls | 11 per selected boundary |

The default two-round plan totals **96 configurations and 96,000,000 timed batches**. Without an LLC interval, round 2 contains 38 configurations, bringing the two-round total to 77; the report must still explain the LLC region observed in the coarse scan. Each larger footprint supplied through `--extend` adds one random and one sequential configuration. There is no automatic loop that keeps adding experiments to seek an exact LLC capacity.

Every point preserves **1,000,000 timed batches**, excluding warm-up. The default batch contains 256 dependent loads; longer-batch controls use 1024. A repeat with a new seed starts a new process, reallocates memory, and rebuilds the pointer cycle. Consecutive batches are not independent experiments.

Round-1 measurement parameters are shared across machines. Machine identity, CPU, and NUMA node are stored separately in `configs/<machine>.json`. Artemisia is configured for CPU 32 / NUMA node 1, and Crux for CPU 6 / NUMA node 0. These configurations are not CPU reservations; machine load and page allocation must still be interpreted using the logs. To add another compatible x86-64 machine, reference the same `common/round1.json` and select follow-up intervals from that machine's new curves. Arm support is not implemented at this stage.

## Preparation and round 1

Dependencies: GCC, make, objdump, numactl, Python 3, NumPy, and Matplotlib. Python dependency versions are recorded in `requirements.txt`. The `huge` policy requires Linux support for `MADV_COLLAPSE` and actual, complete backing by 2 MiB transparent huge pages. On failure, the collector preserves the logs and stops; it does not silently switch to base pages.

```bash
cd /home/swu35/ECE592-Project1/ECE592-HW1/timing-only/capacity
python3 -m pip install -r requirements.txt
make MACHINE=artemisia capacity assembly
make check

# Check configuration and output paths only; do not collect data or check live page allocation/load.
python3 scripts/run_capacity.py --machine artemisia --run-id round1 --dry-run

# Collect round 1; coarse is the default sweep.
python3 scripts/run_capacity.py --machine artemisia --run-id round1
python3 scripts/analyze_capacity.py --machine artemisia --run-id round1
```

First inspect `results/artemisia/round1/figures/capacity_s64_b256_huge.png`, the corresponding box plots, and `transitions.csv`. The latter lists median ratios and repeat ranges at adjacent working-set sizes. It assists point selection but does not automatically infer cache levels or capacities.

Before collection, the runner checks the hostname, ISA, CPU/NUMA relationship, and permission to bind to the target CPU. An inherited affinity mask can be narrower than the range of CPUs actually available for binding, so the runner briefly attempts to bind to the target CPU and then restores the original mask. The benchmark subprocess performs the actual measurement binding. Run timing jobs serially. Every collection uses a new run ID; an existing data or results directory with the same ID is never overwritten. Interrupted data are preserved. Automatic resume is not currently implemented.

## Generate round 2 from round 1

Select L1 and L2 transition intervals from the **new** random-chain curve. You may also select a broad LLC candidate interval. Both endpoints must be previously measured random points with the same primary layout, batch length, and page policy. The intervals specify where to measure next; they are not established capacity estimates.

The following commands prompt for intervals from the new curves. Use `LOWER:UPPER`, with integer bytes or KiB, MiB, or GiB units; exact decimal values are supported. Do not simply substitute the old V2 answers.

```bash
read -r -p 'L1 interval from the new curve (LOWER:UPPER, with KiB/MiB units): ' CAPACITY_L1
read -r -p 'L2 interval from the new curve (LOWER:UPPER, with KiB/MiB units): ' CAPACITY_L2
read -r -p 'LLC candidate interval from the new curve (LOWER:UPPER, with MiB units): ' CAPACITY_LLC
python3 scripts/plan_capacity.py --machine artemisia --from-runs round1 --round 2 \
    --l1 "$CAPACITY_L1" --l2 "$CAPACITY_L2" --llc "$CAPACITY_LLC" \
    --output configs/artemisia-round2.json

python3 scripts/run_capacity.py --machine artemisia \
    --config configs/artemisia-round2.json --sweep all --run-id round2 --dry-run
python3 scripts/run_capacity.py --machine artemisia \
    --config configs/artemisia-round2.json --sweep all --run-id round2

# Plot both rounds together while preserving separate raw data for each round.
python3 scripts/analyze_capacity.py --machine artemisia \
    --run-id round1 round2 --output-id combined12
```

The LLC measurements comprise 5 primary-layout points, 5 compact 8 B-layout points, 3 compact-layout repeats with a new seed, 3 primary-layout sequential points, and 3 base-page points: 19 configurations in total. The L1/L2 compact-layout controls also use 8 B spacing, which is the pointer size rather than an assumed cache-line size. If the primary configuration is later changed to 8 B spacing, the alternative layout uses 32 B spacing. Base-page and huge-page results are always analyzed separately.

If a reasonable LLC candidate interval cannot be selected, omit `--llc` and document the limitation in the report. If the largest round-1 footprint does not sufficiently cover a clear memory-access region, add larger points with an option such as `--extend 1GiB`. Extension points must exceed the largest previously measured primary-layout footprint.

The planner checks completion of the source runs, raw-sample checksums, measured endpoints, and the relationship between rounds. The generated config records source run IDs, raw-sample hashes, selected intervals, and the planner's hash. Use `--note` to record the reason for selecting the intervals. Generated files are never overwritten; choose another output filename when revising a plan.

## Decide whether round 3 is needed

After two rounds, a capacity estimate or empirical interval can be reported if distribution changes on both sides of the L1/L2 boundaries are distinguishable, repeats with new seeds support similar boundaries, and the controls do not contradict the interpretation. If an L1/L2 interval remains too broad or repeats disagree, collect additional points only around that boundary. A broad LLC transition may remain uncertain.

For example, to refine only L1, enter a narrower interval that remains unresolved after round 2:

```bash
read -r -p 'L1 interval that still needs refinement (LOWER:UPPER, with units): ' CAPACITY_L1_REFINE
python3 scripts/plan_capacity.py --machine artemisia --from-runs round1 round2 --round 3 \
    --l1 "$CAPACITY_L1_REFINE" --output configs/artemisia-round3.json
python3 scripts/run_capacity.py --machine artemisia \
    --config configs/artemisia-round3.json --sweep all --run-id round3 --dry-run
python3 scripts/run_capacity.py --machine artemisia \
    --config configs/artemisia-round3.json --sweep all --run-id round3
python3 scripts/analyze_capacity.py --machine artemisia \
    --run-id round1 round2 round3 --output-id combined123
```

Use `--l2` when only L2 needs refinement. Supply both intervals when both boundaries need refinement, for a total of 22 points. After round 3, report any remaining uncertainty according to the evidence. The plan does not guarantee an exact value for every boundary.

## Data, figures, and reporting

```text
data/artemisia/<run-id>/
  config.json                  # Fully resolved config, independent of later changes to the shared config
  manifest.json                # Per-point commands and completion/failure status
  environment.json             # Machine, CPU/NUMA, compiler, page policy, and related settings
  source/                      # Snapshots of the C source, scripts, Makefile, and dependencies
  cache_capacity.bin           # Executable used for this run
  disassembly.txt              # Disassembly for this run
  build.log / commands.txt
  raw/<point>.u64.gz           # Little-endian uint64 values: total TSC ticks per batch
  logs/<point>.json / .txt     # Per-point statistics, hashes, page backing, CPU activity, faults, and switches

results/artemisia/<run-id-or-combined-id>/
  summary.csv                  # Includes run_id; all statistics recomputed from raw samples
  transitions.csv              # Adjacent random-footprint comparisons, not automatic inference
  capacity_points.json         # Representative runs and ranges of individual run medians
  temporal_medians.csv         # Medians for ten consecutive time blocks at each point
  provenance.json              # Analysis inputs, run IDs, sample/script hashes, and manual boundaries
  figures/
    capacity_s<spacing>_b<batch>_<pages>.png / .pdf
    boxplots_s<spacing>_b<batch>_<pages>.pdf
    layout_comparison_b<batch>_<pages>.png / .pdf
    temporal_stability.pdf
    method.png / .pdf
```

Statistics include the mean, sample standard deviation, median, Q1/Q3, P05/P95/P99, minimum/maximum, Tukey outlier count, and ten temporal medians. No samples are removed. Each run has its own box plot. Curve values are **TSC ticks / dependent load**, computed by dividing batch-total ticks by the recorded batch length. Empty-timer measurements remain in ticks/interval. TSC ticks are not treated as validated core cycles.

Combined analysis rejects runs that differ in CPU, NUMA node, C source, timing method, compiler flags, processor model, kernel, or base-page size; such runs should be analyzed separately. Different spacing, batch, and page settings always remain in separate groups. Representative runs are selected using the predetermined priority `round3 → round2 → coarse`, with ties resolved by seed and run identifier rather than measured performance. The range of all repeat medians is shown separately with error bars; repeats are not pooled into new cache plateaus. Reanalysis may update a results directory for the same inputs. Different inputs require a new output ID.

For boundary zoom plots, create a JSON list based on the new data. Each entry contains `level`, `estimate` (bytes or null), `interval`, `zoom`, `unit`, `box_points`, `spacing`, `batch`, and `pages`. Every `box_points` value must be a measured random-access point. Pass the file to the analyzer with `--boundaries PATH`. The planner does not automatically write final capacity conclusions.

The report should state the distinguishable cache levels, L1/L2 estimates, and supporting boundary evidence. For LLC, it may state that an effective transition region was observed but the exact physical capacity was not uniquely determined, accompanied by the actual curves and controls. Layout, TLB behavior, shared workloads, and other factors that have not been isolated should be discussed only as possible explanations, not established causes. Do not force the result to contain three levels if three plateaus cannot be distinguished.

## Kernel and validation scope

The C kernel is compiled with `-O0`. Its timed region uses inline assembly for a single dependency chain; the 16 unrolled loads remain mutually dependent. The benchmark binds the CPU, uses `numactl --membind` to bind memory, and first-touches that memory after CPU binding. Warm-up covers at least four full traversals and at least 1,048,576 loads. Complete huge-page backing is checked before and after measurement; base-page controls use `MADV_NOHUGEPAGE`. The output buffer is touched in advance, and raw-file output and compression occur only after measurement.

`make check` uses synthetic data and mocked collection to validate configuration, raw-data checks, combined analysis, and point selection. Building and running these checks does not establish new capacity measurements. Actual page-allocation success must still be demonstrated by the measurement logs.

Commit the experiment code, configurations, compressed raw samples (`.u64.gz`), per-run source and executable snapshots, build and measurement logs, environment records, statistics, figures, and analysis notes. These files preserve the evidence needed for the report and allow the distributions and plots to be regenerated. The Git ignore policy excludes rebuildable working files under `build/`, temporary uncompressed samples (`.u64`), Python caches, and local virtual environments. Keep the raw samples in the assignment submission as well as the repository.
