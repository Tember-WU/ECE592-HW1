# Ookay latency: completed seven-group experiment

Run **`latency01-retry2` completed all seven groups and 30 configurations** in 120.22 seconds, from 2026-09-10T20:56:23.145495+00:00 to 2026-09-10T20:58:23.367023+00:00. Each configuration contains 1,000,000 batches after warm-up. Nine paired configurations save two timer intervals per batch, giving **30,000,000 batches and 39,000,000 recorded timer intervals**. The original `order_seed=59280` shuffles the point order once; all points ran serially in separate processes, with the configured alternate footprints and second-seed repeats.

The completed run uses the existing Ookay configuration unchanged: CPU 2 / NUMA node 0, 64 B spacing, 256 loads per ordinary batch, 1024 loads for the three long-batch controls, and complete 2 MiB transparent-huge-page backing. The C source, timer header, collector, helper, compiler flags, and pinned dependencies match the Artemisia collection snapshot; the analyzer matches the version used for Artemisia's published analysis. The footprint choices use Ookay's saved capacity results, whose inference hash was checked and whose input was copied to [capacity_basis_inference.json](../../../data/ookay/capacity_basis_inference.json). Cache specifications and PMU counters were not consulted.

The two incomplete attempts and allocation preparation are documented below. Their samples are excluded from this completed run's results.

## Resident candidates

Units are **TSC ticks per dependent load**, not validated core cycles. These labels describe timing-supported residency candidates, not verified hit/miss states for every access.

| Group | Configurations | Address spans | Median range across three processes | Primary P05–P95 |
|---|---:|---|---:|---:|
| `l1_hit` | 3 | 8 KiB, 16 KiB | 3.67188 | 3.66406–3.68750 |
| `l2_hit` | 3 | 64 KiB, 128 KiB | 10.71094–10.71875 | 10.68750–11.51562 |
| `llc_hit` | 3 | 1 MiB, 2 MiB | 30.88281–32.39062 | 29.98438–31.91406 |

The L1 and L2 medians agree closely across the alternate footprint and new-seed repeat. The 1 MiB LLC primary/repeat medians are 30.97656/30.88281; the 2 MiB alternate is somewhat higher at 32.39062. This supports a distinct third residency timing region while preserving footprint-dependent variation. The three processes remain separate distributions.

The footprints lie within the regions identified by Ookay's earlier capacity study: L1D approximately 32 KiB, L2 approximately 256 KiB, and the broad LLC transition above the lower-latency 1–2 MiB region. The capacity experiment supplies footprint-selection evidence; it does not determine these newly measured latency values.

## First pass, immediate reread, and next-level contrasts

| Pressure group | Configurations | Address spans | First-pass median range | Immediate-reread median range | First minus previous resident median |
|---|---:|---|---:|---:|---:|
| `l1_miss` | 3 | 64 KiB, 128 KiB | 10.71875–10.72656 | 3.67969–3.94531 | 7.04688–7.05469 |
| `l2_miss` | 3 | 1 MiB, 2 MiB | 30.90625–32.38281 | 3.96094–4.14844 | 20.19531–21.67188 |
| `llc_miss` | 3 | 256 MiB, 512 MiB | 232.73438–234.28125 | 10.00781–11.00000 | 201.75781–203.30469 |

The paired method times the next 256 dependent loads in a large random cycle, resets to the same starting cursor, immediately times those same loads again, then advances to the next batch. Full-cycle reuse distance provides working-set pressure. There is no fresh target flush or set-selective eviction before each sample.

L1-miss/L2-candidate and L2-miss/LLC-candidate first passes agree closely with the corresponding resident reference at the same footprint. At 64 KiB, immediate rereads return near the 3.67188 L1 reference. At 128 KiB and 1–2 MiB, rereads remain slightly above that reference, so they are not described as a perfectly pure L1-hit class. The first pass is slower in approximately 99.964–99.973% of samples in these six paired configurations; signed negative differences are retained.

At 256/512 MiB, first-pass medians are 232.73438–234.28125, while rereads remain at 10.00781–11.00000, well above the L1 reference. This provides a strong same-address recency contrast without identifying a unique pure DRAM latency or the exact serving level of the reread. Translation, conflicts, shared workloads, and surrounding-workload effects were not independently isolated. All three memory-candidate points have a first-slower fraction of 1.0 in the recorded samples.

The last table column subtracts a **separately measured primary previous-level resident median**. It is an empirical next-level incremental access-cost contrast, conditional on the intended residency classes. It is not a measured pipeline stall count or a paired penalty distribution. The actual paired difference is calculated sample by sample and saved separately in [contrasts.csv](contrasts.csv). For example, the primary L2-miss point has a first-minus-L2-reference difference of medians of 20.21875, whereas its median paired first-minus-reread benefit is 26.85938. These quantities answer different questions.

## Calibration and method controls

The `calibration` group completed all 12 configurations. The empty timer median is **42 ticks per interval**, with P05–P95 of 40–44. No fixed timer minimum was subtracted from individual measurements.

