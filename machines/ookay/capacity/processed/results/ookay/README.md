# Ookay experiment results

The requested two rounds completed on 2026-09-10. Start with the [combined experiment record](combined12/RUN_NOTES.md) and [boundary plots](combined12/figures/boundary_zoom.png).

| Completed round | Run ID | Configurations | Timed batches | Collection time |
|---|---|---:|---:|---:|
| Coarse scan | `round1-retry1` | 39 | 39,000,000 | 169.39 s |
| Refinement and controls | `round2` | 57 | 57,000,000 | 172.56 s |

Both rounds used CPU 2 / NUMA node 0. The timing-only evidence supports approximately 32 KiB L1D and 256 KiB L2; LLC has a broad 5–8 MiB effective transition, without a unique nominal physical capacity estimate. See the combined record for distribution evidence and shared-machine limitations.

The earlier `data/ookay/round1/` is a preserved failed attempt, not the completed first round: transparent-huge-page allocation failed at 512 MiB after four configurations. It is excluded from the two-round analysis. [Recovery details](../../data/ookay/recovery.json) explain the unchanged full restart.

The measurement code and shared first-round protocol are unchanged. [ookay.json](../../configs/ookay.json) selects the machine binding; [ookay-round2.json](../../configs/ookay-round2.json) records the new first-round evidence used for planning. Preparation, dependency versions, console output, and every raw-run snapshot are under [data/ookay](../../data/ookay/).

To regenerate the existing analyses from the capacity directory:

```bash
.venv/bin/python scripts/analyze_capacity.py --machine ookay --run-id round1-retry1
.venv/bin/python scripts/analyze_capacity.py --machine ookay --run-id round2
.venv/bin/python scripts/analyze_capacity.py --machine ookay --run-id round1-retry1 round2 --output-id combined12 --boundaries results/ookay/combined12/boundaries.json
.venv/bin/python results/ookay/validate_runs.py round1-retry1 round2
```

The local `.venv` contains the versions pinned in `requirements.txt`; full installed versions are in [preparation.json](../../data/ookay/preparation.json). Compilation and all 10 existing `make check` tests passed before collection. `validate_runs.py` saves each round's integrity/binding/page checks; final interpretation and combined validation are recorded alongside the combined analysis.
