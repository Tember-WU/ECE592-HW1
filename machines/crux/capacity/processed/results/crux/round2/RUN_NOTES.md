# Crux round-2 collection

All 57 configurations completed, each retaining 1,000,000 timed batches,
for 57,000,000 batches total. Collection ran from
2026-09-10T16:57:08.546424+00:00 to 2026-09-10T17:00:32.612730+00:00
(204.07 seconds). Round 2 started after the complete first round was
analyzed and validated.

The plan was generated from `round1-retry1`: L1D 32–64 KiB, L2 256–512 KiB,
and a broad LLC interval of 4–16 MiB. It retained the original planner's
dense points, new-seed repeats, sequential chains, compact 8 B layouts,
1024-load batch controls, and base-page controls. See the provenance and
selection rationale in [crux-round2.json](../../../configs/crux-round2.json).

CPU 6 / NUMA node 0, C source, executable hash, timing method, and compiler
flags match the complete first round. All 54 huge-page configurations had
full THP backing, and all 3 base-page configurations had zero THP coverage,
before and after measurement. All mappings remained local to node 0.
Raw checksums, counts, statistics, and placement checks passed; see
[validation.json](validation.json).

There were no measured minor/major page faults or voluntary context
switches. Involuntary switches totaled 598, with a maximum of 48 per
configuration. CPU 0 and CPU 3 were 100% busy throughout every recorded
subprocess interval. Shared-machine load and layout differences limit LLC
capacity interpretation even though data-integrity checks passed. No
samples or outliers were removed.

The compressed raw arrays occupy 88,110,745 bytes (456,000,000 uncompressed).
Source, binary, assembly, commands, page/placement logs, and raw samples
are under `../../../data/crux/round2/`.

See the [combined two-round record](../combined12/RUN_NOTES.md) for the
capacity interpretation, controls, disclosed initial `lscpu` exposure,
and boundary plots. [Statistics](summary.csv) and
[figures](figures/capacity_s64_b256_huge.png) here describe round 2 alone.
