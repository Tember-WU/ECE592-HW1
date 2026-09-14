#!/usr/bin/env python3
"""Audit the Crux run manifests, analysis provenance, and placement logs.

Run after analyze_capacity.py, which verifies hashes/counts from the raw arrays
and recomputes every statistic. This audit also compares those statistics with
the collection records; it does not discard any samples.
"""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def read_json(path):
    return json.loads(path.read_text())


def audit(run_id):
    data = ROOT / 'data/crux' / run_id
    output = ROOT / 'results/crux' / run_id
    manifest = read_json(data / 'manifest.json')
    env = read_json(data / 'environment.json')
    provenance = read_json(output / 'provenance.json')
    rows = {r['name']: r for r in csv.DictReader((output / 'summary.csv').open())}
    inputs = {r['name']: r for r in provenance['inputs']}
    jobs = manifest['jobs']
    errors, events, backing = [], [], {'huge': 0, 'base': 0}
    raw_bytes = compressed_bytes = samples = 0
    busy = {f'cpu{i}': [] for i in range(8)}

    def check(condition, detail):
        if not condition:
            errors.append(detail)

    check(manifest['status'] == 'complete', 'Collection is incomplete')
    check(provenance['run_ids'] == [run_id], 'Incorrect analysis source run')
    names = {j['name'] for j in jobs}
    check(names == set(rows) == set(inputs), 'Manifest/summary/provenance point mismatch')
    check(names == {p.stem for p in (data / 'logs').glob('*.json')}, 'Log point mismatch')
    check(env['cpu'] == 6 and env['numa_node'] == 0, 'Incorrect placement')
    for path, key in ((data / 'cache_capacity.bin', 'binary_sha256'),
                      (data / 'source/src/cache_bench.c', 'source_sha256')):
        check(hashlib.sha256(path.read_bytes()).hexdigest() == env[key], f'{path.name} hash mismatch')
    for job in jobs:
        name = job['name']
        record = read_json(data / 'logs' / f'{name}.json')
        p = record['parameters']
        log = (data / 'logs' / f'{name}.txt').read_text()
        check(job['status'] == 'complete', f'{name}: incomplete')
        check(p == job['parameters'], f'{name}: parameter mismatch')
        check(log == record['log'], f'{name}: text/JSON log mismatch')
        check(inputs[name]['sha256'] == record['raw_sha256'], f'{name}: analysis checksum mismatch')
        check(inputs[name]['file'] == record['raw_file'], f'{name}: raw filename mismatch')
        check(int(rows[name]['n']) == p['samples'] == 1000000, f'{name}: sample count mismatch')
        for key, value in record['stats'].items():
            if key != 'decile_medians':
                check(float(rows[name][key]) == value, f'{name}: recomputed {key} mismatch')
        actual = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', log)}
        for key in ('bytes', 'spacing', 'samples', 'batch', 'seed'):
            check(actual[key] == p[key], f'{name}: logged {key} mismatch')
        check(actual['cpu_start'] == actual['cpu_end'] == 6, f'{name}: CPU binding mismatch')
        mapped = (p['bytes'] + 2097151) // 2097152 * 2097152
        check(actual['mapped_bytes'] == mapped, f'{name}: mapping length mismatch')
        huge = [int(n) * 1024 for n in re.findall(r'AnonHugePages:\s+(\d+) kB', log)]
        expected = mapped if p['pages'] == 'huge' else 0
        check(huge == [expected, expected], f'{name}: before/after page backing mismatch')
        mappings = [line for line in log.splitlines() if line.startswith('numa_mapping:')]
        check(len(mappings) == 2, f'{name}: missing NUMA mapping')
        for line in mappings:
            nodes = dict(re.findall(r'\bN(\d+)=(\d+)', line))
            check('bind:0' in line and nodes == {'0': str(mapped // env['page_size'])},
                  f'{name}: nonlocal or incomplete NUMA mapping')
        events.append({k: actual[k] for k in ('measurement_minor_faults', 'major_faults',
                                            'voluntary_switches', 'involuntary_switches')})
        for cpu, value in record['cpu_busy_percent'].items():
            busy[cpu].append(value)
        backing[p['pages']] += 1
        samples += p['samples']
        raw_bytes += p['samples'] * 8
        compressed_bytes += (data / record['raw_file']).stat().st_size
    start, finish = (dt.datetime.fromisoformat(manifest[k]) for k in ('started_utc', 'finished_utc'))
    report = dict(passed=not errors, errors=errors, machine='crux', run_id=run_id,
                  checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  collection_status=manifest['status'], expected_configurations=len(jobs),
                  complete_configurations=sum(j['status'] == 'complete' for j in jobs),
                  total_timed_batches=samples, raw_bytes=raw_bytes, raw_gzip_bytes=compressed_bytes,
                  started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
                  wall_seconds=(finish-start).total_seconds(), cpu=6, numa_node=0,
                  smt_sibling=None, page_policy_counts=backing,
                  all_mappings_match_page_policy_and_are_local=not errors,
                  raw_checksums_and_statistics='Raw hashes, counts and positive intervals checked and statistics recomputed by analyze_capacity.py; matched against manifest and collection records here.',
                  runtime_events={k: dict(minimum=min(e[k] for e in events),
                                         maximum=max(e[k] for e in events),
                                         total=sum(e[k] for e in events)) for k in events[0]},
                  cpu_busy_percent_ranges={k: [min(v), max(v)] for k, v in busy.items()},
                  source_sha256=env['source_sha256'], binary_sha256=env['binary_sha256'],
                  limitation='Passing integrity and placement checks does not establish absence of shared-machine interference.')
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(1)
    return report


def audit_combined(reports):
    output = ROOT / 'results/crux/combined12'
    provenance = read_json(output / 'provenance.json')
    run_ids = [r['run_id'] for r in reports]
    expected = set()
    for run in run_ids:
        source = read_json(ROOT / 'results/crux' / run / 'provenance.json')
        expected.update((i['run_id'], i['name'], i['sha256']) for i in source['inputs'])
    actual = {(i['run_id'], i['name'], i['sha256']) for i in provenance['inputs']}
    rows = list(csv.DictReader((output / 'summary.csv').open()))
    assert provenance['run_ids'] == run_ids
    assert expected == actual and len(actual) == len(rows) == 96
    assert {(r['run_id'], r['name']) for r in rows} == {(r, n) for r, n, _ in expected}
    assert sum(int(r['n']) for r in rows) == 96000000
    assert provenance['boundaries'] == read_json(output / 'boundaries.json')
    report = dict(passed=True, errors=[], machine='crux', source_runs=run_ids,
                  checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  complete_configurations=len(rows), total_timed_batches=96000000,
                  raw_bytes=sum(r['raw_bytes'] for r in reports),
                  raw_gzip_bytes=sum(r['raw_gzip_bytes'] for r in reports),
                  collection_wall_seconds=sum(r['wall_seconds'] for r in reports),
                  run_validation_files=[f'../{r}/validation.json' for r in run_ids],
                  runtime_event_totals={k: sum(r['runtime_events'][k]['total'] for r in reports)
                                        for k in reports[0]['runtime_events']},
                  checks=['Complete manifests and matching single-run audits',
                          'Combined analyzer verified raw files and compatible environments',
                          'Combined inputs exactly equal the union of the two complete runs',
                          'All 96 million batches represented; no failed-run records included',
                          'Manual boundaries match analysis provenance'],
                  excluded_runs={'round1': 'Incomplete THP-allocation attempt; retained separately'},
                  limitation='Integrity checks do not remove shared-machine interference or the disclosed initial cache-specification exposure.')
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    reports = [audit(run) for run in sys.argv[1:]]
    if sys.argv[1:] == ['round1-retry1', 'round2']:
        audit_combined(reports)
