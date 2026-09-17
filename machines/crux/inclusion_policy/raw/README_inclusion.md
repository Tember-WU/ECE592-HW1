# Experiment 5: Inclusion / Exclusion Behavior

This implements slide 18's four-step recipe on top of the same fenced
RDTSC/RDTSCP timing skeleton used in `associativity_bench.cpp` and
`line_size_bench.cpp`. It's the hardest of the five experiments because it
needs an LLC conflict set, and the LLC is physically indexed and often
sliced/hashed -- so unlike L1D (VIPT, page-offset stride works, see
Experiment 3) you cannot just compute the right stride. You have to search
for it empirically and be honest about how well the search worked.

## Files

| File | Purpose |
|---|---|
| `inclusion_bench.cpp` | The C++ benchmark: `calibrate`, `find_conflict`, `test` modes |
| `run_inclusion_experiment.py` | Orchestrates all three modes for one machine, produces plots + a per-machine JSON verdict |
| `machine_configs/*.json` | One config per machine: cache geometry (from your Exp 1-3 results) + candidate LLC strides to search |
| `aggregate_inclusion_results.py` | Combines all 8 machines' verdicts into one CSV/table for the report |

## 1. Build

```
g++ -O0 -g -std=c++11 -m64 -Wall -Wextra -fno-omit-frame-pointer \
    -o inclusion_bench inclusion_bench.cpp
```

(Add an `inclusion` target to your Makefile if you want `make inclusion`; a
snippet is at the bottom of this file.)

## 2. Fill in one config per machine

Copy `machine_configs/_TEMPLATE.json` (or edit the six already-started files:
`artemisia.json`, `sunbird.json`, `skylark.json`, `charnwood.json`,
`crux.json`, `ookay.json` -- these already have your `pin` field filled in
from what you gave me). You still need `thunderbird.json` and
`upgrade.json` since those two weren't in the pinning list you gave me --
add their `taskset -c <CPU>` core/CPU the same way you ran the other two
experiments on them.

Required fields you must fill from your **own already-completed** Experiment
1 (capacity plateaus) and Experiment 3 (L1/L2 sets & ways) results, per
machine -- **do not look these up externally**, that would violate the
Phase-I timing-only rule (slide 3):

- `l2_bytes`, `llc_bytes`: the plateau sizes from Experiment 1 for that
  machine (per-socket LLC size on the two-socket boxes -- Sunbird, Skylark,
  Artemisia -- per slide 12's warning never to sum across sockets)
- `l2_sets`: `l2_bytes / (line_size * l2_ways)` using the L2 ways you found
  in Experiment 3
- `assumed_llc_ways_upper_bound`: just a ceiling to steer the search sweep
  (e.g. 12 or 16); it is not asserted as ground truth anywhere in the output
- `candidate_llc_strides`: a handful of byte strides to test as LLC
  set-conflating strides. Reasonable starting points: multiples of
  `llc_bytes / (a guessed LLC set count)`, and simple powers of two around
  that value. Cast a wide net -- this is the part that needs real search.
- `candidate_k_values`: conflict-ring sizes to sweep, spanning below and
  above `assumed_llc_ways_upper_bound`, e.g. `[2,4,6,8,10,12,14,16,20,24,32]`

## 3. Run, per machine (pin exactly like you did for the other experiments)

```
taskset -c 4 python3 run_inclusion_experiment.py --config machine_configs/skylark.json
```

This does, in order:

1. **calibrate** -- builds L2-resident, LLC-resident, and DRAM-resident
   regions and records single-access reload latency distributions for each.
   Computes two classification boundaries: midpoint(L2, LLC) and
   midpoint(LLC, DRAM).
2. **find_conflict sweep** -- for every `(stride, K)` pair in your config,
   builds a K-line conflict ring at that stride, warms line 0 into the LLC,
   chases the other K-1 lines, reloads line 0, and reports the fraction of
   trials that look evicted. Writes `find_conflict_summary.csv`. **Look at
   this file yourself.** You want strides where eviction probability is
   near 0 for `K <= assumed_llc_ways_upper_bound` and jumps toward 1 above
   it -- exactly the same sharp-step signature as Experiment 3, slide 3's
   Figure 8, just aimed at the LLC instead of L1/L2. If nothing shows a
   clean jump, add more strides to the config and re-run before trusting
   the next step.
3. **test** -- using the best `(stride, K)` found, runs the actual
   slide-18 trial across `num_targets` independent target regions and
   `num_trials` repeats each: place T (repeated direct hits), pressure the
   LLC only (chase the K-1 ring), reload T once (single fenced access),
   classify against the calibrated boundaries. Also records, per target,
   whether any pressure line's low-order address bits collide with T's
   under the VIPT L2-indexing assumption -- a same-L2-set collision means
   that trial's "we only pressured the LLC" claim is compromised and should
   be down-weighted or excluded.
4. **classify** -- aggregates the fractions of `L2_hit` / `LLC_hit` / `DRAM`
   reloads into a verdict (`inclusive`, `non-inclusive/exclusive-like`, or
   `mixed/ambiguous`) and writes `inclusion_report.json` plus
   `inclusion_summary.pdf` (bar chart of outcome fractions + the calibration
   histograms with the two boundaries marked, so a grader can see the
   thresholds weren't cherry-picked).

## 4. After all 8 machines

```
python3 aggregate_inclusion_results.py
```

Produces `inclusion_summary_all_machines.csv` -- this is the inclusion
column of your Table 2 (slide 22): machine, verdict, evidence fractions,
which stride/K was used, and how many target regions were flagged as
possibly L2-contaminated (report this number, don't hide it).

## Reading the result honestly (per the TA's note)

> "This is the hardest experiment... a clean textbook label may not be
> supportable. A well-argued 'non-inclusive, with these caveats' beats a
> confident wrong answer."

Concretely, in your writeup:
- If `find_conflict_summary.csv` never shows a clean low-K/high-K jump for
  a machine, say so and report the LLC-pressure result as a **behavioral
  bound** ("reload was DRAM-class in X% of trials against this
  best-available conflict set"), not a confirmed inclusion/exclusion label.
- If `possibly_l2_contaminated_target_regions` is nonzero, mention it -- it
  means some of the "LLC-only pressure" trials may have also perturbed T's
  L2 line, which would bias you toward the "looks inclusive" outcome.
- LLC slicing/hashing (common on multi-core Intel parts, and worth calling
  out for Sunbird/Ookay/Upgrade/Crux/Artemisia specifically) is the single
  biggest reason a linear-stride search can fail to find a true conflict
  set even when one exists. If it fails, that is itself worth a sentence in
  the report, not a silently-dropped machine.
- Validate against documentation/PMU results only in Phase II (slide 18's
  last line) -- keep this Phase-I output timing-only and frozen, same rule
  as the other four experiments.

## Makefile addition

```
inclusion_bench: inclusion_bench.cpp
	$(CXX) $(CXXFLAGS) -o $@ $^
```

Add `inclusion_bench` to the `all:` target's prerequisite list, and
`rm -f inclusion_bench` to `clean:`.
