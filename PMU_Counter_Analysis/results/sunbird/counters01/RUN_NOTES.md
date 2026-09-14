# Sunbird PMU Counter Run Notes

Primary contributor: Preet Patel

Run timestamp: 2026-09-14T19:49:36.100693+00:00

Host: `sunbird.ece.ncsu.edu`

CPU profile: Intel Xeon E5-2680 v3, Haswell, 2014

Pinned logical CPU: `1`

Allowed CPUs during the run: `0,1,2,24,25,26`

Workloads:

- `l1_resident`: 16,384 bytes
- `llc_sized`: 31,457,280 bytes
- `beyond_llc`: 125,829,120 bytes

## Commands Run

```bash
cd ~/ECE592-HW1/PMU_Counter_Analysis
. .venv/bin/activate
make test
lscpu -e=CPU,CORE,SOCKET,NODE
python3 scripts/run.py --cpu 1 --preflight --run-id preflight01 --contributor 'Preet Patel'
python3 scripts/run.py --cpu 1 --smoke --run-id smoke01 --contributor 'Preet Patel'
python3 scripts/run.py --cpu 1 --run-id counters01 --contributor 'Preet Patel'
python3 scripts/analyze.py results/artemisia/counters01 results/skylark/counters01 results/sunbird/counters01 --output results/comparison_artemisia_skylark_sunbird01
```

The Sunbird host profile needed `model_contains` set to `E5-2680 v3` so it matches `/proc/cpuinfo` on this machine.

## Result Coverage

- Full run completed all 81 expected passes.
- The run contains 3 workloads x 3 repeats x 9 measurement slots, where the 9 slots are timing plus the 8 selected PMU event slots.
- `analysis/coverage.csv` reports `full_sample_coverage=True`.
- The multi-host comparison run includes Artemisia, Skylark, and Sunbird. The remaining missing ECE hosts are Charnwood, Crux, Ookay, Thunderbird, and Upgrade.

## Main Outputs

- Raw per-pass outputs: `raw/`
- Selected PMU events: `selected_events.json`
- Per-host analysis report: `analysis/REPORT.md`
- Normalized counter summary: `analysis/normalized_summary.csv`
- Timing statistics: `analysis/timing_statistics.csv`
- Per-host workload plot: `analysis/workload_comparison_sunbird.pdf`
- Combined comparison output: `../../comparison_artemisia_skylark_sunbird01/`

## Quick Sanity Check

Median timing increased with the intended working-set classes:

- `l1_resident`: about 5.06 TSC ticks/access
- `llc_sized`: about 110.81 to 148.94 TSC ticks/access across repeats
- `beyond_llc`: about 250.13 to 250.56 TSC ticks/access across repeats

The normalized PMU data also shows near-zero LLC-load-misses for the L1-resident workload and about 1,000 LLC-load-misses per 1,000 accesses for the beyond-LLC workload. As documented by the project, these event slots should still be interpreted with the semantic caveats in `analysis/event_semantics.csv`.
