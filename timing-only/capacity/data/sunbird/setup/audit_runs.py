#!/usr/bin/env python3
"""Audit the saved Sunbird runs after analysis; write per-run validation records."""
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run_id):
    data = ROOT / 'data/sunbird' / run_id
    output = ROOT / 'results/sunbird' / run_id
    manifest = json.loads((data / 'manifest.json').read_text())
    config = json.loads((data / 'config.json').read_text())
    env = json.loads((data / 'environment.json').read_text())
    provenance = json.loads((output / 'provenance.json').read_text())
    jobs = manifest['jobs']
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    check(manifest['status'] == 'complete', 'Run is incomplete')
    check(all(j.get('status') == 'complete' for j in jobs), 'Incomplete jobs')
    names = {j['name'] for j in jobs}
    check({p.stem for p in (data / 'logs').glob('*.json')} == names, 'Log/manifest mismatch')
    check(provenance['run_ids'] == [run_id], 'Analysis run mismatch')
    check({x['name'] for x in provenance['inputs']} == names, 'Analysis/manifest mismatch')
    verified_hashes = {x['name']: x['sha256'] for x in provenance['inputs']}
    check(sha(data / 'source/src/cache_bench.c') == env['source_sha256'], 'Source hash mismatch')
    check(sha(data / 'cache_capacity.bin') == env['binary_sha256'], 'Binary hash mismatch')
    cpu, node = config['cpu'], config['numa_node']
    siblings = [int(s) for s in env['siblings'].split(',') if int(s) != cpu]
    events = {k: [] for k in ('measurement_minor_faults', 'major_faults',
                              'voluntary_switches', 'involuntary_switches')}
    sibling_busy = []
    raw_bytes = gzip_bytes = samples = huge_points = base_points = 0
    for job in jobs:
        name, p = job['name'], job['parameters']
        record = json.loads((data / 'logs' / f'{name}.json').read_text())
        log = (data / 'logs' / f'{name}.txt').read_text()
        check(record['parameters'] == p, f'{name}: parameter mismatch')
        check(record['log'] == log, f'{name}: text/JSON log mismatch')
        check(record['environment'] == env, f'{name}: environment mismatch')
        raw_path = data / record['raw_file']
        payload = gzip.decompress(raw_path.read_bytes())
        raw = np.frombuffer(payload, dtype='<u8')
        check(len(raw) == p['samples'] == 1000000, f'{name}: sample count')
        check(bool(np.all(raw > 0)), f'{name}: nonpositive samples')
        check(hashlib.sha256(payload).hexdigest() == record['raw_sha256'] == verified_hashes[name],
              f'{name}: raw checksum mismatch')
        check(re.findall(r'cpu_start=(\d+) cpu_end=(\d+)', log) == [(str(cpu), str(cpu))],
              f'{name}: CPU binding mismatch')
        mapped = (p['bytes'] + 2097151) // 2097152 * 2097152
        check(re.findall(r'mapped_bytes=(\d+)', log) == [str(mapped)], f'{name}: mapped size')
        expected_huge = mapped if p['pages'] == 'huge' else 0
        huge = [int(x) * 1024 for x in re.findall(r'AnonHugePages:\s+(\d+) kB', log)]
        check(huge == [expected_huge, expected_huge], f'{name}: page backing mismatch')
        mappings = re.findall(r'^numa_mapping: (.+)$', log, re.M)
        check(len(mappings) == 2, f'{name}: missing NUMA mapping')
        for mapping in mappings:
            placement = {int(n): int(count) for n, count in re.findall(r'\bN(\d+)=(\d+)', mapping)}
            check(f'bind:{node} ' in mapping, f'{name}: memory policy mismatch')
            check(placement == {node: mapped // env['page_size']}, f'{name}: nonlocal/incomplete mapping')
        for key, values in events.items():
            matches = re.findall(rf'\b{key}=(\d+)', log)
            check(len(matches) == 1, f'{name}: missing {key}')
            if matches:
                values.append(int(matches[0]))
        sibling_busy.extend(record['cpu_busy_percent'][f'cpu{s}'] for s in siblings)
        raw_bytes += len(payload)
        gzip_bytes += raw_path.stat().st_size
        samples += len(raw)
        huge_points += p['pages'] == 'huge'
        base_points += p['pages'] == 'base'
    start, end = (dt.datetime.fromisoformat(manifest[k]) for k in ('started_utc', 'finished_utc'))
    result = dict(machine='sunbird', run_id=run_id, passed=not errors, errors=errors,
                  checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  collection_status=manifest['status'], expected_configurations=len(jobs),
                  complete_configurations=sum(j.get('status') == 'complete' for j in jobs),
                  total_timed_batches=samples, raw_bytes=raw_bytes, raw_gzip_bytes=gzip_bytes,
                  started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
                  wall_seconds=(end-start).total_seconds(), cpu=cpu, numa_node=node,
                  smt_siblings=siblings, smt_busy_percent_range=[min(sibling_busy), max(sibling_busy)],
                  huge_configurations=huge_points, base_configurations=base_points,
                  runtime_events={k: dict(minimum=min(v), maximum=max(v), total=sum(v))
                                  for k, v in events.items()},
                  source_sha256=env['source_sha256'], binary_sha256=env['binary_sha256'],
                  audit_script_sha256=sha(Path(__file__)),
                  raw_checks='Counts, positive samples, and hashes independently checked; '
                             'analysis provenance matched. All statistics recomputed by analyze_capacity.py.',
                  caveat='Data integrity and page checks do not establish freedom from machine interference.')
    (output / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return not errors


if __name__ == '__main__':
    if not sys.argv[1:]:
        raise SystemExit('Supply completed, analyzed run IDs')
    outcomes = [audit(run_id) for run_id in sys.argv[1:]]
    raise SystemExit(0 if all(outcomes) else 1)
