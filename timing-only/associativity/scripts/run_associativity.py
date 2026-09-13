#!/usr/bin/env python3
"""
run_associativity.py

Sweeps candidate `num_sets` values per cache level (from configs/<hostname>.json) and
auto-selects whichever candidate produces a clean, sharp eviction-probability transition
(handout Figure 8 shape: eviction jumps from ~0 to ~1 across one or two K steps). This
implements the "search empirically for mutually conflicting addresses" guidance from the
TA slides (Slide 16) rather than assuming a single num_sets value is correct.

L1 candidates rely on the VIPT/huge-page trick (associativity_bench now always requests
huge pages) and are generally low-risk. L2 is physically indexed, so the true num_sets is
genuinely unknown until a candidate demonstrates a real edge in your own data -- do not
report an associativity number from a candidate that never showed a clean transition.
"""
import subprocess
import os
import socket
import json
import pandas as pd
import matplotlib.pyplot as plt

BENCH = "../src/associativity_bench"

def load_machine_config():
    """Load configs/<hostname>.json. Searches several plausible locations since repo
    layouts vary (e.g. scripts/ and configs/ as siblings under an experiment directory),
    rather than assuming run_associativity.py sits next to configs/. Override with the
    ASSOC_CONFIG_DIR environment variable if none of these match your layout."""
    hostname = socket.gethostname().split(".")[0].lower()
    script_dir = os.path.dirname(os.path.abspath(__file__))

    search_dirs = []
    if os.environ.get("ASSOC_CONFIG_DIR"):
        search_dirs.append(os.environ["ASSOC_CONFIG_DIR"])
    search_dirs += [
        os.path.join(script_dir, "configs"),               # configs/ next to this script
        os.path.join(script_dir, "..", "configs"),          # scripts/ and configs/ as siblings
        os.path.join(script_dir, "..", "..", "configs"),    # one level deeper (e.g. timing-only/associativity/scripts)
        os.path.join(os.getcwd(), "configs"),               # configs/ under current working dir
    ]

    tried = []
    for d in search_dirs:
        candidate = os.path.join(os.path.abspath(d), f"{hostname}.json")
        tried.append(candidate)
        if os.path.exists(candidate):
            print(f"Hostname: {hostname}")
            print(f"Loading config: {candidate}")
            with open(candidate) as f:
                cfg = json.load(f)
            required = ("pinned_cpu", "assoc_l1_num_sets_candidates", "assoc_l2_num_sets_candidates")
            missing = [k for k in required if not cfg.get(k)]
            if missing:
                raise SystemExit(
                    f"{candidate} is missing {missing}. Run Experiment 1 (capacity) and "
                    f"Experiment 2 (line size) on {hostname} first, then fill these candidate "
                    f"lists in from THIS host's own results before running the associativity "
                    f"sweep here."
                )
            return cfg

    raise SystemExit(
        f"No config found for hostname '{hostname}'. Looked in:\n  " +
        "\n  ".join(tried) +
        "\nSet ASSOC_CONFIG_DIR=/path/to/configs if your layout differs, or move "
        f"{hostname}.json into one of the paths above."
    )

CFG = load_machine_config()
PINNED_CPU = CFG["pinned_cpu"]
PINNED_CORE = CFG.get("pinned_core")
PINNED_SOCKET = CFG.get("pinned_socket")
PINNED_NODE = CFG.get("pinned_node")

MAX_K = 16
LEVEL_CANDIDATES = {
    "L1": CFG["assoc_l1_num_sets_candidates"],
    "L2": CFG["assoc_l2_num_sets_candidates"],
}
BASE = {"samples": 1000000, "warmup": 1000, "seed": 701, "line_size": 64, "batch": 128}

RAW_DIR = "raw_data"
PLOT_DIR = "plots"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

def candidate_outfile(level, num_sets):
    return os.path.join(RAW_DIR, f"{level.lower()}_associativity_candidate{num_sets}.csv")

def final_outfile(level):
    return os.path.join(RAW_DIR, f"{level.lower()}_associativity.csv")

