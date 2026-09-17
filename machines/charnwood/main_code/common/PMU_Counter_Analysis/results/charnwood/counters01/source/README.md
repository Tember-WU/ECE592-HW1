# Section 8.4 — eight performance counters across generations

Everything for this section lives here. `timing-only` (8.2) and `PMU-verification` (8.3) are inputs/evidence only and are not modified. This directory runs independently after copying it to another Linux machine. C++11 supports Intel/AMD x86-64 and Arm AArch64; build natively on each host. PMU access and CPU-specific semantics still require verification on that host.

The completed Artemisia full run is in [`results/artemisia/counters01`](results/artemisia/counters01/). Read its [`RUN_NOTES.md`](results/artemisia/counters01/RUN_NOTES.md) for observed behavior and limitations. Skylark is also complete in [`results/skylark/counters01`](results/skylark/counters01/); see its [`RUN_NOTES.md`](results/skylark/counters01/RUN_NOTES.md), including the preserved TLB anomaly and diagnostic repeats. Combined two-host plots and tables are in [`results/comparison_artemisia_skylark01`](results/comparison_artemisia_skylark01/). The other six hosts still need native collection. Testing details are in [`docs/VALIDATION.md`](docs/VALIDATION.md).

## Start on any of the eight ECE machines

Requirements: Linux, Python 3.9+, GCC/G++ (or `make CXX=clang++`), make, binutils/objdump, NumPy and Matplotlib. `perf` is useful for the archived event inventory; the benchmark accesses counters directly with `perf_event_open`. No root privileges or system changes are required.

```bash
cd ~/ECE592-HW1/PMU_Counter_Analysis
# Only if Python dependencies are missing:
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
make test
# Check topology, pick a permitted logical CPU and check its SMT sibling activity.
lscpu -e=CPU,CORE,SOCKET,NODE
# These examples use CPU 4; use your chosen core or omit --cpu for first allowed CPU.
python3 scripts/run.py --cpu 4 --preflight --run-id preflight01
python3 scripts/run.py --cpu 4 --smoke --run-id smoke01
python3 scripts/run.py --cpu 4 --run-id counters01 --contributor 'Full Name (GitHub username)'
```

Use a new run ID each time. Existing run directories are never overwritten. The full default is **1,000,000 timed batches × 64 dependent loads × 3 repetitions for each of three workloads**, plus eight independent counter passes per workload/repetition. `--samples` cannot fall below one million except in explicitly marked smoke mode. Smoke mode uses the same working sets and warm-up, but only 2,000 timed batches and one repeat. Preflight uses tiny workload probes and does not collect report data. It can take several minutes to complete a full run; free memory should comfortably exceed four times the local LLC plus setup overhead. Do not run competing copies on the same physical core.

Known profiles: sunbird, charnwood, ookay, upgrade, crux, skylark, thunderbird, artemisia. Hostname selects the profile, and the actual CPU/ISA must match. On a renamed machine use `--config configs/<matching-host>.json`. Unknown hardware needs a reviewed configuration with exactly eight slots; do not reuse raw encodings from another generation. Generic-only candidates use stable Linux API constants and are probed before collection.

## Workloads and eight events

All three use one randomized cyclic permutation, one pointer per cache line, and a true register-carried load dependency. Working sets default to **half the local L1D**, **one local LLC sharing domain**, and **four times that LLC**. Sizes come from the pinned CPU's Linux sysfs, never summed across sockets or AMD CCXs. This is Phase II. First-touch allocation follows pinning; `MADV_NOHUGEPAGE` requests base pages consistently. Each pass performs two full warm-up traversals before measurement. This tests steady-state behavior, not compulsory cold misses.

If the kernel omits a system-level cache, or your report uses a different documented/frozen LLC estimate, override explicitly:

```bash
python3 scripts/run.py --llc-bytes 32M --capacity-source 'Exact evidence file / section and cache sharing domain' --run-id counters02
```

Thunderbird's profile automatically uses its documented 32 MiB socket SLC if sysfs omits L3, with the supplied Altra datasheet (sections 2.1/2.5) copied as evidence. A core/cluster L2 reported as the highest sysfs level must not be called the chip SLC. The runner records the complete cache inventory. LLC-sized does not imply every load hits LLC, especially for noninclusive caches, shared domains, and contention. The protocol is capacity-relative, so byte counts differ between machines. Record all overrides and use the same policy across systems.

Exactly eight selected event slots are: cache references, cache misses, L1D loads, L1D load misses, L1D stores/replacements, LLC loads, LLC load misses, and DTLB misses. Profiles prefer generic events and then documented raw proxies if opening/counting fails. Thunderbird explicitly selects read-specific raw L1 events where the generic base mapping can alias the already selected cache-reference/miss slots; the reason is preserved in the probe log. `selected_events.json` records the actual eight choices. The alternatives are **not eight extra events**. Generic aliases may overlap semantically (e.g. generic cache misses and LLC load misses); they are not independent categories and must not be added together.

