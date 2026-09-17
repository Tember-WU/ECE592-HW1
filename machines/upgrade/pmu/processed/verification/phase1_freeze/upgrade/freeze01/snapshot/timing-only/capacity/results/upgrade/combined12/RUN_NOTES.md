# Upgrade capacity results from two rounds

Two sequential rounds are complete: `round1-retry2` has 39 configurations and `round2` has 57, totaling **96 configurations and 96,000,000 timed batches**. Collection took 152.95 and 120.17 seconds respectively, or 273.11 seconds in total, excluding preparation, failed attempts and analysis. Each point preserves 1,000,000 batches and all outliers.

Both rounds ran on `upgrade.ece.ncsu.edu`, CPU 2 / NUMA node 0, with the original dependent-load kernel compiled at `-O0`. The C kernel and collection, planning and analysis scripts are byte-identical to the Artemisia round-2 source snapshots. The machine configuration and second-round intervals were chosen for Upgrade. No cache geometry, vendor cache capacity or PMU measurements were consulted. The timer reports **TSC ticks per dependent load**, not validated core cycles.

## Timing-only inferences

The measurements support three distinguishable data-cache residency regions before the memory-access region. Approximate L1D capacity is **32 KiB**, and approximate L2 capacity is **256 KiB**. The LLC result is an **effective transition between sampled 7 and 8 MiB points** under these operating conditions; nominal physical LLC capacity is not uniquely determined.

| Region | Evidence: random chains, TSC ticks/load | Interpretation |
|---|---|---|
| L1D | Round-2 medians at 32 KiB: 3.2500 / 3.2578; round 1: 3.3398. At 36 KiB: 8.8242, with Q1–Q3 8.7969–9.0000. | Approximately 32 KiB; sampled transition bracket 32–36 KiB. |
| L2 | Round-2 medians at 256 KiB: 8.9414 / 8.9453; round 1: 8.9336. At 288 KiB: 14.5547, with Q1–Q3 14.0977–15.0352. | Approximately 256 KiB; sampled onset bracket 256–288 KiB. |
| LLC effective transition | Primary 64 B layout: 7 MiB 28.4648; 8 MiB 114.1016, versus round-1 114.5898. Compact 8 B layout: 7 MiB 28.8867; 8 MiB repeat medians 55.7617 / 57.3242. | A reproducible large rise between 7 and 8 MiB, with layout-dependent miss-region latency. No exact physical capacity estimate. |

These are empirical sampling brackets, not statistical confidence intervals or bounds on vendor specifications. The 64 B and 8 B spacing curves stay separate. A compact pointer layout changes spatial reuse and therefore can change miss-region timing without implying another capacity or cache level.

The coarse sweep covers 2 KiB–512 MiB. After the third residency region near 26–28 ticks/load, random medians reach 178.7109 at 16 MiB, 194.9023 at 32 MiB and 205.7109 at 512 MiB. This supports interpreting the later region as memory access; its gradual slope is not counted as additional cache levels.

## Controls and measurement quality

The two longer-batch controls yield 3.2158 ticks/load at 32 KiB and 8.9062 at 256 KiB, supporting the two low-latency residency regions. Compact-layout controls also distinguish the smaller and larger working sets, while sequential controls have different latency because of their access pattern.

All 93 huge-page configurations and 3 base-page configurations matched their page policy before and after measurement. All mappings remained local to node 0, and every recorded CPU start/end value was 2. Raw checksums, positive sample intervals, sample counts, saved/recomputed statistics, configuration/manifest membership and source/executable provenance passed validation. The existing 10 tests passed before collection.

| Operating-condition metric | Round 1 (`round1-retry2`) | Round 2 |
|---|---:|---:|
| Involuntary context switches, total | 276 | 205 |
| Maximum at a single point | 35 | 23 |
| Minor / major faults during measurement | 0 / 0 | 0 / 0 |
| Voluntary context switches during measurement | 0 | 0 |
| SMT sibling CPU 8 average busy range per subprocess | 0–3.98% | 0–6.897% |

Another `cache_bench` process was observed on CPU 0 before both rounds. It was left running. Passing validation does not establish an isolated machine. Shared-cache contention, scheduling and layout are possible influences that these controls do not uniquely separate.

The primary-layout 8 MiB medians agree closely across the two rounds, at 114.5898 and 114.1016. The more pronounced variability is in layout comparisons and some individual time blocks: for example, the compact 4 MiB repeats have overall medians 27.6133 and 29.2266, while the latter includes ten-block medians up to 38.4063. At 8 MiB, base pages give 133.9141 compared with 114.1016 for huge pages. These differences are visible in the layout, page-policy and temporal figures and do not isolate a unique cause.

## Failed attempts and local preparation

The original `round1` and `round1-retry1` attempts each stopped after four points because the 512 MiB random configuration could not obtain complete huge-page backing. Their manifests, partial raw data, logs and failure explanations are preserved under `data/upgrade/`. They are excluded from the valid 96 configurations and combined analysis.

A page-only diagnostic obtained 492 MiB huge-page coverage in a 512 MiB scratch mapping. After allocating, touching and releasing a bounded 1 GiB anonymous base-page scratch mapping, a new full sweep (`round1-retry2`) completed under the unchanged page checks. There was no silent page fallback, sample reduction or system-setting change. Preparation records are in the successful first-round raw directory; the original prelaunch observation is explicitly named `preflight-before-initial-attempt.json`.

Dependencies were installed locally under `.venv`, including the exact NumPy/Matplotlib versions in `requirements.txt`; `numactl` was extracted from the Ubuntu package under `.venv/native/root`. Python package lists are preserved per run. See the [experiment entry point](../README.md) for analysis and audit commands.

## Artifacts and scope

- [Boundary zoom](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf)
- [Boundary distributions](figures/boundary_boxplots.pdf)
- [Full primary capacity curve](figures/capacity_s64_b256_huge.png)
- [Layout comparison](figures/layout_comparison_b256_huge.png), [temporal stability](figures/temporal_stability.pdf)
- [Statistics](summary.csv), [transitions](transitions.csv), [validation](validation.json), [provenance](provenance.json)
- [Machine-readable inferences](inference.json), [boundary annotations](boundaries.json)
- Raw inputs: [first round](../../../data/upgrade/round1-retry2/) and [second round](../../../data/upgrade/round2/)

The valid raw arrays total 768,000,000 uncompressed bytes and 141,864,778 gzip-compressed bytes. Source snapshots, executables, disassembly, build/test/measurement logs, environment records and all raw samples are preserved.

The requested two-round experiment is complete. These data support approximate L1/L2 capacities and a bounded LLC effective transition. A third round was not run. Narrower L1/L2 brackets, or an isolated-machine confirmation of LLC behavior, would require further measurements; no automatic additional scan is part of this result.
