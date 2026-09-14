"""Small shared helpers for capacity collection and analysis."""
import hashlib
import json
from pathlib import Path
import random
import re
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Invalid machine or run ID')
    return value


def expand_event_passes(config, jobs):
    """Repeat each unchanged workload for explicitly partitioned event groups."""
    passes = config.get('event_passes')
    if passes is None:
        return jobs
    if not passes or len({p['name'] for p in passes}) != len(passes):
        raise ValueError('Event passes must be nonempty and uniquely named')
    indices = []
    for p in passes:
        identifier(p['name'])
        if not p['event_indices'] or any(type(i) is not int for i in p['event_indices']):
            raise ValueError('Each event pass needs integer event indices')
        indices.extend(p['event_indices'])
    if sorted(indices) != list(range(len(config['events']))):
        raise ValueError('Event passes must partition the configured events exactly once')
    return [dict(job, name=job['name'] + '__' + p['name'], point_name=job['name'],
                 pmu_pass=p['name'], event_indices=p['event_indices'].copy())
            for job in jobs for p in passes]


def selected_events(config, job=None):
    return [config['events'][i] for i in (job or {}).get('event_indices', range(len(config['events'])))]


def plan(config):
    identifier(config['machine'])
    if config['isa'] != 'x86_64':
        raise ValueError('This PMU capacity implementation currently supports Linux x86-64')
    for key in ('cpu', 'numa_node', 'samples', 'batch', 'spacing', 'seed'):
        if type(config[key]) is not int or config[key] < 0:
            raise ValueError(f'Invalid {key}')
    if config['cpu'] >= 1024 or config['samples'] < 1000000:
        raise ValueError('Invalid CPU or fewer than one million batches')
    if (not config['batch'] or config['batch'] % 16 or config['spacing'] < 8 or
            config['spacing'] % 8 or not config['seed'] or config['pages'] not in ('huge', 'base') or
            config['mode'] not in ('random', 'sequential')):
        raise ValueError('Invalid access parameters')
    if len(config['events']) != 4 or len({e['name'] for e in config['events']}) != 4:
        raise ValueError('Exactly four distinct event definitions required')
    for e in config['events']:
        if not re.fullmatch(r'[a-zA-Z0-9_.]+', e['name']) or not 0 < int(e['config'], 0) < 65536:
            raise ValueError('This runner supports simple raw event/umask pairs only')
    jobs = []
    for region, sizes in config['regions'].items():
        identifier(region)
        for size in sizes:
            if type(size) is not int or size < config['spacing'] * 2 or size % config['spacing']:
                raise ValueError('Invalid working-set size')
            jobs.append(dict(name=f'{region}_w{size}', region=region, bytes=size))
    if not jobs or len({j['bytes'] for j in jobs}) != len(jobs):
        raise ValueError('Empty or duplicate working sets')
    random.Random(config['order_seed']).shuffle(jobs)
    return expand_event_passes(config, jobs)


def summarize(raw, batch):
    x = raw.astype(np.float64) / batch
    p05, q1, median, q3, p95, p99 = np.percentile(x, [5, 25, 50, 75, 95, 99])
    low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    inside = x[(x >= low) & (x <= high)]
    return dict(n=len(x), mean=float(x.mean()), std=float(x.std(ddof=1)),
                median=float(median), q1=float(q1), q3=float(q3), p05=float(p05),
                p95=float(p95), p99=float(p99), minimum=float(x.min()), maximum=float(x.max()),
                outliers=int(np.count_nonzero((x < low) | (x > high))),
                whisker_low=float(inside.min()), whisker_high=float(inside.max()),
                decile_medians=[float(np.median(a)) for a in np.array_split(x, 10)])


def validate_counts(counts, config, job=None):
    if counts['chain_loads'] != config['samples'] * config['batch']:
        raise ValueError('Wrong PMU normalization denominator')
    if not counts['time_running_ns'] or counts['time_enabled_ns'] != counts['time_running_ns']:
        raise ValueError('Unscheduled or multiplexed counter group')
    events = selected_events(config, job)
    if len(counts['events']) != len(events):
        raise ValueError('Wrong PMU event count')
    for actual, requested in zip(counts['events'], events):
        if actual['config'] != int(requested['config'], 0) or type(actual['count']) is not int or actual['count'] < 0:
            raise ValueError('Wrong PMU event encoding or invalid count')


def cpu_stat():
    return {v[0]: list(map(int, v[1:9])) for line in Path('/proc/stat').read_text().splitlines()
            if (v := line.split())[0].startswith('cpu') and v[0][3:].isdigit()}


def activity(before, after, cpus):
    result = {}
    for cpu in cpus:
        d = [b - a for a, b in zip(before[f'cpu{cpu}'], after[f'cpu{cpu}'])]
        result[str(cpu)] = 100 * (sum(d) - d[3] - d[4]) / sum(d) if sum(d) else 0
    return result


def frequency(cpu):
    p = Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq')
    return {n: (p / n).read_text().strip() for n in
            ('scaling_governor', 'scaling_cur_freq', 'scaling_min_freq', 'scaling_max_freq')
            if (p / n).exists()}
