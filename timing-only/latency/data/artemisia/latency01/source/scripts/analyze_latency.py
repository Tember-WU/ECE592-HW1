#!/usr/bin/env python3
"""Recheck a saved run, plot distributions, and report qualified latency contrasts."""
import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from common import ROOT, GROUPS, identifier, load_record, sha, write_json
from run_latency import verify_log

LABELS = {'l1_hit': 'L1 resident candidate', 'l2_hit': 'L2 resident candidate',
          'llc_hit': 'LLC resident candidate', 'l1_miss': 'L1 miss / L2 candidate',
          'l2_miss': 'L2 miss / LLC candidate', 'llc_miss': 'LLC miss / memory candidate'}
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                     'savefig.dpi': 160, 'pdf.fonttype': 42})


def size_label(n):
    return f'{n / 2**20:g} MiB' if n >= 2**20 else f'{n / 1024:g} KiB'


def box(s, label):
    return dict(label=label, med=s['median'], q1=s['q1'], q3=s['q3'],
                whislo=s['whisker_low'], whishi=s['whisker_high'], fliers=[])


def save(fig, out, name):
    fig.tight_layout()
    for extension in ('png', 'pdf'):
        fig.savefig(out / f'{name}.{extension}', bbox_inches='tight')
    plt.close(fig)


def write_csv(path, rows):
    if rows:
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)


def same_statistics(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_statistics(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same_statistics(x, y) for x, y in zip(a, b))
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9)


