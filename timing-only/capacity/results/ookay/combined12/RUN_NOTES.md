# Ookay cache levels and capacity: completed two-round experiment

The two completed rounds contain **96 configurations and 96,000,000 timed batches**. The coarse round, `round1-retry1`, contains 39 configurations and took 169.39 seconds. Round 2 contains 57 configurations and took 172.56 seconds. They were collected serially on 2026-09-10 using CPU 2 / NUMA node 0, the unchanged Artemisia C kernel and timing method, and `-O0` compiler flags. Second-round intervals were selected from Ookay's new first-round curve. Cache specifications and PMU counters were not used.

## Inferences from the two rounds

The data support **three distinguishable data-cache residency plateaus**, with approximate capacities of **32 KiB for L1D** and **256 KiB for L2**. For LLC, the data show an effective transition across approximately **5–8 MiB**; they do not uniquely determine nominal physical capacity.

| Region | Random-chain evidence, TSC ticks per dependent load | Interpretation |
|---|---|---|
| L1D | 16 KiB: 3.6719; second-round 32 KiB repeats: 3.9062 / 4.0000; 36 KiB: 10.6719 | Approximately 32 KiB; sampled onset bracket 32–36 KiB |
| L2 | Second-round 256 KiB repeats: 10.9219 / 10.8828; 288 KiB: 17.4062; 320 KiB: 23.2266 | Approximately 256 KiB; sampled onset bracket 256–288 KiB |
| LLC effective transition | Primary layout: 5 MiB: 33.1797; 6 MiB: 36.7422; 7 MiB: 113.3359; 8 MiB: 170.5859 | The previous plateau persists through 5 MiB, begins rising at 6 MiB, and gives way to much slower access at 7–8 MiB |

The 64 B / huge-page curve has residency plateaus near 3.7, 10.7, and 31–33 ticks/load, followed by large-footprint latencies around 216–236 ticks/load. The initial coarse LLC refinement interval was 4–8 MiB. The denser second round supports describing the effective change from the plateau at 5 MiB through 8 MiB. This empirical transition region does not bound nominal physical LLC capacity. None of the reported intervals is a statistical confidence interval, and TSC ticks are not treated as validated core cycles.

L1/L2 boundary distributions are clearly separated: at 32 KiB, the two second-round interquartile ranges are 3.8750–3.9453 and 3.9141–4.0469, compared with 10.6484–10.7031 at 36 KiB. At 256 KiB, the two ranges are 10.8125–11.1875 and 10.7891–11.1719, compared with 16.8672–18.0391 at 288 KiB. New-seed runs at 48/64 KiB and 384/512 KiB support the higher-latency side of the corresponding boundaries. The 1024-load controls give medians of 3.8945 at 32 KiB and 10.8359 at 256 KiB, consistent with the respective low-latency regions.

## Layout, page, and temporal controls

The LLC result depends on layout. At 4 MiB, compact 8 B-layout repeat medians are 32.2891 / 32.3125; at 6 MiB they are 36.2266 / 36.1328; at 8 MiB they are 87.9375 / 87.9453. The primary 64 B-layout 8 MiB medians are 170.6758 in round 1 and 170.5859 in round 2. Compact layouts permit more spatial reuse, so a different median beyond a plateau is not itself evidence of a different cache capacity. All layouts, page policies, and batch lengths remain separate analysis groups.

Base-page medians at 4, 6, and 8 MiB are 44.9453, 80.6641, and 188.0781, compared with huge-page primary-layout medians of 33.0078, 36.7422, and 170.5859. These controls establish page-policy sensitivity; they do not isolate its cause. Sequential access also remains faster than random access above the small-cache boundaries and is plotted separately.

LLC distributions have broad tails and temporal variation. For example, the ten consecutive block medians at the 7 MiB primary-layout point range from 99.0703 to 217.2344. The 4 MiB base-page point ranges from 44.3203 to 159.3359. Those blocks are consecutive observations within one run, not independent experimental repeats. All samples, including outliers, were retained.

## Integrity and shared-machine conditions

The [combined validation record](validation.json) and per-round records verify completion, all raw sample counts and SHA-256 hashes, CPU binding, page backing, and local NUMA placement. The analyzer recomputed statistics from raw data and accepted both runs as compatible in CPU/NUMA binding, C source, timing method, compiler flags, processor model, kernel, and base-page size. Both runs also used identical binary hashes. The study contains 93 configurations with fully verified huge-page mappings and 3 explicit base-page configurations. Raw arrays total 768,000,000 bytes, or 139,857,274 bytes after gzip compression.

There were no minor faults, major faults, or voluntary context switches during either completed round's measurement intervals. Involuntary switches totaled 42 in round 1 and 45 in round 2, with at most 5 at any one configuration. Recorded SMT-sibling busy percentages ranged from 0 to 3.333% in round 1 and 0 to 2.222% in round 2. Other timing benchmarks were observed on CPUs 0 and 4 before both rounds. A mostly idle selected core does not establish exclusive access to the shared cache or memory system. Scheduling, shared workloads, address layout, and translation effects were not independently isolated; none is claimed as the sole cause of LLC behavior.

## Preserved failed attempt

The initial attempt named `round1` stopped after four completed configurations when a 512 MiB mapping failed `MADV_COLLAPSE` with `Cannot allocate memory`. Its data and logs remain in [data/ookay/round1](../../../data/ookay/round1/). The full unchanged protocol was restarted as `round1-retry1`, which completed. The failed attempt's four million timed batches are excluded from all counts and figures in this combined study. No samples were resumed or pooled from that attempt, and no page-policy fallback or system setting change was made. See the [recovery record](../../../data/ookay/recovery.json).

## Artifacts

- [Boundary zoom](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf), [boundary box plots](figures/boundary_boxplots.pdf)
- [Full primary capacity curve](figures/capacity_s64_b256_huge.png), [layout comparison](figures/layout_comparison_b256_huge.png), [temporal stability](figures/temporal_stability.pdf)
- [Summary](summary.csv), [adjacent comparisons](transitions.csv), [temporal medians](temporal_medians.csv)
- [Machine-readable inferences](inference.json), [boundary annotations](boundaries.json), [validation](validation.json), [analysis provenance](provenance.json)
- First-round [notes](../round1-retry1/RUN_NOTES.md) and [raw data](../../../data/ookay/round1-retry1/); second-round [notes](../round2/RUN_NOTES.md) and [raw data](../../../data/ookay/round2/)

The requested two rounds are complete. The approximate L1/L2 estimates and stated LLC uncertainty can be reported under this protocol. No third round was run; a tighter L1/L2 sampling bracket would require a separately selected refinement round.
