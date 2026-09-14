#!/usr/bin/env python3
"""Reconstruct every statistic, check provenance, and compare frozen estimates."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from estimator import estimate, read_raw, statistics

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pmu_reference(metadata, expected, tolerance):
    p = metadata['pmu']
    loads, misses = p['retired_loads'], p['l1_misses']
    if p['time_running_ns'] <= 0 or p['time_running_ns'] != p['time_enabled_ns']:
        raise ValueError('PMU group is not continuously scheduled')
    if loads <= 0 or misses < 0 or misses > loads:
        raise ValueError('Invalid load/miss counts')
    if loads < expected or loads - expected > tolerance * expected:
        raise ValueError('Auxiliary loads or event undercount invalidate the denominator')
    return 1 - misses / loads


def target_reference_bounds(metadata, expected):
    """Bounds allowing every extra retired load to be either hit or miss.

    Conditional on valid event counting; not a bound on PMU implementation error.
    """
    p = metadata['pmu']
    extra = p['retired_loads'] - expected
    if extra < 0:
        raise ValueError('Retired-load event undercounts known target accesses')
    return (max(0.0, 1 - p['l1_misses'] / expected),
            min(1.0, 1 - max(0, p['l1_misses'] - extra) / expected))


def write_csv(path, rows):
    with Path(path).open('w', newline='') as f:
        out = csv.DictWriter(f, fieldnames=list(rows[0]))
        out.writeheader(); out.writerows(rows)


def figures(out, jobs, arrays, model, comparison, cases):
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    def save(name, fig):
        fig.tight_layout()
        fig.savefig(out / (name + '.pdf'))
        fig.savefig(out / (name + '.png'), dpi=180)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    maximum = max(np.percentile(arrays['hit_fit_software'], 99.5), np.percentile(arrays['miss_fit_software'], 99.5))
    bins = np.arange(0, int(maximum) + 3, max(1, int(maximum) // 160))
    for key, label in [('hit_fit_software', '8 KiB: expected L1 hit'), ('miss_fit_software', '512 KiB: expected L1 miss')]:
        ax.hist(arrays[key], bins=bins, weights=np.full(len(arrays[key]), 1 / len(arrays[key])),
                histtype='step', linewidth=1.5, label=label)
    ax.axvline(model['threshold_ticks'], color='black', linestyle='--', label=f"Frozen threshold: {model['threshold_ticks']} ticks")
    ax.set(xlabel='Single target-load interval (raw timer ticks, fences included)', ylabel='Fraction of all samples per bin',
           title='Timing-only calibration (zoom; full tails preserved in raw data)')
    ax.legend(); save('calibration', fig)

    fig, ax = plt.subplots(figsize=(10, 4.8))
    boxes = []
    for case in cases:
        x = arrays[f'{case}_r1_pmu']; s = statistics(x)
        boxes.append(dict(label=case.replace('_', '\n'), med=s['median'], q1=s['q1'], q3=s['q3'],
                          whislo=s['whisker_low'], whishi=s['whisker_high'], fliers=[]))
    ax.bxp(boxes, showfliers=False)
    ax.axhline(model['threshold_ticks'], color='tab:red', linestyle='--')
    ax.set(yscale='log', ylabel='Raw timer ticks per target load',
           title='Validation distributions, repeat 1 (1M samples each; 1.5 IQR whiskers)')
    fig.text(.5, .005, 'Outlier points omitted in this view; exact counts and complete samples are retained.', ha='center', fontsize=8)
    save('validation_boxplots', fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    x = np.arange(len(cases))
    for column, label, offset in [('software_same_run', 'Timing classifier (PMU validation execution)', -.12),
                                  ('pmu_hit_rate', 'PMU reference', 0),
                                  ('software_standalone', 'Separate estimator-only execution', .12)]:
        values = [np.array([r[column] for r in comparison if r['case'] == case]) * 100 for case in cases]
        means = np.array([v.mean() for v in values])
        errors = np.array([[means[i] - v.min(), v.max() - means[i]] for i, v in enumerate(values)]).T
        axes[0].errorbar(x + offset, means, yerr=errors, fmt='o', capsize=3, label=label)
    axes[0].set(ylabel='L1D hit rate (%)', ylim=(-4, 104), title='Frozen classifier versus PMU (mean and range of three repeats)')
    axes[0].legend(fontsize=8)
    values = [np.mean([r['absolute_error_pp'] for r in comparison if r['case'] == case]) for case in cases]
    axes[1].bar(x, values, color='tab:orange')
    axes[1].set(ylabel='Mean absolute error\n(percentage points)', xticks=x,
                xticklabels=[c.replace('_', '\n') for c in cases])
    save('hit_rate_comparison', fig)

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.axis('off')
    boxes = [(.02, .54, .27, .35, '1. Calibrate without counters\nSmall random ring: A → B → C → A\nLarge random ring: A → ... → A\n1M single-load timings per point'),
             (.36, .54, .27, .35, '2. Freeze a timing threshold\nFit hit/miss distributions\nCheck with independent seeds\nNo PMU inputs to classifier'),
             (.70, .54, .28, .35, '3. Held-out workloads\nChange footprint and node reuse\nTime one load at a time\n3 repeats × 1M accesses/case'),
             (.02, .04, .44, .32, 'Actual sample: fence → timer → load *p → timer\nSave raw delta; optionally repeat p, otherwise p = next\nCount hit when delta ≤ frozen threshold'),
             (.54, .04, .44, .32, '4. Validation copy: same exact assembly loop\nPMU counts only around 1M-load loop\nReference = 1 − L1 misses / retired loads\nCheck auxiliary loads; compare error and uncertainty')]
    from matplotlib.patches import FancyBboxPatch
    for left, bottom, width, height, text in boxes:
        ax.add_patch(FancyBboxPatch((left, bottom), width, height, boxstyle='round,pad=0.01',
                                    facecolor='#f0f5fa', edgecolor='#58728a', transform=ax.transAxes))
        ax.text(left + width / 2, bottom + height / 2, text, ha='center', va='center', transform=ax.transAxes, fontsize=9)
    for a, b in [((.29, .71), (.36, .71)), ((.63, .71), (.70, .71)), ((.84, .54), (.77, .37))]:
        ax.annotate('', xy=b, xytext=a, xycoords='axes fraction', arrowprops={'arrowstyle': '->'})
    save('methodology', fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--machine', required=True); ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    folder = ROOT / 'data' / args.machine / args.run_id
    out = ROOT / 'results' / args.machine / args.run_id
    (out / 'figures').mkdir(parents=True, exist_ok=True)
    # Analysis may be improved after collection; preserve its exact final source
    # separately without editing the original run/source checkpoint.
    analysis_source = out / 'analysis_source'
    analysis_source.mkdir(exist_ok=True)
    for name in ['analyze.py', 'estimator.py']:
        shutil.copy2(ROOT / 'scripts' / name, analysis_source / name)
    (analysis_source / 'sha256.json').write_text(json.dumps(
        {name: digest(analysis_source / name) for name in ['analyze.py', 'estimator.py']}, indent=2) + '\n')
    cfg = json.loads((folder / 'config.json').read_text())
    manifest = json.loads((folder / 'manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError('Only complete formal runs may produce final results')
    model = json.loads((folder / 'model.json').read_text())
    checkpoint = json.loads((folder / 'threshold-checkpoint.json').read_text())
    if digest(folder / 'model.json') != checkpoint['model_sha256']:
        raise ValueError('Frozen threshold was modified')
    for name, sha in json.loads((folder / 'source' / 'sha256.json').read_text()).items():
        if digest(folder / 'source' / name) != sha:
            raise ValueError(f'Source snapshot changed: {name}')
    arrays, metas, estimates, all_rows = {}, {}, {}, []
    for job in manifest['jobs']:
        x, sha = read_raw(folder / job['raw_file'])
        if sha != job['raw_sha256'] or len(x) != cfg['samples'] or statistics(x) != job['statistics']:
            raise ValueError(f"Raw hash/count/statistic mismatch: {job['name']}")
        if digest(folder / job['metadata_file']) != job['metadata_sha256']:
            raise ValueError('Metadata hash mismatch')
        m = json.loads((folder / job['metadata_file']).read_text())
        if m['cpu_before'] != cfg['cpu'] or m['cpu_after'] != cfg['cpu']:
            raise ValueError('Recorded CPU differs from requested placement')
        if job['phase'] != 'calibration' and job['started_utc'] <= checkpoint['created_utc']:
            raise ValueError('Verification predates threshold checkpoint')
        e = estimate(x, model)
        if job['phase'] == 'validation' and e['classified_hits'] != m['classified_hits']:
            raise ValueError('Python reconstruction differs from standalone C classifier')
        arrays[job['name']], metas[job['name']], estimates[job['name']] = x, m, e
        all_rows.append({'name': job['name'], 'phase': job['phase'], 'bytes': job['bytes'],
                         'reuse': job['reuse'], 'pmu_enabled': job['pmu_enabled'], **job['statistics'],
                         'software_hit_rate': e['software_hit_rate'], 'ci95_low': e['block_bootstrap_95'][0],
                         'ci95_high': e['block_bootstrap_95'][1], 'raw_sha256': sha})
    control = metas['counter_overhead_pmu']['pmu']
    if control['retired_loads'] > cfg['samples'] * cfg['max_auxiliary_load_fraction']:
        raise ValueError('Empty-loop PMU overhead exceeds permitted denominator bound')
    rows = []
    for j in manifest['jobs']:
        if j['phase'] != 'validation' or not j['pmu_enabled']:
            continue
        key = j['name']; pure = j['id'] + '_software'
        e, m, other = estimates[key], metas[key], estimates[pure]
        reference = pmu_reference(m, cfg['samples'], cfg['max_auxiliary_load_fraction'])
        reference_low, reference_high = target_reference_bounds(m, cfg['samples'])
        error = abs(e['software_hit_rate'] - reference)
        lo, hi = e['block_bootstrap_95']
        rows.append({'case': j['case'], 'repeat': j['repeat'] + 1, 'bytes': j['bytes'], 'reuse': j['reuse'],
                     'software_same_run': e['software_hit_rate'], 'pmu_hit_rate': reference,
                     'absolute_error_pp': error * 100,
                     'relative_error_percent': error / reference * 100 if reference else None,
                     'software_standalone': other['software_hit_rate'],
                     'standalone_paired_error_pp': abs(other['software_hit_rate'] - reference) * 100,
                     'ci95_low': lo, 'ci95_high': hi,
                     'threshold_sensitivity_low': e['threshold_sensitivity_rates'][0],
                     'threshold_sensitivity_high': e['threshold_sensitivity_rates'][1],
                     'pmu_l1_misses': m['pmu']['l1_misses'], 'pmu_retired_loads': m['pmu']['retired_loads'],
                     'pmu_target_hit_bound_low': reference_low, 'pmu_target_hit_bound_high': reference_high,
                     'auxiliary_loads': m['pmu']['retired_loads'] - cfg['samples']})
    write_csv(out / 'statistics.csv', all_rows); write_csv(out / 'comparison.csv', rows)
    result = {'status': 'passed', 'scope': 'Integrity, sample counts, classifier reconstruction, placement, source checkpoint and PMU denominator; not proof of universal estimator accuracy',
              'machine': args.machine, 'run_id': args.run_id, 'configurations': len(manifest['jobs']),
              'timed_samples': manifest['timed_samples'], 'validation_pairs': len(rows),
              'threshold_ticks': model['threshold_ticks'], 'model_sha256': checkpoint['model_sha256'],
              'all_pmu_groups_without_multiplexing': True,
              'max_auxiliary_loads': max(abs(r['auxiliary_loads']) for r in rows),
              'max_auxiliary_reference_bound_pp': max(abs(r['auxiliary_loads']) for r in rows) / cfg['samples'] * 100,
              'empty_loop_retired_loads': control['retired_loads'],
              'mean_absolute_error_pp': float(np.mean([r['absolute_error_pp'] for r in rows])),
              'worst_absolute_error_pp': float(max(r['absolute_error_pp'] for r in rows)),
              'standalone_paired_mean_absolute_error_pp': float(np.mean([r['standalone_paired_error_pp'] for r in rows])),
              'total_minor_faults': sum(m['minor_faults'] for m in metas.values()),
              'total_major_faults': sum(m['major_faults'] for m in metas.values()),
              'total_involuntary_switches': sum(m['involuntary_switches'] for m in metas.values())}
    (out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    cases = [p['id'] for p in cfg['validation']]
    figures(out / 'figures', manifest['jobs'], arrays, model, rows, cases)
    report = [f"# {args.machine}: Section 8.5 software-only L1D hit-rate estimator", '',
              f"Completed `{args.run_id}`: {result['timed_samples']:,} single-access timing samples, "
              f"five timing-only calibration configurations, one empty PMU control, and {len(rows)} paired validations "
              f"({len(cases)} workloads × {cfg['repeats']} repeats × estimator-only/PMU executions). Every configuration retains {cfg['samples']:,} samples.", '',
              f"The timing-only threshold is **hit iff raw interval ≤ {model['threshold_ticks']} ticks**. "
              f"Balanced training error is {100 * model['balanced_training_error']:.3f}%; independent-seed calibration "
              f"check error is {100 * model['holdout_balanced_error']:.3f}%. Threshold selection never used PMU data. "
              'Calibration labels mean strongly expected L1-resident/non-resident states, not hardware-proven per-access labels.', '',
              f"Mean absolute error over all {len(rows)} same-execution validation cases is **{result['mean_absolute_error_pp']:.3f} percentage points**, "
              f"with worst-case **{result['worst_absolute_error_pp']:.3f} pp**. Separate estimator-only executions versus their paired PMU references "
              f"have mean absolute error **{result['standalone_paired_mean_absolute_error_pp']:.3f} pp**; that comparison additionally includes run-to-run drift.", '',
              '| Workload | Reuse | Software hit % (validation execution) | PMU hit % | Mean absolute error (pp) |',
              '|---|---:|---:|---:|---:|']
    for case in cases:
        r = [x for x in rows if x['case'] == case]
        report.append(f"| {case} | {r[0]['reuse']} | {np.mean([x['software_same_run'] for x in r])*100:.3f} | "
                      f"{np.mean([x['pmu_hit_rate'] for x in r])*100:.3f} | {np.mean([x['absolute_error_pp'] for x in r]):.3f} |")
    report += ['', '## Measurement and PMU reference', '',
               'Each interval contains one actual target load, not a divided batch latency. Reuse r means the same node is read r times before following its next pointer. '
               'A random ring determines node order. Reuse is a workload control; the estimator receives only timing samples and its threshold. '
               'The timer fences serialize even repeated visits. All measurement-loop state is in registers at -O0. '
               'One raw-output store per sample is essential for retaining the distribution; its cache effects remain part of the measured instrumented workload.', '',
               f"Placement: CPU {cfg['cpu']}, NUMA node {cfg['numa_node']}, local first touch with explicit memory binding, base pages, prefaulted chain/output, "
               'at least one million warm-up loads plus 2,048 discarded instrumentation warm-up samples. Raw times include fences/branch/timer overhead; '
               'they are not core cycles or uninstrumented load latency. The empty-timer distribution is retained rather than subtracting one minimum.', '',
               f"Reference events: `{cfg['pmu']['miss_event']}` ({cfg['pmu']['miss_config']}) and "
               f"`{cfg['pmu']['loads_event']}` ({cfg['pmu']['loads_config']}); per-thread, user mode, grouped and pinned, with equal enabled/running times. "
               'The reference is `1 - L1_misses / retired_loads`. All counters enclose the same single-load loop used by the estimator. '
               f"Maximum absolute difference between retired loads and {cfg['samples']:,} known target loads was {result['max_auxiliary_loads']} loads; "
               f"the empty-loop control recorded {result['empty_loop_retired_loads']} retired loads. "
               'Entry/exit helper loads are retained in the reference denominator, not silently subtracted. '
               'Their fraction bounds the possible mismatch between the all-load reference and target-only metric. '
               f"The largest such fraction was {result['max_auxiliary_reference_bound_pp']:.4f} pp, comparable to the measured mean error. "
               'Therefore this experiment does not establish target-only accuracy more precise than that reference limitation. '
               '`pmu_target_hit_bound_low/high` in the comparison table allow every auxiliary load to be either hit or miss; '
               'these bounds assume the events themselves count correctly. Near-zero PMU hit rates at the largest footprints can be predominantly helper hits. '
               'Calibration PMU values and per-access hardware labels are not used.', '',
               'Event provenance: the local Section 8.3 `perf list --details` is copied under the run preflight directory. '
               'The CPU-specific definitions can also be checked against [Intel perfmon, Sapphire Rapids](https://github.com/intel/perfmon/blob/main/SPR/events/sapphirerapids_core.json). '
               'Grouping and user/kernel counting scope follow [perf_event_open(2)](https://man7.org/linux/man-pages/man2/perf_event_open.2.html).', '',
               '## Uncertainty, limitations, and failure cases', '',
               '- `comparison.csv` reports the raw estimate, a 95% contiguous-block bootstrap interval, threshold sensitivity, absolute pp error and relative percent error for every repeat. '
               'The interval assumes approximately exchangeable blocks and conditions on the frozen classifier; it does not cover systematic misclassification. '
               'Absolute error is the useful metric near zero hit rate; relative error becomes unstable and is undefined for a zero PMU reference.',
               '- A fixed threshold can fail when L1-hit and L2-hit intervals overlap, frequency or interference shifts timing, or the generic timer is too coarse. '
               f"The runner refuses calibration with more than {100 * cfg['max_balanced_calibration_error']:g}% balanced training/check error. Passing that check does not guarantee unseen-workload accuracy.",
               '- Repeated loads, prefetching, fill-buffer service, TLB misses, logging stores and interrupts can change observed timings. '
               'The estimate describes these explicitly instrumented microbenchmarks, not an arbitrary application with no timing overhead. '
               'No claim is made that a nominal reuse factor guarantees an exact hardware hit rate.',
               '- The 48 KiB case has a low measured hit rate because the instrumented footprint also competes with output logging and other cache occupants. '
               'It is a hit-rate test, not a new estimate of physical L1 capacity. The repeated-node mixed cases deliberately provide different hit fractions; '
               'their success is not evidence of comparable accuracy on arbitrary access streams.',
               '- Only Artemisia is experimentally validated here. x86-64 and AArch64 instruction paths share the algorithm, but the Arm path is untested; '
               'single-access Arm timer resolution may make calibration fail. Other CPUs require their own calibration and semantically valid PMU configuration. '
               'This retired-load ratio must not be copied to AMD/Arm refill/dispatch events without denominator validation.',
               f"- Recorded quality: {result['total_minor_faults']} minor faults, {result['total_major_faults']} major faults and "
               f"{result['total_involuntary_switches']} involuntary switches across all measurement regions. Per-run CPU/sibling activity is retained in the manifest.", '',
               '## Reproduction and figures', '',
               f"`python3 scripts/analyze.py --machine {args.machine} --run-id {args.run_id}` reopens every compressed raw array, verifies hashes and recomputes statistics and figures. "
               'The analyzer verifies the frozen model, every archived source/binary hash and the C/Python classifier counts. '
               'See `statistics.csv`, `comparison.csv`, `validation.json` and `figures/` (calibration, boxplots, hit-rate/error comparison, methodology; PNG and PDF). '
               'The exact final analyzer is retained in `analysis_source/`, separately from the unchanged pre-collection source checkpoint.', '',
               'The run contains exact commands, effective config, raw uint64 timing arrays, metadata, local event descriptions, compiler/CPU topology, source and executable/disassembly snapshots. '
               'The threshold checkpoint predates validation; it is not an official Git competition freeze. '
               'Commit the final estimator, parameters and results and record that commit before official scoring. No commit/push is performed by this workflow.', '']
    (out / 'RUN_NOTES.md').write_text('\n'.join(report))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
