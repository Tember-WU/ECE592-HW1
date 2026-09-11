#!/usr/bin/env python3
"""
run_line_size_experiment.py
- Runs line_size_bench for initial sweep, dense sweep, and controls.
- Computes per-stride statistics (median, mean, std, quartiles, percentiles).
- Generates:
    * latency_vs_stride.pdf (initial + dense)
    * boxplots_representative.pdf (just below/at/above the candidate)
    * control_comparison.pdf (random vs sequential vs fully random)
- Also saves stats to CSV.
"""

import subprocess
import os
import sys
import glob
import socket
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# ============ Configuration ============
BENCH_EXE = "../src/line_size_bench"

def load_machine_config():
    """Load configs/<hostname>.json. Every machine (Sunbird, Charnwood, Ookay, Upgrade,
    Crux, Skylark, Thunderbird, Artemisia) needs its own file -- see configs/skylark.json
    for a filled-in example and the other configs/*.json files for templates. Pinning
    (§5) and cache-geometry assumptions (§8.2) are per-machine, not shared across hosts."""
    hostname = socket.gethostname().split(".")[0].lower()
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "configs",
        f"{hostname}.json"
    )   
    if not os.path.exists(path):
        raise SystemExit(
            f"No config found at {path}. Copy a template from configs/, run "
            f"`lscpu -e=CPU,CORE,SOCKET,NODE` on this host, and fill in pinned_cpu/core/"
            f"socket/node before running here."
        )
    with open(path) as f:
        cfg = json.load(f)
    if cfg.get("pinned_cpu") is None:
        raise SystemExit(f"configs/{hostname}.json has pinned_cpu=null -- fill it in first.")
    return cfg

CFG = load_machine_config()
PINNED_CPU = CFG["pinned_cpu"]
PINNED_CORE = CFG.get("pinned_core")
PINNED_SOCKET = CFG.get("pinned_socket")
PINNED_NODE = CFG.get("pinned_node")
# Grouping window (bytes) for random_lines/sequential_lines traversal order -- must be >=
# the largest stride tested anywhere in the sweeps below. NOT a guess at the real
# cache-line size (see line_size_bench.cpp build_chain() for why hardcoding this to the
# candidate answer, e.g. 64, would bias the result).
GROUP_WINDOW = CFG.get("line_size_group_window", 512)

BASE_PARAMS = {
    "footprint": 262144,   # 256 KiB
    "batch": 1024,
    "samples": 1000000,
    "warmup": 1000,
    "seed": 701,
}

# Grouping window (bytes) used to control traversal order in random_lines/sequential_lines
# mode. This must be >= the largest stride tested anywhere in the sweeps below (512 B here).
# It is NOT a guess at the real cache-line size -- see line_size_bench.cpp build_chain() for
# why hardcoding this to the candidate answer (e.g. 64) would bias the result.
GROUP_WINDOW = 512

# Sweeps: (name, list_of_strides, alignments, mode)
SWEEPS = {
    "initial": {
        "strides": [8, 16, 32, 64, 128, 256, 512],
        "alignments": [0, 16, 32, 48],
        "mode": "random_lines",
        "seed_offset": 0,
    },
    "dense": {
        "strides": [48, 56, 60, 64, 68, 72, 80, 96],
        "alignments": [0, 16, 32, 48],
        "mode": "random_lines",
        "seed_offset": 10,
    },
    "control_random": {
        "strides": [8, 64],
        "alignments": [0],
        "mode": "fully_random",
        "seed_offset": 20,
    },
    "control_sequential": {
        "strides": [8, 16, 32, 64, 128, 256, 512, 56, 72],
        "alignments": [0],
        "mode": "sequential_lines",
        "seed_offset": 30,
    },
}

# Output directories
RAW_DIR = "raw_data"
STATS_DIR = "stats"
PLOT_DIR = "plots"
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(STATS_DIR, exist_ok=True)
os.makedirs(PLOT_DIR, exist_ok=True)

