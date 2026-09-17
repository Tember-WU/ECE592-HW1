#!/usr/bin/env python3
"""Serial calibration, immutable threshold checkpoint, paired PMU verification."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time

from estimator import estimate, fit, read_raw, statistics

ROOT = Path(__file__).resolve().parents[1]


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cpu_times():
    rows = {}
    for line in Path('/proc/stat').read_text().splitlines():
        a = line.split()
        if a[0].startswith('cpu') and a[0][3:].isdigit():
            v = list(map(int, a[1:]))
            rows[a[0]] = (sum(v[:8]), v[3] + v[4])
    return rows


def busy(before, after):
    return {k: 100 * (1 - (after[k][1] - before[k][1]) / (after[k][0] - before[k][0]))
            for k in before if after[k][0] > before[k][0]}


def identity():
    fields = {}
    for line in Path('/proc/cpuinfo').read_text().split('\n\n')[0].splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            if k.strip() in ['vendor_id', 'cpu family', 'model', 'model name', 'CPU implementer', 'CPU part']:
                fields[k.strip()] = v.strip()
    return fields


def run_point(folder, cfg, point, phase, threshold, pmu):
    name = point['id'] + ('_pmu' if pmu else '_software')
    raw = folder / 'raw' / (name + '.u64')
    meta = folder / 'metadata' / (name + '.json')
    exe = ROOT / 'build' / cfg['machine'] / ('verify_hit_rate' if pmu else 'hit_rate')
    command = ['numactl', f"--membind={cfg['numa_node']}", str(exe),
               str(point['bytes']), str(point.get('spacing', cfg['spacing'])),
               str(cfg['samples']), str(point['seed']), str(cfg['cpu']), str(point['reuse']),
               str(threshold), point['mode'], str(raw), str(meta)]
    if pmu:
        command += [cfg['pmu']['miss_config'], cfg['pmu']['loads_config']]
    record = {**point, 'name': name, 'phase': phase, 'pmu_enabled': pmu,
              'command': command, 'started_utc': now(), 'status': 'running'}
    before = cpu_times(); start = time.monotonic()
    with (folder / 'logs' / (name + '.txt')).open('w') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    record.update(finished_utc=now(), elapsed_seconds=time.monotonic() - start,
                  returncode=result.returncode, cpu_busy_percent=busy(before, cpu_times()))
    if result.returncode:
        record['status'] = 'failed'
        save(folder / 'metadata' / (name + '_failure.json'), record)
        raise RuntimeError(f"Measurement failed: {name}; see logs")
    x, raw_hash = read_raw(raw)
    metadata = json.loads(meta.read_text())
    if len(x) != cfg['samples'] or metadata['samples'] != cfg['samples']:
        raise RuntimeError('Incomplete sample array')
    if metadata['cpu_before'] != cfg['cpu'] or metadata['cpu_after'] != cfg['cpu']:
        raise RuntimeError('CPU placement mismatch')
    if metadata['major_faults']:
        raise RuntimeError('Major page faults during measurement')
    record['statistics'] = statistics(x)
    record['raw_sha256'] = raw_hash
    with raw.open('rb') as src, gzip.GzipFile(str(raw) + '.gz', 'wb', mtime=0, compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    raw.unlink()
    record.update(raw_file=str(Path('raw') / (name + '.u64.gz')),
                  metadata_file=str(meta.relative_to(folder)), metadata_sha256=digest(meta), status='complete')
    print(f"{phase}: {name}: {len(x):,} samples, median {record['statistics']['median']:.1f} ticks", flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--machine', default=platform.node().split('.')[0])
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    if not args.run_id.replace('-', '').replace('_', '').isalnum():
        parser.error('Use a simple alphanumeric run ID')
    path = args.config or ROOT / 'configs' / (args.machine + '.json')
    cfg = json.loads(path.read_text())
    if args.machine != cfg['machine'] or platform.node().split('.')[0] != cfg['machine']:
        raise RuntimeError('Machine/config mismatch')
    if platform.machine() != cfg['isa'] or sys.byteorder != 'little':
        raise RuntimeError('ISA mismatch or unsupported byte order')
    if cfg['samples'] < 1000000:
        raise RuntimeError('Formal measurements require at least one million samples per point')
    ident = identity()
    for key, config_key in [('vendor_id', 'vendor'), ('cpu family', 'family'), ('model', 'model')]:
        if ident.get(key) != cfg['pmu'][config_key]:
            raise RuntimeError('PMU configuration does not match CPU identity')
    folder = ROOT / 'data' / cfg['machine'] / args.run_id
    folder.mkdir(parents=True, exist_ok=False)
    for name in ['raw', 'metadata', 'logs', 'source', 'preflight']:
        (folder / name).mkdir()
    save(folder / 'config.json', cfg)
    # Save exact source and effective configuration before formal collection.
    for part in ['src', 'scripts', 'configs', 'tests']:
        shutil.copytree(ROOT / part, folder / 'source' / part,
                        ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['Makefile', 'requirements.txt']:
        shutil.copy2(ROOT / name, folder / 'source' / name)
    shutil.copytree(ROOT / 'build' / cfg['machine'], folder / 'source' / 'compiled')
    source_hashes = {str(p.relative_to(folder / 'source')): digest(p)
                     for p in (folder / 'source').rglob('*') if p.is_file()}
    save(folder / 'source' / 'sha256.json', source_hashes)
    env = {'host': platform.node(), 'isa': platform.machine(), 'kernel': platform.release(),
           'identity': ident, 'recorded_utc': now(), 'python': sys.version,
           'parent_git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'git_status_before_run': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
           'affinity': sorted(os.sched_getaffinity(0)), 'cpu': cfg['cpu'], 'numa_node': cfg['numa_node'],
           'placement': 'sched_setaffinity plus numactl --membind; prefaulted base pages',
           'sample_unit': 'one fenced target load; never a batch average'}
    topo = Path(f"/sys/devices/system/cpu/cpu{cfg['cpu']}/topology")
    env['topology'] = {name: (topo / name).read_text().strip()
                       for name in ['core_id', 'physical_package_id', 'thread_siblings_list']}
    save(folder / 'environment.json', env)
    for name, command in [('compiler.txt', ['gcc', '--version']),
                          ('topology.txt', ['lscpu', '-e=CPU,CORE,SOCKET,NODE,ONLINE'])]:
        (folder / 'preflight' / name).write_text(subprocess.check_output(command, text=True))
    # Reuse the already recorded local event descriptions; no online source is
    # an input to threshold fitting or runtime classification.
    source = (ROOT / cfg['pmu']['source']).resolve()
    shutil.copy2(source, folder / 'preflight' / 'perf-list-details.txt')
    manifest = {'machine': cfg['machine'], 'run_id': args.run_id, 'status': 'running',
                'started_utc': now(), 'jobs': []}
    save(folder / 'manifest.json', manifest)
    try:
        cal = {}
        for point in cfg['calibration']:
            record = run_point(folder, cfg, point, 'calibration', 0, False)
            manifest['jobs'].append(record)
            save(folder / 'manifest.json', manifest)
            cal[point['id']] = read_raw(folder / record['raw_file'])[0]
        model = fit(cal['hit_fit'], cal['miss_fit'])
        model.update(machine=cfg['machine'], isa=cfg['isa'], created_utc=now(),
                     calibration_inputs={j['id']: j['raw_sha256'] for j in manifest['jobs']},
                     pmu_used_for_fitting=False, source_hashes_sha256=digest(folder / 'source' / 'sha256.json'))
        model['holdout_false_negative_rate'] = 1 - estimate(cal['hit_check'], model)['software_hit_rate']
        model['holdout_false_positive_rate'] = estimate(cal['miss_check'], model)['software_hit_rate']
        model['holdout_balanced_error'] = (model['holdout_false_negative_rate'] + model['holdout_false_positive_rate']) / 2
        save(folder / 'model.json', model)
        if max(model['balanced_training_error'], model['holdout_balanced_error']) > cfg['max_balanced_calibration_error']:
            raise RuntimeError('Timing classes overlap too much; no justified fixed-threshold estimator')
        save(folder / 'threshold-checkpoint.json', {
            'created_utc': now(), 'model_sha256': digest(folder / 'model.json'),
            'note': 'Immutable run checkpoint before ANY validation PMU measurement; not a Git commit or official competition freeze'})
        threshold = model['threshold_ticks']
        print(f"Threshold checkpoint: hit <= {threshold} ticks; training/holdout error "
              f"{model['balanced_training_error']:.4%}/{model['holdout_balanced_error']:.4%}", flush=True)
        plan = []
        for rep in range(cfg['repeats']):
            order = list(cfg['validation'])
            random.Random(cfg['order_seed'] + rep).shuffle(order)
            for point in order:
                p = {**point, 'case': point['id'], 'repeat': rep,
                     'id': f"{point['id']}_r{rep + 1}", 'seed': 86000 + rep * 100 + cfg['validation'].index(point)}
                modes = [False, True] if rep % 2 == 0 else [True, False]
                plan.extend([{**p, 'pmu': flag} for flag in modes])
        save(folder / 'validation-plan.json', plan)
        control = {**cfg['calibration'][0], 'id': 'counter_overhead'}
        record = run_point(folder, cfg, control, 'counter_control', threshold, True)
        manifest['jobs'].append(record); save(folder / 'manifest.json', manifest)
        for p in plan:
            record = run_point(folder, cfg, p, 'validation', threshold, p['pmu'])
            manifest['jobs'].append(record); save(folder / 'manifest.json', manifest)
        checkpoint = json.loads((folder / 'threshold-checkpoint.json').read_text())
        if digest(folder / 'model.json') != checkpoint['model_sha256']:
            raise RuntimeError('Threshold checkpoint changed during validation')
        manifest.update(status='complete', finished_utc=now(), timed_samples=sum(j['statistics']['n'] for j in manifest['jobs']))
    except Exception as e:
        manifest.update(status='failed', finished_utc=now(), error=str(e))
        save(folder / 'manifest.json', manifest)
        raise
    save(folder / 'manifest.json', manifest)
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'analyze.py'), '--machine', cfg['machine'],
                    '--run-id', args.run_id], check=True)


if __name__ == '__main__':
    main()
