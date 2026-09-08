#!/usr/bin/env python3
"""Recompute capacity statistics and figures from one V3 run; never collect data."""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from run_capacity import ROOT, identifier, summarize

BLUE, ORANGE, GREEN = '#2166ac', '#d66020', '#1b7837'
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.grid': False,
                     'savefig.dpi': 180, 'pdf.fonttype': 42, 'font.family': 'DejaVu Sans'})


def size_label(w):
    return f'{w / 1048576:g} MiB' if w >= 1048576 else f'{w / 1024:g} KiB'


def family(d):
    p = d['parameters']
    return p['spacing'], p['batch'], p['pages']


def save(fig, figures, name):
    fig.savefig(figures / f'{name}.png', bbox_inches='tight')
    fig.savefig(figures / f'{name}.pdf', bbox_inches='tight')
    plt.close(fig)


def load_records(data_dir, machine):
    records = []
    for path in sorted((data_dir / 'logs').glob('*.json')):
        d = json.loads(path.read_text())
        if d['machine'] != machine:
            raise ValueError(f'Machine mismatch in {path}')
        with gzip.open(data_dir / d['raw_file'], 'rb') as f:
            payload = f.read()
        if hashlib.sha256(payload).hexdigest() != d['raw_sha256']:
            raise ValueError(f'Raw sample checksum mismatch: {d["raw_file"]}')
        raw = np.frombuffer(payload, dtype='<u8')
        if len(raw) != d['parameters']['samples'] or not np.all(raw > 0):
            raise ValueError(f'Invalid sample count/interval in {d["raw_file"]}')
        divisor = 1 if d['parameters']['mode'] == 'empty' else d['parameters']['batch']
        d['stats'] = summarize(raw, divisor)
        d['units'] = 'TSC ticks / timer interval' if divisor == 1 else 'TSC ticks / dependent load'
        records.append(d)
    if not records:
        raise ValueError(f'No completed measurement records in {data_dir / "logs"}')
    return records


def rank_run(d):
    priority = {'dense': 0, 'refine': 0, 'llc_final': 0, 'llc_dense': 1,
                'coarse': 2, 'llc_layout': 2, 'controls': 3}
    return priority.get(d['suite'], 1), d['parameters']['seed']


def representative(records):
    """Predefined selection: dense lowest seed first, otherwise coarse.
    Never select a run because its measured median looks preferable.
    Keep the range of replicate medians distinct from within-run percentiles.
    """
    groups = {}
    for d in records:
        groups.setdefault(d['parameters']['bytes'], []).append(d)
    points = []
    for w, ds in sorted(groups.items()):
        chosen = sorted(ds, key=rank_run)[0]
        medians = [d['stats']['median'] for d in ds]
        points.append(dict(bytes=w, primary_run=chosen['name'], runs=[d['name'] for d in ds],
                           repeat_low=min(medians), repeat_high=max(medians), **chosen['stats']))
    return points


def repeats(ax, points, unit=1):
    selected = [p for p in points if len(p['runs']) > 1]
    if selected:
        x = np.array([p['bytes'] for p in selected]) / unit
        lo, hi = np.array([p['repeat_low'] for p in selected]), np.array([p['repeat_high'] for p in selected])
        ax.errorbar(x, (lo + hi) / 2, yerr=(hi - lo) / 2, fmt='none',
                    ecolor='#333333', elinewidth=1, capsize=3, label='Range of run medians')


def curve(ax, points, color, label, unit=1, band=True, style='.-'):
    if not points:
        return
    x = np.array([p['bytes'] for p in points]) / unit
    ax.plot(x, [p['median'] for p in points], style, color=color, label=label, lw=1.3, ms=5)
    if band:
        ax.fill_between(x, [p['p05'] for p in points], [p['p95'] for p in points],
                        color=color, alpha=.13)


def boxes(ax, records):
    entries = []
    for d in records:
        s, p = d['stats'], d['parameters']
        entries.append(dict(label=f"{size_label(p['bytes'])}\n{p['mode']} s{p['seed']}",
                            med=s['median'], q1=s['q1'], q3=s['q3'],
                            whislo=s['whisker_low'], whishi=s['whisker_high'],
                            mean=s['mean'], fliers=[]))
    ax.bxp(entries, showfliers=False, showmeans=True, patch_artist=True,
           boxprops=dict(facecolor=BLUE, alpha=.25), medianprops=dict(color=BLUE))
    for i, d in enumerate(records, 1):
        s = d['stats']
        ax.plot([i, i], [s['p05'], s['p95']], '_', color=ORANGE, ms=10)
    ax.tick_params(axis='x', labelsize=7, rotation=25)
    ax.set_ylabel(records[0]['units'])
    ax.grid(False)


