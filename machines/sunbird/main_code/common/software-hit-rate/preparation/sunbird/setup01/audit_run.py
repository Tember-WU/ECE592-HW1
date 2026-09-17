#!/usr/bin/env python3
"""Post-collection provenance/placement audit and Sunbird failure visualization.

Uses saved data only; does not run a benchmark or change the frozen estimator.
"""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import statistics as stats
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from estimator import fit, read_raw
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    data = ROOT / 'data/sunbird/hitrate01'
    out = ROOT / 'results/sunbird/hitrate01'
    m, c = read(data / 'manifest.json'), read(data / 'config.json')
    model, checkpoint = read(data / 'model.json'), read(data / 'threshold-checkpoint.json')
    expected = [(p['id'], 'calibration', False) for p in c['calibration']]
    expected += [('counter_overhead', 'counter_control', True)]
    expected += [(p['id'], 'validation', p['pmu']) for p in read(data / 'validation-plan.json')]
    assert [(j['id'], j['phase'], j['pmu_enabled']) for j in m['jobs']] == expected
    assert m['status'] == 'complete' and len(m['jobs']) == len({j['name'] for j in m['jobs']}) == 54
    assert m['timed_samples'] == 54000000
    previous, pmu_count, mapping_count, merged = None, 0, 0, 0
    for j in m['jobs']:
        assert j['status'] == 'complete' and j['statistics']['n'] == c['samples'] == 1000000
        if previous:
            assert previous <= j['started_utc']
        previous = j['finished_utc']
        meta = read(data / j['metadata_file'])
        assert meta['samples'] == 1000000 and meta['target_loads'] == (0 if j['mode'] == 'empty' else 1000000)
        assert meta['cpu_before'] == meta['cpu_after'] == 32
        lines = re.findall(r'^mapping: (.*)$', (data / 'logs' / (j['name'] + '.txt')).read_text(), re.M)
        # Adjacent chain/output mmaps can coalesce into one VMA. Check total
        # prefaulted pages instead of incorrectly requiring two VMA lines.
        assert len(lines) in (1, 2), j['name']
        pages = sum(int(re.search(r'\banon=(\d+)', line)[1]) for line in lines)
        assert pages == math.ceil(j['bytes'] / 4096) + math.ceil(c['samples'] * 8 / 4096)
        for line in lines:
            assert set(re.findall(r'\bN(\d+)=', line)) == {'0'} and 'kernelpagesize_kB=4' in line
        mapping_count += len(lines)
        merged += len(lines) == 1
        if j['pmu_enabled']:
            assert j['started_utc'] > checkpoint['created_utc']
            assert meta['threshold_ticks'] == model['threshold_ticks']
            p = meta['pmu']
            assert p['time_running_ns'] == p['time_enabled_ns'] > 0
            pmu_count += 1
        else:
            assert meta['pmu'] is None
    for p in c['validation']:
        selected = [j for j in m['jobs'] if j.get('case') == p['id']]
        assert {(j['repeat'], j['pmu_enabled']) for j in selected} == {(r, mode) for r in range(3) for mode in (False, True)}
        for j in selected:
            assert all(j[k] == p[k] for k in ('bytes', 'mode', 'reuse'))
    original = read(ROOT / 'configs/artemisia.json')
    assert {k: v for k, v in original.items() if k not in ('machine', 'cpu', 'numa_node', 'pmu')} == {
        k: v for k, v in c.items() if k not in ('machine', 'cpu', 'numa_node', 'pmu')}
    before = read(Path(__file__).parent / 'preservation-before.json')
    for f in before['files']:
        assert sha(ROOT / f['path']) == f['sha256'], f['path']
    for p in (ROOT / 'src').glob('*'):
        assert p.read_bytes() == (data / 'source/src' / p.name).read_bytes()
    assert (ROOT / 'scripts/estimator.py').read_bytes() == (data / 'source/scripts/estimator.py').read_bytes()
    for p in (ROOT / 'build/sunbird').glob('*'):
        assert p.read_bytes() == (data / 'source/compiled' / p.name).read_bytes()
    arrays = {}
    for name in ('hit_fit_software', 'miss_fit_software', 'boundary_48k_r1_pmu', 'nonresident_128k_r1_pmu'):
        arrays[name], _ = read_raw(data / 'raw' / (name + '.u64.gz'))
    fitted = fit(arrays['hit_fit_software'], arrays['miss_fit_software'])
    assert all(model[k] == v for k, v in fitted.items())
    assert sha(data / 'model.json') == checkpoint['model_sha256']
    assert model['pmu_used_for_fitting'] is False
    with (out / 'comparison.csv').open() as f:
        comparisons = list(csv.DictReader(f))
    rows = []
    for case in c['validation']:
        r = [x for x in comparisons if x['case'] == case['id']]
        assert len(r) == 3
        rows.append(dict(case=case['id'], reuse=case['reuse'],
            software_same_run_percent=100 * stats.mean(float(x['software_same_run']) for x in r),
            pmu_hit_percent=100 * stats.mean(float(x['pmu_hit_rate']) for x in r),
            software_standalone_percent=100 * stats.mean(float(x['software_standalone']) for x in r),
            mean_absolute_error_pp=stats.mean(float(x['absolute_error_pp']) for x in r),
            worst_absolute_error_pp=max(float(x['absolute_error_pp']) for x in r),
            mean_relative_error_percent=stats.mean(float(x['relative_error_percent']) for x in r),
            ci_covers_pmu_runs=sum(float(x['ci95_low']) <= float(x['pmu_hit_rate']) <= float(x['ci95_high']) for x in r)))
    with (out / 'case_summary.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    v = read(out / 'validation.json')
    audit = dict(status='passed', audited_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        collection_started_utc=m['started_utc'], collection_finished_utc=m['finished_utc'],
        collection_elapsed_seconds=(dt.datetime.fromisoformat(m['finished_utc']) - dt.datetime.fromisoformat(m['started_utc'])).total_seconds(),
        original_artemisia_and_estimator_files_verified=len(before['files']), source_and_compiled_copies_match=True,
        threshold_refitted_from_saved_timing_only_data=True, serial_exact_plan_and_unique_names_verified=True,
        formal_pmu_executions=pmu_count, software_only_executions=54 - pmu_count,
        numa_basepage_mapping_records_verified=mapping_count, runs_with_coalesced_chain_output_vma=merged,
        raw_payload_bytes=54000000 * 8,
        raw_gzip_bytes=sum((data / j['raw_file']).stat().st_size for j in m['jobs']),
        max_sibling_cpu8_busy_percent=max(j['cpu_busy_percent'].get('cpu8', 0) for j in m['jobs']),
        total_voluntary_switches=sum(read(data / j['metadata_file'])['voluntary_switches'] for j in m['jobs']),
        ci_covers_pmu_reference_runs=sum(x['ci_covers_pmu_runs'] for x in rows),
        mean_absolute_error_pp=v['mean_absolute_error_pp'], worst_absolute_error_pp=v['worst_absolute_error_pp'],
        note='Integrity/provenance checks pass; unchanged estimator has large systematic error on Sunbird. No PMU input is fed back into its threshold.')
    (out / 'execution_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    fig, ax = plt.subplots(figsize=(9, 5), layout='constrained')
    grid = np.arange(0, 141)
    labels = ['Calibration: expected hit (8 KiB)', 'Calibration: expected miss (512 KiB)',
              'Held out: 48 KiB (PMU hit 0.119%, repeat 1)', 'Held out: 128 KiB (PMU hit 0.149%, repeat 1)']
    for (name, values), label in zip(arrays.items(), labels):
        cdf = np.searchsorted(np.sort(values), grid, side='right') / len(values)
        ax.step(grid, cdf * 100, where='post', label=label)
    ax.axvline(model['threshold_ticks'], color='black', ls='--', label='Frozen hit threshold: 70 ticks')
    ax.set(xlim=(40, 115), ylim=(-2, 102), xlabel='Raw single-target timer interval (TSC ticks)',
           ylabel='Samples at or below interval (%)', title='Sunbird: held-out miss-heavy workloads overlap hit calibration')
    ax.legend(fontsize=8, loc='lower right')
    for ext in ('png', 'pdf'):
        fig.savefig(out / 'figures' / ('heldout_overlap.' + ext), dpi=180)
    plt.close(fig)
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
