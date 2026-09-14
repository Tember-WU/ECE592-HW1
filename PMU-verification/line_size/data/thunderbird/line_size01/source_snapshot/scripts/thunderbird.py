#!/usr/bin/env python3
"""Additive Thunderbird workflow; the Artemisia programs remain untouched.

Usage: thunderbird.py discover|check|run|analyze [--experiment ...] [--run-id ...]
Run capacity, line_size, associativity serially. Formal runs require 1M batches.
"""
import argparse
import copy
import csv
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'capacity/scripts'))
from common import activity, cpu_stat, frequency, save, sha, summarize
sys.path.insert(0, str(ROOT / 'common'))
from run_verification import worker_command, denominators
from analyze_verification import baseline as cpp_baseline

EXPERIMENTS = ('capacity', 'line_size', 'associativity')
UNITS = 'CNTVCT_EL0 ticks / timed chain load'
NUMACTL = ROOT.parent / 'timing-only/capacity/build/thunderbird/deps/usr/bin/numactl'
os.environ['PATH'] = str(NUMACTL.parent) + os.pathsep + os.environ['PATH']


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def config(experiment):
    return json.loads((ROOT / experiment / 'configs/thunderbird.json').read_text())


def plan(c):
    if c['machine'] != 'thunderbird' or c['isa'] != 'aarch64' or c['samples'] < 1000000:
        raise ValueError('Thunderbird AArch64 and >=1M samples required')
    if len(c['events']) != 4 or len({int(e['config'], 0) for e in c['events']}) != 4:
        raise ValueError('Four distinct raw events required')
    for e in c['events']:
        if not re.fullmatch(r'[a-z0-9_]+', e['name']) or not 0 < int(e['config'], 0) < 65536:
            raise ValueError('Invalid event')
    if c['experiment'] == 'capacity':
        points = [dict(name=f'{g}_w{b}', group=g, bytes=b) for g, sizes in c['regions'].items() for b in sizes]
        if c['batch'] % 16 or c['spacing'] % 8 or c['spacing'] < 8:
            raise ValueError('Invalid capacity layout')
        if any(p['bytes'] % c['spacing'] or p['bytes'] < c['spacing'] * 2 for p in points):
            raise ValueError('Invalid footprint')
    else:
        points = copy.deepcopy(c['points'])
        for p in points:
            if c['experiment'] == 'line_size':
                if p['stride'] < 8 or p['stride'] % 8 or p['alignment'] % 8:
                    raise ValueError('Unaligned pointer layout')
            elif not 1 <= p['k'] <= p['max_k'] or c['line_size'] % 8:
                raise ValueError('Invalid conflict chain')
    if not points or len({p['name'] for p in points}) != len(points):
        raise ValueError('Empty/duplicate points')
    random.Random(c['order_seed']).shuffle(points)
    return points


def divisor(c, p):
    return (c['batch'], c['samples'] * c['batch']) if c['experiment'] == 'capacity' else denominators(c, p)


def validate_counts(counts, c, p):
    if counts['chain_loads'] != divisor(c, p)[1]:
        raise ValueError('Wrong chain-load denominator')
    if not counts['time_enabled_ns'] or counts['time_enabled_ns'] != counts['time_running_ns']:
        raise ValueError('Unscheduled/multiplexed group')
    if len(counts['events']) != 4:
        raise ValueError('Wrong event count')
    for actual, expected in zip(counts['events'], c['events']):
        if actual['config'] != int(expected['config'], 0) or type(actual['count']) is not int or actual['count'] < 0:
            raise ValueError('Wrong encoding/count')


def baseline(c, p):
    if c['experiment'] != 'capacity':
        return cpp_baseline(c, p)
    path = ROOT.parent / 'timing-only/capacity/results/thunderbird/combined12/summary.csv'
    with path.open() as f:
        matches = [r for r in csv.DictReader(f) if int(r['bytes']) == p['bytes'] and
                   all(int(r[k]) == c[k] for k in ('samples', 'batch', 'spacing', 'seed')) and
                   all(r[k] == c[k] for k in ('mode', 'pages'))]
    if len(matches) != 1:
        raise ValueError('No unique identical Phase-I point: ' + p['name'])
    return float(matches[0]['median'])