def run_bench(num_sets, max_k, outfile):
    if os.path.exists(outfile):
        print(f"Skipping existing {outfile}")
        return
    cmd = ["taskset", "-c", str(PINNED_CPU),
           BENCH,
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

def edge_quality(df):
    """Score how 'clean' the eviction-probability transition is: (has_edge, ways, jump_size).
    A clean edge means probability starts low (<0.2), ends high (>0.8), and the single
    largest step between consecutive K values is >=0.5 (a sharp jump, not a slow ramp)."""
    p = df.sort_values("K")["eviction_probability"].to_numpy()
    k = df.sort_values("K")["K"].to_numpy()
    if len(p) < 2:
        return False, None, 0.0
    starts_low = p[0] < 0.2
    ends_high = p[-1] > 0.8
    diffs = p[1:] - p[:-1]
    jump_idx = diffs.argmax()
    jump_size = diffs[jump_idx]
    ways = int(k[jump_idx])  # last K with low eviction prob = inferred number of ways
    has_edge = starts_low and ends_high and jump_size >= 0.5
    return has_edge, ways, float(jump_size)

def collect():
    manifest_path = os.path.join(RAW_DIR, "pinning_manifest.txt")
    with open(manifest_path, "w") as f:
        f.write(f"pinned_cpu={PINNED_CPU}\n")
        f.write(f"pinned_core={PINNED_CORE}\n")
        f.write(f"pinned_socket={PINNED_SOCKET}\n")
        f.write(f"pinned_node={PINNED_NODE}\n")
        f.write("smt_sibling=none (CPU==CORE for all rows in lscpu -e topology)\n")
        f.write(f"affinity_method=taskset -c {PINNED_CPU}\n")

    selection_report = []
    for level, candidates in LEVEL_CANDIDATES.items():
        selection_report.append(f"=== {level} candidate sweep ===")
        chosen = None
        for num_sets in candidates:
            outfile = candidate_outfile(level, num_sets)
            run_bench(num_sets, MAX_K, outfile)
            df = pd.read_csv(outfile)
            has_edge, ways, jump = edge_quality(df)
            line = (f"num_sets={num_sets}: has_edge={has_edge} inferred_ways={ways} "
                    f"largest_jump={jump:.3f}")
            print(line)
            selection_report.append(line)
            if has_edge and chosen is None:
                chosen = (num_sets, outfile, ways)
        if chosen is None:
            msg = (f"WARNING: no candidate for {level} produced a clean edge "
                   f"(tried {candidates}). Do NOT report an associativity value for "
                   f"{level} yet -- add more candidates to configs/*.json and re-run. "
                   f"Inspect the candidate CSVs in {RAW_DIR}/ to see how far off each was.")
            print(msg)
            selection_report.append(msg)
        else:
            num_sets, outfile, ways = chosen
            final = final_outfile(level)
            pd.read_csv(outfile).to_csv(final, index=False)
            msg = (f"SELECTED {level}: num_sets={num_sets} -> inferred ways={ways} "
                   f"(copied {outfile} -> {final})")
            print(msg)
            selection_report.append(msg)

    with open(os.path.join(RAW_DIR, "associativity_candidate_selection.txt"), "w") as f:
        f.write("\n".join(selection_report) + "\n")

def plot():
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    for idx, level in enumerate(LEVEL_CANDIDATES):
        final = final_outfile(level)
        if not os.path.exists(final):
            print(f"Skipping plot for {level}: no candidate produced a clean edge yet "
                  f"(see raw_data/associativity_candidate_selection.txt).")
            continue
        df = pd.read_csv(final)
        ax1 = axes[idx, 0]
        ax1.plot(df["K"].to_numpy(), df["eviction_probability"].to_numpy(), marker='o')
        ax1.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
        ax1.set_xlabel("K (conflicting lines)")
        ax1.set_ylabel("Eviction probability")
        ax1.set_title(f"{level} – Eviction Probability")
        ax1.set_ylim(-0.05, 1.05)
        ax1.grid(False)

        ax2 = axes[idx, 1]
        ax2.plot(df["K"].to_numpy(), df["median_latency"].to_numpy(), marker='s')
        ax2.set_xlabel("K")
        ax2.set_ylabel("Median latency (ticks/access)")
        ax2.set_title(f"{level} – Median Latency")
        ax2.grid(False)

        step = df[df["eviction_probability"] > 0.5]["K"].min()
        if pd.notna(step):
            ax1.axvline(x=step, color='red', linestyle='--', label=f"ways={step-1}")
            ax1.legend()
            ax2.axvline(x=step, color='red', linestyle='--')
    fig.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, "associativity_plot.pdf"), bbox_inches='tight')
    plt.close()
    print(f"Plot saved to {PLOT_DIR}/associativity_plot.pdf")

if __name__ == "__main__":
    collect()
    plot()