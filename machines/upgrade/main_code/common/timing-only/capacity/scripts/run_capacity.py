#!/usr/bin/env python3
"""Run capacity sweeps from a machine config; preserve every timed sample."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shlex
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BUILD_FLAGS = '-O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer'
DEFAULTS = dict(samples=1000000, batch=256, spacing=64, seed=59201,
                pages='huge', mode='random')
SOURCE_FILES = ('src/cache_bench.c', 'src/cache_bench_aarch64.c', 'Makefile', 'scripts/run_capacity.py',
                'scripts/analyze_capacity.py', 'scripts/plan_capacity.py', 'requirements.txt')


def load_config(path):
    """Machine settings may reference the shared first-round protocol."""
    path = Path(path).resolve()
    config = json.loads(path.read_text())
    if isinstance(config['capacity'], str):
        protocol = (path.parent / config['capacity']).resolve()
        config['capacity'] = json.loads(protocol.read_text())
    return config


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', value):
        raise ValueError(f'Invalid machine, sweep, or run ID: {value!r}')
    return value


def plan(config, sweeps):
    """Resolve and validate every point before building or collecting anything."""
    identifier(config['machine'])
    for key in ('cpu', 'numa_node'):
        if type(config[key]) is not int or config[key] < 0:
            raise ValueError(f'{key} must be a nonnegative integer')
    if config['cpu'] >= 1024:
        raise ValueError('cpu must fit the benchmark CPU_SETSIZE (1024)')
    if config['isa'] not in ('x86_64', 'aarch64'):
        raise ValueError('The capacity benchmark supports x86_64 and aarch64 only')
    capacity = config['capacity']
    defaults = dict(DEFAULTS, **capacity.get('defaults', {}))
    if defaults.keys() != DEFAULTS.keys():
        raise ValueError('Unknown capacity default setting')
    available = capacity['sweeps']
    selected = list(available) if sweeps == ['all'] else sweeps
    jobs, names = [], set()
    for suite in selected:
        identifier(suite)
        if suite not in available:
            raise ValueError(f'Unknown sweep {suite!r}; choose from {list(available)}')
        sweep = available[suite]
        points = sweep['points'].copy()
        random.Random(sweep['order_seed']).shuffle(points)
        for point in points:
            p = dict(defaults, **point)
            if p.keys() != DEFAULTS.keys() | {'bytes'}:
                raise ValueError(f'Missing bytes or unknown point setting: {point}')
            for key in ('bytes', 'spacing', 'samples', 'batch', 'seed'):
                if type(p[key]) is not int or not 0 < p[key] < 2**63:
                    raise ValueError(f'{key} must be a positive integer below 2**63')
            if p['samples'] < 1000000:
                raise ValueError('Assignment requires >= 1,000,000 timed batches per point')
            if (p['spacing'] < 8 or p['spacing'] % 8 or p['bytes'] % p['spacing'] or
                    p['bytes'] // p['spacing'] < 2 or p['batch'] % 16):
                raise ValueError(f'Invalid footprint, spacing, or batch: {p}')
            if p['pages'] not in ('huge', 'base') or p['mode'] not in ('random', 'sequential', 'empty'):
                raise ValueError(f'Invalid pages or traversal mode: {p}')
            name = (f"{suite}_w{p['bytes']}_s{p['spacing']}_{p['mode']}"
                    f"_b{p['batch']}_seed{p['seed']}_{p['pages']}_n{p['samples']}")
            if name in names:
                raise ValueError(f'Duplicate point: {name}; use distinct seeds or run IDs')
            names.add(name)
            jobs.append(dict(name=name, suite=suite, parameters=p))
    if not jobs:
        raise ValueError('No points selected')
    return jobs


def read(path):
    return Path(path).read_text().strip()


def frequency_state(cpu):
    base = Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq')
    return {name: read(base / name) for name in
            ('scaling_governor', 'scaling_cur_freq', 'scaling_min_freq', 'scaling_max_freq')
            if (base / name).exists()}


def valid_intervals(raw, parameters):
    # A short empty control can legitimately fit within one generic-timer tick.
    return len(raw) == parameters['samples'] and (
        parameters['mode'] == 'empty' or np.all(raw > 0))


def cpu_stat():
    return {a[0]: list(map(int, a[1:])) for line in read('/proc/stat').splitlines()
            if (a := line.split())[0].startswith('cpu') and a[0][3:].isdigit()}


def check_affinity(cpu):
    """An inherited affinity mask is not the cgroup's CPU permission limit."""
    inherited = os.sched_getaffinity(0)
    try:
        os.sched_setaffinity(0, {cpu})
    except OSError as error:
        raise ValueError(f'Cannot bind to CPU {cpu}: {error}') from error
    else:
        os.sched_setaffinity(0, inherited)


