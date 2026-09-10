# Artemisia capacity results from two rounds

Round 1 contains 39 configurations and round 2 contains 57, totaling 96 configurations and 96,000,000 timed batches. Round-2 collection took 482.43 seconds, approximately 8 minutes 2 seconds. Both rounds used the same C kernel, CPU 32, NUMA node 1, and -O0 compiler flags. No cache specifications or PMU measurements were consulted.

## Current inferences

The data support three distinguishable data-cache residency plateaus. L1D is approximately 48 KiB and L2 approximately 2 MiB. For LLC, only a broad effective transition region is reported; its exact physical capacity was not uniquely determined.

| Region | New evidence from this round: random chains, TSC ticks/load | Interpretation |
|---|---|---|
| L1D | 44 KiB: 5.2031; two runs at 48 KiB: 5.8828 / 5.7812; 52 KiB: 15.9922 | Approximately 48 KiB; 44–52 KiB is the sampled transition neighborhood |
| L2 | Two runs at 2 MiB: 16.4141 / 16.4375; 2.25 MiB: 34.0312; 4 MiB: 62.7969–62.8906 | Approximately 2 MiB; 2–2.25 MiB brackets the sampled onset of the transition |
| LLC | Compact 8 B layout: two runs at 32 MiB, 60.7734 / 64.6094; 40 MiB, 68.8125; 48 MiB, 111.2734 / 133.8438; 64 MiB, 151.1094 / 152.1875 | A broad transition across the 32–64 MiB region depends on layout, run, and time; physical capacity cannot be determined from it |

These ranges describe empirical sampling regions, not statistical confidence intervals. The LLC interval also does not bound nominal physical capacity. The 8 B and 64 B layouts remain separate curves. Compact layouts offer additional opportunities for spatial reuse, so different latencies beyond a plateau do not directly imply different capacities. Different runs have not been pooled into additional cache levels.

## Controls and interference

Round 2 contains 54 configurations with complete huge-page backing and 3 explicit base-page configurations. All mappings remained local to node 1, and page backing matched the configured policy before and after measurement. Longer-batch controls used 1024 dependent loads: approximately 5.0586 ticks/load at 32 KiB and 16.1895 at 2 MiB, supporting the existence of the low-latency residency regions. Differences in the base-page and layout controls remain visible in their respective figures; they cannot all be attributed to a single factor.

**This round experienced substantial scheduling interference.** Two short prelaunch observations measured CPU 32 busy time at approximately 8.08% and 9.0%; CPU 88 was at 0%. CPU 88's recorded average busy time remained 0% over every benchmark subprocess interval. However, round-2 measurement intervals contained 115,454 involuntary context switches in total, ranging from 0–16,359 per point. Round 1 contained 136 in total, with at most 38 per point. Round 2 also recorded 2 minor faults and 2 voluntary context switches in total, with no major faults. Other benchmark processes were observed on the machine at launch and were not interrupted.

Passing data-integrity checks does not establish the absence of interference. Key L1/L2 run medians and boundary changes remained repeatable, but absolute latencies, distribution tails, and LLC results require caution. For the same 64 B / huge-page layout at the 64 MiB random point, the median changed from 101.0469 in round 1 to 169.6719 in round 2. These experiments cannot uniquely attribute the LLC differences to scheduling, shared-cache contention, or memory layout. All outliers and raw samples have been retained.

## Files and next steps

- [Boundary zoom plots](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf)
- [Boundary box plots](figures/boundary_boxplots.pdf)
- [Full capacity curve for the primary layout](figures/capacity_s64_b256_huge.png)
- [Layout comparison](figures/layout_comparison_b256_huge.png)
- [Temporal stability](figures/temporal_stability.pdf)
- [Per-point statistics](summary.csv), [adjacent-point comparisons](transitions.csv)
- [Machine-readable inferences](inference.json), [boundary annotations](boundaries.json)
- [Combined validation record](validation.json), [complete analysis provenance](provenance.json)

The raw directories are `../../../data/artemisia/round1/` and `../../../data/artemisia/round2/`; the round-2 configuration is `../../../configs/artemisia-round2.json`. The two rounds contain 768,000,000 bytes of uncompressed raw arrays, or 137,719,168 bytes after gzip compression. Raw-file hashes and sample counts have been verified, and the analyzer has recomputed the statistics.

Under the current plan, the approximate L1/L2 capacities and LLC uncertainty can be reported now. If narrower L1/L2 boundaries are needed, or confirmation during a period with less scheduling interference is desired, one bounded third round can refine intervals between already measured endpoints, such as 48–52 KiB and 2–2.25 MiB. There is no need to keep adding scans to seek an exact LLC capacity. Round 3 has not been executed.
