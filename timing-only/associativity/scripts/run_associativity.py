#!/usr/bin/env python3
import subprocess
import os
import pandas as pd
import matplotlib.pyplot as plt

BENCH = "../src/associativity_bench"

# NOTE on LLC: AMD EPYC 7532 (Rome/Zen 2) L3 is per-CCX (shared by 4 cores),
# sliced/hashed, and NOT a single monolithic cache. num_sets below is a
# starting guess (16 MiB CCX slice / (64B line * 16 ways) = 16384 sets) —
# verify empirically, and if the step is fuzzy/partial, report an EFFECTIVE
# bound per the assignment rather than forcing a clean number.
LEVELS = {
    "L1":  {"num_sets": 64,    "max_k": 16, "out": "raw_data/l1_associativity.csv"},
    "L2":  {"num_sets": 512,  "max_k": 20, "out": "raw_data/l2_associativity.csv"},
    "LLC": {"num_sets": 2048, "max_k": 24, "out": "raw_data/llc_associativity.csv"},
}
BASE = {"samples": 1000000, "warmup": 1000, "seed": 701, "line_size": 64, "batch": 128}

os.makedirs("raw_data", exist_ok=True)
os.makedirs("plots", exist_ok=True)

def run_bench(level, num_sets, max_k, outfile):
    if os.path.exists(outfile):
        print(f"Skipping {outfile} (delete it to re-run)")
        return
    # Pin to a single logical CPU. For L2/LLC this MUST be a core you have
    # confirmed shares the target cache domain (check lscpu -e and, for LLC
    # on a multi-CCX part, the CCX/CCD topology) -- pick core 4 as a
    # placeholder, replace with your reserved lab core.
    cmd = ["taskset", "-c", "4", BENCH,
           "--num_sets", str(num_sets),
           "--line_size", str(BASE["line_size"]),
           "--max_k", str(max_k),
           "--samples", str(BASE["samples"]),
           "--warmup", str(BASE["warmup"]),
           "--batch", str(BASE["batch"]),
           "--seed", str(BASE["seed"]),
           "--output", outfile]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)

def collect():
    for level, params in LEVELS.items():
        run_bench(level, params["num_sets"], params["max_k"], params["out"])

def infer_ways(df):
    """First K where eviction probability crosses 0.5 => ways = K-1."""
    step = df[df["eviction_probability"] > 0.5]["K"].min()
    return step

def plot():
    n = len(LEVELS)
    fig, axes = plt.subplots(n, 1, figsize=(7, 4 * n), squeeze=False)
    for idx, (level, params) in enumerate(LEVELS.items()):
        if not os.path.exists(params["out"]):
            continue
        df = pd.read_csv(params["out"])
        ax = axes[idx, 0]
        ax.plot(df["K"], df["eviction_probability"], marker='o')
        ax.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
        ax.set_xlabel("K (conflicting lines)")
        ax.set_ylabel("Eviction probability P")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(False)

        step = infer_ways(df)
        if pd.notna(step):
            ways = int(step) - 1
            ax.axvline(x=step, color='red', linestyle='--', label=f"ways={ways}")
            ax.set_title(f"{level} \u2013 associativity \u2248 {ways}-way")
            ax.legend()
        else:
            ax.set_title(f"{level} \u2013 no clean 50% crossing found "
                         f"(report an effective bound, see assignment \u00a7Associativity)")
    fig.tight_layout()
    plt.savefig("plots/associativity_plot.pdf", bbox_inches='tight')
    plt.close()
    print("Plot saved to plots/associativity_plot.pdf")

if __name__ == "__main__":
    collect()
    plot()