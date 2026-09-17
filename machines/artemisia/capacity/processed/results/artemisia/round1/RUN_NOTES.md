# Artemisia round-1 coarse-scan record

Run ID: `round1`. Started: 2026-09-10T14:56:11.564043+00:00; finished: 2026-09-10T15:01:43.586476+00:00. Collection took 332.0 seconds.

This round completed 39/39 configurations: random and sequential chains at each of 19 powers-of-two working-set sizes, plus an empty-timer control. Each point retained 1,000,000 batches, for a total of 39,000,000 batches.

Measurements used CPU 32 / NUMA node 1, 64 B node spacing, 256 dependent loads per batch, and complete transparent-huge-page backing. The benchmark was compiled with -O0. Per-point configurations, commands, C source, executable, and disassembly are preserved in the raw run directory.

## Preliminary observations and follow-up point selection

The following refinement intervals were selected from this round's new data. They are neither exact capacity conclusions nor statistical confidence intervals. The three low-latency plateaus support further examination of L1D, L2, and LLC. Continued slowing at large working sets is not, by itself, evidence of additional cache levels.

| Candidate region | Lower endpoint: random-chain median | Upper endpoint: random-chain median | Candidate interval for the next round |
|---|---:|---:|---|
| L1D | 32 KiB: 5.1875 | 64 KiB: 16.1172 | 32 KiB–64 KiB |
| L2 | 2 MiB: 16.4141 | 4 MiB: 62.9141 | 2 MiB–4 MiB |
| LLC effective transition | 32 MiB: 62.9297 | 64 MiB: 101.0469 | 32 MiB–64 MiB |

Latency values in the table are TSC ticks / dependent load. The empty-timer median is 50 ticks/interval. Sequential-access distributions above 64 MiB are broad and should be interpreted alongside the random-access controls and per-point box plots. The next round needs only bounded LLC refinement and layout/base-page controls; the exact physical LLC capacity has not been uniquely determined.

## Data and environment checks

- The analyzer verified sample counts, positive timing intervals, and SHA-256 checksums for all 39 raw files. All statistics were recomputed from raw data.
- CPU binding remained at CPU 32 before and after every measurement. Every mapping was fully backed by huge pages and located on NUMA node 1.
- CPU 88's recorded average busy percentage was 0% over every benchmark subprocess interval. There were no minor/major faults or voluntary context switches during measurement. Involuntary context switches ranged from 0–38 per point, totaling 136.
- Another benchmark process was observed on CPU 4 before collection and was not stopped. CPU 32/88 had 0% busy time in the short prelaunch observation, but this does not establish that the entire shared machine was free of interference.
- Huge-page verification uses the byte coverage reported by AnonHugePages. A KernelPageSize value of 4 kB in smaps does not by itself indicate transparent-huge-page fallback.
- The raw uint64 arrays total 312,000,000 bytes, or 47,283,532 bytes after gzip compression. All samples were retained; no outliers were removed.

## Files

- [Capacity curve](figures/capacity_s64_b256_huge.png) / [PDF](figures/capacity_s64_b256_huge.pdf)
- [Per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Per-point statistics](summary.csv), [adjacent-point comparisons](transitions.csv)
- [Validation record](validation.json), [analysis provenance](provenance.json)
- Raw directory: `../../../data/artemisia/round1/`

This record covers only completion and analysis of round 1. Rounds 2 and 3 had not been executed at the time of this record.
