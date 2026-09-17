#!/usr/bin/env python3
"""
run_inclusion_experiment.py
Experiment 5: Inclusion / exclusion behavior, per machine (TA slides 17-18).

Workflow (matches slide 18 exactly):
    1. calibrate     -> reference L2 / LLC / DRAM single-access distributions
    2. find_conflict -> empirically search candidate LLC strides for a real
                         conflict set (LLC is physically indexed + often
                         sliced/hashed, so we can't just compute the index
                         like we could for the VIPT L1D in Experiment 3)
    3. test          -> pressure the (candidate) LLC-only set, reload T,
                         classify, repeat over many targets/trials
    4. classify      -> aggregate into a verdict per machine + caveats

Usage (from the scripts/ directory, matching this project's layout):
    python3 run_inclusion_experiment.py --config ../configs/artemisia.json

Each machine gets its own JSON config (see ../configs/*.json). Fill in
the cache geometry fields from your team's Experiment 1-3 results before
running -- this script does NOT look anything up; Phase I stays timing-only.

Pin the process the same way you pinned the line-size/associativity runs:
    taskset -c <CPU> python3 run_inclusion_experiment.py --config ...
(the per-machine core/CPU pins you used are recorded in each config's
"pin" field purely for your own bookkeeping / report table -- this script
does not call taskset itself so it matches how you invoked the other
experiments; wrap the whole command in taskset -c <CPU> yourself.)

Finding the compiled benchmark:
    By default this script looks for the inclusion_bench binary in, in
    order: $INCLUSION_BENCH (if set), ./inclusion_bench, ../src/inclusion_bench,
    ../build/<machine>/inclusion_bench, ./build/<machine>/inclusion_bench,
    where <machine> comes from the config's "machine" field. Override with
    --bench /path/to/inclusion_bench if none of those match your layout.
"""
import argparse
import json
import os
import subprocess
import sys
import glob

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BENCH = None  # resolved in main() via resolve_bench()


