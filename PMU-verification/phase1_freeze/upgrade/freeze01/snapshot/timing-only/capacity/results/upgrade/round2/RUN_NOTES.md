# Upgrade round-2 refinement

Run `round2` completed all 57 configurations and retained 57,000,000 timed batches. Collection ran from 2026-09-10T16:58:08.403399+00:00 to 17:00:08.570639+00:00, taking 120.17 seconds. It started after the completed first round had been analyzed and checked.

The planner used only `round1-retry2` evidence to select 32–64 KiB, 256–512 KiB and 4–8 MiB intervals. The resulting [configuration](../../../configs/upgrade-round2.json) records source manifests, raw hashes, selected endpoints and the selection rationale. The original kernel and collection/planning/analysis scripts match the Artemisia round-2 snapshots byte for byte. CPU 2 / NUMA node 0 and the original `-O0` flags were retained.

The 57 points comprise 38 L1/L2 refinement and control configurations, plus 19 LLC configurations. Each preserves 1,000,000 batches: normally 256 dependent loads per batch, with two 1024-load controls. There are 54 huge-page points and 3 explicit base-page controls. Every mapping matched its requested policy before and after measurement and remained local to node 0.

The random primary layout rises from 3.2500–3.2578 ticks/load at 32 KiB to 8.8242 at 36 KiB, and from 8.9414–8.9453 at 256 KiB to 14.5547 at 288 KiB. At 7 MiB it remains at 28.4648, while 8 MiB rises to 114.1016. Compact-layout medians at 8 MiB are 55.7617 and 57.3242; the base-page median is 133.9141. These controls are separate distributions, not additional cache levels or pooled observations.

The prelaunch three-second sample recorded 0% busy time on CPUs 2 and 8. During benchmark subprocess intervals CPU 8 averaged 0–6.897% busy. Measurement intervals recorded no minor/major faults or voluntary context switches; involuntary switches totaled 205, with at most 23 at one point. Another benchmark was present on CPU 0. These checks do not certify absence of interference. All outliers and all raw samples remain saved.

See the [combined interpretation](../combined12/RUN_NOTES.md), [round-2 statistics](summary.csv), [validation](validation.json), [provenance](provenance.json), [layout comparison](figures/layout_comparison_b256_huge.png), and [raw run](../../../data/upgrade/round2/).
