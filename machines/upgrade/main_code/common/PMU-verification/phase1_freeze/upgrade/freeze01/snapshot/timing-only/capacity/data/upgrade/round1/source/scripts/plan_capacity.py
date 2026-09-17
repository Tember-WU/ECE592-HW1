#!/usr/bin/env python3
"""Create a bounded round-2/3 config from manually selected, newly measured intervals."""
import argparse
import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from analyze_capacity import family, load_study
from run_capacity import ROOT, identifier, load_config, plan


def byte_size(text):
    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(B|KiB|MiB|GiB)?', text, re.IGNORECASE)
    if not match:
        raise argparse.ArgumentTypeError('Use bytes or binary units, e.g. 48KiB or 2.0625MiB')
    scale = {'b': 1, 'kib': 1024, 'mib': 1024**2, 'gib': 1024**3}
    value = Decimal(match[1]) * scale[(match[2] or 'B').lower()]
    if value <= 0 or value != int(value):
        raise argparse.ArgumentTypeError('Working-set size must be a positive whole number of bytes')
    return int(value)


def interval(text):
    parts = text.split(':')
    if len(parts) != 2:
        raise argparse.ArgumentTypeError('Use LOWER:UPPER, e.g. 32KiB:64KiB')
    lo, hi = map(byte_size, parts)
    if lo >= hi:
        raise argparse.ArgumentTypeError('The interval must have LOWER < UPPER')
    return lo, hi


