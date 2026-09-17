#!/usr/bin/env python3
"""Run one-million-batch line-size or associativity PMU configurations."""
import argparse
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import subprocess
import sys
import time
import numpy as np

PMU = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PMU / 'capacity/scripts'))
from common import activity, cpu_stat, frequency, identifier, raw_event_encoding, save, sha, summarize


def plan(c):
    identifier(c['machine'])
    if c['isa'] != 'x86_64' or c['samples'] < 1000000 or c['batch'] < 1 or c['warmup'] < 1:
        raise ValueError('Linux x86-64 and >= 1,000,000 batches required')
    if len(c['events']) != 4 or len({e['name'] for e in c['events']}) != 4:
        raise ValueError('Four distinct events required')
    if not c['points'] or len({p['name'] for p in c['points']}) != len(c['points']):
        raise ValueError('Empty or duplicate points')
    points = [dict(p) for p in c['points']]
    for p in points:
        identifier(p['name']); identifier(p['group'])
        if c['experiment'] == 'line_size':
            if (p['stride'] < 8 or p['stride'] % 8 or p['alignment'] % 8 or
                    c['footprint'] // p['stride'] < 2 or c['group_window'] < p['stride'] or
                    p['mode'] not in ('random_lines', 'sequential_lines', 'fully_random')):
                raise ValueError('Invalid/alignment-unsafe line-size parameters')
        elif c['experiment'] == 'associativity':
            if not 1 <= p['k'] <= p['max_k'] or p['num_sets'] < 1 or c['line_size'] % 8:
                raise ValueError('Invalid associativity parameters')
        else:
            raise ValueError('Unsupported experiment')
    random.Random(c['order_seed']).shuffle(points)
    return points


def denominators(c, p):
    if c['experiment'] == 'line_size':
        return c['batch'], c['samples'] * c['batch']
    return c['batch'] + 1, c['samples'] * (p['k'] + c['batch'])


def validate_counts(counts, c, p):
    if counts['chain_loads'] != denominators(c, p)[1]:
        raise ValueError('Incorrect chain-load denominator')
    if not counts['time_enabled_ns'] or counts['time_enabled_ns'] != counts['time_running_ns']:
        raise ValueError('Counter group was not fully scheduled')
    if len(counts['events']) != 4:
        raise ValueError('Wrong event count')
    for actual, expected in zip(counts['events'], c['events']):
        if actual['config'] != int(expected['config'], 0) or actual['count'] < 0:
            raise ValueError('Event encoding/count mismatch')


