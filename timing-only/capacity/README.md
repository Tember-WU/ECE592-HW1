# Cache Levels and Capacity

This experiment implements **PROJECT 1.pdf §8.2: Cache levels and capacity**. The original measurement kernel is preserved; all supporting files now live in the self-contained `timing-only-V3/capacity/` directory. Paths below are relative to this directory. It measures dependent-load timing across working-set sizes so that cache-level plateaus and capacity transitions can be inferred from new data.

**Migration map**

| V2 file | Location within `capacity/` | Changes |
|---|---|---|
| `cache_bench.c` | `src/cache_bench.c` | Byte-for-byte copy of the final V2 source; no changes to the measurement kernel. |
| `configs/*.json` | `configs/artemisia.json` | All seven sweeps, point values, and order seeds preserved in `capacity.sweeps`; CPU 32, NUMA node 1, hostname, ISA, and point defaults made explicit. |
| `run.py` | `scripts/run_capacity.py` | Machine config selection, paths under `data/<machine>/<run-id>/`, validation before collection, build/source snapshots, and an explicit dry run. Each collection uses a new run ID. |
| `analyze.py` | `scripts/analyze_capacity.py` | Reads V3 raw data and writes only to the matching results directory; regenerates statistics from verified raw samples. Machine labels and layout groups come from the data. |
| `Makefile` | `Makefile` | Builds `build/<machine>/cache_capacity` and its disassembly with the original compiler flags. |
| `requirements.txt` | `requirements.txt` | Original NumPy and Matplotlib version pins retained. |

V2 remains unchanged. Historical results, raw data, figures, binaries, reports, `FREEZE.md`, `SHA256SUMS`, and `boundaries.json` were not copied. The V2 boundary file contains prior conclusions; a V3 run needs its own timing-based interpretation.

**Machine configuration**

`configs/artemisia.json` contains `machine`, `hostname`, `isa`, `cpu`, `numa_node`, and `capacity`. The latter contains `defaults` and the following named `sweeps`:

| Sweep | Points | Purpose inherited from V2 |
|---|---:|---|
| `coarse` | 39 | Broad working-set sweep, random/sequential comparison, and an empty-timer control. |
| `dense` | 56 | Denser candidate-boundary sampling and seed/order comparisons. |
| `refine` | 12 | Further local refinement and repeatability checks. |
| `controls` | 15 | Node-spacing, batch-length, and base-page controls. |
| `llc_layout` | 8 | Large working sets with 32-byte node spacing. |
| `llc_dense` | 18 | Larger-footprint refinement and compact 8-byte pointer layouts. |
| `llc_final` | 19 | Additional compact-layout refinement and repeat seeds/orders. |

The full plan has 167 points, each with 1,000,000 timed batches. Its uncompressed sample payload is 1,336,000,000 bytes; source snapshots, logs, and processed figures are additional. The default batch contains 256 dependent loads, and the batch-length controls use 1,024. A fixed `order_seed` shuffles points within each sweep; selected sweeps run in the requested order. `--sweep all` uses the configuration's stored sweep order.

To add another compatible Linux x86-64 machine, create `configs/<machine>.json`, set its identity and local CPU/NUMA placement, and choose its experimental points. The scripts create its build/data/results directories automatically. Begin with a broad scan and refine from that machine's timing evidence; Artemisia's dense sweeps are historical experimental choices, not universal cache sizes. No benchmark source edit is needed for another machine that supports the same timer and page-control interfaces.

**Build, collect, and analyze**

Run the commands from `timing-only-V3/capacity/`. Dependencies are Linux x86-64, GCC, make, objdump, numactl, Python 3, NumPy, and Matplotlib. The `huge` policy needs the kernel's `MADV_COLLAPSE` support and full 2 MiB transparent-huge-page backing. The C program rejects an unsupported or incomplete huge-page allocation. A separately configured `base` run explicitly requests ordinary pages and should be interpreted as such. AArch64 is not yet implemented.

```bash
python3 -m pip install -r requirements.txt
make MACHINE=artemisia capacity assembly
make check

# Validate the entire config without building or measuring.
python3 scripts/run_capacity.py --machine artemisia --sweep all --run-id capacity01 --dry-run

# Collect all seven sweeps serially on Artemisia, then analyze this new run.
python3 scripts/run_capacity.py --machine artemisia --sweep all --run-id capacity01
python3 scripts/analyze_capacity.py --machine artemisia --run-id capacity01
```

For a shorter starting scan, use `--sweep coarse --run-id coarse01`. Several sweeps may be selected together, for example `--sweep coarse dense controls`. Use `--config /path/to/config.json` to select an alternative config whose machine ID matches `--machine`. Settings such as CPU, node, and sample count belong in that config.

The normal collector verifies the actual hostname, ISA, allowed CPU, and CPU/NUMA relationship. CPU 32 / node 1 are inherited run settings, not a new reservation. Confirm availability before a real run and record any SMT or shared-machine interference. Run timing jobs serially. The collector rebuilds automatically, preserves every sample, and stops on a failed point while retaining its logs. It refuses to overwrite any existing raw or processed run ID; interrupted runs stay in place, and a retry uses a new ID. There is no automatic resume or merge of separate runs.

