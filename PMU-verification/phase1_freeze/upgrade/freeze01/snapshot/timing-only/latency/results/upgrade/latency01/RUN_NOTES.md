# Upgrade latency: complete seven-group run

Run `latency01` completed all **30 configurations in seven groups** in 111.82 seconds (about 1 minute 52 seconds), from 2026-09-10T20:53:22.320478+00:00 to 2026-09-10T20:55:14.145004+00:00. Every configuration contains 1,000,000 batches after warm-up. Nine paired configurations save two intervals per batch, giving **30,000,000 batches and 39,000,000 recorded timer intervals**. All points ran serially in the original order shuffled by `order_seed=59280`, with the configured alternate footprints and second-seed repeats. The formal run completed on its first attempt; no follow-up measurement was added.

Units below are **TSC ticks per dependent load**, not validated core cycles. Intended hit/miss levels are timing-supported candidates; no PMU or cache-geometry query establishes the level serving each individual access.

## Configuration and capacity evidence

The existing `configs/upgrade.json` was used unchanged: CPU 2 / NUMA node 0, 64 B node spacing, 256 dependent loads per ordinary batch, 1024 for the long-batch controls, huge pages, seeds 59221 and 59222. Its selected footprints reference Upgrade's completed capacity runs `round1-retry2` and `round2`; the capacity-inference checksum was verified and the inference file was copied into the raw latency directory.

The seven groups comprise 12 calibration points and three points each for `l1_hit`, `l2_hit`, `llc_hit`, `l1_miss`, `l2_miss` and `llc_miss`. Upgrade's footprints follow its own observed capacity regions rather than Artemisia's footprints. The C source, timer header, collector and common data-handling script match the Artemisia collection snapshots byte for byte. The analyzer matches Artemisia's saved `analysis_source/analyze_latency.py`, including its diagnostic unit-label correction.

## Resident candidates

| Group | Tested address spans | Median range across three processes | Primary P05–P95 |
|---|---|---:|---:|
| l1_hit | 8 KiB, 16 KiB | 3.03125–3.03516 | 2.96484–3.04688 |
| l2_hit | 64 KiB, 128 KiB | 8.84766–8.85547 | 8.65234–9.54688 |
| llc_hit | 1 MiB, 2 MiB | 26.10938–27.44141 | 25.30859–26.99219 |

L1 and L2 medians agree closely across the alternate footprints and new-seed repeats. The LLC primary and repeat at 1 MiB have medians 26.29297 and 26.10938, while the 2 MiB alternate is 27.44141. Retain this footprint dependence and the wider distributions instead of pooling them into one exact LLC latency. The three regions remain distinguishable under this method.

## First pass versus immediate reread

| Pressure group | First-pass median range | Immediate-reread median range | First minus previous resident median |
|---|---:|---:|---:|
| l1_miss | 8.85547–8.86328 | 3.14844–3.28906 | 5.82422–5.83203 |
| l2_miss | 26.19531–27.36719 | 3.29297–3.42578 | 17.34766–18.51953 |
| llc_miss | 204.75781–206.13672 | 8.26562–9.12891 | 178.46484–179.84375 |

Each paired sample times the next batch in a random cycle, immediately rereads exactly the same addresses, then continues at the next batch. Full-cycle reuse distance supplies working-set pressure. This is not a freshly flushed target or a set-selective eviction experiment.

The first passes in the L1-miss/L2 and L2-miss/LLC groups agree with the corresponding resident references at the matching footprints. Their immediate rereads move toward the low-latency region, although they remain slightly above the small resident L1 reference. This is evidence of a strong same-address recency contrast, not proof that every reread is a pure L1 hit.

At 256 MiB, first-pass medians are 204.75781 and 204.82812 for the primary and new-seed repeat. The 512 MiB alternate is 206.13672. Their immediate rereads remain at 8.26562–9.12891, well above the approximately 3.03 L1 resident reference. Conflicts, translation and surrounding-workload effects were not isolated. Report the first passes as memory-dominated candidates, not a unique pure DRAM latency.

The final table column subtracts the separately measured primary previous-level resident median: L1 for `l1_miss`, L2 for `l2_miss`, and LLC for `llc_miss`. It is an empirical next-level access-cost contrast, not a paired distribution or measured pipeline stall count. In contrast, the medians of the actual per-sample FIRST-minus-REREAD distributions are 5.59375–5.79688, 22.79688–23.97266 and 196.48438–197.00391 for the three pressure groups. Both quantities are preserved separately in `contrasts.csv`.

## Method controls and timer overhead

