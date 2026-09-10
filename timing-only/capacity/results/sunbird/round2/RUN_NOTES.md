# Sunbird second-round collection

All **57/57 configurations** completed, each retaining 1,000,000 timed batches, for 57,000,000 batches. Collection ran from 2026-09-10T16:35:38.034031+00:00 to 2026-09-10T16:40:57.587201+00:00 and took 319.55 seconds (5 minutes 19.55 seconds).

The [configuration](../../../configs/sunbird-round2.json) was generated from the new `round1_retry1` measurements: L1 32–64 KiB, L2 256–512 KiB, and bounded LLC refinement at 16–64 MiB. It contains the original dense/repeat/sequential/layout/longer-batch controls for L1/L2 and layout/repeat/sequential/base-page controls for LLC. CPU 32 / NUMA node 0, C source, executable, compiler flags, and timing method match the formal first round.

[Validation](validation.json) passed for raw-data integrity, manifest completion, source/executable hashes, analysis input provenance, CPU binding, NUMA placement, and page backing. All 54 huge-page configurations were fully huge-page backed before and after timing; all 3 base-page configurations had no huge-page backing. All mappings were local to NUMA node 0. CPU 8 recorded 0% busy time during every benchmark subprocess interval. Timed regions had no minor faults, major faults, or voluntary context switches; involuntary context switches totaled 91, with at most 7 at one configuration. These checks do not establish absence of machine interference.

Raw arrays total 456,000,000 bytes, compressed to 57,030,291 bytes. All samples and outliers are preserved in the [raw run directory](../../../data/sunbird/round2/). The analyzer recomputed statistics from the raw samples.

The [combined two-round record](../combined12/RUN_NOTES.md) contains the capacity interpretation, boundary evidence, controls, and limitations. It estimates L1D at approximately 32 KiB and L2 at approximately 256 KiB and reports an effective LLC transition without an exact physical capacity.

- [Primary curve](figures/capacity_s64_b256_huge.png), [per-point box plots](figures/boxplots_s64_b256_huge.pdf)
- [Layout comparison](figures/layout_comparison_b256_huge.png), [temporal stability](figures/temporal_stability.pdf)
- [Statistics](summary.csv), [adjacent comparisons](transitions.csv), [provenance](provenance.json), [validation](validation.json)

To reproduce this round's analysis from the capacity directory:

```bash
.venv/bin/python scripts/analyze_capacity.py --machine sunbird --run-id round2
.venv/bin/python data/sunbird/setup/audit_runs.py round2
```
