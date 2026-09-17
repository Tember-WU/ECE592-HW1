#!/usr/bin/env python3
"""Validate saved Ookay runs after analysis; retain runtime quality diagnostics.

Usage: .venv/bin/python results/ookay/validate_runs.py RUN_ID [RUN_ID ...]
"""
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EVENTS = ('measurement_minor_faults', 'major_faults', 'voluntary_switches',
          'involuntary_switches')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(run_id):
    data = ROOT / 'data/ookay' / run_id
    output = ROOT / 'results/ookay' / run_id
    manifest = json.loads((data / 'manifest.json').read_text())
    config = json.loads((data / 'config.json').read_text())
    env = json.loads((data / 'environment.json').read_text())
    provenance = json.loads((output / 'provenance.json').read_text())
    rows = list(csv.DictReader((output / 'summary.csv').open()))
    records = [json.loads(p.read_text()) for p in sorted((data / 'logs').glob('*.json'))]
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    jobs = {j['name']: j for j in manifest['jobs']}
    check(manifest['status'] == 'complete', 'Manifest is not complete')
    check(all(j.get('status') == 'complete' for j in jobs.values()), 'Incomplete jobs')
    names = {r['name'] for r in records}
    check(names == set(jobs), 'Saved records differ from manifest jobs')
    check(names == {r['name'] for r in rows}, 'Analysis summary differs from records')
    check(names == {r['name'] for r in provenance['inputs']}, 'Provenance differs from records')
    check(env['source_sha256'] == sha(data / 'source/src/cache_bench.c'), 'C snapshot hash mismatch')
    check(env['binary_sha256'] == sha(data / 'cache_capacity.bin'), 'Binary hash mismatch')
    check(env['cpu'] == config['cpu'] and env['numa_node'] == config['numa_node'], 'Environment binding mismatch')
    check(env['host'].split('.')[0] == 'ookay', 'Wrong host')
    raw_bytes = compressed_bytes = samples = 0
    events = {key: [] for key in EVENTS}
    sibling_busy = []
    page_counts = {'huge': 0, 'base': 0}
    sibling = 6
    for record in records:
        name, p, log = record['name'], record['parameters'], record['log']
        check(p == jobs[name]['parameters'], f'{name}: parameters mismatch')
        check(record['command'] == jobs[name]['command'], f'{name}: command mismatch')
        check(record['environment'] == env, f'{name}: environment mismatch')
        check(log == (data / 'logs' / f'{name}.txt').read_text(), f'{name}: text log mismatch')
        path = data / record['raw_file']
        payload = gzip.decompress(path.read_bytes())
        raw = np.frombuffer(payload, dtype='<u8')
        check(hashlib.sha256(payload).hexdigest() == record['raw_sha256'], f'{name}: raw hash mismatch')
        check(len(raw) == p['samples'] == 1000000 and np.all(raw > 0), f'{name}: invalid samples')
        check(record['stats']['n'] == len(raw), f'{name}: statistics count mismatch')
        samples += len(raw)
        raw_bytes += len(payload)
        compressed_bytes += path.stat().st_size
        values = dict(re.findall(r'(\w+)=(\d+)', log))
        check(int(values['cpu_start']) == int(values['cpu_end']) == config['cpu'], f'{name}: CPU mismatch')
        mapped = int(values['mapped_bytes'])
        expected_mapping = ((p['bytes'] + 2097151) // 2097152) * 2097152
        check(mapped == expected_mapping, f'{name}: mapping size mismatch')
        check(int(values['warm_loads']) >= max(1048576, p['bytes'] // p['spacing'] * 4), f'{name}: insufficient warmup')
        huge = [int(x) * 1024 for x in re.findall(r'AnonHugePages:\s+(\d+) kB', log)]
        check(huge == ([mapped, mapped] if p['pages'] == 'huge' else [0, 0]), f'{name}: page backing mismatch')
        mappings = re.findall(r'^numa_mapping: (.+)$', log, re.M)
        check(len(mappings) == 2, f'{name}: missing NUMA mapping checks')
        for mapping in mappings:
            nodes = {int(n): int(count) for n, count in re.findall(r'\bN(\d+)=(\d+)', mapping)}
            page_kib = int(re.search(r'kernelpagesize_kB=(\d+)', mapping)[1])
            check(set(nodes) == {config['numa_node']}, f'{name}: nonlocal NUMA mapping')
            check(sum(nodes.values()) * page_kib * 1024 == mapped, f'{name}: NUMA coverage mismatch')
        for key in EVENTS:
            events[key].append(int(values[key]))
        sibling_busy.append(record['cpu_busy_percent'][f'cpu{sibling}'])
        page_counts[p['pages']] += 1
    start, end = (dt.datetime.fromisoformat(manifest[k]) for k in ('started_utc', 'finished_utc'))
    report = dict(passed=not errors, errors=errors, machine='ookay', run_id=run_id,
                  checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  validation_scope='Data integrity, completion, CPU/NUMA binding and page backing; not a claim of no shared-machine interference.',
                  collection_status=manifest['status'], expected_configurations=len(jobs),
                  complete_configurations=len(records), total_timed_batches=samples,
                  raw_bytes=raw_bytes, raw_gzip_bytes=compressed_bytes,
                  raw_checksums_and_statistics='All raw hashes/counts checked; statistics recomputed by analyze_capacity.py, see provenance.json.',
                  started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
                  wall_seconds=(end-start).total_seconds(), cpu=config['cpu'], numa_node=config['numa_node'],
                  smt_sibling=sibling, smt_busy_percent_range=[min(sibling_busy), max(sibling_busy)],
                  page_policy_configurations=page_counts,
                  runtime_events={k: dict(minimum=min(v), maximum=max(v), total=sum(v)) for k, v in events.items()},
                  source_sha256=env['source_sha256'], binary_sha256=env['binary_sha256'],
                  validation_script_sha256=sha(Path(__file__)))
    (output / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if errors:
        raise SystemExit(f'Validation failed: {run_id}')


if __name__ == '__main__':
    for run_id in sys.argv[1:]:
        validate(run_id)
