# Sunbird latency: complete seven-group run

Run **`latency01` completed all seven groups and all 30 configurations** in 169.26 seconds (2 minutes 49.26 seconds), from 2026-09-10T20:53:04.471496+00:00 to 2026-09-10T20:55:53.727582+00:00. This is September 10, 2026, 16:53:04–16:55:53 EDT on Sunbird. Every configuration retained 1,000,000 batches after warm-up. The nine paired configurations save two intervals per batch, giving **30,000,000 batches and 39,000,000 recorded timer intervals** in total.

The existing `configs/sunbird.json` was used unchanged. Its capacity-basis hash matches the saved Sunbird capacity inference from `round1_retry1` and `round2`; timing observations exist for all eight distinct configured footprints. The C kernel and timer header are identical to the Artemisia collection snapshots. All points ran serially in the original collector's deterministic shuffled order (`order_seed=59280`), each in a fresh process. No formal collection retry or extra follow-up group was needed.

| Group | Completed configurations | Recorded intervals |
|---|---:|---:|
| calibration | 12/12 | 12,000,000 |
| l1_hit | 3/3 | 3,000,000 |
| l2_hit | 3/3 | 3,000,000 |
| llc_hit | 3/3 | 3,000,000 |
| l1_miss | 3/3 | 6,000,000 |
| l2_miss | 3/3 | 6,000,000 |
| llc_miss | 3/3 | 6,000,000 |

Latency units below are **TSC ticks per dependent load**, not validated instantaneous core cycles or nanoseconds. Hit/miss labels denote working-set candidates supported by timing; no PMU verifies the source of every access.

## Resident candidates

| Group | Tested address spans | Median range across three processes | Primary P05–P95 |
|---|---|---:|---:|
| l1_hit | 8 KiB, 16 KiB | 4.15625 | 4.15625–4.53125 |
| l2_hit | 64 KiB, 128 KiB | 12.14063–12.15625 | 12.14063–12.15625 |
| llc_hit | 4 MiB, 8 MiB | 41.70313–41.73438 | 41.09375–42.32813 |

The alternate footprints and new-seed repeats support three distinct residency timing classes. The LLC distribution is wider than the L1/L2 distributions, while its run medians remain close. No measurements from different processes were pooled into a new distribution.

## First pass and immediate reread

| Pressure group | First-pass median range | Immediate-reread median range | First minus previous resident median |
|---|---:|---:|---:|
| l1_miss / L2 candidate | 12.12500–12.17188 | 4.15625–4.43750 | 7.96875–8.01563 |
| l2_miss / LLC candidate | 41.70313–41.71875 | 4.48438–4.53125 | 29.54688–29.56250 |
| llc_miss / memory candidate | 209.79688–211.00000 | 10.59375–11.59375 | 168.06250–169.26563 |

The paired test traverses the next 256 targets in one random ring, immediately rereads those exact targets, and advances the next sample to the end of the first pass. The full-cycle reuse distance supplies working-set pressure. Targets are not explicitly flushed, and the method does not force a particular hit/miss state for every load.

L1-miss first passes agree with the L2 resident references, and L2-miss first passes agree with the LLC resident references. Their immediate rereads fall near the L1 timing region, with measurable differences between points. For the 256/512 MiB candidates, rereads remain at 10.59–11.59 ticks/load, above the 4.16 L1 reference. These rereads must not be relabeled as pure L1 hits. Translation, conflicts, and surrounding-workload effects have not been separated.

The 256 MiB first-pass primary/repeat medians are 209.79688 and 209.81250; the 512 MiB median is 211.00000. This gives a reasonably repeatable memory-dominated timing region under this method, not a unique pure DRAM latency.

The last table column subtracts the previous level's primary resident median measured in a separate process. It is an **empirical next-level incremental access-cost contrast**, conditional on the intended residency classes. It is not a measured pipeline stall count or a paired difference distribution. The median of actual per-sample FIRST minus REREAD is separately preserved: 7.68750–8.00000 for `l1_miss`, 37.12500–37.18750 for `l2_miss`, and 199.17188–199.37500 for `llc_miss`. See [contrasts.csv](contrasts.csv) for both quantities and the first-slower fractions.

## Method controls and temporal variability

The empty timer has a median of 58 TSC ticks/interval and P05–P95 of 52–75. No fixed timer offset was subtracted. At 1024 dependent loads per batch, L1/L2/LLC medians are 4.03906 / 12.03906 / 41.59375 ticks/load, close to the 256-load values. This supports the three resident regions and shows the smaller per-load contribution of batch-boundary overhead.

Four independent streams yield 1.17188 / 3.28125 / 11.26563 ticks/load at the three resident footprints and 55.65625 at 256 MiB. These are throughput diagnostics and are not substituted for dependent-load latency. Sequential controls yield 4.15625 / 6.53125 / 9.07813 at the three resident footprints and 26.73438 at 256 MiB. They demonstrate access-pattern sensitivity; this experiment does not isolate a unique cause for the differences.

