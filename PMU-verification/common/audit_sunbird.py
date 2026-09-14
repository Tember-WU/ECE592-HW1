#!/usr/bin/env python3
"""Audit Sunbird's completed Section 8.3 run and frozen Phase-I provenance."""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

PMU = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    previous_end = None
    runs, pairs = [], []
    for experiment in ('capacity', 'line_size', 'associativity'):
        run_id = experiment + '01'
        data = PMU / experiment / 'data/sunbird' / run_id
        result = PMU / experiment / 'results/sunbird' / run_id
        m, c = read(data / 'manifest.json'), read(data / 'config.json')
        v, q = read(result / 'validation.json'), read(result / 'quality.json')
        assert m['status'] == 'complete' and v['status'] == 'passed'
        jobs = m['jobs']
        assert len(jobs) == (28 if experiment == 'capacity' else 24)
        assert c['samples'] == 1000000
        gzip_bytes = 0
        for j in jobs:
            assert j['status'] == 'complete' and j['statistics']['n'] == c['samples']
            if previous_end is not None:
                assert j['started_utc'] >= previous_end, 'Measurement runs overlap'
            previous_end = j['finished_utc']
            counts = read(data / j['counts_file'])
            assert counts['time_running_ns'] == counts['time_enabled_ns'] > 0
            assert len(counts['events']) == 2
            assert [e['config'] for e in counts['events']] == [int(c['events'][i]['config'], 0) for i in j['event_indices']]
            gzip_bytes += (data / j['raw_file']).stat().st_size
        for a, b in zip(jobs[::2], jobs[1::2]):
            assert a['point_name'] == b['point_name']
            assert a['event_indices'] + b['event_indices'] == [0, 1, 2, 3]
            med_a, med_b = a['statistics']['median'], b['statistics']['median']
            page_a = a.get('anon_huge_kib_before_after', 'complete THP (enforced)')
            page_b = b.get('anon_huge_kib_before_after', 'complete THP (enforced)')
            pairs.append(dict(experiment=experiment, point=a['point_name'],
                              l1_l2_median=med_a, l3_loads_median=med_b,
                              anon_huge_kib_l1_l2=page_a, anon_huge_kib_l3_loads=page_b,
                              same_observed_page_backing=page_a == page_b,
                              max_min_ratio=max(med_a, med_b) / min(med_a, med_b)))
        temporal = q.get('temporal_median_max_min', q.get('temporal_max_min'))
        runs.append(dict(experiment=experiment, run_id=run_id, unique_workloads=len(jobs) // 2,
                         passes=len(jobs), timed_batches=len(jobs) * c['samples'],
                         raw_payload_bytes=len(jobs) * c['samples'] * 8, gzip_bytes=gzip_bytes,
                         started_utc=m['started_utc'], finished_utc=m['finished_utc'],
                         elapsed_seconds=m['elapsed_seconds'],
                         involuntary_switches=q['total_involuntary_switches'],
                         minor_faults=q['total_minor_faults'], major_faults=q['total_major_faults'],
                         max_sibling_busy_percent=q['max_sibling_busy_percent'],
                         temporal_ratio_over_1_2={k: v for k, v in temporal.items() if v > 1.2}))
    freeze = PMU / 'phase1-freeze/sunbird/freeze01'
    fm = read(freeze / 'manifest.json')
    assert fm['frozen_utc'] < runs[0]['started_utc']
    copies = 0
    for f in fm['files']:
        assert digest(PMU.parent / f['path']) == f['sha256'], f['path']
        if f.get('snapshot'):
            assert digest(freeze / f['snapshot']) == f['sha256'], f['snapshot']
            copies += 1
    freeze_audit = dict(status='passed', verified_utc=now,
                        originals_checked=len(fm['files']), snapshots_checked=copies,
                        bytes_in_originals=sum(f['bytes'] for f in fm['files']),
                        all_originals_and_snapshots_unchanged=True,
                        freeze_manifest_sha256=digest(freeze / 'manifest.json'))
    save(freeze / 'verification-after.json', freeze_audit)
    source = PMU / 'common/data/sunbird/source01'
    sm = read(source / 'manifest.json')
    for f in sm['files']:
        assert digest(source / f['stored_path']) == f['sha256'], f['stored_path']
        assert digest(PMU / f['path']) == f['sha256'], f['path']
    out = PMU / 'common/results/sunbird'
    with (out / 'paired_pass_medians.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(pairs[0]))
        writer.writeheader(); writer.writerows(pairs)
    save(out / 'run_summary.json', dict(status='passed', verified_utc=now, runs=runs,
         total_unique_workloads=sum(r['unique_workloads'] for r in runs),
         total_passes=sum(r['passes'] for r in runs),
         total_timed_batches=sum(r['timed_batches'] for r in runs),
         total_raw_payload_bytes=sum(r['raw_payload_bytes'] for r in runs),
         total_gzip_bytes=sum(r['gzip_bytes'] for r in runs),
         serial_measurement_order_verified=True, all_groups_fully_scheduled=True,
         source_and_build_files_verified=len(sm['files']), phase1_integrity=freeze_audit,
         max_pair_median_ratio=max(p['max_min_ratio'] for p in pairs),
         pairs_with_different_page_backing=[p['experiment'] + '/' + p['point'] for p in pairs
                                            if not p['same_observed_page_backing']],
         note='Uses each analyzer raw/statistics validation; audits scheduling, serial order, pass pairing and provenance. Integrity is not proof of isolated hardware state.'))
    print('Audited 38 workloads / 76 passes / 76 million batches; all groups fully scheduled;')
    print(f'{len(fm["files"])} Phase-I originals, {copies} snapshots and {len(sm["files"])} PMU source/build files match.')


if __name__ == '__main__':
    main()
