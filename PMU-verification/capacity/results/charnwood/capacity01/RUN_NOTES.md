# Charnwood capacity01: failed before sampling

The complete-plan attempt failed on its first shuffled point, `LLC_w7340032`, before warmup or PMU measurement: `MADV_COLLAPSE: Cannot allocate memory`.

No formal samples or counts were collected. The [failed manifest, log and binary](../../../data/charnwood/capacity01/) are retained. This run is excluded from formal analysis; the complete subsequent run is [capacity03](../capacity03/RUN_NOTES.md). No failed or partial measurement was combined with the successful run.

See [preparation records](../../../../results/charnwood/preparation/README.md) for the excluded allocation diagnostic, allocator environment and bounded premeasurement retry adaptation. The exact allocation failure cause was not established.
