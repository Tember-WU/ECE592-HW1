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

# Default max_k per level. LLC associativity commonly runs higher than L1/L2 (e.g. Zen 2
# L3 is 16-way; some Intel LLCs report an "effective" associativity well above that due to
# slicing/hashing -- Slide 16: "report an effective associativity or bound"), so LLC gets
# a larger default sweep unless overridden in the config.
DEFAULT_MAX_K = {"L1": 16, "L2": 16, "LLC": 24}
LEVEL_MAX_K = {
    level: CFG.get(f"assoc_{level.lower()}_max_k", DEFAULT_MAX_K[level])
    for level in ("L1", "L2", "LLC")
}

LEVEL_CANDIDATES = {
    "L1": CFG["assoc_l1_num_sets_candidates"],
    "L2": CFG["assoc_l2_num_sets_candidates"],
}
# LLC is optional: only run it once assoc_llc_num_sets_candidates is filled in (requires
# an actual measured LLC capacity plateau from Experiment 1 -- do not guess this from
# vendor specs; some machines, e.g. Ampere-based Thunderbird, may not have a traditional
# shared LLC at all, in which case this should stay empty on that machine's config).
if CFG.get("assoc_llc_num_sets_candidates"):
    LEVEL_CANDIDATES["LLC"] = CFG["assoc_llc_num_sets_candidates"]
else:
    print("NOTE: assoc_llc_num_sets_candidates not set in this machine's config -- "
          "skipping LLC associativity. Fill it in (from a real measured LLC capacity "
          "plateau) once available.")

BASE = {"samples": 1000000, "warmup": 1000, "seed": 701, "line_size": 64, "batch": 128}

RAW_DIR = "raw_data"
PLOT_DIR = "plots"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

def candidate_outfile(level, num_sets):
    return os.path.join(RAW_DIR, f"{level.lower()}_associativity_candidate{num_sets}.csv")

def final_outfile(level):
    return os.path.join(RAW_DIR, f"{level.lower()}_associativity.csv")

def boundary_raw_outfile(level):
    return os.path.join(RAW_DIR, f"{level.lower()}_associativity_boundary_raw.csv")

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

def run_bench_boundary_raw(num_sets, max_k, boundary_ks, summary_outfile, raw_outfile):
    """Cheap re-run restricted to just the boundary K's (--only_ks), to get raw per-access
    samples for a real box plot -- the full sweep never keeps raw samples (they'd be huge:
    1e6 samples x up to 16 K's), so this targeted re-run is far cheaper than dumping raw
    data for the entire sweep."""
    if os.path.exists(raw_outfile):
        print(f"Skipping existing {raw_outfile}")
        return
    ks_arg = ",".join(str(k) for k in boundary_ks)
    cmd = ["taskset", "-c", str(PINNED_CPU),
           BENCH,
           "--num_sets", str(num_sets),
           "--line_size", str(BASE["line_size"]),
           "--max_k", str(max_k),
           "--samples", str(BASE["samples"]),
           "--warmup", str(BASE["warmup"]),
           "--batch", str(BASE["batch"]),
           "--seed", str(BASE["seed"]),
           "--output", summary_outfile,
           "--raw_output", raw_outfile,
           "--raw_ks", ks_arg,
           "--only_ks", ks_arg]
    print("Running (boundary raw dump):", " ".join(cmd))
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
        max_k = LEVEL_MAX_K[level]
        selection_report.append(f"=== {level} candidate sweep (max_k={max_k}) ===")
        chosen = None
        for num_sets in candidates:
            outfile = candidate_outfile(level, num_sets)
            run_bench(num_sets, max_k, outfile)
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
                   f"(tried {candidates}, max_k={max_k}). Do NOT report an associativity "
                   f"value for {level} yet -- add more candidates (or raise "
                   f"assoc_{level.lower()}_max_k) in configs/*.json and re-run. Inspect "
                   f"the candidate CSVs in {RAW_DIR}/ to see how far off each was.")
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

            # Get real per-sample distributions at ways-1/ways/ways+1 (clamped to
            # [1, max_k]) for a box plot -- the summary CSV only has one median per K,
            # which cannot support quartiles/whiskers/outliers.
            boundary_ks = sorted(set(k for k in (ways - 1, ways, ways + 1) if 1 <= k <= max_k))
            run_bench_boundary_raw(num_sets, max_k, boundary_ks,
                                    os.path.join(RAW_DIR, f"{level.lower()}_boundary_summary_tmp.csv"),
                                    boundary_raw_outfile(level))

    with open(os.path.join(RAW_DIR, "associativity_candidate_selection.txt"), "w") as f:
        f.write("\n".join(selection_report) + "\n")

def plot():
    n_levels = len(LEVEL_CANDIDATES)
    fig, axes = plt.subplots(n_levels, 2, figsize=(12, 5 * n_levels), squeeze=False)
    for idx, level in enumerate(LEVEL_CANDIDATES):
        final = final_outfile(level)
        if not os.path.exists(final):
            print(f"Skipping plot for {level}: no candidate produced a clean edge yet "
                  f"(see raw_data/associativity_candidate_selection.txt).")
            continue
        df = pd.read_csv(final)
        ax1 = axes[idx, 0]
        ax1.plot(df["K"], df["eviction_probability"], marker='o')
        ax1.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
        ax1.set_xlabel("K (conflicting lines)")
        ax1.set_ylabel("Eviction probability")
        ax1.set_title(f"{level} – Eviction Probability")
        ax1.set_ylim(-0.05, 1.05)
        ax1.grid(False)

        ax2 = axes[idx, 1]
        ax2.plot(df["K"], df["median_latency"], marker='s', color='red')
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

def plot_boundary_boxplots():
    """Box plots of the actual per-access latency DISTRIBUTION for K = boundary-1,
    boundary, boundary+1, using raw samples from run_bench_boundary_raw() -- not the
    single aggregated median that the summary CSV stores."""
    import inspect
    boxplot_kwargs = inspect.signature(plt.Axes.boxplot).parameters
    labels_kw = "tick_labels" if "tick_labels" in boxplot_kwargs else "labels"

    for level in LEVEL_CANDIDATES:
        raw_path = boundary_raw_outfile(level)
        if not os.path.exists(raw_path):
            print(f"Skipping box plot for {level}: no boundary raw data (no clean edge found).")
            continue
        df = pd.read_csv(raw_path)
        ks = sorted(df["K"].unique())
        series = [df[df["K"] == k]["latency_per_access"].to_numpy() for k in ks]

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.boxplot(series, showmeans=True, showfliers=False,
                   **{labels_kw: [f"K={k}" for k in ks]})
        all_vals = df["latency_per_access"].to_numpy()
        ax.set_ylim(all_vals.min() * 0.9, min(all_vals.max(), pd.Series(all_vals).quantile(0.99)) * 1.1)
        ax.set_ylabel("Latency (ticks / access)")
        ax.set_xlabel("K (conflicting lines)")
        ax.set_title(f"{level} associativity: latency distribution near boundary")
        ax.grid(False)
        fig.savefig(os.path.join(PLOT_DIR, f"{level.lower()}_associativity_boxplot.pdf"),
                    bbox_inches='tight')
        plt.close(fig)
        print(f"Box plot saved to {PLOT_DIR}/{level.lower()}_associativity_boxplot.pdf")

if __name__ == "__main__":
    collect()
    plot()
    plot_boundary_boxplots()