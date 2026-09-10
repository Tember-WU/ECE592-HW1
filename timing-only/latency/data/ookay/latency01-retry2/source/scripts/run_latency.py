#!/usr/bin/env python3
"""Collect a finite latency plan and preserve raw samples plus run provenance."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time

import numpy as np

from common import ROOT, FLAGS, identifier, plan, write_json, sha, decode, statistics


def read(path):
    return Path(path).read_text().strip()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def cpu_stat():
    return {a[0]: list(map(int, a[1:])) for line in read('/proc/stat').splitlines()
            if (a := line.split())[0].startswith('cpu') and a[0][3:].isdigit()}


def busy(first, last):
    result = {}
    for name in first.keys() & last.keys():
        d = [b - a for a, b in zip(first[name], last[name])]
        result[name] = round(100 * (1 - (d[3] + d[4]) / max(1, sum(d[:8]))), 3)
    return result


def frequency(cpu):
    base = Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq')
    return {n: read(base / n) for n in ('scaling_governor', 'scaling_cur_freq',
            'scaling_min_freq', 'scaling_max_freq') if (base / n).exists()}


def environment(config, binary):
    cpu = config['cpu']
    topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
    blocks = [{k.strip(): v.strip() for k, v in
               (line.split(':', 1) for line in block.splitlines() if ':' in line)}
              for block in read('/proc/cpuinfo').split('\n\n')]
    info = next(b for b in blocks if b.get('processor') == str(cpu))
    model = info.get('model name') or '; '.join(f'{k}={info[k]}' for k in
            ('CPU implementer', 'CPU architecture', 'CPU variant', 'CPU part', 'CPU revision') if k in info)
    timer = json.loads(subprocess.check_output([str(binary), '--timer-info'], text=True))
    if timer.get('observed_frequency_hz') and abs(timer['observed_frequency_hz'] / timer['timer_frequency_hz'] - 1) > .01:
        raise ValueError('Arm timer frequency calibration differs from CNTFRQ by >1%')
    return dict(machine=config['machine'], host=platform.node(), isa=platform.machine(),
                kernel=platform.release(), model=model, cpu=cpu, numa_node=config['numa_node'],
                core=read(topology / 'core_id'), package=read(topology / 'physical_package_id'),
                siblings=read(topology / 'thread_siblings_list'),
                nodes={p.parent.name: read(p) for p in Path('/sys/devices/system/node').glob('node*/cpulist')},
                inherited_affinity=sorted(os.sched_getaffinity(0)), page_size=os.sysconf('SC_PAGE_SIZE'),
                thp=read('/sys/kernel/mm/transparent_hugepage/enabled'),
                compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                flags=FLAGS, python_version=platform.python_version(), numpy_version=np.__version__,
                source_hashes={str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT / 'src').glob('*'))},
                binary_sha256=sha(binary), cpu_frequency=frequency(cpu), **timer)


def verify_log(log, config, p):
    for key, expected in [('cpu_start', config['cpu']), ('cpu_end', config['cpu']),
                          ('dependency_result_verified', 1), ('samples', p['samples'])]:
        match = re.search(r'\b' + key + r'=(\d+)', log)
        if not match or int(match[1]) != expected:
            raise ValueError(f'Missing/incorrect benchmark evidence: {key}')
    mapped = int(re.search(r'\bmapped_bytes=(\d+)', log)[1])
    huge = list(map(int, re.findall(r'AnonHugePages:\s+(\d+) kB', log)))
    if len(huge) != 2 or any(v * 1024 != (mapped if p['pages'] == 'huge' else 0) for v in huge):
        raise ValueError('Page backing differs from requested policy')
    mappings = re.findall(r'^numa_mapping:.*$', log, re.M)
    if len(mappings) != 2:
        raise ValueError('Missing before/after NUMA mapping evidence')
    for mapping in mappings:
        nodes = {int(n): int(count) for n, count in re.findall(r'\bN(\d+)=(\d+)', mapping)}
        if not nodes or any(n != config['numa_node'] and count for n, count in nodes.items()):
            raise ValueError('Mapping is not local to the requested NUMA node')
    events = {}
    for field in ('measurement_minor_faults', 'major_faults', 'voluntary_switches', 'involuntary_switches'):
        events[field] = int(re.search(r'\b' + field + r'=(\d+)', log)[1])
    return events


def collect(config, jobs, out, manifest):
    machine, cpu, node = config['machine'], config['cpu'], config['numa_node']
    write_json(out / 'config.json', config)
    source = out / 'source'
    files = [ROOT / n for n in ('Makefile', 'requirements.txt', 'README.md')]
    files += list((ROOT / 'src').glob('*')) + list((ROOT / 'scripts').glob('*.py'))
    for path in files:
        target = source / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    manifest['source_snapshot_hashes'] = {str(p.relative_to(source)): sha(p) for p in source.rglob('*') if p.is_file()}
    build = ['make', '-B', f'MACHINE={machine}', 'CC=gcc', f'CFLAGS={FLAGS}', 'all']
    with (out / 'build.log').open('w') as f:
        subprocess.run(build, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True)
    binary = out / 'latency_bench.bin'
    shutil.copy2(ROOT / 'build' / machine / 'latency_bench', binary)
    shutil.copyfile(ROOT / 'build' / machine / 'latency_bench.dis', out / 'disassembly.txt')
    env = environment(config, binary)
    env.update(build_command=build, git_head=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        git_status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        memory_policy=f'numactl --membind={node}; first touch after CPU binding')
    write_json(out / 'environment.json', env)
    manifest['environment_sha256'] = sha(out / 'environment.json')
    (out / 'commands.txt').write_text(f'Build directory: {ROOT}\n{shlex.join(build)}\n')
    for index, job in enumerate(jobs, 1):
        p, name = job['parameters'], job['name']
        raw_path = out / 'raw' / (name + '.u64')
        cmd = ['numactl', f'--membind={node}', str(binary)] + list(map(str,
            (p['bytes'], p['spacing'], p['mode'], p['samples'], p['batch'], p['seed'], cpu, p['pages'], raw_path)))
        with (out / 'commands.txt').open('a') as f:
            f.write(shlex.join(cmd) + '\n')
        job.update(status='running', command=cmd)
        write_json(out / 'manifest.json', manifest)
        print(f'[{index}/{len(jobs)}] {name}: {p["mode"]}, W={p["bytes"]}, batch={p["batch"]}', flush=True)
        before, frequency_before, started = cpu_stat(), frequency(cpu), utc()
        clock = time.monotonic()
        process = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.monotonic() - clock
        after, frequency_after = cpu_stat(), frequency(cpu)
        (out / 'logs' / (name + '.txt')).write_text(process.stderr)
        if process.returncode:
            raise RuntimeError(f'{name}: {process.stderr}')
        events = verify_log(process.stderr, config, p)
        payload = raw_path.read_bytes()
        raw = decode(payload, p)
        stats = statistics(raw, p)
        with gzip.open(str(raw_path) + '.gz', 'wb', compresslevel=6) as f:
            f.write(payload)
        raw_path.unlink()
        record = dict(name=name, group=job['group'], machine=machine, parameters=p,
                      columns=job['columns'], raw_format='little-endian uint64, row-major interleaved columns',
                      raw_file=f'raw/{name}.u64.gz', raw_sha256=hashlib.sha256(payload).hexdigest(),
                      stats=stats, start_utc=started, elapsed_seconds=elapsed, command=cmd,
                      cpu_busy_percent=busy(before, after), cpu_frequency_before=frequency_before,
                      cpu_frequency_after=frequency_after, runtime_events=events)
        write_json(out / 'logs' / (name + '.json'), record)
        job.update(status='complete', raw_sha256=record['raw_sha256'])
        write_json(out / 'manifest.json', manifest)
        message = f'  first median={stats["first"]["median"]:.5f}'
        if 'reread' in stats:
            message += f'; reread={stats["reread"]["median"]:.5f}'
        print(message + f'; {elapsed:.1f}s', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--config', type=Path)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--groups', nargs='+', default=['all'])
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    machine, run_id = identifier(args.machine), identifier(args.run_id)
    config = json.loads((args.config or ROOT / 'configs' / (machine + '.json')).read_text())
    if config['machine'] != machine:
        raise ValueError('Machine ID differs from configuration')
    jobs = plan(config, args.groups)
    out = ROOT / 'data' / machine / run_id
    if out.exists() or (ROOT / 'results' / machine / run_id).exists():
        raise FileExistsError('Run ID already exists; use a new ID, never overwrite a run')
    print(f'{len(jobs)} configurations, {sum(j["parameters"]["samples"] for j in jobs):,} batches, '
          f'{sum(j["parameters"]["samples"] * len(j["columns"]) for j in jobs):,} recorded timer intervals', flush=True)
    if args.dry_run:
        for j in jobs:
            print(j['name'], j['parameters'])
        return
    if platform.system() != 'Linux' or platform.machine() != config['isa']:
        raise ValueError('Actual operating system/ISA differs from configuration')
    if platform.node().split('.')[0].lower() != config['hostname'].split('.')[0].lower():
        raise ValueError('Actual hostname differs from configuration')
    inherited = os.sched_getaffinity(0)
    try:
        os.sched_setaffinity(0, {config['cpu']})
    finally:
        os.sched_setaffinity(0, inherited)
    if not Path(f'/sys/devices/system/cpu/cpu{config["cpu"]}/node{config["numa_node"]}').exists():
        raise ValueError('Configured CPU does not belong to configured NUMA node')
    if not shutil.which('numactl'):
        raise RuntimeError('numactl is required for explicit local memory placement')
    out.mkdir(parents=True)
    (out / 'raw').mkdir(); (out / 'logs').mkdir()
    before = cpu_stat()
    time.sleep(1)
    write_json(out / 'preflight.json', dict(recorded_utc=utc(), cpu_busy_percent=busy(before, cpu_stat()),
                                         cpu_frequency=frequency(config['cpu'])))
    manifest = dict(machine=machine, experiment='latency', run_id=run_id, phase='timing-only',
                    started_utc=utc(), status='running', command=sys.argv, jobs=jobs)
    try:
        collect(config, jobs, out, manifest)
    except BaseException as error:
        manifest.update(status='failed', error=str(error))
        for job in jobs:
            if job.get('status') == 'running':
                job['status'] = 'failed'
        raise
    else:
        manifest['status'] = 'complete'
    finally:
        manifest['finished_utc'] = utc()
        write_json(out / 'manifest.json', manifest)


if __name__ == '__main__':
    main()
