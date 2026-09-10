"""Recheck this machine's saved samples, analysis, provenance, and mapping logs.

Run after analyze_capacity.py with the capacity virtual environment:
  .venv/bin/python results/charnwood/preparation/validate_runs.py round1 round2
"""
import collections
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_capacity import load_study
from run_capacity import plan


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate(run_id, records):
    data = ROOT / 'data/charnwood' / run_id
    output = ROOT / 'results/charnwood' / run_id
    manifest = json.loads((data / 'manifest.json').read_text())
    config = json.loads((data / 'config.json').read_text())
    env = json.loads((data / 'environment.json').read_text())
    provenance = json.loads((output / 'provenance.json').read_text())
    with (output / 'summary.csv').open() as f:
        summary = {row['name']: row for row in csv.DictReader(f)}
    expected = {j['name'] for j in plan(config, ['all'])}
    check(manifest['status'] == 'complete', f'{run_id}: incomplete run')
    check(all(j['status'] == 'complete' for j in manifest['jobs']), 'Incomplete jobs')
    check(expected == {j['name'] for j in manifest['jobs']} ==
          {d['name'] for d in records} == set(summary), 'Point sets differ')
    check(len(records) == len(manifest['jobs']) == len(expected), 'Duplicate records')
    check({p.name for p in (data / 'raw').glob('*')} ==
          {Path(d['raw_file']).name for d in records}, 'Raw file set differs')
    check(provenance['run_ids'] == [run_id], 'Analysis inputs differ')
    check({d['name']: d['sha256'] for d in provenance['inputs']} ==
          {d['name']: d['raw_sha256'] for d in records}, 'Analysis hashes differ')
    check(sha(data / 'source/src/cache_bench.c') == env['source_sha256'], 'Source hash')
    check(sha(data / 'cache_capacity.bin') == env['binary_sha256'], 'Binary hash')
    check(sha(ROOT / 'scripts/analyze_capacity.py') == provenance['analysis_sha256'],
          'Analysis script changed')
    check(sha(ROOT / 'scripts/run_capacity.py') == provenance['statistics_sha256'],
          'Statistics script changed')
    cpu, node = config['cpu'], config['numa_node']
    check(cpu == 3 and node == 0 and env['host'].split('.')[0] == 'charnwood',
          'Unexpected host or binding')
    events = collections.defaultdict(list)
    pages = collections.Counter()
    sibling_busy = []
    for d in records:
        p, name = d['parameters'], d['name']
        log = (data / 'logs' / f'{name}.txt').read_text()
        check(log == d['log'], f'{name}: text/JSON log mismatch')
        check(d['environment'] == env, f'{name}: environment mismatch')
        fields = dict(re.findall(r'\b(\w+)=(\d+)\b', log))
        for key in ('bytes', 'spacing', 'samples', 'batch', 'seed'):
            check(int(fields[key]) == p[key], f'{name}: {key}')
        check(int(fields['cpu_start']) == int(fields['cpu_end']) == cpu, f'{name}: CPU')
        mapped = ((p['bytes'] + 2097151) // 2097152) * 2097152
        check(int(fields['mapped_bytes']) == mapped, f'{name}: mapping size')
        huge_kib = list(map(int, re.findall(r'AnonHugePages:\s+(\d+) kB', log)))
        check(huge_kib == [mapped // 1024 if p['pages'] == 'huge' else 0] * 2,
              f'{name}: page policy before/after')
        mappings = re.findall(r'^numa_mapping: (.+)$', log, re.M)
        check(len(mappings) == 2, f'{name}: missing NUMA mappings')
        for mapping in mappings:
            placement = {int(n): int(count) for n, count in re.findall(r'\bN(\d+)=(\d+)', mapping)}
            check(placement == {node: mapped // env['page_size']}, f'{name}: NUMA placement')
            check(f'bind:{node} ' in mapping, f'{name}: memory policy')
        for key in ('measurement_minor_faults', 'major_faults', 'voluntary_switches', 'involuntary_switches'):
            events[key].append(int(fields[key]))
        for key, value in d['stats'].items():
            if key != 'decile_medians':
                check(math.isclose(float(summary[name][key]), value, rel_tol=1e-12, abs_tol=1e-12),
                      f'{name}: recomputed {key} differs from summary.csv')
        pages[p['pages']] += 1
        sibling_busy.append(d['cpu_busy_percent']['cpu7'])
    started = dt.datetime.fromisoformat(manifest['started_utc'])
    finished = dt.datetime.fromisoformat(manifest['finished_utc'])
    result = dict(passed=True, errors=[], machine='charnwood', run_id=run_id,
                  checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  validation_scope='Raw SHA-256, positive sample counts, recomputed statistics, manifest/config/analysis agreement, source/binary hashes, CPU/NUMA binding and page backing. Does not certify absence of interference.',
                  collection_status=manifest['status'], expected_configurations=len(expected),
                  complete_configurations=len(records),
                  total_timed_batches=sum(d['parameters']['samples'] for d in records),
                  raw_bytes=sum(d['parameters']['samples'] * 8 for d in records),
                  raw_gzip_bytes=sum((data / d['raw_file']).stat().st_size for d in records),
                  started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
                  wall_seconds=(finished - started).total_seconds(), cpu=cpu, numa_node=node,
                  smt_sibling=7, configured_page_counts=dict(pages),
                  smt_busy_percent_range=[min(sibling_busy), max(sibling_busy)],
                  smt_busy_points_above_50_percent=[
                      dict(name=d['name'], busy_percent=d['cpu_busy_percent']['cpu7'],
                           median=d['stats']['median'])
                      for d in records if d['cpu_busy_percent']['cpu7'] > 50],
                  all_mappings_local_and_matching_page_policy=True,
                  runtime_events={k: dict(minimum=min(v), maximum=max(v), total=sum(v))
                                  for k, v in events.items()},
                  source_sha256=env['source_sha256'], binary_sha256=env['binary_sha256'])
    (output / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    run_ids = sys.argv[1:]
    check(bool(run_ids), 'Supply completed run IDs')
    records = load_study(ROOT, 'charnwood', run_ids)
    results = [validate(r, [d for d in records if d['run_id'] == r]) for r in run_ids]
    if run_ids == ['round1', 'round2']:
        output = ROOT / 'results/charnwood/combined12'
        provenance = json.loads((output / 'provenance.json').read_text())
        check(provenance['run_ids'] == run_ids, 'Combined input runs differ')
        check({(d['run_id'], d['name']): d['sha256'] for d in provenance['inputs']} ==
              {(d['run_id'], d['name']): d['raw_sha256'] for d in records}, 'Combined hashes differ')
        combined = dict(passed=True, errors=[], machine='charnwood', source_runs=run_ids,
                        complete_configurations=sum(r['complete_configurations'] for r in results),
                        total_timed_batches=sum(r['total_timed_batches'] for r in results),
                        raw_bytes=sum(r['raw_bytes'] for r in results),
                        raw_gzip_bytes=sum(r['raw_gzip_bytes'] for r in results), runs=results)
        (output / 'validation.json').write_text(json.dumps(combined, indent=2) + '\n')
    for result in results:
        print(json.dumps(result, indent=2))
