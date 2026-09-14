#!/usr/bin/env python3
"""Validate saved raw files, summarize counters, and compare capacity curves."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import ROOT, identifier, plan, save, sha, summarize, validate_counts


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    identifier(args.machine); identifier(args.run_id)
    data = ROOT / 'data' / args.machine / args.run_id
    out = ROOT / 'results' / args.machine / args.run_id
    config = json.loads((data / 'config.json').read_text())
    manifest = json.loads((data / 'manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError('Run is not complete')
    expected = plan(config)
    if [(j['name'], j['bytes'], j['region']) for j in expected] != [
            (j['name'], j['bytes'], j['region']) for j in manifest['jobs']]:
        raise ValueError('Plan/manifest mismatch')
    out.mkdir(parents=True, exist_ok=True)
    figures = out / 'figures'; figures.mkdir(exist_ok=True)
    rows, counters, temporal = [], [], []
    for job in sorted(manifest['jobs'], key=lambda j: j['bytes']):
        if job['status'] != 'complete':
            raise ValueError('Incomplete point')
        raw_path, counts_path = data / job['raw_file'], data / job['counts_file']
        if sha(raw_path) != job['raw_sha256'] or sha(counts_path) != job['counts_sha256']:
            raise ValueError('Raw/counts hash mismatch')
        with gzip.open(raw_path, 'rb') as f:
            payload = f.read()
        if len(payload) != config['samples'] * 8:
            raise ValueError('Raw size mismatch')
        raw = np.frombuffer(payload, dtype='<u8')
        if not np.all(raw > 0):
            raise ValueError('Nonpositive timing sample')
        stats = summarize(raw, config['batch'])
        if stats != job['statistics']:
            raise ValueError('Recomputed statistics differ')
        counts = json.loads(counts_path.read_text()); validate_counts(counts, config)
        row = dict(name=job['name'], region=job['region'], bytes=job['bytes'],
                   **{k: v for k, v in stats.items() if k != 'decile_medians'},
                   units='TSC ticks / dependent load',
                   **job['measurement_events'])
        for i, (event, actual) in enumerate(zip(config['events'], counts['events'])):
            per1000 = actual['count'] / counts['chain_loads'] * 1000
            row[event['name'] + '_per_1000_chain_loads'] = per1000
            counters.append(dict(name=job['name'], bytes=job['bytes'], event=event['name'],
                                 raw_config=event['config'], count=actual['count'],
                                 chain_loads=counts['chain_loads'],
                                 per_1000_chain_loads=per1000,
                                 time_enabled_ns=counts['time_enabled_ns'],
                                 time_running_ns=counts['time_running_ns']))
        rows.append(row)
        temporal.extend(dict(name=job['name'], block=i + 1, median=value,
                             units='TSC ticks / dependent load')
                        for i, value in enumerate(stats['decile_medians']))
    write_csv(out / 'summary.csv', rows)
    write_csv(out / 'pmu_counts.csv', counters)
    write_csv(out / 'temporal_medians.csv', temporal)
    # Read the existing timing-only summary in place. No baseline snapshot,
    # Git checkpoint, or separate prior-result reference file is created.
    baseline_path = ROOT.parents[1] / 'timing-only' / 'capacity' / 'results' / args.machine / 'combined12' / 'summary.csv'
    with baseline_path.open() as f:
        baseline = list(csv.DictReader(f))
    before = {}
    for row in rows:
        matches = [r for r in baseline if int(r['bytes']) == row['bytes'] and
                   all(int(r[k]) == config[k] for k in ('samples', 'batch', 'spacing', 'seed')) and
                   all(r[k] == config[k] for k in ('pages', 'mode'))]
        if len(matches) != 1:
            raise ValueError(f'Expected one identical timing-only configuration for {row["name"]}')
        before[row['name']] = float(matches[0]['median'])
    plt.rcParams.update({'font.size': 10, 'axes.grid': False, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(2, 3, figsize=(13, 7), layout='constrained')
    for col, region in enumerate(config['regions']):
        selected = [r for r in rows if r['region'] == region]
        divisor = 1024 if region == 'L1' else 1024**2
        x = [r['bytes'] / divisor for r in selected]
        ax = axes[0, col]
        ax.plot(x, [before[r['name']] for r in selected], 's-', color='0.5', label='Timing-only median')
        ax.plot(x, [r['median'] for r in selected], 'o-', color='#1464a0', label='With PMU median')
        ax.fill_between(x, [r['p05'] for r in selected], [r['p95'] for r in selected],
                        color='#1464a0', alpha=.13, label='With PMU P05–P95')
        ax.set_title(region + ' capacity region')
        ax.set_ylabel('TSC ticks / dependent load')
        ax.legend(fontsize=8)
        event = config['events'][col]['name']
        axes[1, col].plot(x, [r[event + '_per_1000_chain_loads'] for r in selected],
                          'o-', color='#bd3c36')
        axes[1, col].set_ylabel(region + ' misses / 1,000 chain loads')
        axes[1, col].set_ylim(0, max(1050, max(r[event + '_per_1000_chain_loads'] for r in selected) * 1.05))
        for a in axes[:, col]:
            a.set_xlabel('Working set (' + ('KiB' if region == 'L1' else 'MiB') + ')')
            a.set_xticks(x)
            a.tick_params(axis='x', labelsize=8)
    fig.suptitle(f'{args.machine}: same capacity workloads, timing and PMU evidence')
    for extension in ('png', 'pdf'):
        fig.savefig(figures / ('capacity_pmu_validation.' + extension), dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.3), layout='constrained')
    for ax, region in zip(axes, config['regions']):
        selected = [r for r in rows if r['region'] == region]
        divisor = 1024 if region == 'L1' else 1024**2
        boxes = [dict(med=r['median'], q1=r['q1'], q3=r['q3'], whislo=r['whisker_low'],
                      whishi=r['whisker_high'], fliers=[], label=f"{r['bytes'] / divisor:g}") for r in selected]
        ax.bxp(boxes, showfliers=False)
        ax.set_title(region)
        ax.set_xlabel('Working set (' + ('KiB' if region == 'L1' else 'MiB') + ')')
        ax.set_ylabel('TSC ticks / dependent load')
    fig.suptitle('With-PMU timing distributions (Tukey whiskers; outliers retained in raw data)')
    for extension in ('png', 'pdf'):
        fig.savefig(figures / ('latency_boxplots.' + extension), dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4), layout='constrained')
    for job in manifest['jobs']:
        medians = job['statistics']['decile_medians']
        ax.plot(range(1, 11), np.asarray(medians) / job['statistics']['median'],
                marker='.', label=job['name'])
    ax.set(xlabel='Consecutive block of 100,000 batches', ylabel='Block median / full-run median',
           title='Temporal stability within each capacity point')
    ax.legend(fontsize=6, ncol=2, bbox_to_anchor=(1.02, 1), loc='upper left')
    for extension in ('png', 'pdf'):
        fig.savefig(figures / ('temporal_stability.' + extension), dpi=180)
    plt.close(fig)
    env = json.loads((data / 'environment.json').read_text())
    quality = dict(preflight_busy_percent=env['preflight_busy_percent'],
                   total_involuntary_switches=sum(r['involuntary_switches'] for r in rows),
                   total_minor_faults=sum(r['measurement_minor_faults'] for r in rows),
                   total_major_faults=sum(r['major_faults'] for r in rows),
                   max_sibling_busy_percent=max((v for j in manifest['jobs'] for cpu, v in j['cpu_busy_percent'].items()
                                                if int(cpu) != config['cpu']), default=None),
                   temporal_median_max_min={j['name']: max(j['statistics']['decile_medians']) /
                       min(j['statistics']['decile_medians']) for j in manifest['jobs']},
                   note='CPU busy time during a run includes this benchmark. Shared-cache/memory interference is not isolated.')
    save(out / 'quality.json', quality)
    save(out / 'validation.json', dict(status='passed', points=len(rows),
         timed_batches=sum(r['n'] for r in rows), all_raw_and_count_hashes_match=True,
         all_statistics_recomputed=True, all_groups_without_multiplexing=True,
         matching_timing_only_workload_for_every_point=True,
         note='Integrity and comparability checks; not proof of an uncontended or pure cache state.'))
    print(f'Validated {len(rows)} points; wrote statistics, PMU counts, and three PNG/PDF figures.')


if __name__ == '__main__':
    main()
