"""Join two identical workload passes, keeping their timings and counts separate."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from support import PMU, frozen_check, sha


def read_csv(path):
    return list(csv.DictReader(path.open()))


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)


def join(experiment):
    ids = [experiment + '01', experiment + '02_refills']
    data = [PMU / experiment / 'data/skylark' / run for run in ids]
    result = [PMU / experiment / 'results/skylark' / run for run in ids]
    configs = [json.loads((d / 'config.json').read_text()) for d in data]
    workload = [{k: v for k, v in c.items() if k not in ('events', 'counter_pass')} for c in configs]
    if workload[0] != workload[1]:
        raise ValueError('Counter passes changed workload parameters')
    if sha(data[0] / 'benchmark.bin') != sha(data[1] / 'benchmark.bin'):
        raise ValueError('Counter passes used different benchmark binaries')
    for d, r in zip(data, result):
        if json.loads((r / 'validation.json').read_text())['status'] != 'passed':
            raise ValueError('Analyze each pass before combining')
        p = json.loads((r / 'provenance.json').read_text())
        if sha(d / 'manifest.json') != p['manifest_sha256']:
            raise ValueError('Input manifest changed since validation')
    summaries = [{r['name']: r for r in read_csv(p / 'summary.csv')} for p in result]
    if set(summaries[0]) != set(summaries[1]):
        raise ValueError('Counter pass point sets differ')
    if experiment == 'capacity':
        old = read_csv(PMU.parent / 'timing-only/capacity/results/skylark/combined12/summary.csv')
    rows = []
    for name in summaries[0]:
        a, b = [s[name] for s in summaries]
        keys = ('region', 'bytes') if experiment == 'capacity' else (
            ('group', 'stride', 'alignment', 'mode', 'seed') if experiment == 'line_size' else
            ('group', 'num_sets', 'k', 'max_k'))
        row = dict(name=name, **{key: a[key] for key in keys})
        if experiment == 'capacity':
            matches = [r for r in old if int(r['bytes']) == int(a['bytes']) and
                       all(int(r[k]) == configs[0][k] for k in ('seed', 'batch', 'spacing', 'samples')) and
                       all(r[k] == configs[0][k] for k in ('pages', 'mode'))]
            if len(matches) != 1: raise ValueError('Ambiguous baseline')
            prior = float(matches[0]['median'])
        else:
            prior = float(a['baseline_median'])
        row.update(baseline_median=prior, pass1_median=float(a['median']), pass2_median=float(b['median']),
                   pass2_vs_pass1_percent=100 * (float(b['median']) / float(a['median']) - 1),
                   samples_per_pass=int(a['n']), units='TSC ticks / timed chain load')
        if int(a['n']) != 1000000 or a['n'] != b['n']:
            raise ValueError('Expected one million samples in each separate pass')
        for c, source in zip(configs, (a, b)):
            for event in c['events']:
                key = event['name'] + '_per_1000_chain_loads' if experiment == 'capacity' else event['field']
                row[event['field']] = float(source[key])
        rows.append(row)
    return rows, data, result


def save_figure(fig, out, name):
    for ext in ('png', 'pdf'):
        fig.savefig(out / (name + '.' + ext), dpi=180)
    plt.close(fig)


def plot_capacity(rows, out):
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5), layout='constrained')
    fields = [('local_l2_demand_fills_per_1000_chain_loads', 'Demand fills from local L2 (pass 2)'),
              ('l2_dc_request_misses_per_1000_chain_loads', 'L2 data-cache request misses (pass 1)'),
              ('local_dram_io_fills_per_1000_chain_loads', 'Local DRAM/IO demand fills (pass 1)')]
    for col, region in enumerate(('L1', 'L2', 'LLC')):
        chosen = sorted([r for r in rows if r['region'] == region], key=lambda r: int(r['bytes']))
        divisor = 1024 if region == 'L1' else 1024**2
        x = [int(r['bytes']) / divisor for r in chosen]
        for key, color, label in [('baseline_median', '0.5', 'Frozen timing-only'),
                                   ('pass1_median', '#166aa0', 'Counter pass 1'),
                                   ('pass2_median', '#d08014', 'Counter pass 2')]:
            axes[0, col].plot(x, [r[key] for r in chosen], 'o-', color=color, label=label)
        axes[0, col].set(title=region + ' capacity region', ylabel='TSC ticks / dependent load')
        field, label = fields[col]
        axes[1, col].plot(x, [r[field] for r in chosen], 'o-', color='#48834b')
        axes[1, col].set(title=label, ylabel='Events / 1,000 chain loads', ylim=(0, None))
        axes[0, col].legend(fontsize=8)
        for ax in axes[:, col]:
            ax.set_xlabel('Working set (' + ('KiB' if region == 'L1' else 'MiB') + ')')
            ax.set_xticks(x)
    fig.suptitle('Skylark capacity: frozen timings and level-specific request/refill evidence')
    save_figure(fig, out, 'capacity_combined')


def plot_other(experiment, rows, out):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), layout='constrained')
    for col in range(2):
        if experiment == 'line_size':
            offset = (0, 16)[col]
            chosen = [r for r in rows if r['mode'] == 'random_lines' and int(r['alignment']) == offset]
            key, title, xlabel = 'stride', f'Random windows, offset {offset} B', 'Stride (B)'
        else:
            group = ('L1', 'L2_candidate')[col]
            chosen = [r for r in rows if r['group'] == group]
            key, title, xlabel = 'k', ('4 KiB address spacing' if col == 0 else '64 KiB address spacing'), 'K (addresses)'
        chosen.sort(key=lambda r: int(r[key])); x = [int(r[key]) for r in chosen]
        for field, color, label in [('baseline_median', '0.5', 'Frozen timing-only'),
                                    ('pass1_median', '#166aa0', 'Counter pass 1'),
                                    ('pass2_median', '#d08014', 'Counter pass 2')]:
            axes[0, col].plot(x, [r[field] for r in chosen], 'o-', color=color, label=label)
        for field, color, label in [('local_l2_demand_fills_per_1000_chain_loads', '#48834b', 'Demand fills from local L2 (pass 2)'),
                                    ('l2_dc_request_misses_per_1000_chain_loads', '#b93c37', 'L2 DC request misses (pass 1)'),
                                    ('local_cache_demand_fills_per_1000_chain_loads', '#72559b', 'Local cache-domain fills (pass 2)')]:
            axes[1, col].plot(x, [r[field] for r in chosen], 'o-', color=color, label=label)
        axes[0, col].set(title=title, ylabel='TSC ticks / timed chain load')
        axes[1, col].set(ylabel='Events / 1,000 chain loads', ylim=(0, None))
        for ax in axes[:, col]:
            ax.set_xlabel(xlabel); ax.set_xticks(x); ax.legend(fontsize=8)
    fig.suptitle('Skylark ' + experiment + ': separate counter passes; rates are not miss probabilities')
    save_figure(fig, out, experiment + '_combined')


def main():
    frozen_check()
    out = PMU / 'skylark/results'; out.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size': 10, 'pdf.fonttype': 42})
    audits, manifests = [], []
    for experiment in ('capacity', 'line_size', 'associativity'):
        rows, data, result = join(experiment)
        write_csv(out / (experiment + '_eight_events.csv'), rows)
        if experiment == 'capacity': plot_capacity(rows, out)
        else: plot_other(experiment, rows, out)
        audits.append(dict(experiment=experiment, points=len(rows), samples_per_point_per_pass=1000000,
                           same_workload_and_binary_between_passes=True,
                           max_absolute_median_change_percent=max(abs(r['pass2_vs_pass1_percent']) for r in rows),
                           source_hashes={str(p.relative_to(PMU)): sha(p) for root in result
                                          for p in (root / 'summary.csv', root / 'validation.json', root / 'provenance.json')}))
        manifests += [json.loads((d / 'manifest.json').read_text()) for d in data]
    ordered = sorted(manifests, key=lambda m: m['started_utc'])
    for a, b in zip(ordered, ordered[1:]):
        if a['finished_utc'] > b['started_utc']:
            raise ValueError('Formal collection runs overlapped')
    (out / 'combined_validation.json').write_text(json.dumps(dict(status='passed',
        distinct_workload_points=38, event_groups=2, distinct_events=8,
        total_timed_batches=76000000, formal_collections_serial=True,
        no_counts_combined_into_same_run_probabilities=True, experiments=audits), indent=2) + '\n')
    print('Validated 38 identical workload pairs, eight events in two separate groups, 76 million timed batches.')


if __name__ == '__main__':
    main()