Two calibration points trigger the existing descriptive temporal-ratio flag: `calibration__l1_independent` has ten-block medians from 1.171875 to 1.46484375 (ratio 1.25), and `calibration__timer` ranges from 56 to 75 ticks/interval (ratio 1.33929). No hit or paired first-pass point exceeds the analyzer's 1.2 ratio threshold. This flag is a diagnostic, not a significance test or a sample-rejection rule. The standard flag covers the first column; all reread and signed-difference block medians remain available in [temporal_medians.csv](temporal_medians.csv).

## Placement, preparation, and validation

All configurations used **CPU 32 / NUMA node 0** with complete 2 MiB THP backing before and after timing. CPU 32 and its SMT sibling CPU 8 both measured 0% busy in the one-second preflight; CPU 8 remained at 0% recorded average busy time during every benchmark subprocess. The existing `schedutil` governor was retained, and the collector recorded frequency settings before and after each point. These observations do not prove exclusivity or isolate frequency and shared-machine effects.

Timed regions contained 41 involuntary context switches in total, with at most 7 at a point, and no minor faults, major faults, or voluntary context switches. All raw samples and outliers remain in the saved arrays and statistics.

Before collection, an untimed 512 MiB allocation failed complete THP collapse. A subsequent process-local 2 GiB preparation allocation also had only partial THP backing and was released. All five following 512 MiB allocations passed complete THP and local-NUMA checks. These were allocation diagnostics, not formal latency samples. No system VM/THP setting or global cache-drop setting was changed, and no silent page-policy fallback was used. The formal run then completed on its first attempt. The failed and successful preparation checks are preserved in the [preparation directory](../../../data/sunbird/latency01/preparation/).

All six existing functional tests passed. Inspection of the actual Sunbird x86 executable verified the expected 16 register-addressed loads per unrolled iteration in both timer loops: one dependent stream or four streams of four loads, with no stack references or calls between timestamps. The checked executable and disassembly hashes match the formal run snapshots; see [assembly validation](../../../data/sunbird/latency01/preparation/assembly-validation.json).

The analyzer reopened all 30 raw archives, checked dimensions and hashes, recomputed every statistic including signed paired differences, verified manifest agreement and source/executable snapshots, and rechecked CPU/NUMA/page evidence. [validation.json](validation.json) reports all seven groups complete and all integrity checks passing. This establishes data integrity and recorded placement, not pure hardware cache states. The nine derived signed-difference rows in `summary.csv` are not additional collected intervals.

Raw payload size is **312,000,000 bytes**, compressed to **25,585,102 bytes**. The paired files preserve interleaved `[first_total, reread_total]` rows and must be decoded as two columns. [run_summary.json](run_summary.json) records group counts, median ranges, event totals, preparation links through the saved run, and provenance checks.

## Capacity evidence and prior specification exposure

This latency execution made no new cache-geometry or hardware-latency specification lookup and used no PMU counters. It used the existing Sunbird configuration, whose hash-checked capacity evidence is preserved as [capacity-inference.json](../../../data/sunbird/latency01/preparation/capacity-inference.json). The selection record also includes saved capacity timing observations for every configured footprint.

During the earlier capacity task, `lscpu` cache specifications had been viewed. That prior exposure remains part of the session, so the overall investigation must not be described as blind to hardware specifications. The generic method diagram's statement about no cache-specification lookup describes the measurement method and this latency execution; it does not erase the earlier exposure.

## Files and reproduction

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [First pass versus reread](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png) / [PDF](figures/method_controls.pdf)
- [Timer overhead](figures/timer_overhead.png), [temporal stability](figures/temporal_stability.png), [method diagram](figures/method.png)
- [Statistics](summary.csv), [contrasts](contrasts.csv), [latency estimates](latency_estimates.json)
- [Validation](validation.json), [quality diagnostics](quality.json), [provenance](provenance.json), [run summary](run_summary.json)
- [Configuration snapshot](../../../data/sunbird/latency01/config.json), [manifest](../../../data/sunbird/latency01/manifest.json), [raw arrays](../../../data/sunbird/latency01/raw/)
- [Preparation, dependency, and capacity-evidence record](../../../data/sunbird/latency01/preparation/preparation-record.json)

The pinned Python environment and local `numactl` from the preceding capacity experiment were reused. From the latency directory:

```bash
export PATH="/home/swu35/ECE592-HW1/timing-only/capacity/.venv/bin:/home/swu35/ECE592-HW1/timing-only/capacity/build/sunbird/deps/usr/bin:$PATH"
python3 scripts/analyze_latency.py --machine sunbird --run-id latency01
```

The executed collection command was `python3 -u scripts/run_latency.py --machine sunbird --run-id latency01`. A future collection must use a new run ID. Existing Artemisia files and the shared measurement source/configurations were preserved.
