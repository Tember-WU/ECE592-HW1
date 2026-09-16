#!/usr/bin/env python3
"""Rebuild tables and figures; --collect imports existing lab summaries, never benchmarks."""
import argparse
import csv
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(HERE / '.cache/matplotlib'))
import lab_data as lab
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter


def write_csv(relative, rows):
    path = HERE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)


def read_csv(relative):
    with (HERE / relative).open() as f:
        return list(csv.DictReader(f))


def collect(cfg):
    if (HERE / 'freeze/manifest.json').exists():
        raise SystemExit('Collection disabled after freeze; use a new analysis directory for new data.')
    src = lab.Sources()
    data = lab.extract(src, cfg)
    names = ['chronological_master', 'capacity', 'latency', 'associativity', 'inclusion',
             'line_size_candidates', 'line_size_evidence', 'software_metric',
             'pmu_normalized', 'pmu_semantics', 'phase2_verification']
    lab.dump(HERE / 'inputs/lab_snapshot.json', {
        'schema_version': 1, 'data': data,
        'tables': {name: read_csv('tables/' + name + '.csv') for name in names}})
    lab.dump(HERE / 'inputs/source_manifest.json', src.manifest)


def ols(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if np.ptp(y) < 1e-12:
        return {'intercept_at_2014': float(y[0]), 'slope_per_year': 0.0,
                'r_squared': None, 'rmse': 0.0, 'flat_baseline_rmse': 0.0}
    b, a = np.polyfit(x - 2014, y, 1)
    fitted = a + b * (x - 2014)
    sst = float(np.sum((y - y.mean()) ** 2))
    return {'intercept_at_2014': float(a), 'slope_per_year': float(b),
            'r_squared': None if sst < 1e-20 else float(1 - np.sum((y - fitted) ** 2) / sst),
            'rmse': float(np.sqrt(np.mean((y - fitted) ** 2))),
            'flat_baseline_rmse': float(np.sqrt(np.mean((y - y.mean()) ** 2)))}


def quantitative_trends(machines):
    metrics = {'l1d_capacity_KiB': ('l1d_inferred_bytes', 1024, 'log2(KiB)'),
               'l2_capacity_KiB': ('l2_inferred_bytes', 1024, 'log2(KiB)'),
               'l2_l1_latency_ratio': ('l2_l1_ratio', 1, 'ratio')}
    cohorts = {'pooled_all_lab': lab.HOSTS,
               'Intel_lab': [h for h in lab.HOSTS if lab.GROUP[h] == 'Intel x86'],
               'Intel_desktop': lab.DESKTOP}
    summaries, residuals, loo_rows, steps = [], [], [], []
    for metric, (key, scale, unit) in metrics.items():
        for cohort, hosts in cohorts.items():
            x = np.array([machines[h]['year'] for h in hosts], float)
            raw = np.array([machines[h][key] / scale for h in hosts])
            y = np.log2(raw) if unit.startswith('log2') else raw
            fit = ols(x, y)
            errors, flat_errors = [], []
            for i, h in enumerate(hosts):
                mask = np.arange(len(hosts)) != i
                leave = ols(x[mask], y[mask])
                predicted = leave['intercept_at_2014'] + leave['slope_per_year'] * (x[i] - 2014)
                error = float(predicted - y[i])
                errors.append(error)
                flat_errors.append(float(np.mean(y[mask]) - y[i]))
                loo_rows.append({'metric': metric, 'cohort': cohort, 'held_out_lab_host': h,
                                 'year': int(x[i]), 'observed_transformed': float(y[i]),
                                 'predicted_transformed': float(predicted), 'error': error,
                                 'unit': unit, 'scope': 'Lab sensitivity only; not Hazel validation'})
                fitted = fit['intercept_at_2014'] + fit['slope_per_year'] * (x[i] - 2014)
                residuals.append({'metric': metric, 'cohort': cohort, 'host': h, 'year': int(x[i]),
                                  'observed': float(raw[i]), 'fitted': float(2 ** fitted if unit.startswith('log2') else fitted),
                                  'residual_transformed': float(y[i] - fitted), 'transformed_unit': unit})
            slope = fit['slope_per_year']
            constant = bool(np.ptp(y) < 1e-12)
            summaries.append({'metric': metric, 'cohort': cohort, 'n_lab_hosts': len(hosts),
                              'training_hosts': ','.join(hosts), 'first_year': int(min(x)), 'last_year': int(max(x)),
                              'model': 'ordinary least squares', 'response_unit': unit, **fit,
                              'doubling_years': float(1 / slope) if unit.startswith('log2') and slope > 1e-10 else None,
                              'annual_multiplier': float(2 ** slope) if unit.startswith('log2') else None,
                              'leave_one_host_out_rmse': float(np.sqrt(np.mean(np.square(errors)))),
                              'flat_leave_one_host_out_rmse': float(np.sqrt(np.mean(np.square(flat_errors)))),
                              'observed_min': float(min(raw)), 'observed_max': float(max(raw)),
                              'interpretation': 'Constant in this cohort; doubling time undefined' if constant else
                              'Descriptive association with year; vendor and server/desktop mix are confounded'})
            changes = np.diff(raw)
            steps.append({'metric': metric, 'cohort': cohort, 'adjacent_pairs': len(changes),
                          'increases': int(sum(changes > 1e-10)), 'decreases': int(sum(changes < -1e-10)),
                          'unchanged': int(sum(abs(changes) <= 1e-10)),
                          'interpretation': 'Counts between sampled hosts; not design-change frequency or a causal lineage'})
    write_csv('tables/trend_summary.csv', summaries)
    write_csv('tables/trend_residuals.csv', residuals)
    write_csv('tables/lab_leave_one_out.csv', loo_rows)
    write_csv('tables/observed_step_counts.csv', steps)
    lookup = {(r['metric'],r['cohort']): r for r in summaries}
    l2 = lookup[('l2_capacity_KiB','pooled_all_lab')]
    intel = lookup[('l2_capacity_KiB','Intel_lab')]
    ratio = lookup[('l2_l1_latency_ratio','pooled_all_lab')]
    write_csv('tables/trend_interpretation.csv', [
        {'metric':'L2 capacity', 'finding':'Growth in the pooled sample',
         'quantitative_evidence':f"OLS log2 slope={l2['slope_per_year']:.6f}/year; doubling time={l2['doubling_years']:.4f} years; R2={l2['r_squared']:.4f}",
         'interpretation':'An empirical description of eight mixed lab hosts; not a causal or universal technology law.'},
        {'metric':'L2 capacity', 'finding':'Large cohort dependence',
         'quantitative_evidence':f"Intel leave-one-out RMSE={intel['leave_one_host_out_rmse']:.4f} log2 KiB versus flat baseline={intel['flat_leave_one_host_out_rmse']:.4f}; four desktop hosts all have 256 KiB",
         'interpretation':'Removing the latest server changes the trend substantially. Do not attribute the pooled growth solely to elapsed years.'},
        {'metric':'L1D capacity', 'finding':'Mostly constant with architectural steps',
         'quantitative_evidence':'Six hosts have 32 KiB, one has 64 KiB, and one has 48 KiB; four desktop hosts all have 32 KiB',
         'interpretation':'The cross-host sequence is non-monotonic. A pooled median and full sampling-bracket envelope are used for prediction.'},
        {'metric':'L2/L1 resident latency', 'finding':'Weak temporal fit',
         'quantitative_evidence':f"OLS slope={ratio['slope_per_year']:.6f}/year; R2={ratio['r_squared']:.4f}; observed range={ratio['observed_min']:.4f}-{ratio['observed_max']:.4f}",
         'interpretation':'Use an empirical median with an observed-variability envelope; do not extrapolate a strong latency growth law.'},
        {'metric':'Other inferred quantities', 'finding':'Insufficient comparable numerical evidence',
         'quantitative_evidence':'Exact timing-derived LLC capacities: 0/8; unique timing line-size estimates: 0/8; software standardized-workload hosts: 2/8',
         'interpretation':'Retain observations, separate validation, and explicit uncertainty; do not fit or invent missing results.'},
    ])
    return summaries


def anchored_l2(machines, hosts, field='l2_inferred_bytes'):
    x = np.array([machines[h]['year'] for h in hosts], float)
    y = np.log2([machines[h][field] / 1024 for h in hosts])
    anchor = int(np.argmax(x))
    dx = x - x[anchor]
    slope = float(np.dot(dx, y - y[anchor]) / np.dot(dx, dx))
    return {'anchor_host': hosts[anchor], 'anchor_year': int(x[anchor]),
            'anchor_KiB': float(2 ** y[anchor]), 'log2_slope_per_year': slope}


def l2_value(model, year):
    return model['anchor_KiB'] * 2 ** (model['log2_slope_per_year'] * (year - model['anchor_year']))


def predictions(machines):
    hosts = lab.HOSTS
    targets = read_csv('inputs/hazel_targets.csv')
    base = anchored_l2(machines, hosts)
    variants, loo = [], []
    for h in hosts:
        model = anchored_l2(machines, [v for v in hosts if v != h])
        expected = machines[h]['l2_inferred_bytes'] / 1024
        prediction = l2_value(model, machines[h]['year'])
        error = float(np.log2(prediction / expected))
        variants.append({'variant': 'leave_out_' + h, **model})
        loo.append({'held_out_lab_host': h, 'observed_KiB': expected, 'predicted_KiB': prediction,
                    'log2_prediction_error': error, 'scope': 'Lab-only diagnostic; anchor reselected within each fold'})
    for name, field in [('all_lower_brackets', 'l2_transition_low_bytes'), ('all_upper_brackets', 'l2_transition_high_bytes')]:
        variants.append({'variant': name, **anchored_l2(machines, hosts, field)})
    max_error = max(abs(row['log2_prediction_error']) for row in loo)
    common = {'training_hosts': hosts, 'n_lab_hosts': len(hosts), 'cohort': 'pooled Intel, AMD and Arm lab hosts',
              'hazel_observations_used': 0, 'year_range': [2014, 2023],
              'uncertainty_probability': None, 'validated_on_hazel': False}
    models = {
        'l1d_capacity_KiB': {**common, 'model_id': 'pooled_l1_empirical_median',
            'equation': 'C_L1(t) = median(lab L1D capacity in KiB)',
            'central': float(np.median([machines[h]['l1d_inferred_bytes'] / 1024 for h in hosts])),
            'low': min(machines[h]['l1d_transition_low_bytes'] / 1024 for h in hosts),
            'high': max(machines[h]['l1d_transition_high_bytes'] / 1024 for h in hosts),
            'uncertainty': 'Full observed lab sampling-bracket envelope; not a probabilistic prediction interval',
            'limitation': 'Constant reference rule; no increasing L1 trend imposed. Does not predict architectural steps.'},
        'l2_capacity_KiB': {**common, 'model_id': 'pooled_l2_anchored_log_linear', **base,
            'equation': 'C_L2(t) = anchor_KiB * 2**(b * (t - anchor_year)); b minimizes squared log2 residuals through latest lab point',
            'doubling_years': 1 / base['log2_slope_per_year'],
            'leave_one_host_out_rmse_log2': float(np.sqrt(np.mean([r['log2_prediction_error'] ** 2 for r in loo]))),
            'max_abs_leave_one_host_out_error_log2': max_error, 'sensitivity_models': variants,
            'uncertainty': 'Union of leave-one-host-out refits, all-lower/all-upper bracket refits, and central prediction times 2**(+/- max absolute lab leave-one-out log2 error); not a calibrated interval',
            'limitation': 'Latest-host anchor and mixed desktop/server cohort strongly affect the slope. AMD has only one training host. Continuous outputs are not rounded to physical cache sizes.'},
        'l2_l1_latency_ratio': {**common, 'model_id': 'pooled_relative_latency_empirical_median',
            'equation': 'R(t) = median(lab L2-resident median / L1-resident median)',
            'central': float(np.median([machines[h]['l2_l1_ratio'] for h in hosts])),
            'low': min(machines[h]['l2_l1_ratio_low'] for h in hosts),
            'high': max(machines[h]['l2_l1_ratio_high'] for h in hosts),
            'uncertainty': 'Envelope of within-host ratios formed from resident P05-P95 extrema over configurations; not a calibrated prediction interval',
            'limitation': 'Timer scale cancels algebraically; differing run frequencies, residency and contention do not. This does not predict absolute cycles or ns.'},
    }

    def estimate(metric, year):
        m = models[metric]
        if metric != 'l2_capacity_KiB':
            return m['central'], m['low'], m['high']
        center = l2_value(m, year)
        values = [l2_value(v, year) for v in variants] + [center * 2 ** (-max_error), center * 2 ** max_error, center]
        return center, min(values), max(values)

    rows, sensitivity = [], []
    for target in targets:
        year = int(target['generation_year'])
        for metric, model in models.items():
            central, low, high = estimate(metric, year)
            rows.append({'constraint': target['constraint'], 'generation': target['microarchitecture'],
                         'year': year, 'implementation_launch_year': int(target['implementation_launch_year']),
                         'metric': metric, 'prediction': central, 'low': low, 'high': high,
                         'unit': 'KiB/core' if 'capacity' in metric else 'ratio', 'model_id': model['model_id'],
                         'n_lab_hosts': len(hosts), 'model_scope': common['cohort'], 'status': 'prediction',
                         'year_relation': 'beyond lab years' if year > 2023 else 'within lab year range',
                         'availability': 'Not checked; assignment target only',
                         'overlap_note': target['lab_overlap_note'], 'uncertainty': model['uncertainty']})
            if year != int(target['implementation_launch_year']):
                sensitivity.append({'constraint': target['constraint'], 'metric': metric, 'main_year': year,
                                    'main_prediction': central, 'implementation_year': int(target['implementation_launch_year']),
                                    'alternative_prediction': estimate(metric, int(target['implementation_launch_year']))[0],
                                    'note': 'Chronology sensitivity only; main prediction retains the Section 8.1 generation-wide year convention'})
    write_csv('predictions/hazel_predictions.csv', rows)
    write_csv('predictions/chronology_sensitivity.csv', sensitivity)
    write_csv('predictions/l2_anchor_leave_one_out.csv', loo)
    lab.dump(HERE / 'predictions/model_parameters.json', models)
    training = []
    for h in hosts:
        m = machines[h]
        for metric, value, low, high in [
            ('l1d_capacity_KiB', m['l1d_inferred_bytes']/1024, m['l1d_transition_low_bytes']/1024, m['l1d_transition_high_bytes']/1024),
            ('l2_capacity_KiB', m['l2_inferred_bytes']/1024, m['l2_transition_low_bytes']/1024, m['l2_transition_high_bytes']/1024),
            ('l2_l1_latency_ratio', m['l2_l1_ratio'], m['l2_l1_ratio_low'], m['l2_l1_ratio_high'])]:
            training.append({'host': h, 'year': m['year'], 'group': lab.GROUP[h], 'metric': metric,
                             'value': value, 'low': low, 'high': high,
                             'source': m['capacity_source'] if 'capacity' in metric else m['latency_source']})
    write_csv('predictions/model_training_points.csv', training)
    curves = []
    for year in np.linspace(2014, 2024, 201):
        for metric in models:
            central, low, high = estimate(metric, float(year))
            curves.append({'year': float(year), 'metric': metric, 'prediction': central, 'low': low, 'high': high,
                           'role': 'future extrapolation' if year > 2023 else 'model evaluation within lab year range'})
    write_csv('predictions/model_curves.csv', curves)
    reasons = {
        'l1d_associativity_ways': 'Timing thresholds have candidate sensitivity and duplicate cross-host provenance; verified ways are separate.',
        'l2_associativity_ways': 'Several original L2 thresholds were L1 conflicts; insufficient uniform independent timing-only physical-way estimates.',
        'llc_capacity_bytes': 'Effective transition spans are not physical sharing-domain capacity estimates.',
        'llc_associativity_ways': 'Reliable LLC eviction was not established.',
        'l1_hit_absolute_latency': 'No calibrated x86 timer frequency or core-cycle measure; cannot transfer ticks to target CPUs.',
        'l2_hit_absolute_latency': 'No calibrated x86 timer frequency or core-cycle measure; relative latency is predicted instead.',
        'llc_hit_absolute_latency': 'Uncalibrated x86 ticks and sharing-domain/residency differences.',
        'l1_miss_penalty': 'Uncalibrated timer units and configuration-dependent differences of medians.',
        'l2_miss_penalty': 'Uncalibrated timer units and configuration-dependent differences of medians.',
        'llc_to_memory_miss_penalty': 'Uncalibrated timers, NUMA and memory-system differences are uncontrolled.',
        'line_size_bytes': 'Saved timing code marks a fixed 64-byte candidate; no unique data-derived size estimate.',
        'inclusion_policy': 'All supported lab classifications are uncertain; LLC eviction was not demonstrated.',
        'software_hit_rate': 'Identical standardized workload available on only two lab hosts; fewer than three observations.',
        'pmu_normalized_metrics': 'Target runtime PMU mappings and workloads are unverified.',
    }
    write_csv('predictions/unavailable_predictions.csv', [{'metric': k, 'status': 'abstained_for_all_targets', 'reason': v} for k, v in reasons.items()])
    matrix = [{'constraint': r['constraint'], 'metric': r['metric'], 'status': 'prediction',
               'prediction': r['prediction'], 'unit': r['unit'], 'reason': ''} for r in rows]
    matrix += [{'constraint': t['constraint'], 'metric': metric, 'status': 'abstained',
                'prediction': None, 'unit': None, 'reason': reason} for t in targets for metric, reason in reasons.items()]
    write_csv('predictions/hazel_prediction_matrix.csv', matrix)
    return models, rows, curves


def master_views(machines, pmu):
    for row in pmu:
        m = machines[row['host']]
        key = 'pmu_' + row['workload'] + '_' + row['slot']
        m[key + '_events_per_1000_pointer_loads'] = float(row['median'])
        m[key + '_event'] = row['event']
    write_csv('tables/chronological_master.csv', [machines[h] for h in lab.HOSTS])
    compact, latency = [], []
    short_arch = ['Haswell server', 'Skylake desktop', 'Kaby Lake', 'Coffee Lake',
                  'Coffee Lake refresh', 'Zen 2 / Rome', 'Neoverse N1 / Altra', 'Sapphire Rapids']
    for h, architecture in zip(lab.HOSTS, short_arch):
        m = machines[h]
        compact.append({'year': m['year'], 'host': h, 'vendor_ISA_group': lab.GROUP[h],
                        'microarchitecture': architecture, 'L1D_KiB_per_core': m['l1d_inferred_bytes']/1024,
                        'L2_KiB_per_core': m['l2_inferred_bytes']/1024,
                        'LLC_effective_transition_low_MiB': m['llc_transition_low_bytes']/1024**2,
                        'LLC_effective_transition_high_MiB': m['llc_transition_high_bytes']/1024**2,
                        'LLC_physical_capacity_inferred': None, 'line_size_inferred': None,
                        'line_size_candidate_bytes': 64, 'inclusion_policy': 'uncertain'})
        latency.append({'year': m['year'], 'host': h, 'native_unit': m['timer_unit'],
                        **{k: m[k] for k in ['l1_hit','l2_hit','llc_hit','l1_miss','l2_miss','llc_miss','l2_l1_ratio']},
                        'absolute_ns_available': m['ns_available'],
                        'note': 'Hits are resident medians; misses are incremental differences of medians'})
    write_csv('tables/chronological_capacity_summary.csv', compact)
    write_csv('tables/chronological_latency_summary.csv', latency)
    fig, ax = plt.subplots(figsize=(13, 4.6), layout='constrained')
    ax.axis('off')
    cells = [[r['year'], r['host'].title(), r['vendor_ISA_group'], r['microarchitecture'],
              f"{r['L1D_KiB_per_core']:.0f}", f"{r['L2_KiB_per_core']:.0f}",
              f"{r['LLC_effective_transition_low_MiB']:.0f}-{r['LLC_effective_transition_high_MiB']:.0f}"] for r in compact]
    table = ax.table(cellText=cells,
                     colLabels=['Year','Lab host','Vendor / ISA','Microarchitecture','L1D\nKiB/core','L2\nKiB/core','LLC transition*\nMiB'],
                     colWidths=[.055,.11,.12,.24,.10,.10,.14], cellLoc='center', bbox=[.02,.18,.96,.72])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.95)
    for (row, col), cell in table.get_celld().items():
        cell.set_linewidth(.6)
        if row == 0:
            cell.set_facecolor('.90')
            cell.set_text_props(weight='bold')
    ax.set_title('Chronological lab capacity overview', pad=12)
    ax.text(.5,.03,'* Effective LLC transition spans are not physical-capacity bounds.\nSampling brackets, CPU models, process nodes, timer units and verification fields are in the CSV tables.',
            transform=ax.transAxes, ha='center', va='bottom', fontsize=10)
    lab.save(fig, '00_chronological_capacity_overview',
             'Compact display of the eight lab hosts in generation-year order. The full master CSV includes CPU/process metadata, all native timing metrics, PMU events and separate verification fields. LLC intervals are effective transition regions, not bounds on physical capacity.')