def environment(cpu, machine):
    topology = Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
    cpuinfo = [dict(line.split(':', 1) for line in block.splitlines() if ':' in line)
               for block in read('/proc/cpuinfo').split('\n\n')]
    cpuinfo = [{k.strip(): v.strip() for k, v in block.items()} for block in cpuinfo]
    selected = next(block for block in cpuinfo if block.get('processor') == str(cpu))
    model = selected.get('model name') or '; '.join(
        f'{key}={selected[key]}' for key in
        ('CPU implementer', 'CPU architecture', 'CPU variant', 'CPU part', 'CPU revision')
        if key in selected)
    isa = platform.machine()
    source_file = 'src/cache_bench_aarch64.c' if isa == 'aarch64' else 'src/cache_bench.c'
    timer = ('DSB ISH/ISB/CNTVCT_EL0/ISB ... DSB ISHLD/ISB/CNTVCT_EL0/ISB; generic timer ticks/access'
             if isa == 'aarch64' else 'LFENCE/RDTSC/LFENCE ... RDTSCP/LFENCE; TSC ticks/access')
    timer_info = {}
    if isa == 'aarch64':
        timer_info = json.loads(subprocess.check_output(
            [str(ROOT / 'build' / machine / 'cache_capacity'), '--timer-info'], text=True))
        if abs(timer_info['observed_frequency_hz'] / timer_info['timer_frequency_hz'] - 1) > .01:
            raise ValueError('Generic timer frequency disagrees with CLOCK_MONOTONIC_RAW by >1%')
    return dict(host=platform.node(), model=model, kernel=platform.release(), isa=isa,
                cpu=cpu, core=read(topology / 'core_id'),
                package=read(topology / 'physical_package_id'),
                siblings=read(topology / 'thread_siblings_list'),
                nodes={p.parent.name: read(p) for p in Path('/sys/devices/system/node').glob('node*/cpulist')},
                inherited_affinity=sorted(os.sched_getaffinity(0)), page_size=os.sysconf('SC_PAGE_SIZE'),
                thp=read('/sys/kernel/mm/transparent_hugepage/enabled'),
                compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                flags=BUILD_FLAGS, timer=timer, timer_unit='CNTVCT ticks' if isa == 'aarch64' else 'TSC ticks',
                source_file=source_file, cpu_frequency=frequency_state(cpu),
                thp_pmd_size=int(read('/sys/kernel/mm/transparent_hugepage/hpage_pmd_size')),
                python_version=platform.python_version(), numpy_version=np.__version__,
                **timer_info,
                source_sha256=hashlib.sha256((ROOT / source_file).read_bytes()).hexdigest(),
                binary_sha256=hashlib.sha256((ROOT / 'build' / machine / 'cache_capacity').read_bytes()).hexdigest(),
                git_head=subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                        capture_output=True, text=True).stdout.strip() or None)


