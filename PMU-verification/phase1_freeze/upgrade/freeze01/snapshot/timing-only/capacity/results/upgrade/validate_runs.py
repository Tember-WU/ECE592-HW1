#!/usr/bin/env python3
"""Audit completed upgrade runs and preserve validation alongside their analyses."""
import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from analyze_capacity import load_study
from run_capacity import plan


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id', nargs='+', required=True)
    ap.add_argument('--output-id', default='combined12')
    args = ap.parse_args()
    # Recompute statistics and verify every raw count, positive interval and hash;
    # also reject incompatible environments across the supplied rounds.
    records = load_study(ROOT, 'upgrade', args.run_id)
    validations = []
    for run_id in args.run_id:
        data = ROOT / 'data/upgrade' / run_id
        output = ROOT / 'results/upgrade' / run_id
        manifest = json.loads((data / 'manifest.json').read_text())
        config = json.loads((data / 'config.json').read_text())
        env = json.loads((data / 'environment.json').read_text())
        provenance = json.loads((output / 'provenance.json').read_text())
        ds = [d for d in records if d['run_id'] == run_id]
        errors = []

        def check(condition, message):
            if not condition:
                errors.append(message)

        expected = plan(config, ['all'])
        check(manifest['status'] == 'complete', 'Collection is incomplete')
        check(all(j.get('status') == 'complete' for j in manifest['jobs']), 'Incomplete manifest jobs')
        check({d['name'] for d in ds} == {j['name'] for j in expected}, 'Config/record point mismatch')
        check({j['name'] for j in manifest['jobs']} == {j['name'] for j in expected}, 'Config/manifest mismatch')
        check(digest(data / 'source/src/cache_bench.c') == env['source_sha256'], 'C snapshot hash mismatch')
        check(digest(data / 'cache_capacity.bin') == env['binary_sha256'], 'Executable hash mismatch')
        check(digest(data / 'source/scripts/analyze_capacity.py') == provenance['analysis_sha256'], 'Analyzer snapshot mismatch')
        check(digest(data / 'source/scripts/run_capacity.py') == provenance['statistics_sha256'], 'Statistics snapshot mismatch')
        check({(i['name'], i['sha256']) for i in provenance['inputs']} ==
              {(d['name'], d['raw_sha256']) for d in ds}, 'Analysis input mismatch')
        cpu, node = config['cpu'], config['numa_node']
        events = {k: [] for k in ('measurement_minor_faults', 'major_faults',
                                 'voluntary_switches', 'involuntary_switches')}
        parameters = {j['name']: j['parameters'] for j in expected}
        for d in ds:
            name, p, log = d['name'], d['parameters'], d['log']
            check(p == parameters.get(name), f'{name}: parameter mismatch')
            check(d['environment'] == env, f'{name}: environment mismatch')
            check((data / 'logs' / f'{name}.txt').read_text() == log, f'{name}: text/JSON log mismatch')
            saved = json.loads((data / 'logs' / f'{name}.json').read_text())
            check(saved['stats'] == d['stats'], f'{name}: saved/recomputed statistics differ')
            fields = dict(re.findall(r'(\w+)=([^\s]+)', log))
            check(fields.get('cpu_start') == fields.get('cpu_end') == str(cpu), f'{name}: CPU binding mismatch')
            mapped = (p['bytes'] + 2097151) // 2097152 * 2097152
            check(fields.get('mapped_bytes') == str(mapped), f'{name}: mapping size mismatch')
            coverage = [int(x) * 1024 for x in re.findall(r'AnonHugePages:\s+(\d+) kB', log)]
            check(coverage == [mapped if p['pages'] == 'huge' else 0] * 2, f'{name}: page policy mismatch')
            mappings = [line for line in log.splitlines() if line.startswith('numa_mapping:')]
            check(len(mappings) == 2, f'{name}: missing NUMA mapping logs')
            for line in mappings:
                allocation = {int(n): int(pages) for n, pages in re.findall(r'\bN(\d+)=(\d+)', line)}
                check(allocation == {node: mapped // env['page_size']} and f'bind:{node} ' in line,
                      f'{name}: nonlocal or incomplete NUMA mapping')
            for key in events:
                if key not in fields:
                    errors.append(f'{name}: missing {key}')
                else:
                    events[key].append(int(fields[key]))
        event_stats = {k: dict(minimum=min(v), maximum=max(v), total=sum(v)) for k, v in events.items() if v}
        sibling = 8
        busy = [d['cpu_busy_percent'][f'cpu{sibling}'] for d in ds]
        result = dict(passed=not errors, errors=errors, machine='upgrade', run_id=run_id,
                      validation_scope='Raw integrity, recomputed statistics, provenance, CPU/NUMA binding and page backing; does not certify absence of interference.',
                      checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      collection_status=manifest['status'], expected_configurations=len(expected),
                      complete_configurations=len(ds), total_timed_batches=sum(d['stats']['n'] for d in ds),
                      raw_bytes=sum(d['stats']['n'] * 8 for d in ds),
                      raw_gzip_bytes=sum((data / d['raw_file']).stat().st_size for d in ds),
                      started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
                      wall_seconds=(dt.datetime.fromisoformat(manifest['finished_utc']) - dt.datetime.fromisoformat(manifest['started_utc'])).total_seconds(),
                      cpu=cpu, numa_node=node, smt_sibling=sibling,
                      smt_busy_percent_range=[min(busy), max(busy)],
                      configured_page_counts=dict(Counter(d['parameters']['pages'] for d in ds)),
                      runtime_events=event_stats, source_sha256=env['source_sha256'], binary_sha256=env['binary_sha256'],
                      audit_script_sha256=digest(Path(__file__)))
        write(output / 'validation.json', result)
        validations.append(result)
        print(f'{run_id}: passed={result["passed"]}; points={len(ds)}; errors={errors}')
    if len(validations) > 1:
        write(ROOT / 'results/upgrade' / args.output_id / 'validation.json',
              dict(passed=all(v['passed'] for v in validations), machine='upgrade',
                   run_ids=args.run_id, runs=validations,
                   complete_configurations=sum(v['complete_configurations'] for v in validations),
                   total_timed_batches=sum(v['total_timed_batches'] for v in validations)))
    if any(not v['passed'] for v in validations):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
