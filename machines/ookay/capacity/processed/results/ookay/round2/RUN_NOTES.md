# Ookay round-2 collection record

All 57/57 configurations completed, with 1,000,000 timed batches per point and 57,000,000 batches in total. Collection ran from 2026-09-10T16:56:57.485110+00:00 to 2026-09-10T16:59:50.046715+00:00, taking 172.56 seconds. It began after the complete first round had finished and been analyzed.

The [configuration](../../../configs/ookay-round2.json) was generated from `round1-retry1` with L1/L2/LLC candidate intervals of 32–64 KiB, 256–512 KiB, and 4–8 MiB. It includes dense measurements, new-seed repeats, sequential controls, 8 B compact-layout controls, two 1024-load batch controls, and three base-page controls. CPU 2, NUMA node 0, the C kernel, and compiler flags match the completed first round.

[Validation](validation.json) passed for all 57 raw files, CPU/NUMA binding, and actual page backing before and after timing. There were 54 huge-page configurations and 3 explicit base-page configurations. All samples and outliers were retained. Raw arrays total 456,000,000 bytes, compressed to 86,804,421 bytes.

Measurement intervals recorded no minor/major faults or voluntary switches, and 45 involuntary switches in total, with at most 5 at a point. The SMT sibling, CPU 6, had recorded busy percentages of 0–2.222% over subprocess intervals. Other benchmarks remained present at the prelaunch observation; these checks do not rule out shared-cache or memory-system interference. The LLC controls show broad distributions, temporal variation, and layout/page sensitivity, whose causes were not isolated.

See the [combined two-round record](../combined12/RUN_NOTES.md) for capacity estimates and their limits. Round-specific [statistics](summary.csv), [figures](figures/capacity_s64_b256_huge.png), [temporal medians](temporal_medians.csv), and [provenance](provenance.json) remain here; the [raw run](../../../data/ookay/round2/) contains all samples, logs, source and executable snapshots.