**Files produced by a new run**

```text
data/<machine>/<run-id>/
    config.json                # Machine config used for this collection
    manifest.json              # Resolved points, commands, completion/failure status
    environment.json           # Model, CPU/core/socket/node, timer, build info, environment
    commands.txt               # Exact build and per-point commands
    build.log
    disassembly.txt
    cache_capacity.bin         # Executable snapshot used for every point in this run
    source/                    # C source, Makefile, runner/analyzer, dependency pins
    raw/<point>.u64.gz          # All batch-total timing intervals, losslessly compressed
    logs/<point>.json          # Parameters, sample checksum, statistics, environment
    logs/<point>.txt           # Mapping/NUMA evidence and benchmark diagnostics

results/<machine>/<run-id>/
    summary.csv                # Recomputed statistics for every completed point
    capacity_points.json       # Representative runs and ranges of repeat medians
    temporal_medians.csv       # Median of each consecutive tenth of every run
    provenance.json            # Input hashes, analysis command, script hashes, annotations
    figures/
        capacity_s<spacing>_b<batch>_<pages>.pdf / .png
        boxplots_s<spacing>_b<batch>_<pages>.pdf
        method.pdf / .png
        temporal_stability.pdf # When matching points have repeat runs
        boundary_zoom.pdf / .png       # When --boundaries is supplied
        boundary_boxplots.pdf / .png   # When --boundaries is supplied
```

Raw files are little-endian `uint64` arrays of **batch-total TSC ticks**. Divide each element by its recorded `batch` to obtain TSC ticks per dependent load. Empty-timer controls are kept in ticks per timer interval and are never divided by the batch length. The interval is not automatically a core-cycle measurement, and each batch mean is not an individual-load latency sample.

```python
import gzip
import json
from pathlib import Path
import numpy as np

run = Path('data/artemisia/capacity01')
record = json.loads(next((run / 'logs').glob('*.json')).read_text())
with gzip.open(run / record['raw_file'], 'rb') as f:
    ticks = np.frombuffer(f.read(), dtype='<u8')
p = record['parameters']
latency = ticks / (1 if p['mode'] == 'empty' else p['batch'])
```

Large raw arrays and generated binaries are ignored by Git. Keep them backed up and include the required raw data in the final submission. Run metadata and source snapshots remain available to commit. A Git revision alone may not describe uncommitted source, so each collection also preserves the actual files.

**Analysis and inference**

Analysis checks raw checksums and sample counts and recomputes the mean, sample standard deviation, median, Q1/Q3, P05/P95/P99, extrema, Tukey outlier count/whiskers, and ten temporal medians. No samples are discarded. Each box is one run; outlier markers are hidden for readability while their counts and raw values remain available. Every completed nonempty point appears in a box-plot PDF. Empty-timer statistics remain in the summary table.

Curves keep spacing, batch length, and page policy separate. The original V2 selection rule is retained when several sweeps measure the same point: prefer `dense`, `refine`, or `llc_final`, followed by `llc_dense`, then `coarse`/`llc_layout`, then `controls`; within a priority use the lowest seed, with input-name order breaking ties. Other sweep names receive the same priority as `llc_dense`. Selection never depends on which measured median looks preferable. The range of repeat medians is shown separately from each selected run's P05–P95 band.

New curves carry no preset cache capacities or level count. After inspecting a run, write an optional boundary JSON file and pass it with `--boundaries`. It is a list of objects with `level`, `estimate` (bytes or `null`), `interval` (two byte values), `zoom` (two byte values), `unit` (axis divisor), `box_points` (measured byte values), `spacing`, `batch`, and `pages`. Choose actual random measurements immediately below, near, and above each observed transition. The old V2 boundary schema is compatible, but its old numbers are not automatically adopted. The analyzer records the supplied annotations in `provenance.json`.

```bash
python3 scripts/analyze_capacity.py --machine artemisia --run-id capacity01 \
    --boundaries results/artemisia/capacity01/boundaries.json
```

**Preserved measurement method and limits**

The unchanged C program binds the CPU, allocates an aligned mapping, first-touches memory after binding, and constructs one cycle through every node. It warms at least four full traversals and at least 1,048,576 dependent loads. The output buffer is touched before timing. Each timed batch uses serialized x86 timestamps and groups of 16 mutually dependent loads in inline assembly so `-O0` does not insert stack traffic into the chain. File writing and compression happen after timing; page backing is checked before and after measurement.

Node spacing is an access-layout parameter. The swept byte count is the traversed address span, excluding rounded-up unused mapping space; it is not automatically the number of distinct cache bytes occupied. Compare the preserved 64-, 32-, and 8-byte layouts and base/huge-page controls before attributing a step to cache capacity. Consecutive batches are not independent trials. LLC behavior may support a broad effective transition rather than a unique physical capacity. This experiment does not yet implement line-size, associativity, inclusion policy, a separate latency-state experiment, or the software hit-rate estimator.

Build and synthetic pipeline checks validate the migration. They do not establish new cache measurements or validate the kernel on another architecture.
