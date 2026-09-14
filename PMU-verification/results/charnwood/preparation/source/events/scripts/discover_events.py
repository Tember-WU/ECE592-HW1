#!/usr/bin/env python3
"""Archive the local perf event descriptions and probe selected user events."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import platform
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SELECTED = [
    'mem_load_retired.l1_hit', 'mem_load_retired.l1_miss',
    'mem_load_retired.l2_hit', 'mem_load_retired.l2_miss',
    'mem_load_retired.l3_hit', 'mem_load_retired.l3_miss',
    'mem_load_retired.fb_hit', 'mem_inst_retired.all_loads',
    'l1d.replacement', 'l2_rqsts.all_demand_data_rd',
    'l2_rqsts.demand_data_rd_miss', 'l2_rqsts.references',
    'l2_rqsts.miss', 'dtlb_load_misses.walk_completed',
    'cache-references', 'cache-misses',
]
GROUP = ['mem_load_retired.l1_miss', 'mem_load_retired.l2_miss',
         'mem_load_retired.l3_miss', 'mem_inst_retired.all_loads']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--cpu', type=int, required=True)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    for value in (args.machine, args.run_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise ValueError('Invalid machine or run ID')
    if platform.node().split('.')[0] != args.machine:
        raise ValueError('Hostname mismatch')
    out = ROOT / 'data' / args.machine / args.run_id
    result = ROOT / 'results' / args.machine / args.run_id
    if out.exists() or result.exists():
        raise FileExistsError('Choose a new run ID')
    out.mkdir(parents=True)
    result.mkdir(parents=True)
    meta = dict(hostname=platform.node(), isa=platform.machine(), kernel=platform.release(),
                cpu=args.cpu, collected_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                perf_version=subprocess.check_output(['perf', '--version'], text=True).strip(),
                perf_event_paranoid=Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip())
    cpuinfo = Path('/proc/cpuinfo').read_text()
    meta['processor_identification'] = [line for line in cpuinfo.split('\n\n')[0].splitlines()
                                      if line.split(':')[0].strip() in
                                      ('vendor_id', 'cpu family', 'model', 'model name', 'stepping')]
    (out / 'environment.json').write_text(json.dumps(meta, indent=2) + '\n')
    for name, cmd in [('perf-list.txt', ['perf', 'list']),
                      ('perf-list-details.txt', ['perf', 'list', '--details'])]:
        with (out / name).open('w') as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True)
    details = (out / 'perf-list-details.txt').read_text()
    # Local perf descriptions are the source: do not infer aliases across PMUs.
    blocks = {}
    current, section = None, ''
    for line in details.splitlines():
        if re.fullmatch(r'\S.*:', line):
            section, current = line[:-1], None
        elif re.fullmatch(r'  [a-zA-Z0-9_.-]+', line):
            current = line.strip()
            blocks[current] = dict(section=section, lines=[])
        elif current and line.strip():
            blocks[current]['lines'].append(line.strip())
    rows = []
    for name, block in blocks.items():
        if block['section'] not in ('cache', 'virtual memory'):
            continue
        content = ' '.join(block['lines'])
        desc = re.search(r'\[(.*?)\]', content)
        encoding = re.search(r'(?:cpu|default_core)/[^ ]+/', content)
        rows.append(dict(event=name, category=block['section'],
                         description=desc.group(1) if desc else content,
                         encoding=encoding.group(0) if encoding else '',
                         availability='listed; not individually tested'))
    probes = []
    for name in SELECTED + ['capacity_group']:
        spec = '{' + ','.join(x + ':u' for x in GROUP) + '}' if name == 'capacity_group' else name + ':u'
        cmd = ['perf', 'stat', '--no-big-num', '-x,', '-e', spec,
               '--', 'taskset', '-c', str(args.cpu), '/usr/bin/true']
        run = subprocess.run(cmd, text=True, capture_output=True)
        (out / (name + '.txt')).write_text(run.stderr + run.stdout)
        ok = run.returncode == 0 and not any(s in run.stderr.lower() for s in
             ('<not supported>', '<not counted>', 'permission', 'no permission', 'error:'))
        probe = dict(event=name, command=cmd, returncode=run.returncode,
                     status='counted in user mode' if ok else 'failed; see raw log')
        probes.append(probe)
        existing = next((r for r in rows if r['event'] == name), None)
        if existing:
            existing['availability'] = probe['status']
        elif name != 'capacity_group':
            rows.append(dict(event=name, category='generic', encoding='',
                             description='Generic Linux hardware alias; do not assume a specific cache level.',
                             availability=probe['status']))
    (out / 'probes.json').write_text(json.dumps(probes, indent=2) + '\n')
    with (result / 'events.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    text = [f'# {args.machine.capitalize()} cache-event inventory', '',
            'Descriptions and encodings come from this host\'s archived `perf list --details`.',
            'A listed event is not necessarily usable. Selected probes count a short `/usr/bin/true` process;',
            'they test access/scheduling, not cache behavior. Formal capacity measurements are separate.', '',
            '| Event | Local meaning | Probe result |', '|---|---|---|']
    for name in SELECTED:
        r = next(r for r in rows if r['event'] == name)
        text.append(f"| `{name}` | {r['description'].replace('|', '/')} | {r['availability']} |")
    text += ['', 'The capacity run groups the three `mem_load_retired.*_miss` events with',
             '`mem_inst_retired.all_loads`, all user mode and per thread. The group probe result is: **' + probes[-1]['status'] + '**.',
             'Raw encodings are specific to this CPU and must be rediscovered on other machines.', '',
             'Miss counts are normalized per known pointer-chase load. The counters also see user-space',
             'loop/timer-helper loads within the measured loop. `all_loads` documents that overhead;',
             'it is not identical to the number of pointer-chase loads. Do not interpret an L3 miss as',
             'proof of local DRAM service, or a generic `cache-misses` count as an L1 miss count.', '',
             'See `events.csv` for all parsed cache/virtual-memory events, including unprobed ones.',
             'The complete unfiltered listings and individual probe commands/output are under the matching `data/` run.', '']
    (result / 'EVENTS.md').write_text('\n'.join(text))
    print(f'Archived {len(rows)} cache/virtual-memory entries; {sum(p["status"] == "counted in user mode" for p in probes)}/{len(probes)} probes passed.')
    if probes[-1]['status'] != 'counted in user mode':
        raise RuntimeError('Capacity group unavailable; inspect saved error before collecting')


if __name__ == '__main__':
    main()
