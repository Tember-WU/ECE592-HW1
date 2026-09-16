# Section 9: lab trends and Hazel prediction snapshot

Data and figure package for the three selected Section 9 tasks. All numerical training data come from the eight ECE lab hosts. No Hazel experiments or held-out evaluation are included.

## Files

| Path | Contents |
|---|---|
| `tables/chronological_master.csv` | Eight hosts, sorted by year; CPU/process metadata, inferred cache metrics, native timer units, separate verification fields, and PMU event names/values |
| `tables/chronological_capacity_summary.csv` | Compact capacity table; LLC transition spans remain explicitly non-physical |
| `tables/chronological_latency_summary.csv` | Resident medians and incremental miss costs with native units |
| `tables/trend_summary.csv` | Slopes, doubling times, fit error, and leave-one-host-out comparison against a flat baseline for three cohorts |
| `tables/trend_interpretation.csv` | Short English findings and their numerical evidence |
| `tables/observed_step_counts.csv` | Increases, decreases, and unchanged adjacent sampled values |
| `figures/` | Matching vector PDF and PNG result figures; captions in `tables/figure_manifest.json` |
| `predictions/hazel_predictions.csv` | 27 quantitative predictions: three metrics for nine planned Hazel constraints |
| `predictions/model_parameters.json` | Exact equations, fitted parameters, training hosts, uncertainty construction, and limitations |
| `predictions/model_training_points.csv` | The 24 numerical inputs used by the three models |
| `predictions/model_curves.csv` | Numerical model evaluations from 2014 through the newest target year, 2024 |
| `predictions/hazel_prediction_matrix.csv` | Predictions and explicit abstentions for every target |
| `inputs/` | English normalized lab snapshot, original-source hashes, target launch metadata, and the team's pre-freeze declaration |
| `freeze/manifest.json` | Local snapshot timestamp and SHA-256 hashes; no Git commit or tag |

## Reading the results

- Main chronological coordinate: first launch of the represented processor generation, inherited from Section 8.1. It is not necessarily the individual SKU or implementation launch year. The third-generation Xeon Scalable family launched in 2020 as Cooper Lake; the Ice Lake-SP implementation followed in 2021. Both dates are retained. `predictions/chronology_sensitivity.csv` records the effect of using 2021 instead.
- Timing inference, original conflict candidates, and later PMU/system verification remain separate fields. Missing numerical values mean unresolved or unavailable, never zero.
- x86 latencies are local TSC ticks/load; calibrated x86 nanoseconds and core cycles are unavailable. Thunderbird's documented 25 MHz timer permits nanoseconds. Cross-architecture latency ratios are dimensionless benchmark observations, not pure hardware latencies.
- Capacity brackets and latency envelopes are descriptive variability. Prediction bands have no assigned coverage probability and are not 95% confidence intervals.
- Historical OLS and the frozen L2 predictor are different models: the predictor is constrained to the latest lab observation, so its future dashed line starts at the measured 2023 endpoint. Its slope is estimated from all eight lab hosts. The L1 and relative-latency predictors use pooled empirical medians.
- Predictions for years at or before 2023 are held-out-machine predictions within the lab year range. Only the 2024 Turin target is a future-year extrapolation. Haswell and Sapphire Rapids already have lab-generation examples; the two Ice Lake constraints share a generation.
- Target availability is unverified. The target list is assignment Table 4, not a live scheduler inventory. Launch-date sources are recorded in `inputs/launch_year_sources.csv`; no target cache values enter model fitting. The declaration records an incidental cache-marketing search snippet transparently.
- PMU plots use only four comparable Intel desktop mappings; all eight hosts remain in the PMU CSV. Kernel mapping and capacity-relative workload differences remain limitations.

## Reproduce and verify

Run from the repository root with the existing scientific Python environment:

```bash
timing-only/capacity/.venv/bin/python section9_moore_analysis/scripts/analyze.py
timing-only/capacity/.venv/bin/python section9_moore_analysis/scripts/validate.py --check-upstream
```

The normal build uses only the normalized snapshot, not changing experiment folders. `--collect` imports selected existing lab summaries and is disabled after a freeze. Dependencies are pinned in `requirements.txt`; `pdfinfo` is used to validate PDFs. No command runs a benchmark or contacts Hazel.

The predictions are saved as a local file snapshot only. No Git commit or tag is retained. The previous assistant-created commit and tag were undone at the user's request. `scripts/freeze.py` only writes local metadata and hashes; it does not stage files, commit, create tags, or push.

This package does not contain a standalone report, slides, Section 9.1 laws, a five-year forecast, or Hazel validation. A local checksum snapshot does not establish a Git-based prediction freeze or independently verified experiment ordering.