**Read `docs/methodology.md`, `docs/generic_mapping_review.md` and `event_semantics.csv` before writing conclusions.** Generic spellings do not prove cross-vendor equivalence. AMD replacements can describe L2 traffic/local fills, and Thunderbird's last-level events have an unresolved SLC interpretation documented in 8.3. A successful probe tests access/scheduling, not semantic validity. If no candidate works, the run stops with exact errors preserved rather than reporting zeros. Never change `perf_event_paranoid` or use system-wide uncore counts as silent per-thread replacements.

## Results and graphs

Each run goes to `results/<actual-host>/<run-id>/`:

- `metadata.json`: CPU identity, cache domain, topology/affinity, page policy, samples, command options, compiler, git state, Slurm fields and complete perf listing.
- `selected_events.json`, `probes/`: exact eight event names, numeric type/config, semantic caveats, errors and successful probes.
- `source/`, `source_sha256.json`: source/config/evidence snapshot, binary, disassembly and hashes. The source hash is authoritative for uncommitted edits.
- `raw/`: per-pass integer counts, enabled/running time, known load denominator, timing arrays (`*.ticks.u64.gz`) and command/error logs. Raw uint64 endianness is in metadata.
- `order.json`, `records.json`, `activity_before.txt`, `activity_after.txt`: deterministic randomized pass order, measurements and CPU activity snapshots.
- `analysis/`: raw-count CSV, normalized median/min/max CSV, all timing distribution statistics, event-semantic table, coverage audit, rankings and report draft.

Plots are PDF vector and PNG. The methodology diagram is also supplied in `docs/figures/` as PDF, SVG and PNG; regenerate its contributor label with `python3 scripts/draw_methodology.py --contributor "Full Name"`. A per-host `workload_comparison_*.pdf` panel shows how all eight counters respond across the three workloads. There are three compact 2×4 ranked/S-curve panels (one per workload), three rank matrices, three 2×4 observed-generation panels, and timing box plots per workload/repetition. No background grids or fitted/extrapolated trends. A single-host graph is a local check, not an eight-machine comparison. Every plot contains the provided contributor name; replace `UNASSIGNED` before submission. The report draft intentionally leaves evidence-dependent interpretation to be completed after collecting all machines.

## Combine all eight machines

Copy each host's results directory back under this folder (using your usual authorized file-transfer method). The script does not SSH, submit jobs or change external services. Select exactly one complete run per host:

```bash
python3 scripts/analyze.py \
  results/sunbird/counters01 results/charnwood/counters01 \
  results/ookay/counters01 results/upgrade/counters01 \
  results/crux/counters01 results/skylark/counters01 \
  results/thunderbird/counters01 results/artemisia/counters01 \
  --output results/comparison01
```

The analyzer refuses duplicate hosts, mixed smoke/full runs, incomplete runs, and different batch/line-spacing protocols. `REPORT.md` lists missing hosts; `coverage.csv` checks full samples. `rankings.csv` and compact Markdown tables give all eight event orderings for all three workloads. Values are median across independent counter passes; ranges show variation, not confidence intervals. Equal numerical values use hostname order; rankings are descriptive, not a hardware performance score. Use the event table to restrict comparisons to defensible semantic groups.

## Hazel / other machines

8.4 explicitly requires the eight ECE hosts. The same source supports later allocated Hazel compute nodes. Use `scripts/slurm.sh` as a template, supply the live site account/constraint at submission, and provide an exact CPU profile. Do not run on login nodes. Follow the project's prediction freeze before collecting held-out cache data. No scheduler generation is hard-coded and no jobs are submitted automatically.

```bash
# Inside an authorized allocation, with a reviewed CPU profile:
srun --cpu-bind=cores python3 scripts/run.py --config configs/actual_cpu.json --run-id hazel01
# Or submit the included template with live scheduler options and matching config:
# sbatch --account=YOUR_ACCOUNT --constraint=LIVE_CONSTRAINT scripts/slurm.sh configs/actual_cpu.json hazel01
```

## Submission checklist for 8.4

Collect all eight ECE hosts, verify workload behavior and PMU definitions, discuss Intel/AMD/Arm and older/newer results, and include normalized rankings, compact panels, distributions, exact event table, methodology diagram, raw data, scripts and complete source listings. Record actual SMT activity/reservation and environment caveats in run notes. The suite captures activity snapshots but does not certify an idle sibling or reserve a core. Add real contributor identities, GitHub/Overleaf links, final narrative and AI-assistance disclosure to the overall report. This directory does not invent remote measurements or complete unrelated report sections.
