# Section 8.5: Software-only L1D hit-rate estimation

Estimate the fraction of **individual timed target loads** that hit L1D, using
only their timing distribution. The estimator does not read PMU counters or
cache specifications. A separate validation executable counts the same workload
to provide a hardware reference. This directory is independent of the existing
Phase-I and Section 8.3 experiments.

## Small experiment design

1. Collect one million samples for an empty timer, an 8 KiB random ring expected
   to hit L1, and a 512 KiB random ring expected to miss L1. Repeat both cache
   classes with independent seeds for a calibration check.
2. Choose a threshold minimizing equally weighted false-hit and false-miss
   rates. Classify an access as a hit when its raw interval is at most that
   threshold. Reject poorly separated calibration distributions. Record the
   model, source hashes and timestamp before validation uses counters.
3. Run eight held-out workload configurations: a small resident ring, a boundary
   ring, a nonresident ring, three mixed workloads with repeated visits to each
   node, and two larger rings. Each has three repeats, each with one million
   individually timed loads. Run both the estimator-only and PMU executables
   with the same seed/configuration, alternating pair order between repeats.
4. Compare the frozen timing classification with a PMU L1 hit-rate reference.
   Preserve absolute percentage-point error, relative percent error, repeated
   results, block-bootstrap intervals and threshold sensitivity. An empty-loop
   PMU control checks entry/exit overhead.

This is **54 million retained timing intervals**: 5M calibration, 1M PMU
empty control, and 8 cases × 3 repeats × 2 executions × 1M validation samples.
This includes 52M single-target-load intervals and 2M empty controls.
Warm-up is additional and excluded. These are two main stages (calibration and
validation), not 54 different experimental designs.

Artemisia's completed [hitrate01 results](results/artemisia/hitrate01/RUN_NOTES.md)
use a timing-only threshold of 57 TSC ticks. The 24 paired validation cases have
mean absolute error 0.015 percentage points and worst-case error 0.033 pp against
the PMU reference. The possible contribution from auxiliary PMU-counted loads
is up to 0.0192 pp, so these figures do not establish finer target-only accuracy.
The [comparison plot](results/artemisia/hitrate01/figures/hit_rate_comparison.pdf)
and [per-repeat table](results/artemisia/hitrate01/comparison.csv) retain both the
same-execution comparison and the standalone estimator's paired comparison.

Sunbird's completed [hitrate01 results and failure analysis](results/sunbird/hitrate01/SUNBIRD_NOTES.md)
retain the same calibration/workload parameters and unchanged estimator. Its independently
calibrated threshold is 70 ticks, but mean absolute error is **26.882 pp**, with a worst
case of **96.692 pp**. Calibration separation does not transfer to the held-out 48/128 KiB
workloads on this machine. All 54 collections and integrity/reference checks passed;
this is an estimator-accuracy failure, preserved without PMU-based threshold retuning.

## Run on Sunbird

```bash
cd /home/swu35/ECE592-HW1/software-hit-rate
export PATH="/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:/home/swu35/ECE592-HW1/timing-only/capacity/build/sunbird/deps/usr/bin:$PATH"
make MACHINE=sunbird check
python scripts/analyze.py --machine sunbird --run-id hitrate01
python preparation/sunbird/setup01/audit_run.py
# For a new collection, choose an unused run ID:
python scripts/run_experiment.py --machine sunbird --run-id hitrate02
```

Sunbird uses CPU 32/node 0 and its locally verified `mem_load_uops_retired.l1_miss`
and `mem_uops_retired.all_loads` events. These count retired load uops; the known
single-load instruction loop and the auxiliary-load check constrain the reference
denominator. No benchmark kernel or timing-only classification logic was changed.

## Run on Artemisia

```bash
cd /home/swu35/ECE592-Project1/ECE592-HW1/software-hit-rate
python3 -m pip install -r requirements.txt  # only if dependencies are absent
make MACHINE=artemisia check
python3 scripts/run_experiment.py --machine artemisia --run-id hitrate01
python3 scripts/analyze.py --machine artemisia --run-id hitrate01
```

The runner refuses existing run IDs. Choose a new ID for a new collection.
It pins CPU 32, binds memory to NUMA node 1, uses prefaulted base pages and logs
CPU/sibling activity. It does not change host-wide settings or make Git commits.

## Files and direct estimator use

