# Section 9.1 — Your Team’s Cache Laws and Future Scaling Walls

This folder contains report-ready lab analysis, two evidence figures, exact model parameters, 18 law-specific Hazel predictions, and a conditional five-year scenario. It uses the existing Section 9 lab snapshot without changing it. **Team: Patel–Wu. We did not complete the Hazel experiments because we ran out of time.** The report therefore presents lab-only laws and untested predictions. The mandatory held-out validation portion was not completed, and a GitHub pre-experiment freeze is not verified by this package. No Hazel values have been invented or substituted from specifications.

## Files and reproduction

- [REPORT.md](REPORT.md): prose, equations, evidence table, captions, scaling walls, and interpretation suitable for the report.
- [figures/law_1.pdf](figures/law_1.pdf) and [figures/law_2.pdf](figures/law_2.pdf): vector report figures; PNG versions are also included.
- [tables/hazel_predictions.csv](tables/hazel_predictions.csv): predictions for both laws on nine assignment targets, retaining chronology and overlap caveats.
- [laws.json](laws.json): exact numerical rules and uncertainty definitions inherited from Section 9.
- [tables/lab_evidence.csv](tables/lab_evidence.csv), [tables/fit_diagnostics.csv](tables/fit_diagnostics.csv), and [provenance.json](provenance.json): evidence and source hashes.
- [tables/conditional_forecast.csv](tables/conditional_forecast.csv): lab-only 2028 scenario, not the required post-Hazel forecast.
- [HAZEL_PROTOCOL.md](HAZEL_PROTOCOL.md): documented, unexecuted freeze and measurement procedure; Hazel experiments were not completed due to time constraints.
- [hazel_results_template.csv](hazel_results_template.csv): blank observation fields; blanks are not zero or failed measurements.
- [OUR_LAWS_SLIDE.md](OUR_LAWS_SLIDE.md): compact presentation content.

From the repository root:

```bash
python3 section9_1_cache_laws/build.py
python3 section9_1_cache_laws/validate.py
```

Build dependencies: Python 3, NumPy and Matplotlib (verified locally with NumPy 1.25.0 and Matplotlib 3.9.4). Validation additionally uses Pillow and `pdfinfo`. `build.py` reads the existing snapshot, writes this folder’s derived files, and preserves the results template if it exists. It does not benchmark, commit, push, or access a cluster. Rebuilding is for the preparation phase; preserve committed prediction artifacts unchanged once the genuine freeze is established.

## Requirement coverage

| Section 9.1 requirement | Deliverable / status |
|---|---|
| At least two different quantities, including capacity and cost/behavior | L2 capacity and L2/L1 resident-latency ratio |
| Names containing both last names followed by Law | Patel–Wu names in REPORT.md and slide notes |
| One-sentence statements and numerical rules | REPORT.md, Laws 1 and 2; laws.json |
| Years, machines, vendors/ISAs and pooled scope | Shared domain and evidence table |
| At least three lab points and future dashed continuation | Eight observations per plot; solid model in measured years; no lines implying cross-vendor lineage |
| Law-specific Hazel predictions | 18 prepared predictions; GitHub freeze not verified |
| Post-freeze held-out test and star/diamond reveal | Not completed: team ran out of time; no Hazel reveal |
| Limitations | Both law discussions and shared measurement limits |
| Scaling walls, physical versus economic constraints, future behavior | Separate detailed analyses for both metrics in REPORT.md |
| Quantitative wall estimate only if justified | No exact wall claimed; missing evidence identified |
| Further forecast after held-out evaluation | Conditional 2028 scenario supplied; post-Hazel forecast not completed |
| “Our Laws” slide and held-out conclusion | Slide text supplied; no held-out verdict: experiments not completed |

The supplied PDF defines the requested deliverable; its example law names and illustrative plots are examples, not team identities or measurements. The attached architecture table supplies the existing year convention. This work does not claim completion of unrelated report sections or the full presentation.
