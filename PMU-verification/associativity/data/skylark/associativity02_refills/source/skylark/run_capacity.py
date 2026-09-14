#!/usr/bin/env python3
"""Collect a small same-workload capacity sweep with a pinned PMU event group."""
import argparse
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'capacity/scripts'))
from common import ROOT, activity, cpu_stat, frequency, identifier, plan, save, sha, summarize, validate_counts


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    identifier(args.machine); identifier(args.run_id)
    config = json.loads((args.config or ROOT / 'configs' / (args.machine + '.json')).read_text())
    if config['machine'] != args.machine:
        raise ValueError('Machine/config mismatch')
    jobs = plan(config)
    print(f'{len(jobs)} configurations, {config["samples"]:,} timed batches each, four simultaneous events.', flush=True)
    if args.dry_run:
        print(json.dumps(jobs, indent=2)); return
    if platform.node().split('.')[0] != args.machine or platform.machine() != config['isa']:
        raise ValueError('Host or ISA mismatch')
    cpu, node = config['cpu'], config['numa_node']
    if not Path(f'/sys/devices/system/cpu/cpu{cpu}/node{node}').exists():
        raise ValueError('CPU/NUMA node mismatch')
    inherited = os.sched_getaffinity(0)
    try:
        os.sched_setaffinity(0, {cpu})
    finally:
        os.sched_setaffinity(0, inherited)
    if not shutil.which('numactl'):
        raise RuntimeError('numactl is required')
    out = ROOT / 'data' / args.machine / args.run_id
    if out.exists() or (ROOT / 'results' / args.machine / args.run_id).exists():
        raise FileExistsError('Choose a new run ID')
    out.mkdir(parents=True)
    for directory in ('raw', 'logs', 'counts'):
        (out / directory).mkdir()
    save(out / 'config.json', config)
    manifest = dict(machine=args.machine, run_id=args.run_id, status='running',
                    started_utc=now(), command=sys.argv, jobs=jobs)
    start = time.monotonic()
    try:
        with (out / 'build.log').open('w') as f:
            subprocess.run(['make', '-B', 'all', 'MACHINE=' + args.machine], cwd=ROOT,
                           stdout=f, stderr=subprocess.STDOUT, check=True)
        executable = ROOT / 'build' / args.machine / 'cache_capacity_pmu'
        # Validate raw encodings against the names exposed by this machine.
        listing = subprocess.check_output(['perf', 'list', '--details'] +
                                         [e['name'] for e in config['events']], text=True)
        (out / 'selected-events.txt').write_text(listing)
        for event in config['events']:
            block = re.search(r'^  ' + re.escape(event['name']) + r'\n(.*?)(?=^  \S|\Z)', listing, re.M | re.S)
            encoding = re.search(r'cpu/event=(0x[0-9a-f]+),[^\n]*umask=(0x[0-9a-f]+)', block.group(1)) if block else None
            if not encoding or int(encoding[1], 16) | (int(encoding[2], 16) << 8) != int(event['config'], 0):
                raise ValueError('Local perf event encoding mismatch: ' + event['name'])
        topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
        sibling_text = (topology / 'thread_siblings_list').read_text().strip()
        siblings = []
        for part in sibling_text.split(','):
            ends = list(map(int, part.split('-')))
            siblings.extend(range(ends[0], ends[-1] + 1))
        pre = cpu_stat(); time.sleep(1); busy = activity(pre, cpu_stat(), siblings)
        env = dict(hostname=platform.node(), kernel=platform.release(), isa=platform.machine(),
                   cpu=cpu, numa_node=node, siblings=siblings,
                   core=(topology / 'core_id').read_text().strip(),
                   socket=(topology / 'physical_package_id').read_text().strip(),
                   preflight_busy_percent=busy, frequency=frequency(cpu),
                   perf_version=subprocess.check_output(['perf', '--version'], text=True).strip(),
                   compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                   python=platform.python_version(), numpy=np.__version__,
                   flags='-O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer',
                   timer_unit='TSC ticks / dependent load',
                   pmu_scope='Calling thread, user mode, measurement loop only; includes loop/helper instructions',
                   perf_event_paranoid=Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip())
        save(out / 'environment.json', env)
        from support import snapshot_run
        snapshot_run(out, executable, config, manifest)
        print('Preflight CPU busy %: ' + str(busy), flush=True)
        for index, job in enumerate(jobs, 1):
            name = job['name']
            raw_path, count_path = out / 'raw' / (name + '.u64'), out / 'counts' / (name + '.json')
            cmd = ['numactl', '--membind=' + str(node), str(executable), str(job['bytes']),
                   str(config['spacing']), config['mode'], str(config['samples']),
                   str(config['batch']), str(config['seed']), str(cpu), config['pages'],
                   str(raw_path), ','.join(e['config'] for e in config['events']), str(count_path)]
            job.update(command=cmd, status='running', started_utc=now(), frequency_before=frequency(cpu))
            save(out / 'manifest.json', manifest)
            before = cpu_stat(); t0 = time.monotonic()
            log_path = out / 'logs' / (name + '.txt')
            with log_path.open('w') as f:
                run = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            job.update(returncode=run.returncode, elapsed_seconds=time.monotonic() - t0,
                       cpu_busy_percent=activity(before, cpu_stat(), siblings), frequency_after=frequency(cpu))
            if run.returncode:
                raise RuntimeError('Benchmark failed: ' + str(log_path))
            log = log_path.read_text()
            if f'cpu_start={cpu} cpu_end={cpu}' not in log:
                raise ValueError('Affinity check failed')
            mappings = re.findall(r'numa_mapping: (.*)', log)
            if len(mappings) != 2 or any(set(re.findall(r'\bN(\d+)=', m)) != {str(node)} for m in mappings):
                raise ValueError('Memory placement check failed')
            job['measurement_events'] = {k: int(v) for k, v in re.findall(
                r'(measurement_minor_faults|major_faults|voluntary_switches|involuntary_switches)=(\d+)', log)}
            raw = np.fromfile(raw_path, dtype='<u8')
            if raw_path.stat().st_size != config['samples'] * 8 or len(raw) != config['samples'] or not np.all(raw > 0):
                raise ValueError('Invalid raw timing samples')
            counts = json.loads(count_path.read_text()); validate_counts(counts, config)
            job['statistics'] = summarize(raw, config['batch'])
            compressed = raw_path.with_suffix('.u64.gz')
            with raw_path.open('rb') as source, gzip.open(compressed, 'wb', compresslevel=6) as target:
                shutil.copyfileobj(source, target)
            raw_path.unlink()
            job.update(status='complete', finished_utc=now(), raw_file=str(compressed.relative_to(out)),
                       raw_sha256=sha(compressed), counts_file=str(count_path.relative_to(out)),
                       counts_sha256=sha(count_path), log_file=str(log_path.relative_to(out)))
            rates = [round(e['count'] / counts['chain_loads'] * 1000, 2) for e in counts['events'][:3]]
            print(f'[{index}/{len(jobs)}] {name}: median {job["statistics"]["median"]:.4f} ticks/load; '
                  f'Configured first three events per 1000 chain loads {rates}', flush=True)
        manifest['status'] = 'complete'
    except BaseException as error:
        manifest.update(status='failed', error=str(error))
        for job in jobs:
            if job.get('status') == 'running':
                job.update(status='failed', error=str(error))
        raise
    finally:
        manifest.update(finished_utc=now(), elapsed_seconds=time.monotonic() - start)
        save(out / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
