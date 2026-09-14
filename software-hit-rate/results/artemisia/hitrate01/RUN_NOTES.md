# artemisia: Section 8.5 software-only L1D hit-rate estimator

Completed `hitrate01`: 54,000,000 single-access timing samples, five timing-only calibration configurations, one empty PMU control, and 24 paired validations (8 workloads × 3 repeats × estimator-only/PMU executions). Every configuration retains 1,000,000 samples.

The timing-only threshold is **hit iff raw interval ≤ 57 ticks**. Balanced training error is 0.014%; independent-seed calibration check error is 0.026%. Threshold selection never used PMU data. Calibration labels mean strongly expected L1-resident/non-resident states, not hardware-proven per-access labels.

Mean absolute error over all 24 same-execution validation cases is **0.015 percentage points**, with worst-case **0.033 pp**. Separate estimator-only executions versus their paired PMU references have mean absolute error **0.014 pp**; that comparison additionally includes run-to-run drift.

| Workload | Reuse | Software hit % (validation execution) | PMU hit % | Mean absolute error (pp) |
|---|---:|---:|---:|---:|
| resident_16k | 1 | 99.942 | 99.966 | 0.025 |
| boundary_48k | 1 | 2.502 | 2.505 | 0.003 |
| nonresident_128k | 1 | 0.134 | 0.137 | 0.003 |
| reuse2_256k | 2 | 50.004 | 50.016 | 0.012 |
| reuse4_256k | 4 | 74.981 | 75.003 | 0.023 |
| reuse8_256k | 8 | 87.480 | 87.501 | 0.021 |
| deeper_8m | 1 | 0.000 | 0.015 | 0.015 |
| large_128m | 1 | 0.000 | 0.018 | 0.018 |

## Measurement and PMU reference

Each interval contains one actual target load, not a divided batch latency. Reuse r means the same node is read r times before following its next pointer. A random ring determines node order. Reuse is a workload control; the estimator receives only timing samples and its threshold. The timer fences serialize even repeated visits. All measurement-loop state is in registers at -O0. One raw-output store per sample is essential for retaining the distribution; its cache effects remain part of the measured instrumented workload.

Placement: CPU 32, NUMA node 1, local first touch with explicit memory binding, base pages, prefaulted chain/output, at least one million warm-up loads plus 2,048 discarded instrumentation warm-up samples. Raw times include fences/branch/timer overhead; they are not core cycles or uninstrumented load latency. The empty-timer distribution is retained rather than subtracting one minimum.

Reference events: `mem_load_retired.l1_miss` (0x08d1) and `mem_inst_retired.all_loads` (0x81d0); per-thread, user mode, grouped and pinned, with equal enabled/running times. The reference is `1 - L1_misses / retired_loads`. All counters enclose the same single-load loop used by the estimator. Maximum absolute difference between retired loads and 1,000,000 known target loads was 192 loads; the empty-loop control recorded 74 retired loads. Entry/exit helper loads are retained in the reference denominator, not silently subtracted. Their fraction bounds the possible mismatch between the all-load reference and target-only metric. The largest such fraction was 0.0192 pp, comparable to the measured mean error. Therefore this experiment does not establish target-only accuracy more precise than that reference limitation. `pmu_target_hit_bound_low/high` in the comparison table allow every auxiliary load to be either hit or miss; these bounds assume the events themselves count correctly. Near-zero PMU hit rates at the largest footprints can be predominantly helper hits. Calibration PMU values and per-access hardware labels are not used.

Event provenance: the local Section 8.3 `perf list --details` is copied under the run preflight directory. The CPU-specific definitions can also be checked against [Intel perfmon, Sapphire Rapids](https://github.com/intel/perfmon/blob/main/SPR/events/sapphirerapids_core.json). Grouping and user/kernel counting scope follow [perf_event_open(2)](https://man7.org/linux/man-pages/man2/perf_event_open.2.html).

## Uncertainty, limitations, and failure cases

- `comparison.csv` reports the raw estimate, a 95% contiguous-block bootstrap interval, threshold sensitivity, absolute pp error and relative percent error for every repeat. The interval assumes approximately exchangeable blocks and conditions on the frozen classifier; it does not cover systematic misclassification. Absolute error is the useful metric near zero hit rate; relative error becomes unstable and is undefined for a zero PMU reference.
- A fixed threshold can fail when L1-hit and L2-hit intervals overlap, frequency or interference shifts timing, or the generic timer is too coarse. The runner refuses calibration with more than 15% balanced training/check error. Passing that check does not guarantee unseen-workload accuracy.
- Repeated loads, prefetching, fill-buffer service, TLB misses, logging stores and interrupts can change observed timings. The estimate describes these explicitly instrumented microbenchmarks, not an arbitrary application with no timing overhead. No claim is made that a nominal reuse factor guarantees an exact hardware hit rate.
- The 48 KiB case has a low measured hit rate because the instrumented footprint also competes with output logging and other cache occupants. It is a hit-rate test, not a new estimate of physical L1 capacity. The repeated-node mixed cases deliberately provide different hit fractions; their success is not evidence of comparable accuracy on arbitrary access streams.
- Only Artemisia is experimentally validated here. x86-64 and AArch64 instruction paths share the algorithm, but the Arm path is untested; single-access Arm timer resolution may make calibration fail. Other CPUs require their own calibration and semantically valid PMU configuration. This retired-load ratio must not be copied to AMD/Arm refill/dispatch events without denominator validation.
- Recorded quality: 0 minor faults, 0 major faults and 2 involuntary switches across all measurement regions. Per-run CPU/sibling activity is retained in the manifest.

## Reproduction and figures

`python3 scripts/analyze.py --machine artemisia --run-id hitrate01` reopens every compressed raw array, verifies hashes and recomputes statistics and figures. The analyzer verifies the frozen model, every archived source/binary hash and the C/Python classifier counts. See `statistics.csv`, `comparison.csv`, `validation.json` and `figures/` (calibration, boxplots, hit-rate/error comparison, methodology; PNG and PDF). The exact final analyzer is retained in `analysis_source/`, separately from the unchanged pre-collection source checkpoint.

The run contains exact commands, effective config, raw uint64 timing arrays, metadata, local event descriptions, compiler/CPU topology, source and executable/disassembly snapshots. The threshold checkpoint predates validation; it is not an official Git competition freeze. Commit the final estimator, parameters and results and record that commit before official scoring. No commit/push is performed by this workflow.
