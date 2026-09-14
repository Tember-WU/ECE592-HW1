# Skylark line_size: line_size02_refills

Completed on2026-09-14. Every configuration contains1,000,000 timed batches and four simultaneous per-thread/user-mode events, with no multiplexing. Counts and timing distributions remain separate between the two event groups.

Spatial reuse and traversal controls are visible. The64 B candidate matches system geometry, but the refill curve has no clean64 B plateau. Absolute timings and request/refill rates vary between groups; preserve these disagreements.

See the [complete Chinese report](../../../../SKYLARK.md), [event definitions](../../../../skylark/EVENTS.md), [combined comparison](../../../../skylark/results/line_size_eight_events.csv), and [combined figure](../../../../skylark/results/line_size_combined.pdf).

This directory includes full statistics, raw/normalized event counts, temporal medians, quality and validation JSON, provenance, analysis-source snapshots, and distribution/comparison figures. The matching data directory contains raw gzip timing arrays, counter JSON, logs, commands, configuration, benchmark/source snapshots, and the frozen Phase-I checksums. All outliers are retained. Original Artemisia and timing-only files are unchanged.