The empty timer has median 34 ticks/interval and P05–P95 32–37. No constant overhead was subtracted. At 1024 dependent loads per batch, the L1/L2/LLC medians are 2.94336 / 8.76465 / 26.12891 ticks/load, close to the ordinary-batch references. These measurements still include the timer and loop instructions.

Four independent streams yield 0.85547 / 2.78516 / 7.25000 ticks/load at the three resident footprints and 56.62891 at 256 MiB. These are throughput diagnostics and are not substituted for dependent-load latency.

Sequential medians are 3.03516 / 4.94531 / 6.64062 at the L1/L2/LLC footprints and 23.35547 at 256 MiB. The large-footprint sequential timing differs greatly from random first-pass timing; it does not establish a comparable memory-access class. The L2 sequential control has P05–P95 4.62891–8.85547 and a 1.7935 ratio between its largest and smallest ten-block medians. It is the only point exceeding the analyzer's descriptive 1.2 temporal-ratio threshold. No resident candidate or miss-group first-pass point exceeds that threshold. This flag is not a significance test or rejection rule.

## Placement, operating conditions and validation

All 30 working mappings had complete 2 MiB THP backing before and after measurement, remained local to node 0, and recorded CPU start/end as 2. All final dependency cursors passed verification. The existing `powersave` governor was retained; there was no frequency/governor change or conversion using nominal GHz. Per-point frequency observations are preserved in the logs.

The runner's one-second preflight recorded 0% busy time on CPU 2 and SMT sibling CPU 8. CPU 8 averaged 0–2.597% busy over individual benchmark subprocess intervals. Another `cache_bench` process was observed on CPU 3 before collection, and that CPU was fully busy during preflight. Other processes were left running. These observations do not establish an isolated cache or memory system.

Measurement intervals recorded 525 involuntary context switches in total, with at most 106 at one point, and zero minor faults, major faults or voluntary switches. All raw samples and outliers remain saved. Box plots omit individual outlier markers only for readability.

The analyzer reopened all 30 archives, verified raw hashes, dimensions and paired-column layout, recomputed statistics and signed differences, checked manifest agreement, verified source/executable/environment snapshots, and rechecked CPU/NUMA/page evidence. `validation.json` reports all seven groups complete and passes integrity checks. This does not certify pure cache states or absence of interference.

Six existing functional tests passed on Upgrade. Disassembly of both x86 timed loops contains 16 register-addressed loads and no stack references between timestamps. The executable used for formal collection matches the assembly-checked executable by SHA-256. No additional AArch64 execution or cross-compilation is claimed for this x86-64 run.

## Local preparation

The pinned NumPy 1.26.3 / Matplotlib 3.9.4 environment and locally extracted numactl were reused from `../capacity/.venv`. No system package installation was required. A page-only preflight for the largest 512 MiB footprint initially obtained only 232 MiB of huge-page coverage. After allocating, touching and releasing a bounded 1 GiB anonymous base-page scratch mapping, a second page-only attempt obtained all 512 MiB. Both attempts are recorded in `page-preflight.json`; neither collected latency samples. The unchanged formal benchmark subsequently completed with full backing at every point. No page-policy fallback or system tuning occurred.

## Saved artifacts

- [Resident distributions](figures/resident_distributions.png) / [PDF](figures/resident_distributions.pdf)
- [First pass versus reread](figures/first_and_reread.png) / [PDF](figures/first_and_reread.pdf)
- [Method controls](figures/method_controls.png), [timer overhead](figures/timer_overhead.png), [temporal stability](figures/temporal_stability.png)
- [Access-method diagram](figures/method.png) / [PDF](figures/method.pdf)
- [Statistics](summary.csv), [contrasts](contrasts.csv), [machine-readable estimates](latency_estimates.json)
- [Validation](validation.json), [quality diagnostics](quality.json), [implementation checks](implementation_checks.json), [provenance](provenance.json)
- [Recorded configuration](../../../data/upgrade/latency01/config.json), [manifest](../../../data/upgrade/latency01/manifest.json), [raw arrays](../../../data/upgrade/latency01/raw/)
- [Capacity evidence snapshot](../../../data/upgrade/latency01/capacity_inference.json), [page preparation](../../../data/upgrade/latency01/page-preflight.json)

Raw payload totals 312,000,000 bytes; gzip archives total 52,040,423 bytes. The raw directory also preserves the exact source, binary, disassembly, build/test logs, commands, console output, dependency versions and prelaunch observations. `analysis_source/` preserves the scripts used to generate these results. Derived signed-difference rows in `summary.csv` do not represent additional collected samples.
