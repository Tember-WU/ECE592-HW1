# Cache-event discovery

On Artemisia, run from this directory:

```bash
python3 scripts/discover_events.py --machine artemisia --cpu 32 --run-id discovery02
```

The completed initial inventory is [discovery01](results/artemisia/discovery01/EVENTS.md).
Its full listings, machine identification, exact probe commands, and probe output are under
`data/artemisia/discovery01/`. `events.csv` distinguishes listed events from individually tested
events. The probes use a short process only to establish that counting is permitted and schedulable;
they are not formal cache experiments or one-million-sample measurements.

The script's selected probes use the Intel event names found on Artemisia. Full event listings are
machine-specific; review and adapt the probe selection for a different PMU. A failed event remains
recorded with its error, and a failed capacity group stops the script. Do not change host security
settings to work around a permission error.