def grid(lo, hi, count, spacing):
    if lo % spacing or hi % spacing:
        raise ValueError('Interval endpoints must be multiples of the primary node spacing')
    values = sorted({lo + ((hi - lo) * i // (count - 1) // spacing) * spacing for i in range(count)})
    if len(values) < 3:
        raise ValueError('Interval is too narrow for three distinct aligned measurements')
    return values


def make_plan(config, records, round_number, intervals, extensions=()):
    """Expand observed intervals; never guess capacities or consult machine specifications."""
    if round_number not in (2, 3):
        raise ValueError('Only round 2 or optional round 3 is supported')
    if round_number == 2 and not {'l1', 'l2'} <= intervals.keys():
        raise ValueError('Round 2 needs the observed --l1 and --l2 intervals')
    if not intervals and not extensions:
        raise ValueError('Select at least one unresolved interval or extension point')
    defaults = config['capacity']['defaults']
    primary = (defaults['spacing'], defaults['batch'], defaults['pages'])
    measured = {d['parameters']['bytes'] for d in records
                if family(d) == primary and d['parameters']['mode'] == 'random'}
    if not measured:
        raise ValueError('No random measurements match the source config primary layout')
    previous = None
    for level in ('l1', 'l2', 'llc'):
        if level not in intervals:
            continue
        lo, hi = intervals[level]
        if lo >= hi or lo not in measured or hi not in measured:
            raise ValueError(f'{level}: both ordered interval endpoints must be measured primary random points')
        if previous is not None and lo < previous:
            raise ValueError('Selected L1, L2, and LLC intervals must be ordered without overlap')
        previous = hi

    seed = max(d['parameters']['seed'] for d in records) + 1
    spacing = defaults['spacing']
    compact = 8 if spacing != 8 else 32
    points = []
    seen = set()

    def add(w, **changes):
        p = dict(bytes=w, seed=seed)
        p.update(changes)
        resolved = dict(defaults, **p)
        key = tuple(sorted(resolved.items()))
        if key not in seen:
            seen.add(key)
            points.append(p)

    for level, (lo, hi) in intervals.items():
        sizes = grid(lo, hi, 9 if round_number == 2 and level != 'llc' else 5, spacing)
        anchors = [sizes[0], sizes[len(sizes) // 2], sizes[-1]]
        for w in sizes:
            add(w)
        if round_number == 2 and level == 'llc':
            # A finite layout/page check; no search for a precise physical LLC size.
            for w in sizes:
                add(w, spacing=compact)
            for w in anchors:
                add(w, spacing=compact, seed=seed + 1)
                add(w, mode='sequential')
                if defaults['pages'] == 'huge':
                    add(w, pages='base')
        else:
            for w in anchors:
                add(w, seed=seed + 1)
                add(w, mode='sequential')
                if round_number == 2:
                    add(w, spacing=compact)
            if round_number == 2:
                add(lo, batch=defaults['batch'] * 4)
    for w in extensions:
        if w <= max(measured):
            raise ValueError('--extend must exceed the largest measured primary random footprint')
        add(w)
        add(w, mode='sequential')

    result = copy.deepcopy(config)
    result['capacity'] = dict(defaults=copy.deepcopy(defaults), sweeps={
        f'round{round_number}': dict(order_seed=592 + round_number, points=points)})
    result['planning'] = dict(round=round_number, intervals_bytes=intervals,
                              extension_bytes=list(extensions),
                              interpretation='Intervals select measurements, not final capacity estimates.')
    plan(result, ['all'])
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--from-runs', nargs='+', required=True, help='Completed new runs providing the timing evidence')
    ap.add_argument('--round', type=int, choices=(2, 3), required=True)
    for level in ('l1', 'l2', 'llc'):
        ap.add_argument(f'--{level}', type=interval, help='Measured primary random endpoints, LOWER:UPPER')
    ap.add_argument('--extend', nargs='+', type=byte_size, default=[], help='Extra larger footprints if the coarse range was insufficient')
    ap.add_argument('--note', default='', help='Why these intervals were selected from the new curves')
    ap.add_argument('--output', type=Path, required=True, help='New self-contained config file; never overwritten')
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(f'{args.output} already exists; choose a new config filename')
    machine = identifier(args.machine)
    run_ids = [identifier(r) for r in args.from_runs]
    configs, sources, manifests = [], [], []
    for run_id in run_ids:
        data = ROOT / 'data' / machine / run_id
        manifest = json.loads((data / 'manifest.json').read_text())
        if manifest.get('status') != 'complete':
            raise ValueError(f'{run_id} is incomplete; inspect its failure before planning a follow-up round')
        config = load_config(data / 'config.json')
        if config['machine'] != machine:
            raise ValueError('Source configuration belongs to another machine')
        configs.append(config)
        manifests.append(manifest)
        sources.append(dict(run_id=run_id, config_sha256=hashlib.sha256((data / 'config.json').read_bytes()).hexdigest(),
                            manifest_sha256=hashlib.sha256((data / 'manifest.json').read_bytes()).hexdigest()))
    stages = [c.get('planning', {}).get('round', 1) for c in configs]
    if max(stages) != args.round - 1:
        raise ValueError('Round 2 must follow new round 1; round 3 must include new round 2')
    records = load_study(ROOT, machine, run_ids)
    for run_id, manifest in zip(run_ids, manifests):
        jobs = manifest['jobs']
        names = {d['name'] for d in records if d['run_id'] == run_id}
        if any(j.get('status') != 'complete' for j in jobs) or names != {j['name'] for j in jobs}:
            raise ValueError(f'{run_id}: completed manifest jobs do not match the saved records')
    intervals = {level: getattr(args, level) for level in ('l1', 'l2', 'llc') if getattr(args, level)}
    latest = configs[stages.index(max(stages))]
    config = make_plan(latest, records, args.round, intervals, args.extend)
    config['planning'].update(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                              note=args.note, source_runs=sources,
                              planner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              evidence=[dict(record_id=d['record_id'], raw_sha256=d['raw_sha256']) for d in records])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        f.write(json.dumps(config, indent=2) + '\n')
    jobs = plan(config, ['all'])
    print(f'Wrote {args.output}: {len(jobs)} points, {sum(j["parameters"]["samples"] for j in jobs):,} timed batches.')
    print('Review this configuration, then collect its single sweep with --sweep all and a new run ID.')


if __name__ == '__main__':
    main()
