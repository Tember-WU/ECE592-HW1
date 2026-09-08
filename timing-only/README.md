# Timing-only V3: Directory Structure and Implementation Plan

This directory is a fresh skeleton for the cache reverse-engineering project described in [PROJECT 1.pdf](../PROJECT%201.pdf). It preserves the original framework's separation of experiment code, machine configurations, raw data, and processed results. It contains only this README and empty `.gitkeep` files so Git can preserve the directories. No benchmark code, configuration values, binaries, or previous results have been copied into V3.

The intended design is simple: share the experiment implementations across machines, select machine-specific settings through one configuration file, and save each machine's outputs in its own folders. The filenames and commands described below are **planned interfaces**, not implemented features.

**Directory layout**

```text
timing-only-V3/
├── README.md
├── configs/
├── src/
│   └── experiments/
│       ├── capacity/
│       ├── line_size/
│       ├── associativity/
│       ├── latency/
│       ├── inclusion/
│       └── software_metric/
├── scripts/
├── build/
│   ├── artemisia/
│   ├── charnwood/
│   ├── crux/
│   ├── ookay/
│   ├── skylark/
│   ├── sunbird/
│   ├── thunderbird/
│   └── upgrade/
├── data/                   # Same eight machine subdirectories as build/
├── results/                # Same eight machine subdirectories as build/
├── docs/
└── tests/
```

All directories shown above, including the eight machine subdirectories under both `data/` and `results/`, already exist. Experiment/run folders inside the output directories should be created when new runs are collected. Historical run names from V1 are not part of this skeleton.

**What belongs in each directory**

| Directory | Future contents and responsibility |
|---|---|
| `configs/` | One `<machine>.json` per machine, such as `artemisia.json` or `thunderbird.json`. Store host identity, CPU/memory binding, timer selection, sample counts, seeds, and experiment sweep parameters. A small `default.json` may hold shared defaults. |
| `src/` | A small common entry point such as `main.c`, plus only the helpers shared by experiments: timing, affinity, allocation, dependent pointer chasing, and sample output. Keep x86-64 and AArch64 timing/serialization paths clearly identifiable, for example in `timing_x86.h` and `timing_arm.h`. |
| `src/experiments/` | The six independent experiment directories described below. Each should contain its measurement implementation and any experiment-specific headers. Keep machine-specific parameter choices in `configs/`. |
| `scripts/` | A small runner, analysis/plotting scripts, and later PMU collection and Hazel Slurm job scripts. Suggested starting files are `run.py`, `analyze.py`, and `plot.py`. Add separate experiment analysis files only when their logic warrants it. |
| `build/<machine>/` | Locally compiled executables, object files, build logs, and disassembly for that machine. This is a working build directory; preserve the build records needed to reproduce a result alongside that run's raw data. |
| `data/<machine>/` | Original measurements and the records needed to reproduce them: full sample distributions, exact commands, resolved config, environment, seeds, compiler/flags, and source commit or snapshot. Preserve failed, interrupted, and exploratory runs with their status. |
| `results/<machine>/` | Statistics, evidence plots, inference notes, and final cache tables derived from that machine's raw data. Every output should identify its input data and processing command. |
| `docs/` | Method descriptions and diagrams, machine research and citations, initial hypotheses, run/reproduction instructions, phase-freeze records, prediction methodology, and eventual report/slide materials. Also keep contribution records and AI-assistance disclosure here. |
| `tests/` | Later, small correctness checks for configuration parsing, access-pattern construction, timer availability, output reading, and statistics. Use synthetic samples where possible; hardware measurements remain experiments with recorded raw outputs. |

A small root `Makefile` and a dependency file can be added when implementation begins. The skeleton deliberately does not provide build or execution commands that would appear runnable today.

**Experiment directories and required evidence**

The first five directories cover PDF §8.2; `software_metric/` covers §8.5. One source file per experiment is a reasonable starting point. Cache-level discovery and capacity share one experiment; hit latency and miss/next-level latency share another.

