# Skylark round-2 collection record

Completed 57/57 configurations with 1,000,000 timed batches each, totaling 57,000,000 batches in 318.45 seconds. The original planner generated this round from the new Skylark round-1 curve: L1 32–64 KiB, L2 512 KiB–1 MiB, and LLC 16–32 MiB. Each region received 19 configurations using the original dense/repeat/control protocol.

The round used CPU 32 / NUMA node 1 and the same original C source, compiler flags, and executable hash as round 1. All raw samples were preserved. The [validation](validation.json) passed raw checksums/counts, recomputed statistics, snapshots, CPU/NUMA placement, and page policy. All 54 huge-page configurations had complete THP backing; all 3 base-page controls had zero huge-page backing. All mappings stayed local to node 1.

Measurement events: zero minor faults, major faults, and voluntary switches; 787 involuntary switches in total, at most 71 per point. The maximum within-point temporal-decile median ratio was 1.058824, at 640 KiB. Validation does not exclude shared-machine interference.

Raw arrays total 456,000,000 bytes, compressed to 57,024,662 bytes. See [combined two-round notes](../combined12/RUN_NOTES.md) for capacity estimates, controls, and limitations; [summary.csv](summary.csv) and [figures](figures/) retain the round-2-only analysis. Raw data are in `../../../data/skylark/round2/`; configuration is `../../../configs/skylark-round2.json`.