def worker_command(c, p, data, executable):
    # taskset can select a permitted CPU outside the inherited affinity mask;
    # numactl's CPU parser can reject that CPU before attempting affinity.
    cmd = ['taskset', '-c', str(c['cpu']), 'numactl', '--membind=' + str(c['numa_node']), str(executable)]
    args = dict(samples=c['samples'], batch=c['batch'], warmup=c['warmup'])
    if c['experiment'] == 'line_size':
        args.update(footprint=c['footprint'], group_window=c['group_window'],
                    **{k: p[k] for k in ('stride', 'alignment', 'seed', 'mode')},
                    output=data / 'raw' / (p['name'] + '.u64'))
    else:
        args.update(num_sets=p['num_sets'], line_size=c['line_size'], max_k=p['max_k'], seed=c['seed'],
                    only_ks=p['k'], output=data / 'legacy' / (p['name'] + '.csv'))
        args['ticks-output'] = data / 'raw' / (p['name'] + '.u64')
    args['pmu-events'] = ','.join(e['config'] for e in c['events'])
    args['pmu-output'] = data / 'counts' / (p['name'] + '.json')
    for key, value in args.items():
        cmd.extend(['--' + key, str(value)])
    return cmd


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experiment', choices=('line_size', 'associativity'), required=True)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    identifier(args.machine); identifier(args.run_id)
    root = PMU / args.experiment
    c = json.loads((args.config or root / 'configs' / (args.machine + '.json')).read_text())
    if c['machine'] != args.machine or c['experiment'] != args.experiment:
        raise ValueError('Config/CLI mismatch')
    jobs = plan(c)
    print(f'{args.experiment}: {len(jobs)} configurations, {c["samples"]:,} batches each', flush=True)
    if args.dry_run:
        print(json.dumps(jobs, indent=2)); return
    if platform.node().split('.')[0] != args.machine or platform.machine() != c['isa']:
        raise ValueError('Host/ISA mismatch')
    if not Path(f'/sys/devices/system/cpu/cpu{c["cpu"]}/node{c["numa_node"]}').exists():
        raise ValueError('CPU/NUMA mismatch')
    data = root / 'data' / args.machine / args.run_id
    if data.exists() or (root / 'results' / args.machine / args.run_id).exists():
        raise FileExistsError('Use a new run ID')
    data.mkdir(parents=True)
    for sub in ('raw', 'counts', 'logs', 'legacy'):
        (data / sub).mkdir()
    save(data / 'config.json', c)
    manifest = dict(status='running', experiment=args.experiment, machine=args.machine,
                    run_id=args.run_id, started_utc=now(), jobs=jobs, command=sys.argv)
    start = time.monotonic()
    try:
        with (data / 'build.log').open('w') as f:
            subprocess.run(['make', '-B', 'all', 'MACHINE=' + args.machine], cwd=root,
                           stdout=f, stderr=subprocess.STDOUT, check=True)
        executable = root / 'build' / args.machine / (args.experiment + '_pmu')
        listing = subprocess.check_output(['perf', 'list', '--details'] + [e['name'] for e in c['events']], text=True)
        (data / 'selected-events.txt').write_text(listing)
        for e in c['events']:
            if raw_event_encoding(listing, e['name']) != int(e['config'], 0):
                raise ValueError('Local encoding mismatch: ' + e['name'])
        topology = Path(f'/sys/devices/system/cpu/cpu{c["cpu"]}/topology')
        siblings = []
        for value in (topology / 'thread_siblings_list').read_text().strip().split(','):
            ends = list(map(int, value.split('-')))
            siblings.extend(range(ends[0], ends[-1] + 1))
        before = cpu_stat(); time.sleep(1)
        env = dict(hostname=platform.node(), kernel=platform.release(), cpu=c['cpu'], numa_node=c['numa_node'],
                   isa=platform.machine(), siblings=siblings, preflight_busy_percent=activity(before, cpu_stat(), siblings),
                   socket=(topology / 'physical_package_id').read_text().strip(),
                   core=(topology / 'core_id').read_text().strip(), frequency=frequency(c['cpu']),
                   compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
                   perf_version=subprocess.check_output(['perf', '--version'], text=True).strip(),
                   python=platform.python_version(), numpy=np.__version__,
                   flags='-O0 -g -std=c++11 -Wall -Wextra -Werror -fno-omit-frame-pointer',
                   timer_unit='TSC ticks / timed chain load',
                   placement_note=c.get('placement_note', 'No prior placement comparison supplied.'),
                   counting_scope='User mode, calling thread, entire sample loop; includes stack/helper loads and associativity preparation loads.')
        save(data / 'environment.json', env)
        print('Preflight: ' + str(env['preflight_busy_percent']), flush=True)
        for index, p in enumerate(jobs, 1):
            cmd = worker_command(c, p, data, executable)
            p.update(status='running', command=cmd, started_utc=now(), frequency_before=frequency(c['cpu']))
            save(data / 'manifest.json', manifest)
            before = cpu_stat(); t0 = time.monotonic()
            log_path = data / 'logs' / (p['name'] + '.txt')
            with log_path.open('w') as f:
                run = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            p.update(returncode=run.returncode, elapsed_seconds=time.monotonic() - t0,
                     cpu_busy_percent=activity(before, cpu_stat(), siblings), frequency_after=frequency(c['cpu']))
            if run.returncode:
                raise RuntimeError('Benchmark failed: ' + str(log_path))
            log = log_path.read_text()
            if f'cpu_end={c["cpu"]}' not in log:
                raise ValueError('CPU placement check failed')
            maps = re.findall(r'numa_mapping: (.*)', log)
            if len(maps) != 2 or any(set(re.findall(r'\bN(\d+)=', m)) != {str(c['numa_node'])} for m in maps):
                raise ValueError('NUMA placement check failed')
            p['measurement_events'] = {k: int(v) for k, v in re.findall(
                r'(minor_faults|major_faults|voluntary_switches|involuntary_switches)=(\d+)', log)}
            p['anon_huge_kib_before_after'] = list(map(int, re.findall(r'AnonHugePages:\s+(\d+)', log)))
            if len(p['anon_huge_kib_before_after']) != 2 or len(set(p['anon_huge_kib_before_after'])) != 1:
                raise ValueError('Mapping huge-page state changed')
            raw_path = data / 'raw' / (p['name'] + '.u64')
            raw = np.fromfile(raw_path, dtype='<u8')
            if raw_path.stat().st_size != c['samples'] * 8 or len(raw) != c['samples'] or not np.all(raw > 0):
                raise ValueError('Invalid timing array')
            count_path = data / 'counts' / (p['name'] + '.json')
            counts = json.loads(count_path.read_text()); validate_counts(counts, c, p)
            timed_loads, chase_loads = denominators(c, p)
            p.update(timed_loads_per_batch=timed_loads, counted_chain_loads=chase_loads,
                     statistics=summarize(raw, timed_loads), legacy_median=float(np.median(raw) / c['batch']))
            compressed = raw_path.with_suffix('.u64.gz')
            with raw_path.open('rb') as source, gzip.open(compressed, 'wb', compresslevel=6) as target:
                shutil.copyfileobj(source, target)
            raw_path.unlink()
            p.update(status='complete', finished_utc=now(), raw_file=str(compressed.relative_to(data)),
                     raw_sha256=sha(compressed), counts_file=str(count_path.relative_to(data)),
                     counts_sha256=sha(count_path), log_file=str(log_path.relative_to(data)))
            rates = [round(e['count'] / chase_loads * 1000, 3) for e in counts['events'][:3]]
            print(f'[{index}/{len(jobs)}] {p["name"]}: {p["statistics"]["median"]:.4f} ticks/timed load; '
                  f'L1/L2/L3 misses per 1000 chain loads {rates}', flush=True)
        manifest['status'] = 'complete'
    except BaseException as error:
        manifest.update(status='failed', error=str(error))
        for p in jobs:
            if p.get('status') == 'running': p.update(status='failed', error=str(error))
        raise
    finally:
        manifest.update(finished_utc=now(), elapsed_seconds=time.monotonic() - start)
        save(data / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
