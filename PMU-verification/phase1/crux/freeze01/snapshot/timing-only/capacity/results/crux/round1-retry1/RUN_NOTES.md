# Crux round-1 coarse scan

Run `round1-retry1` completed all 39 configurations and retained 39,000,000
timed batches. Collection ran from 2026-09-10T16:53:06.478173+00:00 to
2026-09-10T16:55:43.083157+00:00 (156.60 seconds).

The shared first-round protocol was used unchanged: 19 powers-of-two address
spans from 2 KiB to 512 MiB, random and sequential dependent chains, and one
empty-timer control. Placement was CPU 6 / NUMA node 0, with 64 B spacing,
256 dependent loads/batch, seed 59201, and complete 2 MiB THP backing. The
original C kernel and `-O0` compiler flags were retained. The empty-timer
median was 31 TSC ticks/interval.

## Refinement selected from the new measurements

| Candidate | Measured primary random-chain evidence (TSC ticks/load) | Round-2 interval |
|---|---|---|
| L1D | 32 KiB: 2.8672; 64 KiB: 7.9609 | 32–64 KiB |
| L2 | 256 KiB: 8.1133; 512 KiB: 22.9023 | 256–512 KiB |
| LLC effective transition | 4 MiB: 27.9297; 8 MiB: 99.3008; 16 MiB: 172.3633 | 4–16 MiB |

The earlier regions are approximately 2.73 ticks/load at 2–16 KiB, 7.96 at
64–128 KiB, and 26.0–27.9 at 1–4 MiB. The 128–512 MiB points reach
201.8–206.6 ticks/load, so no range extension is needed. The LLC interval
includes the last observed low-latency point and the broader rise through
the 8 MiB point. These intervals select follow-up measurements; they are
not exact capacities or statistical confidence intervals.

## Validation and limitations

All raw-file checksums, sample counts, and positive intervals were checked
by the analyzer; all statistics were recomputed from raw data. The
[validation record](validation.json) also checks the manifest, analysis
provenance, source/binary hashes, CPU binding, page backing, and NUMA logs.
All mappings stayed on node 0 with full huge-page coverage before and after
measurement. There were no measured minor/major page faults or voluntary
context switches; involuntary switches totaled 439, with a maximum of 61
in one configuration.

CPU 0 and CPU 3 were 100% busy throughout every recorded benchmark subprocess
interval, and other users' `cache_bench` processes were observed before
launch. CPU 6 has no other SMT thread. Pinning a quiet core does not remove
shared-cache/memory interference; the LLC result describes this workload
environment. All samples and outliers are retained.

The initial attempt, `round1`, stopped after four configurations because
512 MiB THP allocation failed before measurement. It remains preserved and
is excluded from this analysis and subsequent point selection. The retry
used the same protocol, without a page-policy fallback or kernel change.

During initial environment inspection, an unfiltered `lscpu` command exposed
OS-reported cache sizes before the experiment instructions were read. This
is a deviation from blind timing-only inference. The table and the generated
round-2 plan cite only this run's timing evidence; no PMU measurements were
taken. See `../../../data/crux/round1-preflight.json` for the disclosure and
prelaunch observation.

## Files

- [Capacity curve](figures/capacity_s64_b256_huge.png) / [PDF](figures/capacity_s64_b256_huge.pdf)
- [Per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Statistics](summary.csv), [adjacent-point comparisons](transitions.csv)
- [Validation](validation.json), [analysis provenance](provenance.json)
- [Round-2 configuration](../../../configs/crux-round2.json)
- Raw data: `../../../data/crux/round1-retry1/`

The compressed raw arrays occupy 53,375,907 bytes (312,000,000 uncompressed).
This record describes round 1 and its follow-up selection, before round-2
interpretation.
