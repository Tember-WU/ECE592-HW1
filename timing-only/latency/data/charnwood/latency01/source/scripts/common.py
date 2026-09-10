"""Configuration and raw-data conventions shared by collection and analysis."""
import gzip
import hashlib
import json
from pathlib import Path
import random
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FLAGS = '-O0 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer'
DEFAULTS = dict(samples=1000000, batch=256, spacing=64, seed=59221, pages='huge')
GROUPS = ('calibration', 'l1_hit', 'l2_hit', 'llc_hit', 'l1_miss', 'l2_miss', 'llc_miss')
MODES = ('empty', 'chase', 'sequential', 'independent', 'paired')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', value):
        raise ValueError(f'Invalid identifier: {value!r}')
    return value


def plan(config, groups=None):
    identifier(config['machine'])
    if config['isa'] not in ('x86_64', 'aarch64'):
        raise ValueError('Supported ISA values: x86_64, aarch64')
    for field in ('cpu', 'numa_node'):
        if type(config[field]) is not int or config[field] < 0:
            raise ValueError(f'{field} must be a nonnegative integer')
    if config['cpu'] >= 1024:
        raise ValueError('CPU must fit CPU_SETSIZE=1024')
    if set(config['groups']) != set(GROUPS):
        raise ValueError(f'Configuration must define exactly these groups: {GROUPS}')
    defaults = dict(DEFAULTS, **config.get('defaults', {}))
    if defaults.keys() != DEFAULTS.keys():
        raise ValueError('Unknown default parameter')
    selected = list(GROUPS) if not groups or groups == ['all'] else groups
    if len(set(selected)) != len(selected) or set(selected) - set(GROUPS):
        raise ValueError('Unknown or duplicate group selection')
    jobs, names = [], set()
    for group in selected:
        for point in config['groups'][group]:
            p = dict(defaults, **{k: v for k, v in point.items() if k != 'id'})
            name = group + '__' + identifier(point['id'])
            if name in names or p.keys() != DEFAULTS.keys() | {'bytes', 'mode'}:
                raise ValueError(f'Duplicate ID or unknown/missing fields: {name}')
            for key in ('bytes', 'spacing', 'batch', 'samples', 'seed'):
                if type(p[key]) is not int or not 0 < p[key] < 2**63:
                    raise ValueError(f'{name}: {key} must be a positive integer below 2**63')
            if p['samples'] < 1000000:
                raise ValueError('Every formal configuration requires >=1,000,000 samples')
            if (p['spacing'] < 8 or p['spacing'] % 8 or p['bytes'] % p['spacing'] or
                    p['bytes'] // p['spacing'] < 16 or p['batch'] % 16 or
                    p['mode'] not in MODES or p['pages'] not in ('huge', 'base')):
                raise ValueError(f'Invalid geometry/mode: {name}')
            if p['samples'] * p['batch'] >= 2**64:
                raise ValueError('Total access count overflows uint64')
            if p['mode'] == 'paired' and p['bytes'] // p['spacing'] < 4 * p['batch']:
                raise ValueError('Paired mode requires at least four distinct batches per cycle')
            if p['mode'] == 'independent' and (p['bytes'] // p['spacing']) % 4:
                raise ValueError('Four-stream diagnostic needs four equal cycle segments')
            if (group.endswith('_miss') and p['mode'] != 'paired') or (
                    group.endswith('_hit') and p['mode'] != 'chase'):
                raise ValueError('Hit groups use chase; miss groups use paired')
            columns = ['first', 'reread'] if p['mode'] == 'paired' else ['first']
            jobs.append(dict(name=name, group=group, parameters=p, columns=columns))
            names.add(name)
    if not jobs:
        raise ValueError('No measurement points selected')
    random.Random(config['order_seed']).shuffle(jobs)
    return jobs


def summarize(x):
    x = np.asarray(x, dtype=np.float64)
    p05, q1, median, q3, p95, p99 = np.percentile(x, [5, 25, 50, 75, 95, 99])
    iqr = q3 - q1
    inside = x[(x >= q1 - 1.5 * iqr) & (x <= q3 + 1.5 * iqr)]
    return dict(n=len(x), mean=float(x.mean()), std=float(x.std(ddof=1)),
                median=float(median), q1=float(q1), q3=float(q3), p05=float(p05),
                p95=float(p95), p99=float(p99), minimum=float(x.min()), maximum=float(x.max()),
                whisker_low=float(inside.min()), whisker_high=float(inside.max()),
                outliers=int(len(x) - len(inside)),
                decile_medians=[float(np.median(a)) for a in np.array_split(x, 10)])


def decode(payload, parameters):
    columns = 2 if parameters['mode'] == 'paired' else 1
    if len(payload) != parameters['samples'] * columns * 8:
        raise ValueError('Raw byte count does not match samples and columns')
    raw = np.frombuffer(payload, dtype='<u8').reshape(-1, columns)
    if parameters['mode'] != 'empty' and not np.all(raw > 0):
        raise ValueError('Nonpositive timed access interval')
    return raw


def statistics(raw, parameters):
    divisor = 1 if parameters['mode'] == 'empty' else parameters['batch']
    x = raw.astype(np.float64) / divisor
    result = {'first': summarize(x[:, 0])}
    if parameters['mode'] == 'paired':
        result['reread'] = summarize(x[:, 1])
        # Signed paired differences; retain negative differences and all outliers.
        result['first_minus_reread'] = summarize(x[:, 0] - x[:, 1])
        result['first_slower_fraction'] = float(np.mean(x[:, 0] > x[:, 1]))
    return result


def load_record(path):
    path = Path(path)
    record = json.loads(path.read_text())
    payload = gzip.decompress((path.parent.parent / record['raw_file']).read_bytes())
    if hashlib.sha256(payload).hexdigest() != record['raw_sha256']:
        raise ValueError(f'Raw checksum mismatch: {path}')
    raw = decode(payload, record['parameters'])
    record['stats'] = statistics(raw, record['parameters'])
    return record