def resolve_bench(explicit_path, machine):
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    env_path = os.environ.get("INCLUSION_BENCH")
    if env_path:
        candidates.append(env_path)
    candidates += [
        "./inclusion_bench",
        "../src/inclusion_bench",
        f"../build/{machine}/inclusion_bench",
        f"./build/{machine}/inclusion_bench",
        f"../build/{machine}",   # tree shows build/<machine> as a bare filename
        f"./build/{machine}",
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    tried = "\n  ".join(candidates)
    print(f"ERROR: could not find an executable inclusion_bench for machine '{machine}'. Tried:\n  {tried}\n"
          f"Build it, e.g.:\n"
          f"  cd ../src && g++ -O0 -g -std=c++11 -m64 -Wall -Wextra -fno-omit-frame-pointer "
          f"-o inclusion_bench inclusion_bench.cpp\n"
          f"or pass --bench /path/to/inclusion_bench, or set $INCLUSION_BENCH.")
    sys.exit(1)


def run(cmd):
    print("Running:", " ".join(str(x) for x in cmd))
    subprocess.check_call([str(x) for x in cmd])


def step_sweep_capacity(cfg, outdir):
    """Self-contained mini Experiment-1 sweep so we don't need your team's
    Experiment 1 numbers (or need them to be correct) to find the L2->LLC
    and LLC->DRAM boundaries. Finds the two biggest steps in the
    median-latency-vs-footprint curve.
    """
    outfile = os.path.join(outdir, "capacity_sweep.csv")
    if not os.path.exists(outfile):
        run([
            BENCH, "--mode", "sweep_capacity", "--output", outfile,
            "--min_bytes", cfg.get("sweep_min_bytes", 16 * 1024),
            "--max_bytes", cfg.get("sweep_max_bytes", 128 * 1024 * 1024),
            "--line_size", cfg["line_size"],
            "--sc_batch", cfg.get("sweep_batch", 512),
            "--sc_samples", cfg.get("sweep_samples", 2000),
            "--warmup", cfg.get("warmup_laps", 1000),
            "--seed", cfg.get("seed", 701),
        ])
    df = pd.read_csv(outfile)
    df = df.sort_values("footprint_bytes").reset_index(drop=True)
    df["log_lat"] = np.log(df["median_ticks_per_access"])
    df["step"] = df["log_lat"].diff()
    # two largest jumps = L1/L2 boundary + L2/LLC boundary + LLC/DRAM boundary
    # (there may be 2 or 3 depending on machine; take the two biggest steps
    # that occur in the *upper* half of the swept range, since the smallest
    # footprints are almost certainly still inside L1 and not what we want).
    candidates = df.iloc[2:].sort_values("step", ascending=False)
    top = candidates.head(4).sort_index()
    print("Capacity sweep (footprint_bytes, median_ticks_per_access, step):")
    print(df[["footprint_bytes", "median_ticks_per_access", "step"]].to_string(index=False))
    print("\nBiggest latency jumps found at footprints:",
          list(top["footprint_bytes"]))

    steps_sorted = candidates.sort_values("step", ascending=False)
    jump_idxs = sorted(steps_sorted.head(2).index)
    if len(jump_idxs) < 2:
        raise RuntimeError(
            "Could not find two clear latency steps in the capacity sweep. "
            "Widen sweep_min_bytes/sweep_max_bytes in the config and re-run.")
    # boundary = last footprint BEFORE the jump
    l2_or_below_boundary_idx = jump_idxs[0] - 1
    llc_boundary_idx = jump_idxs[1] - 1
    llc_bytes = int(df.loc[llc_boundary_idx, "footprint_bytes"])
    l2_bytes = int(df.loc[l2_or_below_boundary_idx, "footprint_bytes"])
    dram_bytes = int(df["footprint_bytes"].max())
    if dram_bytes < 4 * llc_bytes:
        print("WARNING: swept max_bytes is not >=4x the detected LLC size; "
              "widen sweep_max_bytes in the config for a cleaner DRAM reference.")
    print(f"Auto-detected: l2_bytes~={l2_bytes} llc_bytes~={llc_bytes} dram_bytes={dram_bytes}")
    return {"l2_bytes": l2_bytes, "llc_bytes": llc_bytes, "dram_bytes": dram_bytes}


def step_calibrate(cfg, outdir, detected):
    outfile = os.path.join(outdir, "calibration.csv")
    l2_bytes = cfg["l2_bytes"] if cfg.get("l2_bytes") not in (None, "auto") else detected["l2_bytes"]
    llc_bytes = cfg["llc_bytes"] if cfg.get("llc_bytes") not in (None, "auto") else detected["llc_bytes"]
    dram_bytes = cfg["dram_bytes"] if cfg.get("dram_bytes") not in (None, "auto") else detected["dram_bytes"]
    if os.path.exists(outfile):
        print(f"Skipping existing {outfile}")
        return outfile
    run([
        BENCH, "--mode", "calibrate", "--output", outfile,
        "--l2_bytes", l2_bytes,
        "--llc_bytes", llc_bytes,
        "--dram_bytes", dram_bytes,
        "--line_size", cfg["line_size"],
        "--cal_samples", cfg.get("cal_samples", 200000),
        "--warmup", cfg.get("warmup_laps", 1000),
        "--seed", cfg.get("seed", 701),
    ])
    return outfile


def compute_thresholds(calibration_csv):
    df = pd.read_csv(calibration_csv)
    meds = df.groupby("class")["ticks"].median()
    l2_med, llc_med, dram_med = meds["L2"], meds["LLC"], meds["DRAM"]
    l2_dram_boundary = (l2_med + llc_med) / 2.0
    llc_dram_boundary = (llc_med + dram_med) / 2.0
    print(f"medians: L2={l2_med:.1f} LLC={llc_med:.1f} DRAM={dram_med:.1f} ticks")
    print(f"boundaries: L2/LLC={l2_dram_boundary:.1f}  LLC/DRAM={llc_dram_boundary:.1f}")
    return {
        "l2_median": float(l2_med), "llc_median": float(llc_med), "dram_median": float(dram_med),
        "l2_dram_boundary": float(l2_dram_boundary), "llc_dram_boundary": float(llc_dram_boundary),
    }


def auto_generate_conflict_candidates(detected_llc_bytes, line_size):
    """When a config doesn't specify explicit strides/K (or sets them to
    "auto"), generate a broad search grid from the auto-detected LLC size
    alone -- no associativity numbers needed, right or wrong. We guess a
    range of plausible LLC set counts (256 to 16384, covering basically
    every real LLC on machines this old-to-new) and derive a stride for
    each: stride = llc_bytes / guessed_sets. This is exactly the "search
    empirically for mutually conflicting addresses" approach slide 16
    calls for when index bits aren't known.
    """
    guessed_set_counts = [256, 512, 1024, 2048, 4096, 8192, 16384]
    strides = sorted(set(
        max(line_size, (detected_llc_bytes // sets) - (detected_llc_bytes // sets) % line_size)
        for sets in guessed_set_counts
    ))
    k_values = [2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32]
    return strides, k_values


def step_find_conflict(cfg, outdir, thresholds, detected):
    """Sweep candidate strides x K, looking for eviction_probability -> 1
    once K exceeds the (unknown, empirically discovered) LLC ways, and ~0
    below it. Writes one CSV per (stride,K) plus a summary CSV you should
    inspect before trusting `test`. Does NOT require knowing LLC
    associativity in advance -- that is what this search finds out.
    """
    results = []
    fc_dir = os.path.join(outdir, "find_conflict")
    os.makedirs(fc_dir, exist_ok=True)
    llc_hit_thresh = int(round(thresholds["llc_median"] * 1.3))  # generous "still an LLC hit" cutoff
    dram_thresh = int(round(thresholds["dram_median"] * 0.9))

    strides_cfg = cfg.get("candidate_llc_strides")
    k_cfg = cfg.get("candidate_k_values")
    if not strides_cfg or strides_cfg == "auto" or (isinstance(strides_cfg, list) and "auto" in strides_cfg):
        strides_cfg, auto_k = auto_generate_conflict_candidates(detected["llc_bytes"], cfg["line_size"])
        if not k_cfg or k_cfg == "auto":
            k_cfg = auto_k
        print(f"Auto-generated candidate strides: {strides_cfg}")
        print(f"Auto-generated candidate K values: {k_cfg}")
    if not k_cfg or k_cfg == "auto":
        k_cfg = [2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32]

    for stride in strides_cfg:
        for k in k_cfg:
            fname = f"stride{stride}_k{k}.csv"
            outfile = os.path.join(fc_dir, fname)
            if not os.path.exists(outfile):
                run([
                    BENCH, "--mode", "find_conflict", "--output", outfile,
                    "--candidate_stride", stride, "--k", k,
                    "--fc_samples", cfg.get("fc_samples", 20000),
                    "--llc_hit_thresh", llc_hit_thresh,
                    "--dram_thresh", dram_thresh,
                    "--seed", cfg.get("seed", 701),
                ])
            df = pd.read_csv(outfile)
            prob = df["classified_evicted"].mean()
            results.append({"stride": stride, "k": k, "eviction_probability": prob})
            print(f"  stride={stride} k={k} -> eviction_probability={prob:.3f}")

    summary = pd.DataFrame(results)
    summary.to_csv(os.path.join(outdir, "find_conflict_summary.csv"), index=False)
    return summary, strides_cfg, k_cfg


def pick_best_conflict(summary, min_k_for_llc=8):
    """Heuristic pick: among strides where eviction_probability is low for
    K <= min_k_for_llc (a K you believe fits within LLC ways) and high for
    larger K, pick the stride with the sharpest jump. You should eyeball
    find_conflict_summary.csv yourself too -- this is a starting point, not
    a substitute for judgement (per the TA note: a well-argued caveated
    answer beats a confident wrong one).

    Always returns an integer suggested_pressure_k when a stride is picked
    at all (never None): if no K crossed the 0.8 eviction-probability
    cutoff, we fall back to the largest K tested for that stride, on the
    logic that more pressure lines can only help evict, never hurt.
    """
    best = None
    best_gap = -1
    for stride, group in summary.groupby("stride"):
        group = group.sort_values("k")
        low = group[group["k"] <= min_k_for_llc]["eviction_probability"]
        high = group[group["k"] > min_k_for_llc]["eviction_probability"]
        if low.empty or high.empty:
            continue
        gap = high.max() - low.min()
        if gap > best_gap:
            best_gap = gap
            crossed = group[group["eviction_probability"] > 0.8]["k"]
            best_k = int(crossed.min()) if not crossed.empty else int(group["k"].max())
            best = {"stride": int(stride), "gap": gap, "suggested_pressure_k": best_k}
    return best, best_gap


def step_test(cfg, outdir, thresholds, llc_stride, pressure_k):
    outfile = os.path.join(outdir, "inclusion_trials.csv")
    if os.path.exists(outfile):
        print(f"Skipping existing {outfile}")
        return outfile
    run([
        BENCH, "--mode", "test", "--output", outfile,
        "--llc_stride", llc_stride,
        "--pressure_k", pressure_k,
        "--l2_sets", (cfg.get("l2_sets", 0) if cfg.get("l2_sets") not in (None, "auto") else 0),
        "--num_targets", cfg.get("num_targets", 20),
        "--num_trials", cfg.get("num_trials", 2000),
        "--warmup", cfg.get("warmup_laps", 1000),
        "--seed", cfg.get("seed", 701),
        "--l2_dram_boundary", int(round(thresholds["l2_dram_boundary"])),
        "--llc_dram_boundary", int(round(thresholds["llc_dram_boundary"])),
    ])
    return outfile


def classify_and_report(machine, outdir, thresholds, conflict_pick, trials_csv):
    df = pd.read_csv(trials_csv)
    total = len(df)
    frac_l2 = (df["classification"] == "L2_hit").mean()
    frac_llc = (df["classification"] == "LLC_hit").mean()
    frac_dram = (df["classification"] == "DRAM").mean()

    contaminated = 0
    if "l2_set_index_of_target" in df.columns:
        contaminated = int((df["l2_set_index_of_target"] == df["l2_set_index_min_pressure_line"]).sum())

    if frac_dram > 0.7:
        verdict = "Evidence consistent with INCLUSIVE LLC (T back-invalidated on LLC eviction)"
    elif frac_l2 > 0.7:
        verdict = "Evidence consistent with NON-INCLUSIVE / exclusive-like LLC (inner copy survived)"
    else:
        verdict = "MIXED / ambiguous -- report as a behavioral bound, not a clean label"

    report = {
        "machine": machine,
        "n_trials": int(total),
        "fraction_L2_hit": float(frac_l2),
        "fraction_LLC_hit": float(frac_llc),
        "fraction_DRAM": float(frac_dram),
        "l2_median_ticks": thresholds["l2_median"],
        "llc_median_ticks": thresholds["llc_median"],
        "dram_median_ticks": thresholds["dram_median"],
        "l2_dram_boundary_ticks": thresholds["l2_dram_boundary"],
        "llc_dram_boundary_ticks": thresholds["llc_dram_boundary"],
        "llc_conflict_stride_bytes": conflict_pick["stride"] if conflict_pick else None,
        "pressure_k_used": conflict_pick["suggested_pressure_k"] if conflict_pick else None,
        "possibly_l2_contaminated_target_regions": contaminated,
        "verdict": verdict,
    }
    with open(os.path.join(outdir, "inclusion_report.json"), "w") as f:
        json.dump(report, f, indent=2)

    # Plot: fraction of trials in each class, and calibration reference
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].bar(["L2_hit", "LLC_hit", "DRAM"], [frac_l2, frac_llc, frac_dram])
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Fraction of reload trials")
    axes[0].set_title(f"{machine}: T reload after LLC-only pressure")

    cal = pd.read_csv(os.path.join(outdir, "calibration.csv"))
    for cls, color in [("L2", "tab:blue"), ("LLC", "tab:orange"), ("DRAM", "tab:green")]:
        vals = cal[cal["class"] == cls]["ticks"]
        axes[1].hist(vals, bins=80, alpha=0.5, label=cls, density=True)
    axes[1].axvline(thresholds["l2_dram_boundary"], color="k", linestyle="--", linewidth=1)
    axes[1].axvline(thresholds["llc_dram_boundary"], color="k", linestyle="--", linewidth=1)
    axes[1].set_xlabel("Single-access ticks")
    axes[1].set_title("Calibration reference distributions")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "inclusion_summary.pdf"), bbox_inches="tight")
    plt.close(fig)

    print(json.dumps(report, indent=2))
    return report