| Location | Contents |
|---|---|
| `src/hit_rate.c`, `src/kernel.h` | Complete benchmark and single-load timing loop; estimator has no PMU interface |
| `src/pmu.h` | Two-event validation wrapper, compiled only with `WITH_PMU` |
| `configs/<machine>.json` | CPU/NUMA, seeds, samples, workloads and validation-only event encodings |
| `scripts/estimator.py` | Timing-only calibration, classification, uncertainty and distribution statistics |
| `scripts/run_experiment.py` | Serial collection and pre-validation threshold checkpoint |
| `scripts/analyze.py` | Full raw-data verification, PMU comparison, report tables and figures |
| `tests/` | Classification, bad-input/reference rejection and binary-kernel equivalence checks |
| `data/<machine>/<run>/` | Effective config, commands, losslessly compressed uint64 samples, counters, environment, frozen model and source/binary snapshots |
| `results/<machine>/<run>/` | Statistics, error table, validation record, run notes and PNG/PDF figures |

`hit_rate` accepts a threshold calibrated from that machine's timing. For
example, replace `THRESHOLD` below with `threshold_ticks` from its saved model:

```text
numactl --membind=1 build/artemisia/hit_rate \
  262144 64 1000000 86003 32 4 THRESHOLD random samples.u64 metadata.json
```

Arguments are bytes, node spacing, samples, seed, CPU, visits per node,
threshold, order, raw output, and JSON output. The JSON reports the classified
hit count and total samples. Classification uses **only raw time and the
threshold**, not the configured footprint, reuse, nominal rate, or PMU result.

Every interval loads the target address itself once. At reuse=1 the loaded
pointer becomes the next target. At reuse>1 the same target is visited repeatedly
before following its pointer; timer fences still prevent overlapping visits.
The full loop uses registers at `-O0`; output stores occur after the stop timer.
Output-store cache effects are retained in both calibration and validation.
The saved empty-timer distribution characterizes overhead; no minimum is
blindly subtracted. Timer ticks are not core cycles.

## PMU reference and uncertainty

Artemisia uses the locally discovered `mem_load_retired.l1_miss` and
`mem_inst_retired.all_loads`. The reference is `1 - misses / retired_loads`, with
both events grouped, pinned, per-thread and user-only. The analyzer rejects
multiplexing and differences greater than 0.1% between recorded total loads and
known target loads. The small entry/exit overhead is disclosed rather than
subtracted. Sources: [the local Section 8.3 inventory](../PMU-verification/events/results/artemisia/discovery01/EVENTS.md),
[Intel's Sapphire Rapids event definitions](https://github.com/intel/perfmon/blob/main/SPR/events/sapphirerapids_core.json),
and [perf_event_open(2)](https://man7.org/linux/man-pages/man2/perf_event_open.2.html).

The primary comparison applies the frozen timing-only rule to the exact timing
samples collected during the validation copy's counter window. A second column
compares a standalone, counter-free estimator execution with its paired PMU
execution; the latter also includes temporal drift. No per-access PMU labels or
validation PMU rates enter training. This separation prevents a reference from
silently becoming an estimator input.

Confidence intervals bootstrap 100 contiguous sample blocks (2,000 resamples).
They condition on the classifier and assume approximately exchangeable blocks;
they do not bound systematic classification bias. The sensitivity range varies
the threshold over choices within one percentage point of the best training
error. It is a sensitivity analysis, not another confidence interval. Relative
error is unstable near zero reference hit rate and undefined at zero.

## Portability and scope

The instruction paths cover Linux x86-64 and AArch64. Artemisia and Sunbird have
been measured; Sunbird exposes substantial estimator error. The generic Arm timer may not
resolve L1 versus L2 single-access timings; calibration must demonstrate usable
separation before reporting a hit rate. Do not claim Arm accuracy from this
implementation alone. The runner currently requires the Intel identity fields
in its validation configuration; AMD/Arm PMU adapters require an appropriate
event/denominator definition and a small runner update. Never copy the Intel raw
encodings or retired-load semantics to another PMU without verification.

CPU model checking and old event-list copying are validation orchestration,
not inputs to the counter-free executable. No cache geometry is read by it.
New machines must recalibrate from timings, keep the same estimator logic,
and use held-out workloads. Strong interference, timing drift, prefetch/fill
buffers, TLB misses, timer quantization and calibration overlap can cause error.
This estimates an instrumented microbenchmark's L1D hit rate, not automatically
the hit rate of an arbitrary application running without probes.

The run checkpoint is a timestamped, hashed model freeze before verification.
For Competition 2, commit the final code, calibration procedure/parameters and
results and record that Git commit before official scoring. The runner does not
commit or push automatically. Other ECE machines and Hazel remain separate runs.
