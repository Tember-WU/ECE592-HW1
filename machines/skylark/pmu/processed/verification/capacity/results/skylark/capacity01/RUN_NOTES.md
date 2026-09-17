# Skylark capacity: capacity01

Completed on2026-09-14. Every configuration contains1,000,000 timed batches and four simultaneous per-thread/user-mode events, with no multiplexing. Counts and timing distributions remain separate between the two event groups.

Supports the frozen32–36 KiB L1 and512–576 KiB L2 transitions. Local DRAM/IO fills rise at16–20 MiB. Direct shared-L3 counters were unavailable; DRAM fills are an indirect measure. MAB allocations do not follow L1 timing; the second group provides refill evidence.

See the [complete Chinese report](../../../../SKYLARK.md), [event definitions](../../../../skylark/EVENTS.md), [combined comparison](../../../../skylark/results/capacity_eight_events.csv), and [combined figure](../../../../skylark/results/capacity_combined.pdf).

This directory includes full statistics, raw/normalized event counts, temporal medians, quality and validation JSON, provenance, analysis-source snapshots, and distribution/comparison figures. The matching data directory contains raw gzip timing arrays, counter JSON, logs, commands, configuration, benchmark/source snapshots, and the frozen Phase-I checksums. All outliers are retained. Original Artemisia and timing-only files are unchanged.
