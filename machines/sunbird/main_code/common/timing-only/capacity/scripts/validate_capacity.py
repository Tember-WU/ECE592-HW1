#!/usr/bin/env python3
"""Audit completed collection, raw arrays, analysis, placement, and source snapshots."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

from analyze_capacity import load_study
from run_capacity import ROOT, identifier


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', nargs='+', required=True)
    ap.add_argument('--output-id', required=True)
    args = ap.parse_args()
    machine = identifier(args.machine)
    run_ids = [identifier(r) for r in args.run_id]
    output = ROOT / 'results' / machine / identifier(args.output_id)
    provenance = json.loads((output / 'provenance.json').read_text())
    assert provenance['run_ids'] == run_ids, 'Analysis belongs to different runs'
    records = load_study(ROOT, machine, run_ids)
    inputs = {(p['run_id'], p['name']): p['sha256'] for p in provenance['inputs']}
    assert inputs == {(d['run_id'], d['name']): d['raw_sha256'] for d in records}
    event_names = ('measurement_minor_faults', 'major_faults', 'voluntary_switches', 'involuntary_switches')
    events = {key: [] for key in event_names}
    rounds = []
    compressed = 0
    page_policies = {}
    frequency_ranges = {}
    for run_id in run_ids:
        data = ROOT / 'data' / machine / run_id
        manifest = json.loads((data / 'manifest.json').read_text())
        env = json.loads((data / 'environment.json').read_text())
        assert manifest['status'] == 'complete', f'{run_id}: incomplete collection'
        assert all(j['status'] == 'complete' for j in manifest['jobs'])
        selected = [d for d in records if d['run_id'] == run_id]
        assert {d['name'] for d in selected} == {j['name'] for j in manifest['jobs']}
        assert len(selected) == len(manifest['jobs'])
        source = env.get('source_file', 'src/cache_bench.c')
        assert digest(data / 'source' / source) == env['source_sha256']
        assert digest(data / 'cache_capacity.bin') == env['binary_sha256']
        for d in selected:
            p, log = d['parameters'], d['log']
            assert d['environment'] == env, f'{d["name"]}: metadata mismatch'
            assert p['samples'] >= 1000000
            assert f'cpu_start={env["cpu"]} cpu_end={env["cpu"]}' in log
            mapped = int(re.search(r'mapped_bytes=(\d+)', log)[1])
            # Validate both measurement boundaries, not just allocation-time hints.
            for label in ('mapping_before:', 'mapping_after:'):
                section = log.split(label, 1)[1].split('mapping_after:', 1)[0]
                huge = int(re.search(r'AnonHugePages:\s+(\d+)', section)[1]) * 1024
                assert huge == (mapped if p['pages'] == 'huge' else 0)
                mapping = re.search(r'numa_mapping: ([^\n]+)', section)[1]
                assert f'bind:{env["numa_node"]} ' in mapping
                nodes = dict((int(n), int(count)) for n, count in re.findall(r'\bN(\d+)=(\d+)', mapping))
                assert nodes == {env['numa_node']: mapped // env['page_size']}, nodes
            if env.get('isa') == 'aarch64':
                assert f'timer_frequency_hz={env["timer_frequency_hz"]}' in log
            for key in event_names:
                events[key].append(int(re.search(rf'\b{key}=(\d+)', log)[1]))
            saved = json.loads((data / 'logs' / f'{d["name"]}.json').read_text())['stats']
            assert saved == d['stats'], f'{d["name"]}: saved statistics differ from raw samples'
            compressed += (data / d['raw_file']).stat().st_size
            page_policies[p['pages']] = page_policies.get(p['pages'], 0) + 1
            for point in ('before', 'after'):
                state = d.get(f'cpu_frequency_{point}', {})
                if 'scaling_cur_freq' in state:
                    frequency_ranges.setdefault(point, []).append(int(state['scaling_cur_freq']))
        seconds = (dt.datetime.fromisoformat(manifest['finished_utc']) -
                   dt.datetime.fromisoformat(manifest['started_utc'])).total_seconds()
        rounds.append(dict(run_id=run_id, configurations=len(selected), wall_seconds=seconds,
                           started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc']))
    preservation = ROOT / 'data' / machine / 'preflight/artemisia_sha256_before.json'
    preserved = None
    if preservation.exists():
        hashes = json.loads(preservation.read_text())
        assert all((ROOT / name).is_file() and digest(ROOT / name) == value
                   for name, value in hashes.items()), 'An original Artemisia file changed'
        preserved = len(hashes)
    validation = dict(passed=True, machine=machine, run_ids=run_ids,
                      checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      validation_scope='Raw hashes, sample counts, recomputed statistics, completed manifests, '
                      'source/binary snapshots, compatible environments, CPU/NUMA and page backing. '
                      'Passing these checks does not establish absence of measurement interference.',
                      configurations=len(records), total_timed_batches=sum(d['stats']['n'] for d in records),
                      raw_bytes=sum(d['stats']['n'] * 8 for d in records), raw_gzip_bytes=compressed,
                      rounds=rounds, page_policies=page_policies, all_mappings_local_and_policy_matched=True,
                      runtime_events={key: dict(minimum=min(values), maximum=max(values), total=sum(values))
                                      for key, values in events.items()},
                      cpu_frequency_khz={key: [min(values), max(values)] for key, values in frequency_ranges.items()},
                      original_artemisia_files_preserved=preserved,
                      validator_sha256=digest(Path(__file__)))
    (output / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
