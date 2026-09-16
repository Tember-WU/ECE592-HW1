#!/usr/bin/env python3
"""Check scientific arithmetic, coverage, rendered files, and optional frozen hashes."""
import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parents[1]


def rows(relative):
    with (HERE / relative).open() as f:
        return list(csv.DictReader(f))


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10), (a, b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-upstream', action='store_true')
    args = parser.parse_args()
    master = rows('tables/chronological_master.csv')
    assert len(master) == 8
    assert [int(r['year']) for r in master] == sorted(int(r['year']) for r in master)
    hosts = {r['host'] for r in master}
    assert len(hosts) == 8
    for r in master:
        assert r['llc_inferred_bytes'] == '' and r['line_timing_inferred_bytes'] == ''
        assert r['inclusion_inferred'] == 'uncertain'
        close(r['l2_l1_ratio'], float(r['l2_hit'])/float(r['l1_hit']))
        if r['host'] == 'thunderbird':
            close(r['l1_hit_ns'], float(r['l1_hit'])*40)
        else:
            assert r['l1_hit_ns'] == '' and r['timer_frequency_hz'] == ''
    latency = rows('tables/latency.csv')
    assert len(latency) == 144
    for r in latency:
        if r['metric'].endswith('_miss'):
            close(r['median'], float(r['next_level_median'])-float(r['reference_median']))
        else:
            assert int(r['n']) == 1_000_000
    dup = [r for r in rows('tables/associativity.csv') if r['identical_other_host_files']]
    assert len(dup) == 4 and {r['host'] for r in dup} == {'sunbird','crux'}
    assert len(rows('tables/pmu_normalized.csv')) == 192
    assert len(rows('tables/software_metric.csv')) == 48
    assert {r['host'] for r in rows('tables/software_metric.csv')} == {'sunbird','artemisia'}
    targets = rows('inputs/hazel_targets.csv')
    assert len(targets) == 9 and len({r['microarchitecture'] for r in targets}) == 8
    assert [int(r['generation_year']) for r in targets] == sorted(int(r['generation_year']) for r in targets)
    for t in targets:
        if t['constraint'].startswith('icelake'):
            assert t['generation_year'] == '2020' and t['implementation_launch_year'] == '2021'
    training = rows('predictions/model_training_points.csv')
    models = json.loads((HERE/'predictions/model_parameters.json').read_text())
    assert len(training) == 24 and {r['host'] for r in training} == hosts
    assert len(models) == 3
    for metric, model in models.items():
        assert model['n_lab_hosts'] == 8 and set(model['training_hosts']) == hosts
        assert model['hazel_observations_used'] == 0 and model['validated_on_hazel'] is False
        data = [r for r in training if r['metric'] == metric]
        if metric != 'l2_capacity_KiB':
            close(model['central'], np.median([float(r['value']) for r in data]))
            close(model['low'], min(float(r['low']) for r in data))
            close(model['high'], max(float(r['high']) for r in data))
        else:
            x = np.array([int(r['year']) for r in data]) - 2023
            y = np.log2([float(r['value'])/2048 for r in data])
            b = float(np.linalg.lstsq(x[:,None], y, rcond=None)[0][0])
            close(model['log2_slope_per_year'], b)
            close(model['anchor_KiB'], 2048)
            assert model['anchor_year'] == 2023
    predictions = rows('predictions/hazel_predictions.csv')
    assert len(predictions) == 27
    assert len({(r['constraint'], r['metric']) for r in predictions}) == 27
    curve = {(float(r['year']),r['metric']): r for r in rows('predictions/model_curves.csv')}
    for r in predictions:
        m = models[r['metric']]
        year = int(r['year'])
        expected = (m['anchor_KiB']*2**(m['log2_slope_per_year']*(year-m['anchor_year']))
                    if r['metric']=='l2_capacity_KiB' else m['central'])
        close(r['prediction'], expected)
        assert 0 < float(r['low']) <= expected <= float(r['high'])
        for field in ['prediction','low','high']:
            close(r[field], curve[(year,r['metric'])][field])
        if r['metric'] == 'l2_capacity_KiB':
            variants = [v['anchor_KiB']*2**(v['log2_slope_per_year']*(year-v['anchor_year'])) for v in m['sensitivity_models']]
            err = m['max_abs_leave_one_host_out_error_log2']
            variants.extend([expected, expected*2**(-err), expected*2**err])
            close(r['low'], min(variants)); close(r['high'], max(variants))
    l2_loo = rows('predictions/l2_anchor_leave_one_out.csv')
    for row in l2_loo:
        kept = [r for r in master if r['host'] != row['held_out_lab_host']]
        latest = max(kept, key=lambda r: int(r['year']))
        anchor_value = float(latest['l2_inferred_bytes'])/1024
        xx = np.array([int(r['year'])-int(latest['year']) for r in kept], float)
        yy = np.log2([float(r['l2_inferred_bytes'])/1024/anchor_value for r in kept])
        slope = np.linalg.lstsq(xx[:,None], yy, rcond=None)[0][0]
        omitted = next(r for r in master if r['host'] == row['held_out_lab_host'])
        predicted = anchor_value*2**(slope*(int(omitted['year'])-int(latest['year'])))
        close(row['predicted_KiB'], predicted)
    trends = rows('tables/trend_summary.csv')
    assert len(trends) == 9
    for row in trends:
        metric = row['metric']
        selected = [r for r in training if r['metric']==metric and r['host'] in row['training_hosts'].split(',')]
        xx = np.array([int(r['year'])-2014 for r in selected], float)
        yy = np.array([float(r['value']) for r in selected])
        if 'capacity' in metric: yy = np.log2(yy)
        a,b = np.linalg.lstsq(np.column_stack([np.ones(len(xx)),xx]),yy,rcond=None)[0]
        close(row['intercept_at_2014'], a); close(row['slope_per_year'], b)
    matrix = rows('predictions/hazel_prediction_matrix.csv')
    assert len(matrix) == 153 and sum(r['status']=='abstained' for r in matrix) == 126
    figs = json.loads((HERE/'tables/figure_manifest.json').read_text())
    assert len(figs) == 22 and len({r['file'] for r in figs}) == 22
    for fig in figs:
        path = HERE/'figures'/fig['file']
        info = subprocess.check_output(['pdfinfo', str(path.with_suffix('.pdf'))], text=True)
        assert re.search(r'Pages:\s+1\b', info)
        with Image.open(path.with_suffix('.png')) as im:
            assert im.width > 700 and im.height > 300
    for path in HERE.rglob('*'):
        if '.cache' in path.parts or '__pycache__' in path.parts or not path.is_file():
            continue
        assert '2028' not in path.name and path.parent.name != 'report'
        if path.suffix in ['.py','.md','.csv','.json','.txt','.tex']:
            assert not re.search('[\u4e00-\u9fff]', path.read_text()), path
    source_manifest = json.loads((HERE/'inputs/source_manifest.json').read_text())
    if args.check_upstream:
        for rel, spec in source_manifest.items():
            assert hashlib.sha256((HERE.parent/rel).read_bytes()).hexdigest() == spec['sha256'], rel
        baseline = HERE/'.cache/upstream_git_status_before.txt'
        if baseline.exists():
            now = subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all','--','.',':(exclude)section9_moore_analysis'],cwd=HERE.parent,text=True)
            assert now == baseline.read_text(), 'Unrelated repository status changed'
    frozen = HERE/'freeze/manifest.json'
    if frozen.exists():
        for rel, spec in json.loads(frozen.read_text())['files'].items():
            assert hashlib.sha256((HERE/rel).read_bytes()).hexdigest() == spec['sha256'], rel
    print(json.dumps({'status':'passed','lab_hosts':8,'figures':22,'predictions':27,
                      'abstentions':126,'source_files':len(source_manifest),
                      'upstream_checked':args.check_upstream,'frozen_hashes_checked':frozen.exists()}))


if __name__ == '__main__':
    main()
