# Skylark associativity: associativity01

Completed on2026-09-14. Every configuration contains1,000,000 timed batches and four simultaneous per-thread/user-mode events, with no multiplexing. Counts and timing distributions remain separate between the two event groups.

L1 local-L2 refills rise atK8→9. At64 KiB spacing L2 request misses already rise atK9; the frozen11-way classification selects a later transition. The first miss onset is consistent with8 ways. Timed-load divisor is129; counting denominator is samples*(K+128).

See the [complete Chinese report](../../../../SKYLARK.md), [event definitions](../../../../skylark/EVENTS.md), [combined comparison](../../../../skylark/results/associativity_eight_events.csv), and [combined figure](../../../../skylark/results/associativity_combined.pdf).

This directory includes full statistics, raw/normalized event counts, temporal medians, quality and validation JSON, provenance, analysis-source snapshots, and distribution/comparison figures. The matching data directory contains raw gzip timing arrays, counter JSON, logs, commands, configuration, benchmark/source snapshots, and the frozen Phase-I checksums. All outliers are retained. Original Artemisia and timing-only files are unchanged.