At 1024 loads per batch, L1/L2/LLC medians are 3.55859 / 10.60547 / 30.81836 ticks per dependent load. Their proximity to the ordinary-batch values supports the measured residency regions; the slightly lower per-load values are consistent with amortizing timer and loop-boundary overhead. The result still includes those instructions.

Four independent streams produce approximately 1.03906 / 2.96875 / 8.57812 ticks per load at the three resident footprints and 63.38281 at 256 MiB. These values are **throughput diagnostics**, not dependent-load latency estimates. Sequential controls give 3.67188 / 5.96094 / 7.98438 at the resident footprints, and 26.41406 at 256 MiB, with P05–P95 of 23.04688–32.19531 at that large footprint. These controls show strong access-pattern sensitivity; they are not substituted for the random dependent measurements.

## Placement, runtime conditions, and validation

All 30 configurations retained CPU 2 and local NUMA-node-0 placement. Every working mapping had complete huge-page coverage before and after timing. The existing `powersave` governor was retained, and per-point before/after frequency snapshots are recorded. Those snapshots do not establish an instantaneous frequency throughout the timed interval, and no nominal-GHz conversion was applied.

The successful run's one-second preflight recorded 0% busy time on CPU 2 and SMT sibling CPU 6, while CPU 0 was at 100%. A separate benchmark had been observed on CPU 0 during preparation. CPU 6's recorded average busy time over individual benchmark subprocesses ranged from 0 to 0.099%. These observations do not establish exclusive access to shared caches or memory bandwidth.

Measured loops recorded **32 involuntary context switches in total**, at most 6 per configuration, and zero minor faults, major faults, or voluntary switches. No first-pass point exceeded the analyzer's descriptive 1.2 ratio between its ten temporal medians. This is a drift diagnostic, not a significance test or a guarantee of constant latency. All raw samples and outliers were retained.

The analyzer reopened all 30 raw archives, checked hashes and dimensions, recomputed single-column and paired-column statistics and signed differences, verified manifest agreement and source/executable snapshots, and rechecked page and CPU/NUMA logs. [validation.json](validation.json) passes all integrity checks; its scope does not certify pure cache states or freedom from interference.

All six original functional tests passed. Local disassembly inspection verified 16 mutually dependent loads in the dependent loop and four groups of four loads in the independent-stream loop, with the expected x86 timestamp/fence sequence and no stack references or calls between timestamps. The inspected binary and disassembly hashes match the actual successful collection artifacts. See [assembly-verification.json](../../../data/ookay/assembly-verification.json) and the [saved disassembly](../../../data/ookay/latency01-retry2/disassembly.txt).

## Allocation failures and recorded recovery

`latency01` and `latency01-retry1` each completed six configurations, then stopped at the 256 MiB sequential control because `MADV_COLLAPSE` returned `Cannot allocate memory`. Both failed directories, all completed samples, and failure logs remain intact. Each incomplete attempt contains 6,000,000 batches and 8,000,000 timer intervals. The combined 16,000,000 intervals from these attempts are excluded from every formal statistic and figure here.

A non-timed 512 MiB diagnostic initially obtained only 274,726,912 bytes of huge-page backing, with no additional coverage after three collapse calls. In a subsequent bounded preparation step, a temporary 1 GiB base-page mapping was touched and released. A newly allocated 512 MiB verification mapping then obtained complete huge-page backing on first touch; that mapping was also released before formal collection began. Peak simultaneously mapped diagnostic allocation was 1 GiB. The full original seven-group plan was then restarted under `latency01-retry2` and completed without changing its source, configuration, point order, or page policy.

These preparations may change reclaimable-memory state, and are recorded as part of the run conditions. They did not modify global VM settings or stop any other process. The underlying allocation failure was not isolated as a single cause. Diagnostic and preparation operations are not formal latency samples. See [recovery.json](../../../data/ookay/recovery.json), [allocation diagnostic](../../../data/ookay/thp-allocation-diagnostic.json), and [allocation preparation](../../../data/ookay/thp-allocation-preparation.json).

## Saved artifacts

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [First pass versus reread](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png), [timer overhead](figures/timer_overhead.png), [temporal stability](figures/temporal_stability.png)
- [Access-method diagram](figures/method.png), [full statistics](summary.csv), [contrasts](contrasts.csv), [machine-readable estimates](latency_estimates.json)
- [Integrity validation](validation.json), [quality diagnostics](quality.json), [analysis provenance](provenance.json)
- [Recorded configuration](../../../data/ookay/latency01-retry2/config.json), [manifest](../../../data/ookay/latency01-retry2/manifest.json), [raw arrays](../../../data/ookay/latency01-retry2/raw/), [preparation record](../../../data/ookay/preparation.json)

The successful run contains 312,000,000 uncompressed raw bytes, compressed to 47,745,721 bytes. Paired files contain interleaved `[first, reread]` uint64 rows. `summary.csv` has 48 statistical rows, including nine derived signed-difference distributions; derived rows are not additional collected intervals. No extra follow-up group was collected after the complete seven-group run.
