# Charnwood latency: complete seven-group run

**Use `latency03` for the formal results.** It completed all 30 configurations across seven groups in 169.005 seconds (about 2 minutes 49 seconds), from 2026-09-10T20:57:36.058712+00:00 to 2026-09-10T21:00:25.063700+00:00. Every configuration retained 1,000,000 batches after warm-up. Nine paired configurations record FIRST and REREAD separately, giving **39,000,000 recorded timer intervals** from 30,000,000 batches. All points ran serially in the original fixed-seed shuffled order.

The run includes 12 calibration configurations and three configurations in each of `l1_hit`, `l2_hit`, `llc_hit`, `l1_miss`, `l2_miss`, and `llc_miss`. The existing Charnwood configuration was used unchanged. Its capacity-inference hash was verified against the preceding two-round Charnwood capacity results. The benchmark and timing header match Artemisia's saved C source.

All latency values below are **TSC ticks per dependent load**, not validated core cycles. Cache-state labels identify timing-supported candidates; no performance counter verified the serving level of every access.

## Resident candidates

| Group | Tested address spans | Median range across three processes | Primary P05–P95 |
|---|---|---:|---:|
| l1_hit | 8 KiB, 16 KiB | 5.28125 | 5.26563–5.30469 |
| l2_hit | 64 KiB, 128 KiB | 15.39844–15.40625 | 15.35938–16.25000 |
| llc_hit | 1 MiB, 2 MiB | 43.39844–45.42969 | 42.14844–44.63281 |

L1 and L2 agree closely across the alternate footprints and second-seed repeats. The LLC reference is broader: the two 1 MiB medians are 43.51563 and 43.39844, while 2 MiB is 45.42969. These observations support three distinct residency timing regions, while retaining the footprint-dependent LLC range.

## First pass versus immediate reread

| Pressure group | First-pass median range | Immediate-reread median range | First minus previous resident median |
|---|---:|---:|---:|
| l1_miss | 15.40625–15.42188 | 5.28906–5.65625 | 10.12500–10.14063 |
| l2_miss | 43.42969–45.42969 | 5.84375–5.96094 | 28.03125–30.03125 |
| llc_miss | 307.67969–312.08594 | 22.84375–25.09375 | 264.16406–268.57031 |

Each paired sample times the next 256 dependent loads in a random ring, resets to the saved cursor, times those same addresses again, then advances to the next batch. Full-cycle reuse distance provides working-set pressure. There is no per-sample cache flush or set-selective eviction, so FIRST is not guaranteed to be a particular cache miss on every load.

L1-miss/L2 first passes agree with the 64/128 KiB resident measurements. The 64 KiB rereads return near the 5.28125 L1 reference; the 128 KiB reread median is slightly higher at 5.65625. L2-miss/LLC first passes also track the matching 1/2 MiB resident references, while their rereads remain around 5.84–5.96 rather than exactly matching L1. These provide clear same-address recency contrasts without establishing pure reread hit classes.

For the large-footprint candidates, the 256 MiB primary/repeat medians are 307.67969 / 309.26563, and 512 MiB is 312.08594. Their rereads remain much slower than the L1 reference. Translation, conflicts, and surrounding-workload effects were not isolated; neither column establishes a unique pure DRAM or L1 latency. The FIRST-slower fraction exceeds 99.95% for all nine paired configurations, but this is an ordering diagnostic, not a measured cache-miss rate.

The last table column subtracts the separately measured primary previous-level resident median. It is an **empirical next-level access-cost contrast**, not a paired penalty distribution or pipeline stall count. The signed per-sample FIRST-minus-REREAD distributions are separately retained in `summary.csv` and `contrasts.csv`; they measure the immediate-reread benefit.

## Method controls and timer overhead

The empty timer median is 60 ticks/interval, with P05–P95 of 56–64. Timer overhead was not subtracted from individual samples. The 1024-load L1/L2/LLC controls give 5.11719 / 15.25000 / 43.29297 ticks/load, close to their 256-load resident references and consistent with lower per-load boundary overhead. The timed intervals retain the original timer and loop instructions.

Four independent streams give 1.48438 / 4.79688 / 12.16406 ticks/load at the three resident footprints and 93.36719 at 256 MiB. These are throughput diagnostics, not dependent-load latency estimates.