def new_plots(machines, models, prediction_rows, curves, trends):
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), layout='constrained')
    labels = ['L1D capacity (KiB/core)', 'L2 capacity (KiB/core)', 'L2 / L1 resident latency ratio']
    keys = ['l1d_inferred_bytes', 'l2_inferred_bytes', 'l2_l1_ratio']
    training = read_csv('predictions/model_training_points.csv')
    for ax, metric, label, key in zip(axes, models, labels, keys):
        divisor = 1024 if 'capacity' in metric else 1
        entries = [r for r in training if r['metric'] == metric]
        lab.points(ax, machines, {r['host']: float(r['value']) for r in entries},
                   {r['host']: float(r['low']) for r in entries}, {r['host']: float(r['high']) for r in entries})
        data = [r for r in curves if r['metric'] == metric]
        historical = [r for r in data if r['year'] <= 2023]
        ax.plot([r['year'] for r in historical], [r['prediction'] for r in historical], color='.65', lw=1.2, label='Pooled fitted reference')
        if metric == 'l2_capacity_KiB':
            future = [r for r in data if r['year'] >= 2023]
            ax.plot([r['year'] for r in future], [r['prediction'] for r in future], '--', color='black', label='Frozen extrapolation')
            ax.fill_between([r['year'] for r in future], [r['low'] for r in future], [r['high'] for r in future], color='.90', zorder=0)
        target = next(r for r in prediction_rows if r['constraint'] == 'turin' and r['metric'] == metric)
        center = target['prediction']
        ax.errorbar(2024, center, yerr=[[center-target['low']], [target['high']-center]], fmt='v', mfc='white',
                    color='black', capsize=3, label='Turin target prediction', zorder=4)
        lab.axes_year(ax, 2024)
        ax.set_xticks([2014, 2017, 2020, 2024])
        ax.set_ylabel(label)
        if divisor == 1024:
            ax.set_yscale('log', base=2)
            ax.yaxis.set_major_formatter(ScalarFormatter())
        if metric == 'l2_l1_latency_ratio':
            ax.set_ylim(2.4, 3.85)
        ax.legend(fontsize=7, loc='upper left')
    fig.suptitle('Lab observations and lab-only prediction rules')
    lab.save(fig, '18_lab_models_and_hazel_extrapolation',
             'Solid vendor-shaped points are lab data; solid observation links join only the related Intel desktops. Thin gray lines are pooled fitted references, not observed lineage. The dashed L2 extrapolation begins at the measured Artemisia 2023 endpoint and extends only to 2024. L1 and relative latency use constant medians; their target predictions are hollow markers. Bars and shading are descriptive envelopes, not probability intervals. No Hazel measurements are present.')
    targets = read_csv('inputs/hazel_targets.csv')
    fig, axes = plt.subplots(1, 3, figsize=(14, 6.3), layout='constrained')
    yy = np.arange(len(targets))
    for ax, metric, label in zip(axes, models, labels):
        for i, target in enumerate(targets):
            row = next(r for r in prediction_rows if r['constraint'] == target['constraint'] and r['metric'] == metric)
            ax.errorbar(row['prediction'], i, xerr=[[row['prediction']-row['low']], [row['high']-row['prediction']]],
                        fmt='v', mfc='white', color='black', capsize=4)
        ax.set_yticks(yy, [t['constraint'] + ' (' + t['generation_year'] + ')' for t in targets])
        ax.invert_yaxis()
        ax.set_xlabel(label)
        ax.spines[['top', 'right']].set_visible(False)
        if 'capacity' in metric:
            ax.set_xscale('log', base=2)
            ax.xaxis.set_major_formatter(ScalarFormatter())
    fig.suptitle('Hazel target predictions with descriptive uncertainty\nNo target measurements; scheduler availability not checked')
    lab.save(fig, '19_hazel_prediction_intervals',
             'Nine assignment constraints ordered by generation year; three quantitative predictions each. These include targets inside the lab year range. Ice Lake constraints share a generation and prediction. The generation-wide year 2020 follows Section 8.1; the Ice Lake implementation launched in 2021, evaluated separately in chronology_sensitivity.csv. Bars are not 95% intervals. Target cache specifications were not model inputs.')
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.4), layout='constrained')
    for ax, metric, title in zip(axes, models, ['L1D capacity', 'L2 capacity', 'L2/L1 relative latency']):
        data = [r for r in trends if r['metric'] == metric]
        x = np.arange(len(data))
        ax.bar(x-.17, [r['leave_one_host_out_rmse'] for r in data], .34, color='.25', label='Linear / log-linear')
        ax.bar(x+.17, [r['flat_leave_one_host_out_rmse'] for r in data], .34, color='.8', edgecolor='black', label='Constant mean')
        ax.set_xticks(x, ['Pooled\n(n=8)', 'Intel\n(n=6)', 'Desktop\n(n=4)'])
        ax.set_ylabel('Lab leave-one-out RMSE (' + ('log2 KiB)' if 'capacity' in metric else 'ratio)'))
        ax.set_title(title)
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].legend(fontsize=8)
    fig.suptitle('Trend sensitivity to the training cohort')
    lab.save(fig, '20_trend_model_comparison',
             'Leave-one-lab-host-out error compares unconstrained OLS with a constant-mean baseline on identical folds; lower is better. Capacity errors are in log2 KiB. This is a lab diagnostic, not Hazel validation. Four related desktops have identical L1 and L2 capacities. The frozen L2 prediction uses a separate anchored fit in model_parameters.json.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    args = parser.parse_args()
    for name in ['inputs', 'tables', 'figures', 'predictions', '.cache']:
        (HERE / name).mkdir(exist_ok=True)
    cfg = json.loads((HERE / 'analysis_config.json').read_text())
    if args.collect:
        collect(cfg)
    snapshot = json.loads((HERE / 'inputs/lab_snapshot.json').read_text())
    for name, rows in snapshot['tables'].items():
        write_csv('tables/' + name + '.csv', rows)
    machines, capacity, latencies, assoc, inclusion, line_stats, software, pmu, checks = snapshot['data']
    lab.FIGS.clear()
    master_views(machines, pmu)
    lab.make_plots(machines, capacity, assoc, inclusion, line_stats, software, pmu)
    trends = quantitative_trends(machines)
    models, rows, curves = predictions(machines)
    new_plots(machines, models, rows, curves, trends)
    lab.dump(HERE / 'tables/figure_manifest.json', lab.FIGS)
    lab.dump(HERE / 'tables/data_validation.json', {'status': 'passed', 'lab_hosts': len(machines),
        'resident_summary_checks': checks, 'latency_rows': len(latencies), 'hazel_observations': 0,
        'source_files': len(json.loads((HERE/'inputs/source_manifest.json').read_text())),
        'scope': 'Selected saved-summary consistency; upstream raw sample arrays were not fully re-audited'})
    print(json.dumps({'lab_hosts': len(machines), 'figures': len(lab.FIGS), 'quantitative_predictions': len(rows),
                      'l2_model': {k: models['l2_capacity_KiB'][k] for k in ['anchor_year', 'anchor_KiB', 'log2_slope_per_year', 'doubling_years']}}))


if __name__ == '__main__':
    main()
