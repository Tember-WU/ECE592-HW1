# Crux capacity results from two rounds

The complete first round (`round1-retry1`) and second round (`round2`)
contain 39 + 57 configurations and 96,000,000 timed batches. Collection
took 156.60 and 204.07 seconds respectively, totaling 360.67 seconds.
Both rounds ran serially on CPU 6 / NUMA node 0 of `crux.ece.ncsu.edu`
with the original C kernel, identical executable hash, and `-O0` flags.
The configured NumPy 1.26.3 and Matplotlib 3.9.4 versions were installed
in the local `.venv`; GCC was 13.3.0.

## Timing inferences

The curves support three distinguishable data-cache residency regions:
approximately 2.73 TSC ticks/load at 2–16 KiB, 7.96 at 64–128 KiB, and
26.0–27.9 at 1–4 MiB. The large random working sets reach approximately
202–207 ticks/load at 128–512 MiB. Timing values include batch overhead
and are not validated core cycles or results from a dedicated hit-latency
experiment.

| Region | Random-chain evidence, 64 B spacing / huge pages (TSC ticks/load) | Interpretation |
|---|---|---|
| L1D | Three processes at 32 KiB: 2.8672–2.9141; 36 KiB: 7.9297; two round-2 processes at 48 KiB: 7.9570 | Approximately 32 KiB; sampled transition bracket 32–36 KiB |
| L2 | Three processes at 256 KiB: 8.0586–8.1133; 288 KiB: 13.8164; 512 KiB: 22.8398–22.9102 | Approximately 256 KiB; sampled onset bracket 256–288 KiB |
| LLC effective transition | Round 2: 4 MiB 27.9180, 7 MiB 71.8789, 10 MiB 142.6172, 13 MiB 163.5039, 16 MiB 171.7539 | Broad effective transition across 4–16 MiB, with sampled onset between 4 and 7 MiB; exact physical capacity remains undetermined |

These brackets describe measured neighborhoods, not statistical confidence
intervals. The LLC region does not bound nominal physical capacity. The
second-round intervals were selected from the complete new coarse scan:
32–64 KiB, 256–512 KiB, and 4–16 MiB. The planner records the source run,
raw hashes, selection rationale, and its own hash in
[crux-round2.json](../../../configs/crux-round2.json).

## Controls and repeatability

The L1/L2 boundary changes exceed the distributions' P05–P95 ranges. At
36 KiB the range is 7.8828–8.1133, compared with 2.8281–3.0039 across the
32 KiB processes. At 288 KiB it is 12.8281–14.9102, compared with
7.9453–8.3945 across the 256 KiB processes. New-seed repeats at the lower,
middle, and upper anchors support the same low/high regions, although the
first newly rising dense point at each boundary has only one process.

The 1024-load controls give 2.8926 ticks/load at 32 KiB and 7.9482 at
256 KiB. They retain the two early residency regions. The empty-timer
median is 31 ticks/interval. Sequential controls have lower latencies
above the early boundaries; compact layouts also change the shape of the
rise. These controls are plotted separately, with no pooling of samples
from different processes or settings.

For the 8 B LLC layout, repeat medians are 27.4141–27.4375 at 4 MiB,
91.8984–92.7031 at 10 MiB, and 135.5117–138.6953 at 16 MiB. The 64 B
base-page controls give 35.6680, 151.2266, and 187.7578 at those same
sizes, compared with 27.9180, 142.6172, and 171.7539 under huge pages.
The different layouts have different spatial-reuse opportunities. Page
policy, layout, and concurrent workloads have not been isolated enough
to attribute the LLC differences to a unique cause.

Temporal diagnostics show some LLC variation: the ten block medians at
16 MiB / 8 B / seed 59202 range from 134.9453 to 150.8320 ticks/load;
the 10 MiB base-page control ranges from 149.7305 to 177.2129. All raw
samples and outliers remain included in the reported statistics.

## Data quality and execution record

The analyzer verified hashes, counts, and positive intervals in all 96 raw
arrays and recomputed their statistics. Placement audits passed: all
mappings remained on node 0; all 93 huge-page configurations had full THP
coverage before and after measurement; the 3 base-page configurations had
zero THP coverage. CPU start/end values were 6 throughout. The two rounds
share the same source and executable hashes. The preparation check passed
all 10 existing tests, and inspection of `time_batch` confirmed 16 mutually
dependent loads per loop between the serialized timestamps.

No minor/major page faults or voluntary context switches were recorded
during measurement. Involuntary switches totaled 439 in round 1 and 598
in round 2, with per-point maxima of 61 and 48. CPU 6 has no additional
SMT thread, but CPU 0 and CPU 3 were 100% busy during every benchmark
subprocess interval. Other users' benchmark processes were observed at
launch. Passing integrity checks does not demonstrate freedom from
shared-cache or memory interference.

The initial attempt `round1` failed on 512 MiB `MADV_COLLAPSE` before that
configuration was timed. Its four completed configurations and failure
evidence remain preserved and excluded from this combined result. A fresh
run ID was used for the successful retry, without changing the kernel,
sample count, order, or page policy. The two intended rounds retain
768,000,000 bytes of raw arrays, compressed to 141,486,652 bytes; the
failed attempt's additional four million batches are stored separately.

**Protocol deviation:** initial environment inspection used unfiltered
`lscpu`, exposing OS-reported cache sizes before the experiment instructions
were read. This run therefore cannot be described as blind cache-capacity
inference. The numerical conclusions above and all follow-up endpoints
are supported by the recorded timing data, and no PMU measurements were
taken. The exposure is also disclosed in the preflight record and generated
round-2 configuration.

## Files

- [Boundary zoom](figures/boundary_zoom.png) / [PDF](figures/boundary_zoom.pdf)
- [Boundary box plots](figures/boundary_boxplots.pdf)
- [Full primary capacity curve](figures/capacity_s64_b256_huge.png)
- [Layout comparison](figures/layout_comparison_b256_huge.png)
- [Temporal stability](figures/temporal_stability.pdf)
- [Statistics](summary.csv), [transitions](transitions.csv)
- [Machine-readable inferences](inference.json), [boundary annotations](boundaries.json)
- [Combined validation](validation.json), [analysis provenance](provenance.json)
- [Run inventory and reproduction commands](../README.md)

The requested two rounds are complete. Approximate L1D/L2 capacities and
the LLC uncertainty can be reported at this resolution. A third round was
not executed; finer early boundaries would require additional points in
32–36 KiB and 256–288 KiB.