Sequential medians are 5.28125 / 8.59375 / 11.46875 at the three resident footprints and 35.08594 at 256 MiB. Their faster results above L1 demonstrate the importance of access order and retain a control for prefetch/spatial effects; they are not substituted for the random-chain latency results.

## Allocation attempts and runtime environment

The first two complete-plan attempts, `latency01` and `latency02`, each stopped after 11 configurations when the 512 MiB point failed to obtain full THP backing. Their partial data and failure logs are preserved but excluded from this analysis. A separate 16-sample allocation diagnostic succeeded between those attempts and is also excluded.

The successful `latency03` used `MALLOC_TRIM_THRESHOLD_=0` and `MALLOC_MMAP_THRESHOLD_=131072` to encourage release of large temporary allocations. These environment settings were inherited by the collector and benchmark subprocesses and apply to allocation outside the timed loops. The C source, measurement configuration, shuffled point order, and huge-page policy were unchanged. No global memory or governor settings were changed. Success followed this adjustment, but the exact failure cause and the adjustment's individual effect were not isolated. The allocator environment differs from the default earlier attempts and is preserved in the raw run's [launch context](../../../data/charnwood/latency03/launch-context.json).

All formal points ran on CPU 3 with memory local to NUMA node 0 and full 2 MiB THP backing before and after timing. The existing `powersave` governor was retained, with configured bounds of 800 MHz–4 GHz; this is not a statement of instantaneous clock rate. Per-point before/after frequency observations are retained in the logs. No nominal-frequency conversion was applied to the timer ticks.

The collector's one-second preflight found CPU 3 2.941% busy and its SMT sibling CPU 7 1.98% busy. Another user's benchmark was active on CPU 6. During formal subprocesses, CPU 7's average busy percentage ranged from 0–18.082%; the maximum occurred during the 256 MiB primary paired point. These observations do not prove CPU or shared-resource exclusivity.

The timed sampling loops recorded 917 involuntary context switches in total, at most 170 per configuration, and zero minor faults, major faults, or voluntary switches. No FIRST-column point exceeded the descriptive 1.2 ratio between its ten temporal medians. Variation still exists below that threshold: the 256 MiB primary first-pass block medians span approximately 282.97–309.33. The drift flag is neither a significance test nor a criterion for dropping samples.

## Validation and saved evidence

Six existing functional tests passed. Assembly inspection confirmed 16 register-addressed loads and zero stack references between timestamps in both x86 timed loops, with one dependent cursor or four independent cursors as intended. Each formal point also verified final cursor progression.

The analyzer reopened all 30 archives, checked raw hashes and dimensions, recomputed all column statistics and signed paired differences, verified manifest agreement and code/executable snapshots, and rechecked CPU/NUMA/page logs. `validation.json` passes all these integrity checks and confirms all seven groups. This is not proof of pure cache states or absence of interference. No raw sample or outlier was removed. The analyzer versions actually used are preserved under `analysis_source/`.

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [First pass versus reread](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png), [timer overhead](figures/timer_overhead.png), [temporal stability](figures/temporal_stability.png), [method diagram](figures/method.png)
- [Full statistics](summary.csv), [paired and next-level contrasts](contrasts.csv), [latency estimates](latency_estimates.json)
- [Integrity validation](validation.json), [quality diagnostics](quality.json), [runtime summary](runtime_summary.json), [implementation checks](implementation_checks.json), [analysis provenance](provenance.json)
- [Recorded configuration](../../../data/charnwood/latency03/config.json), [manifest](../../../data/charnwood/latency03/manifest.json), [raw archives](../../../data/charnwood/latency03/raw/), [collector log](../../../data/charnwood/latency03/collector.log)
- [Preparation and reproduction commands](../preparation/README.md), [latency01 failure record](../latency01/RUN_NOTES.md), [latency02 failure record](../latency02/RUN_NOTES.md)

The formal raw payload contains 312,000,000 bytes, compressed to 51,639,665 bytes. `summary.csv` contains 48 rows, including nine derived difference distributions; those derived rows are not extra collected samples. The requested seven-group experiment is complete; no further measurement is required to report the observed ranges and qualifications above.
