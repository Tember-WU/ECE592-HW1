# Charnwood round-2 collection record

All 57/57 configurations completed, retaining 57,000,000 timed batches (1,000,000 per configuration). Collection started at 2026-09-10T16:57:07.829287+00:00 and finished at 2026-09-10T17:02:18.577837+00:00: 310.749 seconds, approximately 5 minutes 11 seconds. Round 1 had finished before this round began.

The [round-2 configuration](../../../configs/charnwood-round2.json) was generated from Charnwood's new round-1 data using 32–64 KiB, 256–512 KiB, and 4–8 MiB intervals. It includes L1/L2 dense sampling, new-seed repeats, sequential and compact-layout controls, longer batches, and bounded LLC layout/base-page controls. The C kernel, CPU 3 / NUMA node 0, and compiler flags match round 1.

[Validation](validation.json) passed for all raw hashes/sample counts, recomputed statistics, manifest/configuration agreement, source/binary hashes, CPU/NUMA binding, and actual page backing. There were 54 huge-page configurations and 3 explicit base-page configurations; every mapping matched its policy before and after measurement and remained local to node 0. No samples were removed.

Measurement intervals recorded zero minor/major page faults, zero voluntary switches, and 1,619 involuntary context switches (0–149 per configuration). Other users' benchmarks were active. SMT sibling CPU 7 averaged 75.812% busy during the 384 KiB / 8 B random-layout subprocess and 97.945% during the 52 KiB / 64 B random-layout subprocess. The former also shows a temporal median change from about 27.4 to 40 TSC ticks/load. Passing integrity checks does not establish absence of interference.

The [combined two-round record](../combined12/RUN_NOTES.md) contains the interpretation, uncertainty, control comparisons, and boundary evidence. This directory preserves [round-2 statistics](summary.csv), [figures](figures/), [temporal medians](temporal_medians.csv), and [provenance](provenance.json). [Raw data, measurement logs, and source/executable snapshots](../../../data/charnwood/round2/) remain separate from round 1.
