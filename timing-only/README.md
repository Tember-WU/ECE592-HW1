# ECE592 HW1: Timing-only Experiments

This project groups the timing-only work in [PROJECT 1.pdf](../../PROJECT%201.pdf) into independent experiment directories. **All code, configurations, scripts, dependencies, tests, documentation, and outputs for Cache levels and capacity are under [`capacity/`](capacity/README.md).** Capacity uses a shared first-round scan, a second round selected from each machine's new timing data, and an optional focused third round. The remaining experiment directories are placeholders for later implementation.

**Directory layout**

```text
ECE592-HW1/timing-only/
├── README.md
├── capacity/
│   ├── README.md                 # Method, commands, data format, and limitations
│   ├── Makefile
│   ├── requirements.txt
│   ├── configs/
│   │   ├── artemisia.json
│   │   └── common/round1.json
│   ├── src/
│   │   └── cache_bench.c
│   ├── scripts/
│   │   ├── run_capacity.py
│   │   ├── plan_capacity.py
│   │   └── analyze_capacity.py
│   ├── tests/
│   │   └── test_capacity.py
│   ├── build/<machine>/
│   ├── data/<machine>/<run-id>/
│   └── results/<machine>/<run-id>/
├── line_size/
├── associativity/
├── latency/
├── inclusion/
├── software_metric/
└── docs/                        # Project-wide research, freezes, and report planning
```

The eight machine directories under `capacity/build/`, `capacity/data/`, and `capacity/results/` already exist: `artemisia`, `charnwood`, `crux`, `ookay`, `skylark`, `sunbird`, `thunderbird`, and `upgrade`. The collector creates run directories when collecting new measurements. Only Artemisia has a supplied configuration. The current capacity kernel supports Linux x86-64; AArch64 needs its own implementation.

**Run capacity**

Starting in `ECE592-HW1/timing-only/`:

```bash
cd capacity
python3 -m pip install -r requirements.txt
make MACHINE=artemisia capacity assembly
make check
python3 scripts/run_capacity.py --machine artemisia --run-id round1 --dry-run
```

The dry run validates the 39-point shared coarse scan without collecting measurements. CPU 32 / NUMA node 1 are the configured Artemisia placement; collect and analyze the new scan:

```bash
python3 scripts/run_capacity.py --machine artemisia --run-id round1
python3 scripts/analyze_capacity.py --machine artemisia --run-id round1
```

After inspecting the new curve, use `plan_capacity.py` to generate a targeted round-2 config. Every collection needs a new run ID; the analyzer can combine multiple compatible rounds while retaining each run's distributions. See the [capacity README](capacity/README.md) for the complete two-to-three-round workflow. The C measurement kernel retains the V2 implementation; historical data and frozen conclusions have not been imported.

**How to organize each experiment**

Use the same internal layout when implementing `line_size/`, `associativity/`, or another experiment. Keep these files within the experiment's own directory:

| Subdirectory or file | Contents |
|---|---|
| `README.md` | The experiment's purpose, method, exact build/run/analysis commands, output format, and limits. |
| `configs/<machine>.json` | Machine identity, CPU/NUMA placement, and that experiment's measurement and sweep settings. |
| `src/` | Its benchmark implementation and any required architecture-specific paths. Keep a small experiment self-contained until shared helpers are needed. |
| `scripts/` | Its runner, analysis/plotting code, and later Slurm scripts when needed. |
| `build/<machine>/` | Locally built executables, object files, and disassembly. |
| `data/<machine>/<run-id>/` | Raw samples, effective config, source/build records, exact commands, environment, seeds, and run status. |
| `results/<machine>/<run-id>/` | Statistics, figures, inference notes, and links back to the raw inputs and analysis commands. |
| `tests/` | Small correctness checks, using synthetic data when possible. |
| `Makefile`, `requirements.txt` | Build rules and dependencies for this experiment. |

The experiment is identified by its outer directory, so output paths do not repeat `capacity` inside `capacity/data/` or `capacity/results/`. Data remain separated by machine and run. Adding a compatible machine means adding a config in the relevant experiment; the runner can create its output directories automatically. A new ISA or unavailable timer may require an implementation change.

For capacity, defaults and sweep points are resolved from `capacity/configs/<machine>.json`. Other experiments can use their own settings without extending one large cross-experiment configuration. Start a new machine with a broad timing sweep and refine from its evidence rather than treating Artemisia's refinement choices as universal cache sizes.

Retain the exact source or source snapshot, compiler/version/flags, command, affinity, sample count, units, seed, raw filenames, and analysis provenance for every run. Use new run IDs when code or parameters change. Preserve failed and exploratory attempts and document exclusions. During final submission packaging, also provide the machine-first, experiment-second evidence organization required in PDF §12.

A consolidated cache table should link the supporting experiment runs for each machine and include `level`, `capacity`, `line_size`, `associativity`, `derived_sets`, `hit_latency`, `miss_or_next_level_latency`, `sharing_scope`, `inclusion_exclusion_behavior`, `units`, and uncertainty. Compute `derived_sets = capacity / (associativity * line_size)` from independent inferences and investigate inconsistent geometry rather than rounding.

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