def analyze(data, out):
    config = json.loads((data / 'config.json').read_text())
    manifest = json.loads((data / 'manifest.json').read_text())
    env = json.loads((data / 'environment.json').read_text())
    if manifest['status'] != 'complete' or any(j.get('status') != 'complete' for j in manifest['jobs']):
        raise ValueError('Only complete runs may produce a formal analysis')
    if sha(data / 'environment.json') != manifest['environment_sha256']:
        raise ValueError('Environment checksum mismatch')
    if sha(data / 'latency_bench.bin') != env['binary_sha256']:
        raise ValueError('Executable snapshot checksum mismatch')
    for name, expected in manifest['source_snapshot_hashes'].items():
        if sha(data / 'source' / name) != expected:
            raise ValueError(f'Source snapshot checksum mismatch: {name}')
    jobs = {j['name']: j for j in manifest['jobs']}
    paths = sorted((data / 'logs').glob('*.json'))
    if len(jobs) != len(manifest['jobs']) or {p.stem for p in paths} != jobs.keys():
        raise ValueError('Manifest/log point sets differ')
    records = {}
    for path in paths:
        original = json.loads(path.read_text())
        d = load_record(path)
        if (d['machine'] != config['machine'] or d['parameters'] != jobs[d['name']]['parameters'] or
                d['raw_sha256'] != jobs[d['name']]['raw_sha256'] or
                d['columns'] != jobs[d['name']]['columns']):
            raise ValueError(f'Manifest/record mismatch: {path}')
        if not same_statistics(original['stats'], d['stats']):
            raise ValueError(f'Recomputed statistics differ: {path}')
        events = verify_log(path.with_suffix('.txt').read_text(), config, d['parameters'])
        if events != d['runtime_events']:
            raise ValueError(f'Runtime event log mismatch: {path}')
        records[d['name']] = d
    out.mkdir(parents=True, exist_ok=True)
    previous = out / 'provenance.json'
    if previous.exists() and json.loads(previous.read_text())['manifest_sha256'] != sha(data / 'manifest.json'):
        raise ValueError('Output belongs to different inputs; choose a different output ID')
    figures = out / 'figures'; figures.mkdir(exist_ok=True)
    units = env['timer_unit'] + ' / dependent load'
    rows, quality, temporal = [], [], []
    for name, d in records.items():
        p = d['parameters']
        for column in d['columns'] + (['first_minus_reread'] if p['mode'] == 'paired' else []):
            s = d['stats'][column]
            rows.append(dict(name=name, group=d['group'], column=column, **p,
                             units=env['timer_unit'] + ' / timer interval' if p['mode'] == 'empty' else units,
                             **{k: v for k, v in s.items() if k != 'decile_medians'}, raw_file=d['raw_file']))
            for i, value in enumerate(s['decile_medians'], 1):
                temporal.append(dict(name=name, column=column, block=i, median=value))
        dm = d['stats']['first']['decile_medians']
        ratio = max(dm) / min(dm) if min(dm) > 0 else None
        quality.append(dict(name=name, temporal_median_ratio=ratio,
                            drift_flag=ratio is not None and ratio > 1.2,
                            **d['runtime_events'], cpu_busy_percent=d['cpu_busy_percent']))
    write_csv(out / 'summary.csv', rows)
    write_csv(out / 'temporal_medians.csv', temporal)
    write_json(out / 'quality.json', dict(
        scope='Descriptive diagnostics; the 1.2 temporal-ratio flag is not a significance test or rejection rule.',
        records=quality))

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, group in zip(axes, ('l1_hit', 'l2_hit', 'llc_hit')):
        ds = [d for d in records.values() if d['group'] == group]
        if ds:
            ax.bxp([box(d['stats']['first'], size_label(d['parameters']['bytes']) + '\nseed ' +
                        str(d['parameters']['seed'])) for d in ds], showfliers=False)
        ax.set(title=LABELS[group], ylabel=units)
    save(fig, figures, 'resident_distributions')

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, group in zip(axes, ('l1_miss', 'l2_miss', 'llc_miss')):
        ds = [d for d in records.values() if d['group'] == group]
        boxes = []
        for d in ds:
            label = size_label(d['parameters']['bytes']) + '\ns' + str(d['parameters']['seed'])
            boxes += [box(d['stats'][column], label + '\n' + column) for column in d['columns']]
        if boxes:
            artists = ax.bxp(boxes, showfliers=False, patch_artist=True)
            for i, patch in enumerate(artists['boxes']):
                patch.set_facecolor('#90bce0' if i % 2 == 0 else '#f4ba8e')
        ax.set(title=LABELS[group], ylabel=units)
        ax.tick_params(axis='x', labelsize=8)
    save(fig, figures, 'first_and_reread')

    fig, axes = plt.subplots(1, 4, figsize=(14, 3.8))
    for ax, level in zip(axes, ('l1', 'l2', 'llc', 'memory')):
        primary = f'{level}_hit__primary' if level != 'memory' else 'llc_miss__primary'
        ids = [primary, f'calibration__{level}_sequential',
               f'calibration__{level}_independent', f'calibration__{level}_long']
        labels = ['Random', 'Sequential', '4 streams', 'Random']
        available = [(records[i], label + '\nN=' + str(records[i]['parameters']['batch']))
                     for i, label in zip(ids, labels) if i in records]
        if available:
            ax.bxp([box(d['stats']['first'], label) for d, label in available], showfliers=False)
        ax.set(title=level.upper() + ' method controls', ylabel=env['timer_unit'] + ' / load')
        ax.tick_params(axis='x', labelsize=8)
    save(fig, figures, 'method_controls')

    timer = records.get('calibration__timer')
    if timer:
        fig, ax = plt.subplots(figsize=(4, 3.5))
        ax.bxp([box(timer['stats']['first'], 'Empty timer')], showfliers=False)
        ax.set(ylabel=env['timer_unit'] + ' / interval', title='Timer overhead (not subtracted)')
        save(fig, figures, 'timer_overhead')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for name, d in records.items():
        if name.endswith('__primary'):
            ax = axes[1 if d['parameters']['mode'] == 'paired' else 0]
            ax.plot(range(1, 11), d['stats']['first']['decile_medians'], '.-', label=d['group'])
    for ax, title in zip(axes, ('Resident candidates', 'First pass after reuse distance')):
        ax.set(title=title, xlabel='Consecutive tenth of the point', ylabel=units, yscale='log')
        if ax.lines:
            ax.legend(fontsize=8)
    save(fig, figures, 'temporal_stability')

    # This plot draws the actual address sequence and the timed operations.
    fig, ax = plt.subplots(figsize=(11, 3.5)); ax.axis('off')
    ax.set(xlim=(0, 11), ylim=(0, 3.5))
    ax.text(.1, 3.25, 'One shuffled pointer cycle over W bytes; fixed spacing, recorded seed', fontsize=12)
    for i, label in enumerate(('p0', 'p7', 'p3', 'p9', '...', 'p2')):
        ax.text(.5 + i * 1.7, 2.5, label, ha='center', bbox=dict(boxstyle='round', fc='#d7e8f5'))
        if i < 5:
            ax.annotate('', xy=(1.8 + i * 1.7, 2.5), xytext=(.9 + i * 1.7, 2.5), arrowprops=dict(arrowstyle='->'))
    ax.text(.1, 1.7, 'Paired sample: [start timer | N dependent loads | stop] = FIRST', fontsize=11)
    ax.text(.1, 1.15, 'Reset to the same batch start; time those N loads again = REREAD', fontsize=11)
    ax.text(.1, .6, 'Continue at the next batch. Earlier targets recur only after traversing the W-byte cycle.', fontsize=11)
    ax.text(.1, .05, 'Vary W to change reuse distance; compare FIRST/REREAD distributions. No cache-specification lookup.', fontsize=10)
    save(fig, figures, 'method')

    contrasts = []
    for group, previous_group, destination in [('l1_miss', 'l1_hit', 'L2 candidate'),
                                               ('l2_miss', 'l2_hit', 'LLC candidate'),
                                               ('llc_miss', 'llc_hit', 'Memory candidate')]:
        reference = records.get(previous_group + '__primary')
        if reference:
            for name, d in records.items():
                if d['group'] == group:
                    contrasts.append(dict(name=name, intended_destination=destination,
                        first_median=d['stats']['first']['median'], first_p05=d['stats']['first']['p05'],
                        first_p95=d['stats']['first']['p95'], reread_median=d['stats']['reread']['median'],
                        reference_name=reference['name'], reference_median=reference['stats']['first']['median'],
                        difference_of_medians=d['stats']['first']['median'] - reference['stats']['first']['median'],
                        paired_first_minus_reread_median=d['stats']['first_minus_reread']['median'],
                        first_slower_fraction=d['stats']['first_slower_fraction'], units=units))
    write_csv(out / 'contrasts.csv', contrasts)
    caveats = [
        'Candidate levels come from prior timing plateaus. No PMU verifies the level serving each access.',
        'Paired first-pass pressure is set by full-cycle reuse distance, not a freshly flushed target before every sample.',
        'Immediate reread is the same-address control; conflicts and translation may prevent a pure L1-hit class.',
        'Large-footprint first passes are memory-dominated candidates, not guaranteed pure DRAM accesses.',
        'Difference of separately measured medians is an empirical next-level contrast, not a paired penalty distribution or pipeline stall count.',
        'All outliers remain in raw samples and statistics. Boxes omit individual outlier markers for readability.',
        'TSC/generic timer ticks are not validated core cycles. Consecutive batches are not independent process trials.']
    if any(q['drift_flag'] for q in quality):
        caveats.append('Some points have >20% variation between temporal-block medians; inspect quality.json.')
    write_json(out / 'latency_estimates.json', dict(machine=config['machine'], run_id=data.name,
               units=units, contrasts=contrasts, caveats=caveats,
               resident_candidates={g: {name: d['stats']['first'] for name, d in records.items() if d['group'] == g}
                                    for g in ('l1_hit', 'l2_hit', 'llc_hit')}))
    write_json(out / 'provenance.json', dict(machine=config['machine'], run_id=data.name,
        manifest_sha256=sha(data / 'manifest.json'), config_sha256=sha(data / 'config.json'),
        analysis_sha256=sha(__file__), common_sha256=sha(Path(__file__).with_name('common.py')),
        generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        raw_hashes={name: d['raw_sha256'] for name, d in records.items()}))
    write_json(out / 'validation.json', dict(passed=True, machine=config['machine'], run_id=data.name,
        full_seven_groups=set(d['group'] for d in records.values()) == set(GROUPS),
        configurations=len(records), timed_batches=sum(d['parameters']['samples'] for d in records.values()),
        recorded_intervals=sum(d['parameters']['samples'] * len(d['columns']) for d in records.values()),
        raw_hashes_counts_statistics_snapshots_and_placement_verified=True,
        scope='Data integrity and recorded placement only; not proof of pure cache states or absence of interference.'))
    print(f'Validated {len(records)} configurations. Results: {out}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    machine, run_id = identifier(args.machine), identifier(args.run_id)
    analyze(ROOT / 'data' / machine / run_id, ROOT / 'results' / machine / run_id)


if __name__ == '__main__':
    main()
