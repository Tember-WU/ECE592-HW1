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
from common import (ROOT, activity, cpu_stat, frequency, identifier, plan, raw_event_encoding,
                    save, selected_events, sha, summarize, validate_counts)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def launch(cmd, log_path, raw_path, count_path, retries, attempts, *, retry_delay=2, on_attempt=None):
    """Retry only a known pre-measurement THP allocation failure, retaining logs."""
    for attempt in range(retries + 1):
        started = now()
        with log_path.open('w') as f:
            run = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
        retryable = (run.returncode != 0 and
                     log_path.read_text().strip() == 'MADV_COLLAPSE: Cannot allocate memory' and
                     not raw_path.exists() and not count_path.exists())
        entry = dict(started_utc=started, finished_utc=now(), returncode=run.returncode,
                     premeasurement_allocation_failure=retryable)
        entry['log_file'] = 'logs/' + log_path.name
        if retryable:
            failed_log = log_path.with_name(log_path.stem + f'.allocation-attempt{attempt + 1}.txt')
            shutil.copy2(log_path, failed_log)
            entry['log_file'] = 'logs/' + failed_log.name
        attempts.append(entry)
        if on_attempt is not None:
            on_attempt()
        if not retryable or attempt == retries:
            return run
        print(f'{log_path.stem}: allocation failed before timing; retry {attempt + 1}/{retries}', flush=True)
        time.sleep(retry_delay)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--dry-run', action='store_true')
    retry_options = ap.add_mutually_exclusive_group()
    retry_options.add_argument('--allocation-attempts', type=int,
                    help='Total THP allocation attempts, 1 to 6, with 10 seconds between retries')
    retry_options.add_argument('--allocation-retries', type=int, default=0,
                    help='Retry only pre-timing MADV_COLLAPSE ENOMEM failures (default: 0)')
    args = ap.parse_args()
    if not 0 <= args.allocation_retries <= 30:
        ap.error('--allocation-retries must be between 0 and 30')
    retry_delay = 2
    if args.allocation_attempts is not None:
        if not 1 <= args.allocation_attempts <= 6:
            ap.error('--allocation-attempts must be between 1 and 6')
        args.allocation_retries = args.allocation_attempts - 1
        retry_delay = 10
    identifier(args.machine); identifier(args.run_id)
    config = json.loads((args.config or ROOT / 'configs' / (args.machine + '.json')).read_text())
    if config['machine'] != args.machine:
        raise ValueError('Machine/config mismatch')
    jobs = plan(config)
    print(f'{len(jobs)} measurement passes, {config["samples"]:,} timed batches each; pinned event groups.', flush=True)
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
                    started_utc=now(), command=sys.argv, jobs=jobs,
                    allocation_retries=args.allocation_retries,
                    allocation_retry_delay_seconds=retry_delay)
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
            if raw_event_encoding(listing, event['name']) != int(event['config'], 0):
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
        print('Preflight CPU busy %: ' + str(busy), flush=True)
        for index, job in enumerate(jobs, 1):
            name = job['name']
            raw_path, count_path = out / 'raw' / (name + '.u64'), out / 'counts' / (name + '.json')
            cmd = ['numactl', '--membind=' + str(node), str(executable), str(job['bytes']),
                   str(config['spacing']), config['mode'], str(config['samples']),
                   str(config['batch']), str(config['seed']), str(cpu), config['pages'],
                   str(raw_path), ','.join(e['config'] for e in selected_events(config, job)), str(count_path)]
            job.update(command=cmd, status='running', started_utc=now(), frequency_before=frequency(cpu))
            save(out / 'manifest.json', manifest)
            before = cpu_stat(); t0 = time.monotonic()
            log_path = out / 'logs' / (name + '.txt')
            job['launch_attempts'] = []
            job['allocation_attempts'] = []

            def record_attempt():
                job['allocation_attempts'] = [
                    dict(attempt=i, utc=entry['finished_utc'], log_file=entry['log_file'])
                    for i, entry in enumerate(job['launch_attempts'], 1)
                    if entry['premeasurement_allocation_failure']]
                save(out / 'manifest.json', manifest)

            run = launch(cmd, log_path, raw_path, count_path, args.allocation_retries,
                         job['launch_attempts'], retry_delay=retry_delay, on_attempt=record_attempt)
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
            counts = json.loads(count_path.read_text()); validate_counts(counts, config, job)
            job['statistics'] = summarize(raw, config['batch'])
            compressed = raw_path.with_suffix('.u64.gz')
            with raw_path.open('rb') as source, gzip.open(compressed, 'wb', compresslevel=6) as target:
                shutil.copyfileobj(source, target)
            raw_path.unlink()
            job.update(status='complete', finished_utc=now(), raw_file=str(compressed.relative_to(out)),
                       raw_sha256=sha(compressed), counts_file=str(count_path.relative_to(out)),
                       counts_sha256=sha(count_path), log_file=str(log_path.relative_to(out)))
            rates = {event['name']: round(actual['count'] / counts['chain_loads'] * 1000, 2)
                     for event, actual in zip(selected_events(config, job), counts['events'])}
            print(f'[{index}/{len(jobs)}] {name}: median {job["statistics"]["median"]:.4f} ticks/load; '
                  f'counts per 1000 chain loads {rates}', flush=True)
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