For every reverse-engineering target, keep a methodology diagram with that experiment, for example in `<experiment>/docs/` showing the access pattern, varied parameter, controls, measured signature, and inference rule. A shared code module may need multiple diagrams: hierarchy and capacity, and hit latency and miss/next-level latency, are distinct targets in the report.

**Measurement requirements to preserve in the implementation**

PDF §§5–6 require at least **1,000,000 timed samples per tested configuration/x-axis point**, excluding warm-up. Preserve the full distributions, optionally losslessly compressed. Analysis must report mean, median, standard deviation, Q1, Q3, P5, P95, and outlier count, with a documented outlier rule.

Pin execution, keep memory local, record placement and interference, compile the benchmark with `-O0`, and inspect critical assembly. Use serialized, trustworthy timing and true dependent loads for latency. Measure timer/barrier overhead and compare regular versus randomized traversal around major capacity/latency boundaries. Preserve page policy, seeds, exact parameters, compiler information, and relevant environment settings. Label TSC ticks, Arm timer ticks, nanoseconds, and validated core cycles correctly; they are not interchangeable.

Produce the required boundary curves and representative box plots below, near, and above each inferred boundary. Prefer vector plots and remove background grids. Report broad transitions and uncertainty honestly. Document the cache domain visible to the pinned core rather than summing capacities across sockets.

**How the remaining PDF requirements fit later**

V3 groups timing-only work by experiment. Project-wide research, freezes, and submission records belong in `docs/`; cross-machine synthesis can later use `results/cross_machine/`. The following files/folders should be added only when the corresponding work begins.

| PDF requirement | Planned location and contents |
|---|---|
| §8.1: machine research and initial hypotheses | `docs/machines.md` for all eight ECE machines, vendor/ISA, microarchitecture, consistent introduction-year convention, process node when documented, and citations. `docs/hypotheses.md` for two hypotheses written before consulting cache specifications. |
| §7: Phase-I freeze | `docs/phase1-freeze.md` recording the commit/tag, timestamp, frozen inference tables, and raw-data inventory. Preserve exact code and measurements so the initial inferences remain auditable. |
| §§8.3–8.4: PMU verification and eight-event study | A future `verification/` directory for PMU scripts and machine-organized raw/processed outputs. Preserve exact event names/semantics and raw counts. Repeat representative boundary points with the required million repetitions. Collect exactly eight selected events for L1-resident, LLC-sized randomized, and larger-than-LLC workloads; retain normalization denominators and ranked comparisons. Add validation tables separating timing inference, PMU evidence, reference values, sources/pages, and agreement. |
| §8.5: estimator verification | PMU references in the future verification directory; calibration, timing-only outputs, frozen parameters, and error comparisons under `software_metric/`, organized by machine. |
| §§8.6–9: lab predictions and Hazel | Within each experiment, later `scripts/slurm/` for job scripts and `configs/hazel_<generation>.json` with matching machine output directories. Save lab-only model parameters, predictions, uncertainty, commit, and timestamp under a future `results/cross_machine/prediction_freeze/`. |
| §§9–9.1: chronological analysis and two cache laws | Later `results/cross_machine/` for the chronological master table, required capacity/ways/latency/penalty/line-size/policy/software-metric plots, at least two comparable normalized PMU metrics, model fits, held-out errors, two named quantitative cache laws, and scaling-limit analysis. Keep a further prediction about five years beyond the newest measured system separate from the original frozen Hazel prediction. |
| §§3, 10, 12–16: report, slides, traceability, submission | `docs/` for report/slide sources and PDF exports, diagrams, contribution tables, meeting records, contributor screenshot, AI disclosure, competition scorecards, and complete ECE/Hazel reproduction instructions. Record a primary contributor for every figure/table. Package final source for each architecture/purpose, scripts, all collected raw data, processed outputs, report, and slides in the final Moodle ZIP. |

Follow the required order: freeze ECE timing-only inferences before PMU or cache-specification verification; complete ECE verification and freeze lab-only models/predictions before Hazel cache experiments; freeze Hazel timing-only inferences before inspecting its cache specifications or cache counters. Hazel benchmarks run on allocated compute nodes through Slurm. Attempt all accessible generations and meet the PDF's minimum of five distinct generations, documenting availability exceptions and including AMD if accessible.

Chronological plots use solid lines/markers for training observations, dashed lines only for extrapolation beyond the last measured training year, and distinct markers for later Hazel observations. Preserve the frozen prediction when adding held-out results. The two named laws must include quantitative rules, scope, uncertainty/limitations, held-out tests, and future scaling-wall analysis; normally one addresses capacity/scaling and one cost/behavior.

The final report title must be **Predicting Cache Evolution: The Growing Capacity and Latency Cost of CPU Caching**. Include the complete main experiment code and architecture-specific paths in the report body, matching the submitted source and recorded Git revision. Slides must include measured evidence for every inference, the prediction/reveal comparison, and both named laws. Add the actual shared GitHub and Overleaf URLs to this README and the report's first page when preparing the final submission.