def plot_family(records, figures, machine, key):
    spacing, batch, pages = key
    stem = f's{spacing}_b{batch}_{pages}'
    title = f'{machine}: {spacing} B spacing, {batch} loads/batch, {pages} pages'
    fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
    points_by_mode = {}
    for mode, color in (('random', BLUE), ('sequential', ORANGE)):
        points = representative([d for d in records if d['parameters']['mode'] == mode])
        points_by_mode[mode] = points
        curve(ax, points, color, mode.capitalize())
        repeats(ax, points)
    ax.set_xscale('log', base=2)
    ax.set_yscale('log', base=2)
    ticks = sorted({d['parameters']['bytes'] for d in records})
    step = max(1, (len(ticks) + 9) // 10)
    ax.set_xticks(ticks[::step], [size_label(w) for w in ticks[::step]], rotation=25)
    ax.set(title=title, xlabel='Working-set size (address span)', ylabel='TSC ticks / dependent load')
    ax.grid(False)
    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    ax.legend(unique.values(), unique.keys(), fontsize=8)
    fig.text(.5, -.025, 'Lines: selected run medians; bands: P05–P95; black bars: range of repeat medians.',
             ha='center', fontsize=9)
    save(fig, figures, f'capacity_{stem}')

    ordered = sorted(records, key=lambda d: (d['parameters']['bytes'], d['parameters']['mode'], rank_run(d)))
    with PdfPages(figures / f'boxplots_{stem}.pdf') as pdf:
        for start in range(0, len(ordered), 12):
            fig, ax = plt.subplots(figsize=(12, 5), layout='constrained')
            boxes(ax, ordered[start:start + 12])
            ax.set_title(title)
            fig.text(.5, -.04, 'Each box is one run. Outlier markers are hidden; all samples and outlier counts are retained.',
                     ha='center', fontsize=9)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    return points_by_mode


def plot_boundaries(records, boundaries, figures, machine):
    """Annotate only boundaries explicitly supplied for these new measurements."""
    if not boundaries:
        return
    fig, axes = plt.subplots(1, len(boundaries), figsize=(5 * len(boundaries), 4), layout='constrained')
    boxfig, boxaxes = plt.subplots(1, len(boundaries), figsize=(5 * len(boundaries), 4.5), layout='constrained')
    for ax, bax, b in zip(np.atleast_1d(axes), np.atleast_1d(boxaxes), boundaries):
        key = (b.get('spacing', 64), b.get('batch', 256), b.get('pages', 'huge'))
        selected = [d for d in records if family(d) == key and d['parameters']['mode'] != 'empty']
        if not selected:
            raise ValueError(f'No matching measurements for boundary {b["level"]}')
        lo, hi = b['zoom']
        unit = b['unit']
        for mode, color in (('random', BLUE), ('sequential', ORANGE)):
            points = representative([d for d in selected if d['parameters']['mode'] == mode])
            points = [p for p in points if lo <= p['bytes'] <= hi]
            curve(ax, points, color, mode.capitalize(), unit)
            repeats(ax, points, unit)
        ax.axvspan(b['interval'][0] / unit, b['interval'][1] / unit, color=GREEN, alpha=.12)
        if b.get('estimate') is not None:
            ax.axvline(b['estimate'] / unit, color=GREEN, ls=':')
        ax.set(title=f'{machine}: {b["level"]}', xlabel=f'Working set / {unit} bytes',
               ylabel='TSC ticks / dependent load', xlim=(lo / unit, hi / unit))
        ax.legend(fontsize=8)
        chosen = []
        for w in b['box_points']:
            matches = sorted([d for d in selected if d['parameters']['bytes'] == w and
                              d['parameters']['mode'] == 'random'], key=rank_run)
            if not matches:
                raise ValueError(f'Missing random box-plot point {w} for {b["level"]}')
            chosen.extend(matches[:2])
        if not chosen:
            raise ValueError('A boundary needs measured box_points')
        boxes(bax, chosen)
        bax.set_title(f'{machine}: {b["level"]}')
    save(fig, figures, 'boundary_zoom')
    save(boxfig, figures, 'boundary_boxplots')


def plot_diagnostics(records, figures, machine):
    groups = {}
    for d in records:
        if d['parameters']['mode'] == 'random':
            key = (*family(d), d['parameters']['bytes'])
            groups.setdefault(key, []).append(d)
    repeated = [(key, ds) for key, ds in sorted(groups.items()) if len(ds) > 1]
    if repeated:
        with PdfPages(figures / 'temporal_stability.pdf') as pdf:
            for (spacing, batch, pages, size), ds in repeated:
                fig, ax = plt.subplots(figsize=(8, 4), layout='constrained')
                for d in ds:
                    ax.plot(range(1, 11), d['stats']['decile_medians'], '.-',
                            label=f"{d['suite']}: seed {d['parameters']['seed']}")
                ax.set(title=f'{machine}: {size_label(size)}, {spacing} B spacing, N={batch}, {pages}',
                       xlabel='Consecutive tenth of each run', ylabel='Median TSC ticks / dependent load')
                ax.legend(fontsize=8)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 3.5), layout='constrained')
    ax.axis('off')
    steps = ['Pin CPU; bind local memory\nAllocate span W; verify page backing',
             'Construct one pointer cycle\nRandomized / sequential order',
             'Warm; time dependent-load batches\nSave every batch interval',
             'Compare curves and distributions\nRefine W around observed transitions']
    for i, label in enumerate(steps):
        x = .13 + i * .245
        ax.text(x, .60, label, ha='center', va='center', fontsize=8,
                bbox=dict(boxstyle='round,pad=.6', facecolor='#deebf7', edgecolor=BLUE),
                transform=ax.transAxes)
        if i < 3:
            ax.annotate('', xy=(x + .137, .60), xytext=(x + .105, .60),
                        xycoords='axes fraction', arrowprops=dict(arrowstyle='->', color=BLUE))
    ax.text(.5, .20, 'p = *(void **)p: each returned pointer supplies the next load address.\n'
            'Spacing is a layout parameter; an observed timing step needs controls before a capacity claim.',
            ha='center', va='center', transform=ax.transAxes)
    ax.set_title(f'{machine}: cache-level and capacity measurement logic')
    save(fig, figures, 'method')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--boundaries', type=Path, help='Optional, manually inferred boundaries for this run')
    args = ap.parse_args()
    machine, run_id = identifier(args.machine), identifier(args.run_id)
    data_dir = ROOT / 'data' / machine / run_id
    output = ROOT / 'results' / machine / run_id
    records = load_records(data_dir, machine)
    boundaries = json.loads(args.boundaries.read_text()) if args.boundaries else []
    figures = output / 'figures'
    figures.mkdir(parents=True, exist_ok=True)
    rows = [dict(name=d['name'], suite=d['suite'], machine=machine, **d['parameters'],
                 **{k: v for k, v in d['stats'].items() if k != 'decile_medians'},
                 units=d['units'], elapsed_seconds=d['elapsed_seconds'], raw_file=d['raw_file']) for d in records]
    with (output / 'summary.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    points = {}
    keys = sorted({family(d) for d in records if d['parameters']['mode'] != 'empty'})
    for key in keys:
        selected = [d for d in records if family(d) == key and d['parameters']['mode'] != 'empty']
        points[str(key)] = plot_family(selected, figures, machine, key)
    (output / 'capacity_points.json').write_text(json.dumps(points, indent=2) + '\n')
    # Retain V2's temporal-drift diagnostic for every run, without a preset conclusion.
    with (output / 'temporal_medians.csv').open('w') as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'block', 'median', 'units'])
        for d in records:
            for i, value in enumerate(d['stats']['decile_medians'], 1):
                writer.writerow([d['name'], i, value, d['units']])
    plot_boundaries(records, boundaries, figures, machine)
    plot_diagnostics(records, figures, machine)
    provenance = dict(machine=machine, run_id=run_id, data_directory=str(data_dir),
                      generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      command=shlex.join([sys.executable] + sys.argv),
                      analysis_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      statistics_sha256=hashlib.sha256((ROOT / 'scripts/run_capacity.py').read_bytes()).hexdigest(),
                      boundaries=boundaries,
                      inputs=[dict(name=d['name'], file=d['raw_file'], sha256=d['raw_sha256']) for d in records])
    (output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'Recomputed {len(records)} points from raw samples; output: {output}')


if __name__ == '__main__':
    main()