| Directory | What the implementation should do | What its results should contain |
|---|---|---|
| `capacity/` | Sweep working-set size using dependent pointer chasing. Compare randomized and regular traversal, then sample densely around observed transitions to infer the number of levels and their effective capacities. | Latency versus working-set size, boundary box plots, inferred levels/capacities, uncertainty, and evidence for any private/shared interpretation. |
| `line_size/` | Sweep byte stride or spatial offset with controlled alignment and footprint. Test just below, at, and above candidate boundaries and control for prefetching. | Latency versus stride/offset, boundary distributions, and the inferred line size for each level where measurable. |
| `associativity/` | Increase a candidate conflict set while controlling its address relationship. Establish eviction behavior experimentally; equal virtual spacing alone does not prove set congruence. | Latency or eviction probability versus conflicting-address count, distributions near the threshold, inferred ways or effective bounds, and indexing/hash limitations. |
| `latency/` | Prepare and measure cache-resident and next-level/memory conditions with true dependent loads. Record timer overhead and timed access counts; use batching where appropriate without averaging away the miss condition being measured. | Hit-latency distributions, observed next-level access latencies, incremental miss penalties where meaningful, accurate units, and LLC ranges/percentiles. |
| `inclusion/` | After the preceding inferences, apply controlled cross-level eviction pressure and measure whether an upper-level copy survives. Include controls that support the claimed lower-level eviction; configure any helper core explicitly. | Eviction/reload evidence and a justified inclusive, exclusive/victim-like, non-inclusive/non-exclusive, or uncertain classification. Capacity ratios or survival alone are insufficient. |
| `software_metric/` | Calibrate resident/non-resident timing distributions and implement a timing-only hit-rate estimator with a justified classification or probabilistic rule. A different residency metric needs the approval specified in §8.5. | Calibration distributions, estimated hit rate, uncertainty, frozen estimator parameters, and later PMU comparison with absolute/relative errors and failure cases. |

For every reverse-engineering target, keep a methodology diagram in `docs/` showing the access pattern, varied parameter, controls, measured signature, and inference rule. A shared code module may need multiple diagrams: hierarchy and capacity, and hit latency and miss/next-level latency, are distinct targets in the report.

**Machine configuration and adding another machine**

Use one stable machine ID consistently in the config filename and the `build/`, `data/`, and `results/` paths. A configuration should eventually specify:

- Identity: machine ID, expected hostname or allocated host information, and ISA.
- Placement: logical CPU, NUMA/memory-locality policy, and helper CPU only when an experiment needs it.
- Measurement: timer, warm-up, timed samples per point, dependent accesses per sample, random seeds, and traversal order.
- Experiments: enabled experiments and candidate working-set sizes, strides/offsets, conflict counts, or eviction-pressure parameters.

The future runner should load shared defaults, apply the selected machine config, compile locally, and create outputs from that machine ID. Adding a supported x86-64 or AArch64 machine should require a new config rather than edits to experiment code. A new ISA or unavailable timing facility may require an additional platform implementation. The resolved configuration must be saved with every run.

Phase-I configs must contain experimental sweep settings, not published cache answers. Refine candidate ranges using timing evidence. For Hazel, later add IDs such as `hazel_<generation>` with separate configs and output folders; retain exact CPU models and allocated hostnames, and distinguish different models within a generation when necessary. Do not assume the PDF's example scheduler constraints are currently available.

**Raw data and processed results**

Use this convention when collecting new data, keeping machine first and experiment second as requested in PDF §12:

```text
data/<machine>/<experiment>/<run-id>/
    samples.csv.gz             # Or another lossless format with a documented reader
    config.json                # Effective settings used for this run
    metadata.json              # Environment, timer/units, counts, seed, status
    commands.txt               # Exact build, run, affinity, and environment settings
    build.txt                  # Compiler/version, all flags, build log
    source_commit.txt          # Exact source revision; include a snapshot for local changes
    disassembly.txt            # Inspected critical measurement loops
    run.log

results/<machine>/<experiment>/<run-id>/
    summary.csv
    curve.pdf
    boxplots.pdf
    inference.md
    provenance.json            # Raw inputs and exact analysis/plotting commands/revisions
```

These are future file conventions, not existing files. Experiments with several configurations may use one sample file per point, with point IDs mapped to their parameters. Record both timed sample count and dependent accesses per sample. Hazel runs must also retain the submitted Slurm script, job ID, requested constraint, actual hostname/model, and binding information.

Use a fresh run ID when the code or parameters change. Label runs as exploratory, formal, failed, or interrupted, and record the project phase. Keep all collected data and document exclusions instead of deleting inconvenient measurements. Matching machine/experiment/run paths connect raw and processed files without a separate database.

After completing a machine's inferences, place its consolidated table under `results/<machine>/`, recording the supporting runs. Include at least:

```text
level, capacity, line_size, associativity, derived_sets,
hit_latency, miss_or_next_level_latency, sharing_scope,
inclusion_exclusion_behavior, units, uncertainty, evidence
```

Compute `derived_sets = capacity / (associativity * line_size)` from independently inferred values. Investigate inconsistent geometry instead of silently rounding. Keep reference values and PMU validation separate from frozen timing inferences.

**Measurement requirements to preserve in the implementation**

