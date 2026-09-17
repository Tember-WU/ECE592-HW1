#!/usr/bin/env python3
"""
make_report_figures.py
Generates the two figures your report needs for Experiment 5:

  1. methodology_diagram.pdf
     A schematic (no data required) of the cross-level eviction/reload test
     itself: place T -> pressure the LLC only -> reload T -> classify. Makes
     explicit the ONE condition that distinguishes inclusive from
     non-inclusive: whether the reload lands in the DRAM-latency class
     (T was invalidated when evicted from the LLC) or the L2/LLC-hit class
     (the inner copy survived). Good for your report's Methods section.
     Run this any time -- it does not need any experiment data.

  2. <machine>_evidence.pdf, one per machine with results available
     The actual cross-level evidence plot: calibration reference
     distributions (L2 / LLC / DRAM single-access latency) with the two
     classification boundaries marked, next to the observed fraction of
     T-reload trials landing in each class after LLC-only pressure. This
     is your report's evidence figure -- it shows the reload latencies
     against the classes with the decision boundary applied, which is
     what makes an inclusion/exclusion claim defensible instead of
     asserted.

  3. all_machines_evidence_grid.pdf
     All available machines' outcome fractions on one page, so the report
     can show the cross-machine comparison in a single figure/table.

Usage (run from the scripts/ directory, after run_inclusion_experiment.py
has produced raw_data_inclusion/<machine>/{calibration.csv,
inclusion_trials.csv,inclusion_report.json} for at least one machine):

    python3 make_report_figures.py
    python3 make_report_figures.py --indir raw_data_inclusion --outdir figures
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


def draw_box(ax, xy, w, h, text, fc="#e8eef7", ec="#2b4a75", fontsize=10.5):
    x, y = xy
    box = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.02,rounding_size=0.02",
                          linewidth=1.4, edgecolor=ec, facecolor=fc)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, wrap=True)
    return (x + w / 2, y), (x + w / 2, y + h), (x, y + h / 2), (x + w, y + h / 2)


def arrow(ax, p0, p1, color="black"):
    a = FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=16,
                         linewidth=1.4, color=color)
    ax.add_patch(a)


def make_methodology_diagram(outpath):
    fig, ax = plt.subplots(figsize=(9, 7.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 11.5)
    ax.axis("off")
    ax.set_title("Cross-level eviction / reload test\n"
                  "(TA slide 18 methodology)", fontsize=13, fontweight="bold")

    b1 = draw_box(ax, (2.5, 9.2), 5, 1.2,
                  "1. Calibrate\nReference single-access latency for\n"
                  "L2-hit, LLC-hit, DRAM classes\n(this run, this machine)")
    b2 = draw_box(ax, (2.5, 7.2), 5, 1.2,
                  "2. Place target T\nRepeated direct hits pull T\ninto L1 / L2")
    b3 = draw_box(ax, (2.5, 5.2), 5, 1.2,
                  "3. Pressure the LLC ONLY\nChase an empirically-found LLC\n"
                  "conflict ring (K lines, K > LLC ways)\n"
                  "that does not also touch T's L2 set")
    b4 = draw_box(ax, (2.5, 3.2), 5, 1.2,
                  "4. Reload T\nSingle fenced dependent access,\n"
                  "record latency in ticks")

    arrow(ax, b1[0], b2[1])
    arrow(ax, b2[0], b3[1])
    arrow(ax, b3[0], b4[1])

    # Decision diamond -> two branches
    ax.text(5, 2.55, "Classify reload against the two boundaries\n"
                      "from step 1 (this is the ONE condition that matters):",
            ha="center", va="center", fontsize=10.5, style="italic")

    left = draw_box(ax, (0.3, 0.2), 4.0, 1.6,
                     "Reload = L2-hit or LLC-hit class\n"
                     "(latency close to calibrated\nL2 / LLC medians)\n\n"
                     "-> inner copy SURVIVED\n"
                     "-> NON-INCLUSIVE / exclusive-like",
                     fc="#e6f4ea", ec="#2e7d32", fontsize=9.5)
    right = draw_box(ax, (5.7, 0.2), 4.0, 1.6,
                      "Reload = DRAM class\n"
                      "(latency close to calibrated\nDRAM median)\n\n"
                      "-> T was back-invalidated\n"
                      "-> INCLUSIVE",
                      fc="#fdecea", ec="#c62828", fontsize=9.5)

    arrow(ax, (3.6, 3.2), (2.3, 1.8))
    arrow(ax, (6.4, 3.2), (7.7, 1.8))

    ax.text(5, 11.0,
            "Repeat over many independent target regions ('sets') and many\n"
            "trials each -- report the FRACTION of trials in each class,\n"
            "not a single trial. Mixed fractions -> report a behavioral\n"
            "bound, not a forced label (TA note on Experiment 5).",
            ha="center", va="center", fontsize=9, color="#444444")

    fig.tight_layout()
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {outpath}")


def make_machine_evidence_figure(machine, indir, outdir):
    mdir = os.path.join(indir, machine)
    cal_path = os.path.join(mdir, "calibration.csv")
    trials_path = os.path.join(mdir, "inclusion_trials.csv")
    report_path = os.path.join(mdir, "inclusion_report.json")
    if not (os.path.exists(cal_path) and os.path.exists(trials_path) and os.path.exists(report_path)):
        return None

    cal = pd.read_csv(cal_path)
    trials = pd.read_csv(trials_path)
    
    cal.columns = cal.columns.str.strip()
    trials.columns = trials.columns.str.strip()
    with open(report_path) as f:
        report = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))

    # Panel A: calibration reference distributions with boundaries.
    colors = {"L2": "#1f77b4", "LLC": "#ff7f0e", "DRAM": "#2ca02c"}
    for cls in ["L2", "LLC", "DRAM"]:
        vals = cal[cal["class"] == cls]["ticks"]
        axes[0].hist(vals, bins=80, alpha=0.55, label=f"{cls} (calibration)",
                     density=True, color=colors[cls])
    axes[0].axvline(report["l2_dram_boundary_ticks"], color="k", linestyle="--",
                     linewidth=1.2, label="L2/LLC boundary")
    axes[0].axvline(report["llc_dram_boundary_ticks"], color="k", linestyle=":",
                     linewidth=1.4, label="LLC/DRAM boundary")

    # Overlay the actual T-reload latencies from the trials as a thin
    # outline histogram so the reader can see exactly which side of the
    # boundary the real data landed on -- this IS the cross-level evidence.
    axes[0].hist(trials["reload_ticks"], bins=80, density=True, histtype="step",
                 linewidth=1.8, color="black", label="T reload after LLC pressure")

    # Clip the x-axis to where the mass of the data actually is. Timing
    # runs on real hardware always have a small tail of outliers (SMT
    # sibling noise, interrupts, migration -- slide 19's "Noise" pitfall);
    # a few outlier samples in the thousands-of-ticks range should not be
    # allowed to squash the DRAM-vs-LLC-vs-L2 detail that the figure exists
    # to show. We keep every sample in the underlying data/CSV -- only the
    # plotted view is clipped, and we report the excluded fraction in the
    # x-label so it's not silently hidden.
    all_vals = pd.concat([cal["ticks"], trials["reload_ticks"]])
    lo = 0
    hi = np.percentile(all_vals, 99.5)
    hi = max(hi, report["dram_median_ticks"] * 1.3)  # never clip below the DRAM class itself
    n_clipped = int((all_vals > hi).sum())
    axes[0].set_xlim(lo, hi)
    axes[0].set_xlabel(f"Single-access latency (ticks)"
                        f"{f'  [view clipped at p99.5; {n_clipped} outlier samples above {hi:.0f} not shown]' if n_clipped else ''}",
                        fontsize=8.5)
    axes[0].set_ylabel("Density")
    axes[0].set_title(f"{machine}: reload latency vs. calibrated classes")
    axes[0].legend(fontsize=8)

    # Panel B: outcome fractions.
    fracs = [report["fraction_L2_hit"], report["fraction_LLC_hit"], report["fraction_DRAM"]]
    bars = axes[1].bar(["L2_hit\n(survived)", "LLC_hit\n(survived)", "DRAM\n(invalidated)"],
                        fracs, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel(f"Fraction of {report['n_trials']} reload trials")
    axes[1].set_title("Cross-level eviction/reload outcome")
    for b, f_ in zip(bars, fracs):
        axes[1].text(b.get_x() + b.get_width() / 2, f_ + 0.02, f"{f_:.2f}",
                     ha="center", fontsize=9)

    fig.suptitle(f"{machine} -- {report['verdict']}", fontsize=11, y=1.03)
    fig.tight_layout()
    outpath = os.path.join(outdir, f"{machine}_evidence.pdf")
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {outpath}")
    return report


def make_cross_machine_grid(reports, outdir):
    if not reports:
        print("No per-machine reports found yet -- skipping the cross-machine grid.")
        return
    machines = [r["machine"] for r in reports]
    frac_l2 = [r["fraction_L2_hit"] for r in reports]
    frac_llc = [r["fraction_LLC_hit"] for r in reports]
    frac_dram = [r["fraction_DRAM"] for r in reports]

    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(machines)), 5.5))
    x = np.arange(len(machines))
    ax.bar(x, frac_l2, label="L2_hit (survived)", color="#1f77b4")
    ax.bar(x, frac_llc, bottom=frac_l2, label="LLC_hit (survived)", color="#ff7f0e")
    bottom2 = [a + b for a, b in zip(frac_l2, frac_llc)]
    ax.bar(x, frac_dram, bottom=bottom2, label="DRAM (invalidated)", color="#2ca02c")
    ax.set_xticks(x)
    ax.set_xticklabels(machines, rotation=30, ha="right")
    ax.set_ylabel("Fraction of reload trials")
    ax.set_ylim(0, 1.25)
    ax.set_title("Cross-level eviction/reload outcome, all machines", pad=28)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8)
    for i, r in enumerate(reports):
        v = r["verdict"]
        if "INCLUSIVE" in v and "NON-INCLUSIVE" not in v:
            short_verdict = "inclusive"
        elif "NON-INCLUSIVE" in v:
            short_verdict = "non-inclusive"
        else:
            short_verdict = "mixed"
        ax.text(i, 1.03, short_verdict, ha="center", va="bottom", fontsize=8, rotation=0)
    fig.tight_layout()
    outpath = os.path.join(outdir, "all_machines_evidence_grid.pdf")
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {outpath}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="raw_data_inclusion")
    ap.add_argument("--outdir", default="figures")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    make_methodology_diagram(os.path.join(args.outdir, "methodology_diagram.pdf"))

    reports = []
    if os.path.isdir(args.indir):
        for machine in sorted(os.listdir(args.indir)):
            report = make_machine_evidence_figure(machine, args.indir, args.outdir)
            if report:
                reports.append(report)
    else:
        print(f"'{args.indir}' not found yet -- only the methodology diagram was made. "
              "Run run_inclusion_experiment.py for at least one machine first, then re-run this script.")

    make_cross_machine_grid(reports, args.outdir)


if __name__ == "__main__":
    main()