# ============ Run benchmarks ============
def run_bench(stride, alignment, mode, seed_offset, outfile):
    seed = BASE_PARAMS["seed"] + seed_offset
    cmd = [
        "taskset", "-c", str(PINNED_CPU),
        BENCH_EXE,
        "--stride", str(stride),
        "--alignment", str(alignment),
        "--footprint", str(BASE_PARAMS["footprint"]),
        "--batch", str(BASE_PARAMS["batch"]),
        "--samples", str(BASE_PARAMS["samples"]),
        "--warmup", str(BASE_PARAMS["warmup"]),
        "--seed", str(seed),
        "--mode", mode,
        "--group_window", str(GROUP_WINDOW),
        "--output", outfile,
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

def collect_data():
    # Record the affinity/topology info once per run for traceability (handout §12:
    # "record CPU, core, socket/package, and NUMA node" next to the raw data).
    manifest_path = os.path.join(RAW_DIR, "pinning_manifest.txt")
    with open(manifest_path, "w") as f:
        f.write(f"pinned_cpu={PINNED_CPU}\n")
        f.write(f"pinned_core={PINNED_CORE}\n")
        f.write(f"pinned_socket={PINNED_SOCKET}\n")
        f.write(f"pinned_node={PINNED_NODE}\n")
        f.write("smt_sibling=none (CPU==CORE for all rows in lscpu -e topology)\n")
        f.write(f"affinity_method=taskset -c {PINNED_CPU}\n")
    for sweep_name, sweep in SWEEPS.items():
        for stride in sweep["strides"]:
            for alignment in sweep["alignments"]:
                # Build output filename
                fname = f"{sweep_name}_stride{stride}_align{alignment}_mode{sweep['mode']}.csv"
                outpath = os.path.join(RAW_DIR, fname)
                # Avoid re-running if already exists (optional)
                if os.path.exists(outpath):
                    print(f"Skipping existing: {outpath}")
                    continue
                run_bench(stride, alignment, sweep["mode"], sweep["seed_offset"], outpath)

# ============ Statistics computation ============
def compute_stats():
    all_stats = []
    for fpath in glob.glob(os.path.join(RAW_DIR, "*.csv")):
        df = pd.read_csv(fpath, header=None, names=["delta"])
        data = df["delta"].values
        # Convert delta to latency per access (ticks/access)
        lat_per_acc = data / BASE_PARAMS["batch"]
        # Compute statistics
        q1 = np.percentile(lat_per_acc, 25)
        q3 = np.percentile(lat_per_acc, 75)
        stats_dict = {
            "file": os.path.basename(fpath),
            "median": np.median(lat_per_acc),
            "mean": np.mean(lat_per_acc),
            "std": np.std(lat_per_acc),
            "q1": q1,
            "q3": q3,
            "p5": np.percentile(lat_per_acc, 5),
            "p95": np.percentile(lat_per_acc, 95),
            "outliers": np.sum(
                (lat_per_acc < q1 - 1.5 * (q3 - q1)) |
                (lat_per_acc > q3 + 1.5 * (q3 - q1))
            ),
        }
        # Also parse parameters from filename: e.g., initial_stride64_align0_mode.csv
        filename = os.path.basename(fpath).replace(".csv", "")

        sweep_name = filename.split("_stride")[0]

        stride_part = filename.split("_stride")[1]
        stride_str = stride_part.split("_align")[0]

        # Check if stride is numeric
        if not stride_str.isdigit():
            print(f"Skipping file with invalid stride: {filename}")
            continue

        stride = int(stride_str)

        alignment_part = stride_part.split("_align")[1]
        alignment = int(alignment_part.split("_mode")[0])

        mode = filename.split("_mode")[1]
        stats_dict["sweep"] = sweep_name
        stats_dict["stride"] = stride
        stats_dict["alignment"] = alignment
        stats_dict["mode"] = mode
        all_stats.append(stats_dict)
    # Save to CSV
    df_stats = pd.DataFrame(all_stats)
    df_stats.to_csv(os.path.join(STATS_DIR, "all_stats.csv"), index=False)
    return df_stats

# ============ Plotting ============
def plot_latency_vs_stride(df_stats):
    # Initial and dense sweeps: median with error bars (Q1-Q3)
    fig, ax = plt.subplots(figsize=(10,6))
    for sweep in ["initial", "dense"]:
        sub = df_stats[df_stats["sweep"] == sweep]
        # Aggregate over alignments: use median of medians, and range of Q1/Q3 across alignments
        grouped = sub.groupby("stride").agg({
            "median": "median",
            "q1": "min",    # min over alignments
            "q3": "max",    # max over alignments
        }).reset_index()
        ax.errorbar(grouped["stride"], grouped["median"],
                    yerr=[grouped["median"]-grouped["q1"], grouped["q3"]-grouped["median"]],
                    marker='o', capsize=3, label=sweep)
    ax.set_xscale('log', base=2)
    ax.set_xlabel("Stride (bytes)")
    ax.set_ylabel("Median latency (TSC ticks / access)")
    ax.axvline(x=64, color='gray', linestyle='--', label="64 B (candidate)")
    ax.legend()
    ax.grid(False)
    fig.savefig(os.path.join(PLOT_DIR, "latency_vs_stride.pdf"), bbox_inches='tight')
    plt.close(fig)

def plot_boxplots_representative(df_stats):
    # Choose three strides: just below (56), at (64), just above (72)
    # For random_lines mode, alignment=0 only for clarity
    sub = df_stats[(df_stats["sweep"] == "dense") &
                   (df_stats["alignment"] == 0) &
                   (df_stats["mode"] == "random_lines") &
                   (df_stats["stride"].isin([56,64,72]))]

    # Load raw data for these combinations
    data_files = {
        56: os.path.join(RAW_DIR, "dense_stride56_align0_moderandom_lines.csv"),
        64: os.path.join(RAW_DIR, "dense_stride64_align0_moderandom_lines.csv"),
        72: os.path.join(RAW_DIR, "dense_stride72_align0_moderandom_lines.csv"),
    }

    data = {}
    for stride, file_path in data_files.items():
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}. Skipping stride {stride}.")
            continue
        data[stride] = pd.read_csv(file_path, header=None)[0].values / BASE_PARAMS["batch"]

    # Ensure we have data for all strides before plotting
    if len(data) < 3:
        print("Warning: Not enough data to plot boxplots. Skipping.")
        return

    labels = ["56 B", "64 B", "72 B"]
    series = [data[56], data[64], data[72]]

    # Outlier counts (IQR rule) are computed and reported separately -- the required "number
    # of outliers" per §5 -- rather than rendered as hundreds of overlapping circles, which
    # crushed the box+whisker detail against the axis before.
    outlier_counts = []
    for vals in series:
        q1, q3 = np.percentile(vals, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outlier_counts.append(int(np.sum((vals < lo) | (vals > hi))))

    fig, ax = plt.subplots(figsize=(8, 6))
    # showfliers=False: outliers are excluded from the drawing only, not from the stats;
    # median/mean/Q1/Q3/whiskers below are still computed from the full 1e6-sample dataset.
    bp = ax.boxplot(series, labels=labels, showmeans=True, showfliers=False)
    # Zoom the y-axis to the p1-p99 range across all three so the boxes stay readable.
    all_vals = np.concatenate(series)
    ax.set_ylim(np.percentile(all_vals, 1) * 0.95, np.percentile(all_vals, 99) * 1.05)
    ax.set_ylabel("Latency (TSC ticks / access)")
    ax.set_title("Latency distributions near candidate line size")
    for i, (lab, n_out) in enumerate(zip(labels, outlier_counts), start=1):
        ax.annotate(f"n_outliers={n_out}", xy=(i, ax.get_ylim()[1]), xytext=(0, -14),
                    textcoords="offset points", ha="center", fontsize=8, color="gray")
    fig.savefig(os.path.join(PLOT_DIR, "boxplots_representative.pdf"), bbox_inches='tight')
    plt.close(fig)

def plot_control_comparison(df_stats):
    # Compare random_lines vs fully_random vs sequential for a couple of strides
    fig, axes = plt.subplots(1, 2, figsize=(12,5))
    for i, stride in enumerate([8, 64]):
        ax = axes[i]
        sub = df_stats[(df_stats["stride"] == stride) & (df_stats["alignment"] == 0)]
        # group by mode, compute median and Q1/Q3 across alignments? but only alignment 0, so just one point
        modes = sub["mode"].unique()
        medians = []
        errors = []
        for mode in modes:
            vals = sub[sub["mode"] == mode]
            if len(vals) == 0: continue
            med = vals["median"].values[0]
            q1 = vals["q1"].values[0]
            q3 = vals["q3"].values[0]
            medians.append(med)
            errors.append([med-q1, q3-med])
        ax.bar(modes, medians, yerr=np.array(errors).T, capsize=5)
        ax.set_title(f"Stride = {stride} B")
        ax.set_ylabel("Median latency (ticks/access)")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "control_comparison.pdf"), bbox_inches='tight')
    plt.close(fig)

# ============ Main ============
def main():
    # 1. Collect data (run benchmarks)
    collect_data()

    # 2. Compute statistics
    df_stats = compute_stats()

    # 3. Generate plots
    plot_latency_vs_stride(df_stats)
    plot_boxplots_representative(df_stats)
    plot_control_comparison(df_stats)

    print("Done. Plots saved in", PLOT_DIR)
    print("Statistics saved in", STATS_DIR)

if __name__ == "__main__":
    main()