def main():
    global BENCH
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="path to a config JSON, e.g. ../configs/artemisia.json")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--bench", default=None, help="explicit path to the compiled inclusion_bench binary")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)
    machine = cfg["machine"]
    outdir = args.outdir or os.path.join("raw_data_inclusion", machine)
    os.makedirs(outdir, exist_ok=True)

    BENCH = resolve_bench(args.bench, machine)
    print(f"Using inclusion_bench: {BENCH}")

    detected = {"l2_bytes": None, "llc_bytes": None, "dram_bytes": None}
    needs_sweep = any(cfg.get(k) in (None, "auto") for k in ("l2_bytes", "llc_bytes", "dram_bytes")) \
        or cfg.get("candidate_llc_strides") in (None, "auto") \
        or (isinstance(cfg.get("candidate_llc_strides"), list) and "auto" in cfg["candidate_llc_strides"])
    if needs_sweep:
        print(f"=== {machine} : sweep_capacity (auto-detecting L2/LLC/DRAM sizes) ===")
        detected = step_sweep_capacity(cfg, outdir)

    print(f"=== {machine} : calibrate ===")
    cal_csv = step_calibrate(cfg, outdir, detected)
    thresholds = compute_thresholds(cal_csv)

    print(f"=== {machine} : find_conflict sweep ===")
    summary, resolved_strides, resolved_k_values = step_find_conflict(cfg, outdir, thresholds, detected)
    min_k = cfg.get("assumed_llc_ways_upper_bound")
    if min_k in (None, "auto") or not isinstance(min_k, int):
        min_k = 8
    conflict_pick, gap = pick_best_conflict(summary, min_k)
    if conflict_pick is None:
        print("WARNING: no candidate stride produced ANY usable low/high split at "
              f"min_k_for_llc={min_k}. Add more strides/K values to the config's candidate "
              "lists and re-run before trusting a `test` result. Falling back to the "
              "largest swept stride/K as a best-effort choice.")
        conflict_pick = {"stride": resolved_strides[-1], "suggested_pressure_k": max(resolved_k_values)}
    elif gap < 0.5:
        print(f"WARNING: best eviction-probability gap found was only {gap:.3f} (want closer to "
              "1.0). This stride/K did not produce a clean eviction jump; treat the `test` "
              "result as a behavioral bound, not a confirmed conflict set. Add more strides/K "
              "values to the config and re-run for a cleaner result if time allows.")
    print(f"Selected llc_stride={conflict_pick['stride']} pressure_k={conflict_pick['suggested_pressure_k']} (gap={gap:.3f})")

    print(f"=== {machine} : test (pressure + reload) ===")
    trials_csv = step_test(cfg, outdir, thresholds, conflict_pick["stride"], conflict_pick["suggested_pressure_k"])

    print(f"=== {machine} : classify ===")
    classify_and_report(machine, outdir, thresholds, conflict_pick, trials_csv)


if __name__ == "__main__":
    main()