PDF §§5–6 require at least **1,000,000 timed samples per tested configuration/x-axis point**, excluding warm-up. Preserve the full distributions, optionally losslessly compressed. Analysis must report mean, median, standard deviation, Q1, Q3, P5, P95, and outlier count, with a documented outlier rule.

Pin execution, keep memory local, record placement and interference, compile the benchmark with `-O0`, and inspect critical assembly. Use serialized, trustworthy timing and true dependent loads for latency. Measure timer/barrier overhead and compare regular versus randomized traversal around major capacity/latency boundaries. Preserve page policy, seeds, exact parameters, compiler information, and relevant environment settings. Label TSC ticks, Arm timer ticks, nanoseconds, and validated core cycles correctly; they are not interchangeable.

Produce the required boundary curves and representative box plots below, near, and above each inferred boundary. Prefer vector plots and remove background grids. Report broad transitions and uncertainty honestly. Document the cache domain visible to the pinned core rather than summing capacities across sockets.

**How the remaining PDF requirements fit later**

V3 starts with the timing-only suite. The same layout can accommodate the full assignment without a second benchmark framework. The following files/folders should be added only when the corresponding work begins.

| PDF requirement | Planned location and contents |
|---|---|
| §8.1: machine research and initial hypotheses | `docs/machines.md` for all eight ECE machines, vendor/ISA, microarchitecture, consistent introduction-year convention, process node when documented, and citations. `docs/hypotheses.md` for two hypotheses written before consulting cache specifications. |
| §7: Phase-I freeze | `docs/phase1-freeze.md` recording the commit/tag, timestamp, frozen inference tables, and raw-data inventory. Preserve exact code and measurements so the initial inferences remain auditable. |
| §§8.3–8.4: PMU verification and eight-event study | Later scripts in `scripts/`; `data/<machine>/pmu/<run-id>/` and matching `results/` paths. Preserve exact event names/semantics and raw counts. Repeat representative boundary points with the required million repetitions. Collect exactly eight selected events for L1-resident, LLC-sized randomized, and larger-than-LLC workloads; retain normalization denominators and ranked comparisons. Add validation tables separating timing inference, PMU evidence, reference values, sources/pages, and agreement. |
| §8.5: estimator verification | PMU reference measurements in the machine's `pmu/` data; estimator calibration, timing-only outputs, frozen parameters, and error comparisons in its `software_metric/` results. |
| §§8.6–9: lab predictions and Hazel | Later `scripts/slurm/` for one job script per target generation; `configs/hazel_<generation>.json` and matching machine directories. Save lab-only model parameters, predictions, uncertainty, commit, and timestamp under a future `results/cross_machine/prediction_freeze/`. |
| §§9–9.1: chronological analysis and two cache laws | Later `results/cross_machine/` for the chronological master table, required capacity/ways/latency/penalty/line-size/policy/software-metric plots, at least two comparable normalized PMU metrics, model fits, held-out errors, two named quantitative cache laws, and scaling-limit analysis. Keep a further prediction about five years beyond the newest measured system separate from the original frozen Hazel prediction. |
| §§3, 10, 12–16: report, slides, traceability, submission | `docs/` for report/slide sources and PDF exports, diagrams, contribution tables, meeting records, contributor screenshot, AI disclosure, competition scorecards, and complete ECE/Hazel reproduction instructions. Record a primary contributor for every figure/table. Package final source for each architecture/purpose, scripts, all collected raw data, processed outputs, report, and slides in the final Moodle ZIP. |

Follow the required order: freeze ECE timing-only inferences before PMU or cache-specification verification; complete ECE verification and freeze lab-only models/predictions before Hazel cache experiments; freeze Hazel timing-only inferences before inspecting its cache specifications or cache counters. Hazel benchmarks run on allocated compute nodes through Slurm. Attempt all accessible generations and meet the PDF's minimum of five distinct generations, documenting availability exceptions and including AMD if accessible.

Chronological plots use solid lines/markers for training observations, dashed lines only for extrapolation beyond the last measured training year, and distinct markers for later Hazel observations. Preserve the frozen prediction when adding held-out results. The two named laws must include quantitative rules, scope, uncertainty/limitations, held-out tests, and future scaling-wall analysis; normally one addresses capacity/scaling and one cost/behavior.

The final report title must be **Predicting Cache Evolution: The Growing Capacity and Latency Cost of CPU Caching**. Include the complete main experiment code and architecture-specific paths in the report body, matching the submitted source and recorded Git revision. Slides must include measured evidence for every inference, the prediction/reveal comparison, and both named laws. Add the actual shared GitHub and Overleaf URLs to this README and the report's first page when preparing the final submission.