def summarize(raw, divisor):
    x = raw.astype(np.float64) / divisor
    p05, q1, median, q3, p95, p99 = np.percentile(x, [5, 25, 50, 75, 95, 99])
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = x[(x >= low) & (x <= high)]
    return dict(n=len(x), mean=float(x.mean()), std=float(x.std(ddof=1)),
                p05=p05, q1=q1, median=median, q3=q3, p95=p95, p99=p99,
                minimum=float(x.min()), maximum=float(x.max()),
                whisker_low=float(inside.min()), whisker_high=float(inside.max()),
                outliers=int(np.count_nonzero((x < low) | (x > high))),
                decile_medians=[float(np.median(a)) for a in np.array_split(x, 10)])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--config', type=Path, help='Default: configs/<machine>.json')
    ap.add_argument('--sweep', nargs='+', default=['coarse'], help='Sweep names, or all')
    ap.add_argument('--run-id', required=True, help='A new ID; existing run directories are never reused')
    ap.add_argument('--dry-run', action='store_true', help='Validate and show the plan without building or measuring')
    args = ap.parse_args()
    machine, run_id = identifier(args.machine), identifier(args.run_id)
    config_path = (args.config or ROOT / 'configs' / f'{machine}.json').resolve()
    config = load_config(config_path)
    if config['machine'] != machine:
        raise ValueError('--machine must match the machine ID in the configuration')
    jobs = plan(config, args.sweep)
    out = ROOT / 'data' / machine / run_id
    processed = ROOT / 'results' / machine / run_id
    print(f'Machine: {machine}; CPU: {config["cpu"]}; NUMA node: {config["numa_node"]}')
    print(f'{len(jobs)} points; {sum(j["parameters"]["samples"] for j in jobs):,} timed batches; '
          f'{sum(j["parameters"]["samples"] * 8 for j in jobs):,} raw bytes before compression')
    print(f'Raw data: {out}\nAnalysis output: {processed}', flush=True)
    if out.exists() or processed.exists():
        raise FileExistsError(f'Run ID {run_id!r} already exists; choose a new ID')
    if args.dry_run:
        return
    if platform.system() != 'Linux' or platform.machine() != config['isa']:
        raise ValueError(f'Run this benchmark on Linux {config["isa"]}')
    if platform.node().split('.')[0].lower() != config['hostname'].split('.')[0].lower():
        raise ValueError('Actual hostname does not match the machine config')
    cpu, node = config['cpu'], config['numa_node']
    check_affinity(cpu)
    if not Path(f'/sys/devices/system/cpu/cpu{cpu}/node{node}').exists():
        raise ValueError(f'CPU {cpu} is not on requested NUMA node {node}')
    if shutil.which('numactl') is None:
        raise RuntimeError('numactl is required to bind memory')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'raw').mkdir()
    (out / 'logs').mkdir()
    manifest = dict(machine=machine, experiment='capacity', run_id=run_id, phase='timing-only',
                    started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), status='running',
                    command=sys.argv, config_file=str(config_path), jobs=jobs)
    try:
        collect(config, jobs, out, manifest)
    except BaseException as error:
        manifest.update(status='failed', error=str(error))
        for job in jobs:
            if job.get('status') == 'running':
                job.update(status='failed', error=str(error))
        raise
    else:
        manifest['status'] = 'complete'
    finally:
        manifest['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def collect(config, jobs, out, manifest):
    machine, cpu, node = config['machine'], config['cpu'], config['numa_node']
    (out / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    source = out / 'source'
    source.mkdir()
    for filename in SOURCE_FILES:
        target = source / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / filename, target)
    build_cmd = ['make', '-B', f'MACHINE={machine}', 'CC=gcc', f'CFLAGS={BUILD_FLAGS}', 'capacity', 'assembly']
    with (out / 'build.log').open('w') as log:
        subprocess.run(build_cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    shutil.copyfile(ROOT / 'build' / machine / 'cache_capacity.dis', out / 'disassembly.txt')
    binary = out / 'cache_capacity.bin'
    shutil.copy2(ROOT / 'build' / machine / 'cache_capacity', binary)
    env = environment(cpu, machine)
    env.update(machine=machine, numa_node=node, build_command=build_cmd,
               memory_policy=f'numactl --membind={node}; first touch after CPU binding',
               variables={k: v for k, v in os.environ.items()
                          if k in ('PATH', 'LD_LIBRARY_PATH', 'LD_PRELOAD', 'OMP_NUM_THREADS',
                                   'CC', 'CFLAGS', 'CPPFLAGS', 'LDFLAGS', 'MAKEFLAGS') or k.startswith('SLURM_')})
    (out / 'environment.json').write_text(json.dumps(env, indent=2) + '\n')
    (out / 'commands.txt').write_text(f'Build working directory: {ROOT}\n{shlex.join(build_cmd)}\n')
    for index, job in enumerate(jobs, 1):
        p, name = job['parameters'], job['name']
        result_path = out / 'logs' / f'{name}.json'
        raw_path = out / 'raw' / f'{name}.u64'
        cmd = ['numactl', f'--membind={node}', str(binary)] + [str(v) for v in
                (p['bytes'], p['spacing'], p['mode'], p['samples'], p['batch'],
                 p['seed'], cpu, p['pages'], raw_path)]
        with (out / 'commands.txt').open('a') as commands:
            commands.write(shlex.join(cmd) + '\n')
        job.update(status='running', command=cmd)
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        before = cpu_stat()
        frequency_before = frequency_state(cpu)
        start = time.monotonic()
        utc = dt.datetime.now(dt.timezone.utc).isoformat()
        print(f'[{index}/{len(jobs)}] running {name}', flush=True)
        process = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.monotonic() - start
        after = cpu_stat()
        frequency_after = frequency_state(cpu)
        (out / 'logs' / f'{name}.txt').write_text(process.stderr)
        if process.returncode:
            raise RuntimeError(process.stderr)
        raw = np.fromfile(raw_path, dtype='<u8')
        if not valid_intervals(raw, p):
            raise RuntimeError('Bad raw sample count or nonpositive timer interval')
        stats = summarize(raw, 1 if p['mode'] == 'empty' else p['batch'])
        busy = {}
        for cpu_name, first in before.items():
            delta = [b - a for a, b in zip(first, after[cpu_name])]
            busy[cpu_name] = round(100 * (1 - (delta[3] + delta[4]) / max(1, sum(delta[:8]))), 3)
        # Compression and all output I/O occur AFTER the timed experiment.
        payload = raw_path.read_bytes()
        with gzip.open(str(raw_path) + '.gz', 'wb', compresslevel=6) as f:
            f.write(payload)
        raw_path.unlink()
        result = dict(name=name, suite=job['suite'], machine=machine, parameters=p, command=cmd,
                      start_utc=utc, elapsed_seconds=elapsed, environment=env,
                      cpu_busy_percent=busy, stats=stats, log=process.stderr,
                      cpu_frequency_before=frequency_before, cpu_frequency_after=frequency_after,
                      raw_file=f'raw/{name}.u64.gz',
                      raw_sha256=hashlib.sha256(payload).hexdigest())
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        job['status'] = 'complete'
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(f"  median={stats['median']:.4f}, p05–p95={stats['p05']:.4f}–{stats['p95']:.4f}, "
              f"elapsed={elapsed:.1f}s; saved all {len(raw):,} samples", flush=True)


if __name__ == '__main__':
    main()
