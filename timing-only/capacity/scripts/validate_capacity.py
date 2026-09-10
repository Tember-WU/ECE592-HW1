#!/usr/bin/env python3
"""Audit completed capacity runs, raw samples, snapshots, and placement logs."""
import argparse
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import numpy as np

from analyze_capacity import load_study
from run_capacity import ROOT, identifier, load_config, plan


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_run(machine, run_id, records):
    data = ROOT / 'data' / machine / run_id
    manifest = json.loads((data / 'manifest.json').read_text())
    config = load_config(data / 'config.json')
    env = json.loads((data / 'environment.json').read_text())
    jobs = manifest['jobs']
    require(manifest['status'] == 'complete', f'{run_id}: incomplete collection')
    require(config['machine'] == machine == manifest['machine'], 'Machine mismatch')
    require(manifest['run_id'] == run_id, 'Run ID mismatch')
    require(all(j.get('status') == 'complete' for j in jobs), 'Incomplete job')
    # These round configurations each contain a single fully collected sweep.
    expected = {j['name']: j['parameters'] for j in plan(config, ['all'])}
    require(len(jobs) == len(records) == len(expected), 'Configuration count mismatch')
    require({d['name'] for d in records} == set(expected), 'Record names mismatch')
    require({j['name'] for j in jobs} == set(expected), 'Manifest names mismatch')
    for j in jobs:
        require(j['parameters'] == expected[j['name']], 'Manifest parameters mismatch')
    source_hash = sha(data / 'source/src/cache_bench.c')
    binary_hash = sha(data / 'cache_capacity.bin')
    require(source_hash == env['source_sha256'], 'Source snapshot hash mismatch')
    require(binary_hash == env['binary_sha256'], 'Executable snapshot hash mismatch')
    cpu, node = config['cpu'], config['numa_node']
    require(env['cpu'] == cpu and env['numa_node'] == node, 'Environment binding mismatch')
    require(env['host'].split('.')[0] == config['hostname'].split('.')[0], 'Host mismatch')
    events = {key: [] for key in ('measurement_minor_faults', 'major_faults',
                                  'voluntary_switches', 'involuntary_switches')}
    huge_count = base_count = total_samples = raw_bytes = gzip_bytes = 0
    temporal_ratios = []
    for d in records:
        p, log = d['parameters'], d['log']
        require(p == expected[d['name']], f'{d["name"]}: parameters mismatch')
        require(d['environment'] == env, 'Per-point environment mismatch')
        require(log == (data / 'logs' / f'{d["name"]}.txt').read_text(), 'Text log mismatch')
        saved = json.loads((data / 'logs' / f'{d["name"]}.json').read_text())
        for key, value in d['stats'].items():
            require(np.allclose(value, saved['stats'][key], rtol=1e-12, atol=1e-12),
                    f'{d["name"]}: recomputed statistic {key} mismatch')
        fields = dict(re.findall(r'(\w+)=([^\s]+)', log))
        for key in ('bytes', 'spacing', 'mode', 'samples', 'batch', 'seed'):
            require(fields.get(key) == str(p[key]), f'Log {key} mismatch')
        require(fields.get('cpu_start') == fields.get('cpu_end') == str(cpu),
                'CPU binding mismatch')
        mapped = (p['bytes'] + 2097151) // 2097152 * 2097152
        require(fields.get('mapped_bytes') == str(mapped), 'Mapped size mismatch')
        require(int(fields['warm_loads']) >= max(1048576, 4 * p['bytes'] // p['spacing']),
                'Insufficient warm-up')
        for start, end in (('mapping_before:\n', 'mapping_after:\n'),
                           ('mapping_after:\n', '\nbytes=')):
            require(log.count(start) == 1, 'Missing/duplicate page inspection')
            section = log.split(start, 1)[1].split(end, 1)[0]
            coverage = re.findall(r'AnonHugePages:\s+(\d+) kB', section)
            target = mapped // 1024 if p['pages'] == 'huge' else 0
            require(coverage == [str(target)], 'Unexpected huge-page coverage')
            mappings = re.findall(r'numa_mapping: (.*)', section)
            require(len(mappings) == 1, 'Missing/duplicate NUMA mapping')
            line = mappings[0]
            require(line.split()[0].lower() == fields['base'][2:].lower(),
                    'NUMA mapping address mismatch')
            require(f'bind:{node}' in line.split(), 'NUMA policy mismatch')
            require(dict(re.findall(r'\bN(\d+)=(\d+)', line)) ==
                    {str(node): str(mapped // env['page_size'])},
                    'Nonlocal or incomplete NUMA placement')
        for key in events:
            events[key].append(int(fields[key]))
        huge_count += p['pages'] == 'huge'
        base_count += p['pages'] == 'base'
        total_samples += d['stats']['n']
        raw_bytes += d['stats']['n'] * 8
        gzip_bytes += (data / d['raw_file']).stat().st_size
        blocks = d['stats']['decile_medians']
        temporal_ratios.append((max(blocks) / min(blocks), d['name']))
    provenance = json.loads((ROOT / 'results' / machine / run_id / 'provenance.json').read_text())
    require(provenance['run_ids'] == [run_id], 'Analysis input mismatch')
    require({(d['name'], d['sha256']) for d in provenance['inputs']} ==
            {(d['name'], d['raw_sha256']) for d in records}, 'Analysis hash mismatch')
    elapsed = (dt.datetime.fromisoformat(manifest['finished_utc']) -
               dt.datetime.fromisoformat(manifest['started_utc'])).total_seconds()
    return dict(passed=True, errors=[], machine=machine, run_id=run_id,
                checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                collection_status='complete', expected_configurations=len(expected),
                complete_configurations=len(records), total_timed_batches=total_samples,
                raw_checksums_and_statistics='Every raw hash/count/positive interval checked; statistics recomputed and compared with saved values.',
                raw_bytes=raw_bytes, raw_gzip_bytes=gzip_bytes, wall_seconds=elapsed,
                started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
                cpu=cpu, numa_node=node, thread_siblings=env['siblings'],
                huge_configurations=huge_count, base_configurations=base_count,
                all_mappings_local_and_page_policy_verified=True,
                runtime_events={k: dict(minimum=min(v), maximum=max(v), total=sum(v))
                                for k, v in events.items()},
                maximum_temporal_decile_median_ratio=max(temporal_ratios)[0],
                most_variable_temporal_point=max(temporal_ratios)[1],
                source_sha256=source_hash, binary_sha256=binary_hash,
                validator_sha256=sha(Path(__file__)),
                validation_scope='Integrity, snapshots, timing environment, CPU/NUMA placement, and page policy. Passing does not prove absence of interference.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', nargs='+', required=True)
    ap.add_argument('--output-id')
    args = ap.parse_args()
    machine = identifier(args.machine)
    run_ids = [identifier(r) for r in args.run_id]
    records = load_study(ROOT, machine, run_ids)
    audits = [audit_run(machine, r, [d for d in records if d['run_id'] == r]) for r in run_ids]
    # Publish validation only after every requested run has passed.
    for r, audit in zip(run_ids, audits):
        (ROOT / 'results' / machine / r / 'validation.json').write_text(json.dumps(audit, indent=2) + '\n')
    if len(run_ids) > 1:
        output_id = identifier(args.output_id or '-'.join(run_ids))
        require(output_id not in run_ids, 'Combined output ID must differ from each run ID')
        output = ROOT / 'results' / machine / output_id
        provenance = json.loads((output / 'provenance.json').read_text())
        require(provenance['run_ids'] == run_ids, 'Combined analysis input mismatch')
        require({(d['run_id'], d['name'], d['sha256']) for d in provenance['inputs']} ==
                {(d['run_id'], d['name'], d['raw_sha256']) for d in records},
                'Combined analysis hash mismatch')
        combined = dict(passed=True, machine=machine, run_ids=run_ids,
                        same_measurement_environment_verified=True,
                        per_run_validation=[f'../{r}/validation.json' for r in run_ids],
                        validator_sha256=sha(Path(__file__)),
                        validation_scope=audits[0]['validation_scope'])
        for key in ('complete_configurations', 'total_timed_batches', 'raw_bytes', 'raw_gzip_bytes'):
            combined[key] = sum(a[key] for a in audits)
        (output / 'validation.json').write_text(json.dumps(combined, indent=2) + '\n')
    print(f'Validated {len(records)} configurations from {machine}: {", ".join(run_ids)}')


if __name__ == '__main__':
    main()