def verify_encodings(c, out):
    # This installed perf segfaults with several positional event filters.
    # Full inventory works; validate each selected event in that inventory.
    run = subprocess.run(['perf', 'list', '--details'], capture_output=True, text=True, check=True)
    (out / 'selected-events.txt').write_text(run.stdout)
    (out / 'selected-events.stderr.txt').write_text(run.stderr)
    for e in c['events']:
        block = re.search(r'^  ' + re.escape(e['name']) + r'\n(.*?)(?=^  \S|\Z)', run.stdout, re.M | re.S)
        raw = re.search(r'armv8_pmuv3_0/event=(0x[0-9a-f]+)/', block[1]) if block else None
        if not raw or int(raw[1], 16) != int(e['config'], 0):
            raise ValueError('Local ARM encoding mismatch: ' + e['name'])


def build(experiment):
    folder = ROOT / experiment / 'build/thunderbird'
    folder.mkdir(parents=True, exist_ok=True)
    exe = folder / (experiment + '_pmu')
    src = ROOT / experiment / 'src' / ('cache_bench_aarch64.c' if experiment == 'capacity' else experiment + '_bench.cpp')
    cmd = ['gcc' if experiment == 'capacity' else 'g++', '-O0', '-g',
           '-std=c11' if experiment == 'capacity' else '-std=c++11', '-Wall', '-Wextra', '-Werror',
           '-fno-omit-frame-pointer', str(src), '-o', str(exe)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    (folder / 'build.log').write_text(run.stdout + run.stderr)
    save(folder / 'build-command.json', cmd)
    run.check_returncode()
    with exe.with_suffix('.dis').open('w') as f:
        subprocess.run(['objdump', '-d', str(exe)], stdout=f, check=True)
    return exe


def command(c, p, data, exe):
    if c['experiment'] != 'capacity':
        return worker_command(c, p, data, exe)
    return ['taskset', '-c', str(c['cpu']), 'numactl', '--membind=' + str(c['numa_node']), str(exe),
            str(p['bytes']), str(c['spacing']), c['mode'], str(c['samples']), str(c['batch']),
            str(c['seed']), str(c['cpu']), c['pages'], str(data / 'raw' / (p['name'] + '.u64')),
            ','.join(e['config'] for e in c['events']), str(data / 'counts' / (p['name'] + '.json'))]


def directories(data):
    for sub in ('raw', 'counts', 'logs', 'legacy'):
        (data / sub).mkdir(parents=True)


def discover():
    out = ROOT / 'events/data/thunderbird/discovery01'
    out.mkdir(parents=True, exist_ok=True)
    c = config('capacity')
    verify_encodings(c, out)
    devices = {}
    for p in sorted(Path('/sys/bus/event_source/devices').iterdir()):
        devices[p.name] = {str(f.relative_to(p)): f.read_text().strip() for f in p.glob('**/*')
                           if f.is_file() and (f.parent.name in ('events', 'format') or f.name in ('type', 'cpumask'))}
    save(out / 'all-pmu-devices.json', devices)
    probes = []
    # Explicit core PMU avoids ambiguous core/DSU aliases and regrouping.
    for cpu in (32, 4):
        event_group = '{' + ','.join('armv8_pmuv3_0/event=' + e['config'] + '/u' for e in c['events']) + '}'
        cmd = ['perf', 'stat', '--no-big-num', '-x,', '-e', event_group, '--', 'taskset', '-c', str(cpu), '/usr/bin/true']
        r = subprocess.run(cmd, capture_output=True, text=True)
        probes.append(dict(cpu=cpu, command=cmd, returncode=r.returncode, stdout=r.stdout, stderr=r.stderr))
        if r.returncode or '<not ' in r.stderr or 'regrouped' in r.stderr:
            save(out / 'probes.json', probes)
            raise RuntimeError('Event group probe failed')
    save(out / 'probes.json', probes)
    hardware = dict(recorded_utc=now(), hostname=platform.node(), isa=platform.machine(),
                    kernel=platform.release(), page_size=os.sysconf('SC_PAGE_SIZE'),
                    perf_event_paranoid=Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip(), caches={})
    for cpu in (4, 32):
        hardware['caches'][str(cpu)] = [{f.name:f.read_text().strip() for f in p.iterdir()
             if f.name in ('level', 'type', 'size', 'ways_of_associativity', 'number_of_sets', 'coherency_line_size', 'shared_cpu_list', 'id')}
             for p in sorted(Path(f'/sys/devices/system/cpu/cpu{cpu}/cache').glob('index*'))]
    save(out / 'hardware.json', hardware)
    print('ARM events discovered and four-event groups probed on CPUs 32 and 4.', flush=True)


def check():
    out = ROOT / 'preflight/thunderbird/smoke01'
    if out.exists():
        raise FileExistsError(out)
    out.mkdir()
    checks = []
    for experiment in EXPERIMENTS:
        c = config(experiment)
        points = plan(c)
        for p in points:
            if baseline(c, p) is None:
                raise ValueError('Missing frozen Phase-I baseline')
        bad = copy.deepcopy(c); bad['samples'] = 999999
        try:
            plan(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Insufficient samples accepted')
        exe = build(experiment)
        d = out / experiment; directories(d)
        verify_encodings(c, d)
        p = points[0]; c['samples'] = 1000
        cmd = command(c, p, d, exe)
        run = subprocess.run(cmd, capture_output=True, text=True)
        (d / 'worker.log').write_text(run.stdout + run.stderr)
        save(d / 'command.json', cmd)
        run.check_returncode()
        raw = np.fromfile(d / 'raw' / (p['name'] + '.u64'), dtype='<u8')
        assert len(raw) == 1000 and np.all(raw > 0)
        counts = json.loads((d / 'counts' / (p['name'] + '.json')).read_text())
        validate_counts(counts, c, p)
        for key in ('time_running_ns', 'chain_loads'):
            bad = copy.deepcopy(counts); bad[key] -= 1
            try:
                validate_counts(bad, c, p)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid counter scope accepted')
        checks.append(dict(experiment=experiment, formal_points=len(points), smoke_samples=len(raw),
                           group_fully_scheduled=True, phase1_matches=True, invalid_scope_rejected=True))
        print(experiment + ': native kernel and counter validation passed', flush=True)
    save(out / 'validation.json', checks)


def snapshot(data, experiment, exe):
    snap = data / 'source_snapshot'
    paths = list((ROOT / experiment / 'src').glob('*')) + list((ROOT / 'common').glob('*.hpp'))
    paths += [Path(__file__), ROOT / 'capacity/scripts/common.py', ROOT / 'common/run_verification.py', ROOT / 'common/analyze_verification.py']
    for p in paths:
        target = snap / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    shutil.copytree(exe.parent, data / 'build_snapshot')
    save(data / 'provenance.json', dict(source_sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},
         binary_sha256=sha(exe), phase1_freeze_sha256=sha(ROOT / 'preflight/thunderbird/phase1_freeze.json')))


def run(experiment, run_id):
    c = config(experiment); jobs = plan(c)
    for p in jobs:
        p['baseline_median'] = baseline(c, p)
    data = ROOT / experiment / 'data/thunderbird' / run_id
    if data.exists() or (ROOT / experiment / 'results/thunderbird' / run_id).exists():
        raise FileExistsError('Choose a new run ID')
    if not Path(f'/sys/devices/system/cpu/cpu{c["cpu"]}/node{c["numa_node"]}').exists():
        raise ValueError('CPU/NUMA mismatch')
    directories(data)
    save(data / 'config.json', c)
    m = dict(machine='thunderbird', experiment=experiment, run_id=run_id, status='running',
             started_utc=now(), jobs=jobs, command=sys.argv)
    start = time.monotonic()
    try:
        exe = build(experiment); snapshot(data, experiment, exe)
        verify_encodings(c, data)
        timer_exe = ROOT / 'capacity/build/thunderbird/capacity_pmu'
        timer = json.loads(subprocess.check_output([str(timer_exe), '--timer-info'], text=True))
        topology = Path(f'/sys/devices/system/cpu/cpu{c["cpu"]}/topology')
        siblings = []
        for part in (topology / 'thread_siblings_list').read_text().strip().split(','):
            ends = list(map(int, part.split('-'))); siblings.extend(range(ends[0], ends[-1] + 1))
        pre = cpu_stat(); time.sleep(1)
        env = dict(hostname=platform.node(), isa=platform.machine(), kernel=platform.release(),
                   cpu=c['cpu'], numa_node=c['numa_node'], siblings=siblings,
                   preflight_busy_percent=activity(pre, cpu_stat(), siblings), frequency=frequency(c['cpu']),
                   timer_unit=UNITS, timer=timer, placement_note=c['placement_note'],
                   compiler=subprocess.check_output(['gcc', '--version'], text=True).splitlines()[0],
                   perf_version=subprocess.check_output(['perf', '--version'], text=True).strip(),
                   counting_scope='User mode, calling thread, entire sample loop; includes helper/stack loads and associativity preparation loads.')
        save(data / 'environment.json', env)
        print(experiment + ' preflight: ' + str(env['preflight_busy_percent']), flush=True)
        for i, p in enumerate(jobs, 1):
            cmd = command(c, p, data, exe)
            p.update(status='running', started_utc=now(), command=cmd)
            save(data / 'manifest.json', m)
            pre = cpu_stat(); t0 = time.monotonic()
            log_path = data / 'logs' / (p['name'] + '.txt')
            with log_path.open('w') as f:
                worker = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
            p.update(returncode=worker.returncode, elapsed_seconds=time.monotonic()-t0,
                     cpu_busy_percent=activity(pre, cpu_stat(), siblings))
            worker.check_returncode()
            log = log_path.read_text()
            if f'cpu_end={c["cpu"]}' not in log:
                raise ValueError('Worker CPU mismatch')
            # Capacity also logs initial THP detection; use the two measurement snapshots.
            maps = re.findall(r'numa_mapping: (.*)', log)[-2:]
            if len(maps) != 2 or any(set(re.findall(r'\bN(\d+)=', x)) != {str(c['numa_node'])} for x in maps):
                raise ValueError('Worker NUMA mismatch')
            p['anon_huge_kib_before_after'] = list(map(int, re.findall(r'AnonHugePages:\s+(\d+)', log)))[-2:]
            if len(p['anon_huge_kib_before_after']) != 2 or len(set(p['anon_huge_kib_before_after'])) != 1:
                raise ValueError('Huge-page backing changed')
            p['measurement_events'] = {k:int(v) for k,v in re.findall(r'(minor_faults|major_faults|voluntary_switches|involuntary_switches)=(\d+)', log)}
            raw_path = data / 'raw' / (p['name'] + '.u64')
            raw = np.fromfile(raw_path, dtype='<u8')
            if raw_path.stat().st_size != c['samples']*8 or len(raw) != c['samples'] or not np.all(raw > 0):
                raise ValueError('Invalid timing array')
            count_path = data / 'counts' / (p['name'] + '.json')
            counts = json.loads(count_path.read_text()); validate_counts(counts, c, p)
            p['statistics'] = summarize(raw, divisor(c, p)[0])
            compressed = raw_path.with_suffix('.u64.gz')
            with raw_path.open('rb') as src, gzip.open(compressed, 'wb', compresslevel=6) as dest:
                shutil.copyfileobj(src, dest)
            raw_path.unlink()
            p.update(status='complete', finished_utc=now(), raw_file=str(compressed.relative_to(data)),
                     raw_sha256=sha(compressed), counts_file=str(count_path.relative_to(data)), counts_sha256=sha(count_path))
            rates = [round(e['count']*1000/counts['chain_loads'], 2) for e in counts['events'][:3]]
            print(f'[{i}/{len(jobs)}] {p["name"]}: {p["statistics"]["median"]:.6f} ticks/load; L1 refill, L2 refill, LL miss / 1000 = {rates}', flush=True)
        m['status'] = 'complete'
    except BaseException as error:
        m.update(status='failed', error=str(error))
        raise
    finally:
        m.update(finished_utc=now(), elapsed_seconds=time.monotonic()-start)
        save(data / 'manifest.json', m)


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys); writer.writeheader(); writer.writerows(rows)


