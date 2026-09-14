# AGENTS.md

## Scope

This file applies only to the `PMU_Counter_Analysis` directory in this repository. This directory implements Section 8.4: eight performance counters across CPU generations. It is an independent, self-contained experiment workflow, not a general project-wide guide.

Important boundary: do not treat `timing-only` or `PMU-verification` as editable inputs for this section. Those directories are evidence and reference material only. This directory is the place where the actual 8.4 runs, analysis, and report artifacts are produced.

## Project purpose

The goal of this project is to collect and compare eight hardware PMU event measurements across multiple Linux hosts using a common benchmark protocol, then normalize and rank them per workload while preserving semantic caveats.

This project is specifically about:

- direct PMU access using `perf_event_open` and a benchmark program in `src/bench.cpp`
- one common workload protocol across multiple machines
- exactly eight selected event slots per run
- validation of PMU semantics across Intel, AMD, and Arm systems
- per-host raw results, analysis, and report-ready plots
- combined comparison across multiple host results

## What this folder contains

- `README.md`: primary operating instructions and project narrative
- `Makefile`: build/test targets for the benchmark and validation checks
- `requirements.txt`: Python dependencies for analysis and plotting
- `src/bench.cpp`: native benchmark driver; does a randomized cyclic dependency chain and performs direct PMU counter collection
- `scripts/run.py`: main execution driver for preflight, smoke, and full collection runs
- `scripts/analyze.py`: combines multiple host result directories into a single comparison
- `scripts/draw_methodology.py`: regenerates the methodology diagram
- `scripts/slurm.sh`: template for lab/Hazel-style job submission
- `configs/*.json`: per-host profiles for the supported ECE machines
- `docs/`: methodology, validation, mapping review, report checklist, event evidence, and figures
- `results/`: per-host result directories and a combined comparison result set
- `tests/`: project validation and integration checks

## Build and run flow

### Initial setup

From this directory:

```bash
cd ~/ECE592-HW1/PMU_Counter_Analysis
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
make test
```

### Check topology and pick a CPU

```bash
lscpu -e=CPU,CORE,SOCKET,NODE
```

Use a valid logical CPU for the host. The project expects a stable affinity and warns against running competing copies on the same physical core.

### Typical command sequence

```bash
python3 scripts/run.py --cpu 4 --preflight --run-id preflight01
python3 scripts/run.py --cpu 4 --smoke --run-id smoke01
python3 scripts/run.py --cpu 4 --run-id counters01 --contributor 'Full Name (GitHub username)'
```

- Use a new run ID each time.
- Existing run directories are never overwritten.
- `--preflight` is a tiny probe mode.
- `--smoke` is a reduced validation mode.
- Full runs use the full protocol and produce report artifacts.

## Core benchmark design

The native benchmark is located in `src/bench.cpp` and is the execution heart of the project.

Core properties:

- uses a randomized cyclic permutation, one pointer per cache line
- uses a true register-carried dependency chain, not independent loads
- first-touch allocation follows affinity and uses `MADV_NOHUGEPAGE`
- warms up to steady state before measurement
- measures both timed loads and counter-only passes
- reads PMU counts through Linux `perf_event_open`
- writes timing data as raw uint64 arrays and JSON metadata

The benchmark is intentionally designed to test behavior under steady-state cache and TLB pressure, not cold misses.

## Workloads and event protocol

This project uses three workloads and exactly eight selected event slots. The README states the intended protocol clearly:

- working sets default to roughly half the local L1D, one local LLC sharing domain, and four times that LLC
- sizes come from the pinned CPU's Linux sysfs, not a sum across sockets or AMD CCX domains
- each pass does two complete warm-up traversals before measurement
- all event selections are recorded in `selected_events.json`
- generic event names are preferred first, followed by documented raw proxies if needed
- Thunderbird specifically preserves a documented raw-proxy caveat
- generic aliases may overlap semantically; they are not independent categories

The project explicitly warns against:

- adding extra event slots beyond the selected eight
- treating generic names as proof of cross-vendor equivalence
- using system-wide uncore counts as silent replacements for per-thread events
- changing `perf_event_paranoid` or operating outside the defined protocol

## Result directory structure

Each run is placed under:

```text
results/<actual-host>/<run-id>/
```

Expected contents include:

- `metadata.json`
- `selected_events.json`
- `probes/`
- `source/`
- `source_sha256.json`
- `raw/`
- `order.json`
- `records.json`
- `activity_before.txt`
- `activity_after.txt`
- `analysis/`

The project creates PDF and PNG plots, and methodology diagrams are kept in `docs/figures/`.

## Analysis and reporting

### Host-specific analysis

`python3 scripts/run.py` produces the run artifacts and report-ready data from one host.

### Multi-host comparison

The combined analysis is performed with:

```bash
python3 scripts/analyze.py \
  results/sunbird/counters01 results/charnwood/counters01 \
  results/ookay/counters01 results/upgrade/counters01 \
  results/crux/counters01 results/skylark/counters01 \
  results/thunderbird/counters01 results/artemisia/counters01 \
  --output results/comparison01
```

This analyzer rejects:

- duplicate hosts
- mixed smoke/full runs
- incomplete runs
- mismatched protocols or batch/line-spacing assumptions

It produces summary CSVs and markdown tables, including ranking outputs that are descriptive rather than a hardware performance score.

### Methodology diagram

Regenerate the figure with:

```bash
python3 scripts/draw_methodology.py --contributor "Full Name"
```

## Host profile and config system

The project uses machine-specific JSON configs in `configs/`.

Examples include:

- `artemisia.json`
- `charnwood.json`
- `crux.json`
- `ookay.json`
- `skylark.json`
- `sunbird.json`
- `thunderbird.json`
- `upgrade.json`

Hostname matching selects the config for the host. If a machine is renamed, use `--config configs/<matching-host>.json`. The config should match the actual CPU/ISA and should not silently reuse raw encodings from another generation.

## Important project guardrails

These are essential constraints for any agent working in this directory:

1. Work only within `PMU_Counter_Analysis`.
2. Do not modify or invent results for `timing-only` or `PMU-verification`.
3. Preserve the exact run protocol; do not change measurement logic without explicit reason.
4. Treat the benchmark and config files as the source of truth for hardware-specific behavior.
5. Keep each run isolated under a unique `--run-id`.
6. Do not overwrite existing result directories.
7. Never report a PMU measurement as valid if the event mapping has unresolved semantic ambiguity.
8. Record environment caveats, system topology, and affinity details in run notes.
9. No fabricated remote measurements, no hidden scheduler actions, and no unsupported assumptions.

## Documentation to read before conclusions

Before writing conclusions or final report text, read the project docs in this order:

- `README.md`
- `docs/methodology.md`
- `docs/generic_mapping_review.md`
- `docs/VALIDATION.md`
- relevant host evidence in `docs/event_evidence/...`
- `docs/REPORT_CHECKLIST.md`

These documents define the evidence model, semantic interpretation limits, and validation process.

## Validation expectations

Use the repository's build/test checks:

```bash
make test
```

The test suite includes validation scripts that are intended to catch broken cross-host assumptions, mismatched analysis workflows, and incomplete result directories.

## Minimal agent summary

If a future agent needs to understand the project quickly, the short version is:

- Section 8.4 is implemented here.
- This folder is an independent PMU collection and comparison pipeline.
- The benchmark uses a pinned, dependency-based load chain and direct `perf_event_open` counters.
- The protocol measures exactly eight events across three workloads and multiple hosts.
- Results are stored per host and combined with `scripts/analyze.py`.
- Semantic caveats are required; raw PMU names do not automatically imply cross-vendor equivalence.
- The workflow is evidence-driven, hardware-aware, and requires explicit documentation of any overrides or caveats.

## Final note for agents

This directory is not a generic benchmarking sandbox. It is a constrained, documented research workflow for a specific academic section of the project. Preserve the project’s evidence standards, run protocol, and host-by-host semantics when making changes or writing summaries.
