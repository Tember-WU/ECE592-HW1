#!/usr/bin/env python3
"""Validate raw evidence and plot line-size / associativity PMU comparisons."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from run_verification import PMU, denominators, identifier, plan, save, sha, summarize, validate_counts


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def baseline(c, p):
    root = PMU.parent / 'timing-only' / c['experiment'] / 'data' / c['machine']
    # Structured freeze references select copied summaries; string references are provenance only.
    if isinstance(c.get('phase1_freeze'), dict):
        freeze = PMU / c['phase1_freeze']['manifest']
        root = freeze.parent / 'snapshot/timing-only' / c['experiment'] / 'data' / c['machine']
    if c['experiment'] == 'line_size':
        sweep = {701: 'initial', 711: 'dense', 721: 'control_random', 731: 'control_sequential'}[p['seed']]
        with (root / 'stats/all_stats.csv').open() as f:
            rows = list(csv.DictReader(f))
        matches = [r for r in rows if r['sweep'] == sweep and int(r['stride']) == p['stride'] and
                   int(r['alignment']) == p['alignment'] and r['mode'] == p['mode']]
        if len(matches) != 1: raise ValueError('Missing/ambiguous timing-only line-size point')
        return float(matches[0]['median'])
    level = 'l1' if p['group'] == 'L1' else 'l2'
    with (root / 'raw_data' / f'{level}_associativity_candidate{p["num_sets"]}.csv').open() as f:
        rows = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(f)]
        matches = [r for r in rows if int(r['K']) == p['k']]
    if not matches and p['k'] > 16: return None
    if len(matches) != 1: raise ValueError('Missing/ambiguous timing-only associativity point')
    # The source times batch+1 loads but divided by batch. Apply the same
    # transparent correction to the displayed old value; do not edit old data.
    return float(matches[0]['median_latency']) * c['batch'] / (c['batch'] + 1)


def figure_save(fig, folder, name):
    for ext in ('png', 'pdf'):
        fig.savefig(folder / (name + '.' + ext), dpi=180)
    plt.close(fig)


def plots(c, rows, folder):
    plt.rcParams.update({'font.size': 10, 'axes.grid': False, 'pdf.fonttype': 42})
    if c['experiment'] == 'line_size':
        # Plot each metric only from the pass that actually counted it.
        all_rows = rows
        rows = [r for r in rows if r['l1_misses_per_1000_chain_loads'] is not None]
        fig, ax = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
        for alignment, color in [(0, '#166aa0'), (16, '#d08014')]:
            selected = sorted([r for r in rows if r['mode'] == 'random_lines' and r['alignment'] == alignment],
                              key=lambda r: r['stride'])
            x = [r['stride'] for r in selected]
            ax[0, 0].plot(x, [r['median'] for r in selected], 'o-', color=color, label=f'With PMU, offset {alignment} B')
            ax[0, 1].plot(x, [r['l1_misses_per_1000_chain_loads'] for r in selected], 'o-', color=color,
                          label=f'Offset {alignment} B')
            if alignment == 0:
                ax[0, 0].plot(x, [r['baseline_median'] for r in selected], 's-', color='0.55', label='Timing-only, offset 0 B')
        ax[0, 0].set(title='Randomized grouping-window traversal', ylabel='TSC ticks / timed chain load', xlabel='Stride (B)')
        ax[0, 1].set(title='L1 miss evidence for the stride boundary', ylabel='L1 misses / 1,000 chain loads', xlabel='Stride (B)', ylim=(0, 1100))
        ax[0, 0].legend(fontsize=8); ax[0, 1].legend(fontsize=8)
        selected = [next(r for r in rows if r['stride'] == 64 and r['alignment'] == 0 and r['mode'] == mode)
                    for mode in ('random_lines', 'sequential_lines', 'fully_random')]
        labels = ['Random windows', 'Sequential', 'Fully random']
        ax[1, 0].bar(labels, [r['median'] for r in selected], color=['#166aa0', '#d08014', '#547f3a'])
        ax[1, 1].bar(labels, [r['l1_misses_per_1000_chain_loads'] for r in selected], color=['#166aa0', '#d08014', '#547f3a'])
        ax[1, 0].set(title='Traversal controls at 64 B stride', ylabel='TSC ticks / timed chain load')
        ax[1, 1].set(title='Traversal controls at 64 B stride', ylabel='L1 misses / 1,000 chain loads', ylim=(0, 1100))
        fig.suptitle(f'{c["machine"].capitalize()} line-size verification ({c["footprint"] / 1024:g} KiB footprint)')
        figure_save(fig, folder, 'line_size_pmu_validation')
        groups = [('Random windows, offset 0 B', sorted([r for r in rows if r['mode'] == 'random_lines' and r['alignment'] == 0], key=lambda r: r['stride']), 'stride'),
                  ('Random windows, offset 16 B', sorted([r for r in rows if r['mode'] == 'random_lines' and r['alignment'] == 16], key=lambda r: r['stride']), 'stride')]
    else:
        group_names = list(dict.fromkeys(p['group'] for p in c['points']))
        fig, ax = plt.subplots(2, len(group_names), figsize=(6 * len(group_names), 7.5),
                               squeeze=False, layout='constrained')
        groups = []
        for col, group in enumerate(group_names):
            selected = sorted([r for r in rows if r['group'] == group], key=lambda r: r['k'])
            x = sorted({r['k'] for r in selected})
            spacings = {r['num_sets'] * c['line_size'] for r in selected}
            if len(spacings) != 1:
                raise ValueError('Each plotted associativity group needs one address spacing')
            label = f'{spacings.pop() / 1024:g} KiB address spacing' + (' (L2 candidate)' if group != 'L1' else '')
            pass_names = list(dict.fromkeys(r['pmu_pass'] for r in selected))
            for pass_name in pass_names:
                subset = [r for r in selected if r['pmu_pass'] == pass_name]
                ax[0, col].plot([r['k'] for r in subset], [r['median'] for r in subset], 'o-',
                                label='With PMU: ' + pass_name)
            old = [r for r in selected if r['baseline_median'] is not None and r['pmu_pass'] == pass_names[0]]
            ax[0, col].plot([r['k'] for r in old], [r['baseline_median'] for r in old], 's-', color='0.55', label='Timing-only (divisor corrected)')
            ax[0, col].set(title=label, ylabel='TSC ticks / timed chain load', xlabel='K (addresses)')
            for level, color in [(1, '#48834b'), (2, '#b93c37'), (3, '#72559b')]:
                subset = [r for r in selected if r[f'l{level}_misses_per_1000_chain_loads'] is not None]
                ax[1, col].plot([r['k'] for r in subset], [r[f'l{level}_misses_per_1000_chain_loads'] for r in subset],
                                'o-', color=color, label=f'L{level} misses')
            ax[1, col].set(ylabel='Misses / 1,000 chain loads (including preparation)', xlabel='K (addresses)', ylim=(0, 1100))
            for a in ax[:, col]: a.legend(fontsize=8); a.set_xticks(x)
            groups.append((label, selected, 'k'))
        fig.suptitle(f'{c["machine"].capitalize()} associativity: identify which cache actually misses')
        figure_save(fig, folder, 'associativity_pmu_validation')
    if c['experiment'] == 'line_size' and c.get('event_passes'):
        groups = [(title, sorted([r for r in all_rows if r['mode'] == 'random_lines' and r['alignment'] == alignment],
                                key=lambda r: r['stride']), 'stride')
                  for title, alignment in [('Random windows, offset 0 B', 0), ('Random windows, offset 16 B', 16)]]
    fig, axes = plt.subplots(1, len(groups), figsize=(6 * len(groups), 4.5), layout='constrained')
    for ax, (label, selected, key) in zip(np.atleast_1d(axes), groups):
        boxes = [dict(med=r['median'], q1=r['q1'], q3=r['q3'], whislo=r['whisker_low'],
                      whishi=r['whisker_high'], fliers=[], label=str(r[key]) +
                      ('\n' + r['pmu_pass'] if c.get('event_passes') else '')) for r in selected]
        ax.bxp(boxes, showfliers=False)
        ax.tick_params(axis='x', labelsize=7)
        ax.set(title=label, ylabel='TSC ticks / timed chain load', xlabel='Stride (B)' if key == 'stride' else 'K (addresses)')
    fig.suptitle('With-PMU distributions: Tukey whiskers; all outliers retained in raw data')
    figure_save(fig, folder, 'latency_boxplots')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experiment', choices=('line_size', 'associativity'), required=True)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    identifier(args.machine); identifier(args.run_id)
    root = PMU / args.experiment
    data = root / 'data' / args.machine / args.run_id
    out = root / 'results' / args.machine / args.run_id
    c = json.loads((data / 'config.json').read_text())
    m = json.loads((data / 'manifest.json').read_text())
    if m['status'] != 'complete': raise ValueError('Incomplete run')
    expected = plan(c)
    for wanted, actual in zip(expected, m['jobs']):
        if any(actual[k] != v for k, v in wanted.items()): raise ValueError('Config/manifest mismatch')
    if len(expected) != len(m['jobs']): raise ValueError('Point count mismatch')
    out.mkdir(parents=True, exist_ok=True)
    figs = out / 'figures'; figs.mkdir(exist_ok=True)
    rows, events, temporal = [], [], []
    for p in m['jobs']:
        if p['status'] != 'complete': raise ValueError('Incomplete point')
        raw_path, count_path = data / p['raw_file'], data / p['counts_file']
        if sha(raw_path) != p['raw_sha256'] or sha(count_path) != p['counts_sha256']:
            raise ValueError('Raw data hash mismatch')
        with gzip.open(raw_path, 'rb') as f: payload = f.read()
        if len(payload) != c['samples'] * 8: raise ValueError('Raw byte count mismatch')
        raw = np.frombuffer(payload, dtype='<u8')
        if not np.all(raw > 0): raise ValueError('Nonpositive samples')
        divisor, counted = denominators(c, p)
        stats = summarize(raw, divisor)
        if stats != p['statistics']: raise ValueError('Statistics mismatch')
        counts = json.loads(count_path.read_text()); validate_counts(counts, c, p)
        row = {k: p[k] for k in ('name', 'group') + (('stride', 'alignment', 'mode', 'seed') if args.experiment == 'line_size' else ('num_sets', 'k', 'max_k'))}
        row.update(point_name=p.get('point_name', p['name']), pmu_pass=p.get('pmu_pass', 'all'))
        row.update({k: v for k, v in stats.items() if k != 'decile_medians'})
        row.update(timed_loads_per_batch=divisor, counted_chain_loads=counted,
                   legacy_median=p['legacy_median'], baseline_median=baseline(c, p),
                   units='TSC ticks / timed chain load', **p['measurement_events'])
        row.update({f'l{i}_misses_per_1000_chain_loads': None for i in (1, 2, 3)})
        row['all_loads_per_1000_chain_loads'] = None
        for i, count in zip(p.get('event_indices', range(len(c['events']))), counts['events']):
            event = c['events'][i]
            rate = count['count'] * 1000 / counted
            row[f'l{i+1}_misses_per_1000_chain_loads' if i < 3 else 'all_loads_per_1000_chain_loads'] = rate
            events.append(dict(name=p['name'], event=event['name'], raw_config=event['config'], count=count['count'],
                               counted_chain_loads=counted, per_1000_chain_loads=rate,
                               time_enabled_ns=counts['time_enabled_ns'], time_running_ns=counts['time_running_ns']))
        rows.append(row)
        temporal.extend(dict(name=p['name'], block=i+1, median=value) for i, value in enumerate(stats['decile_medians']))
    write_csv(out / 'summary.csv', rows); write_csv(out / 'pmu_counts.csv', events)
    write_csv(out / 'temporal_medians.csv', temporal)
    plots(c, rows, figs)
    env = json.loads((data / 'environment.json').read_text())
    quality = dict(preflight_busy_percent=env['preflight_busy_percent'],
                   max_sibling_busy_percent=max((v for p in m['jobs'] for cpu,v in p['cpu_busy_percent'].items() if int(cpu) != c['cpu']), default=None),
                   total_involuntary_switches=sum(p['measurement_events']['involuntary_switches'] for p in m['jobs']),
                   total_minor_faults=sum(p['measurement_events']['minor_faults'] for p in m['jobs']),
                   total_major_faults=sum(p['measurement_events']['major_faults'] for p in m['jobs']),
                   temporal_max_min={p['name']:max(p['statistics']['decile_medians'])/min(p['statistics']['decile_medians']) for p in m['jobs']},
                   huge_kib={p['name']:p['anon_huge_kib_before_after'] for p in m['jobs']},
                   caveat=c.get('placement_note', 'No prior placement comparison supplied.') + ' PMU loop totals include helper loads.')
    save(out / 'quality.json', quality)
    save(out / 'validation.json', dict(status='passed', configurations=len(rows), timed_batches=sum(r['n'] for r in rows),
         unique_workloads=len({r['point_name'] for r in rows}), event_passes=c.get('event_passes'),
         phase1_freeze=c.get('phase1_freeze'),
         raw_hashes_lengths_and_statistics_verified=True, actual_load_denominators_verified=True,
         all_pmu_groups_without_multiplexing=True, note='Integrity checks, not proof of exact physical geometry.'))
    print(f'{args.experiment}: validated {len(rows)} configurations; wrote statistics and two PNG/PDF figures.')


if __name__ == '__main__':
    main()