def analyze(experiment, run_id):
    data = ROOT / experiment / 'data/thunderbird' / run_id
    out = ROOT / experiment / 'results/thunderbird' / run_id
    c = json.loads((data / 'config.json').read_text()); m = json.loads((data / 'manifest.json').read_text())
    env = json.loads((data / 'environment.json').read_text())
    expected = plan(c)
    assert m['status'] == 'complete' and len(expected) == len(m['jobs'])
    for want, actual in zip(expected, m['jobs']):
        assert all(actual[k] == v for k,v in want.items()) and actual['status'] == 'complete'
    figs = out / 'figures'; figs.mkdir(parents=True, exist_ok=True)
    rows, events, temporal = [], [], []
    for p in m['jobs']:
        rp, cp = data / p['raw_file'], data / p['counts_file']
        assert sha(rp) == p['raw_sha256'] and sha(cp) == p['counts_sha256']
        with gzip.open(rp, 'rb') as f: payload = f.read()
        raw = np.frombuffer(payload, dtype='<u8')
        assert len(payload) == c['samples']*8 and np.all(raw > 0)
        stats = summarize(raw, divisor(c, p)[0]); assert stats == p['statistics']
        counts = json.loads(cp.read_text()); validate_counts(counts, c, p)
        assert p['baseline_median'] == baseline(c, p)
        row = {k:v for k,v in p.items() if k in ('name', 'group', 'bytes', 'stride', 'alignment', 'mode', 'seed', 'num_sets', 'k', 'max_k')}
        row.update({k:v for k,v in stats.items() if k != 'decile_medians'})
        row.update(units=UNITS, baseline_median=p['baseline_median'],
                   median_ns=stats['median']*env['timer']['timer_tick_ns'],
                   baseline_median_ns=p['baseline_median']*env['timer']['timer_tick_ns'],
                   timed_loads_per_batch=divisor(c,p)[0], counted_chain_loads=counts['chain_loads'],
                   **p['measurement_events'])
        for e,a in zip(c['events'], counts['events']):
            rate = a['count']*1000/counts['chain_loads']
            row[e['name']+'_per_1000_chain_loads'] = rate
            events.append(dict(name=p['name'], event=e['name'], raw_config=e['config'], count=a['count'],
                 chain_loads=counts['chain_loads'], per_1000_chain_loads=rate,
                 time_enabled_ns=counts['time_enabled_ns'], time_running_ns=counts['time_running_ns']))
        rows.append(row)
        temporal.extend(dict(name=p['name'], block=i+1, median=x, units=UNITS) for i,x in enumerate(stats['decile_medians']))
    write_csv(out / 'summary.csv', rows); write_csv(out / 'pmu_counts.csv', events)
    write_csv(out / 'temporal_medians.csv', temporal)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':9, 'pdf.fonttype':42})
    if experiment == 'capacity':
        groups = [(g, sorted([r for r in rows if r['group']==g], key=lambda r:r['bytes']), 'bytes', 1024 if g=='L1' else 1024**2) for g in c['regions']]
    elif experiment == 'associativity':
        groups = [(g, sorted([r for r in rows if r['group']==g], key=lambda r:r['k']), 'k', 1) for g in ('L1','L2_candidate')]
    else:
        groups = [(g, sorted([r for r in rows if r['group']==g], key=lambda r:r['stride']), 'stride', 1) for g in ('random_alignment0','random_alignment16','sequential_control','fully_random_control')]
    fig, axes = plt.subplots(2,len(groups),figsize=(5*len(groups),8),squeeze=False,layout='constrained')
    boxfig, boxaxes = plt.subplots(1,len(groups),figsize=(5*len(groups),4.5),squeeze=False,layout='constrained')
    for col,(group,rs,key,scale) in enumerate(groups):
        x = [r[key]/scale for r in rs]
        xlabel = ('Working set (KiB)' if scale==1024 else 'Working set (MiB)') if key=='bytes' else ('K (addresses)' if key=='k' else 'Stride (B)')
        title = group
        if experiment=='associativity': title += f' ({rs[0]["num_sets"]*c["line_size"]//1024} KiB spacing)'
        ax=axes[0,col]
        ax.plot(x,[r['baseline_median_ns'] for r in rs],'s-',color='0.5',label='Frozen Phase I')
        ax.plot(x,[r['median_ns'] for r in rs],'o-',label='With PMU')
        ax.fill_between(x,[r['p05']*env['timer']['timer_tick_ns'] for r in rs],[r['p95']*env['timer']['timer_tick_ns'] for r in rs],alpha=.15,label='PMU P05–P95')
        ax.set(title=title,ylabel='ns / timed chain load',xlabel=xlabel); ax.legend(fontsize=8)
        for e in c['events'][:3]:
            label = 'LL_CACHE_MISS_RD (0x37)' if e['name'] == 'll_cache_miss_rd' else e['label']
            axes[1,col].plot(x,[r[e['name']+'_per_1000_chain_loads'] for r in rs],'o-',label=label)
        axes[1,col].set(ylabel='Events / 1,000 counted chain loads',xlabel=xlabel)
        axes[1,col].set_ylim(bottom=0); axes[1,col].legend(fontsize=8)
        boxes=[dict(med=r['median'],q1=r['q1'],q3=r['q3'],whislo=r['whisker_low'],whishi=r['whisker_high'],fliers=[],label=f'{v:g}') for r,v in zip(rs,x)]
        boxaxes[0,col].bxp(boxes,showfliers=False)
        boxaxes[0,col].set(title=title,ylabel=UNITS,xlabel=xlabel)
    fig.suptitle('Thunderbird '+experiment+': identical Phase-I workloads, four simultaneous user PMU events')
    boxfig.suptitle('Thunderbird distributions: Tukey whiskers; outliers retained in raw data')
    for name,f in [(experiment+'_pmu_validation',fig),('latency_boxplots',boxfig)]:
        for ext in ('png','pdf'): f.savefig(figs/(name+'.'+ext),dpi=180)
        plt.close(f)
    quality = dict(preflight_busy_percent=env['preflight_busy_percent'],
        sibling_cpus=[cpu for cpu in env['siblings'] if cpu != c['cpu']],
        max_sibling_busy_percent=max((v for p in m['jobs'] for cpu,v in p['cpu_busy_percent'].items() if int(cpu)!=c['cpu']),default=None),
        faults_and_switches={k:sum(p['measurement_events'][k] for p in m['jobs']) for k in ('minor_faults','major_faults','voluntary_switches','involuntary_switches')},
        temporal_max_min={p['name']:max(p['statistics']['decile_medians'])/min(p['statistics']['decile_medians']) for p in m['jobs']},
        huge_kib={p['name']:p['anon_huge_kib_before_after'] for p in m['jobs']},
        caveat=c['placement_note']+' Counts include helper traffic; refill/speculation semantics differ from retired-load misses.')
    save(out/'quality.json',quality)
    save(out/'validation.json',dict(status='passed',configurations=len(rows),timed_batches=sum(r['n'] for r in rows),
         raw_hashes_lengths_statistics_verified=True,baseline_matches_verified=True,actual_load_denominators_verified=True,
         all_pmu_groups_without_multiplexing=True,timer_unit=UNITS,timer_frequency_hz=env['timer']['timer_frequency_hz']))
    print(f'{experiment}: validated {len(rows)} points / {sum(r["n"] for r in rows):,} samples',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('discover','check','run','analyze'))
    ap.add_argument('--experiment',choices=EXPERIMENTS)
    ap.add_argument('--run-id',default='verification01')
    args=ap.parse_args()
    if platform.node().split('.')[0]!='thunderbird' or platform.machine()!='aarch64':
        raise ValueError('This additive entry point is for Thunderbird AArch64')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',args.run_id): raise ValueError('Invalid run ID')
    if args.action in ('run','analyze'):
        if not args.experiment: ap.error('--experiment is required')
        globals()[args.action](args.experiment,args.run_id)
    else:
        globals()[args.action]()


if __name__=='__main__':
    main()
