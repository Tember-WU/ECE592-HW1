#!/usr/bin/env python3
"""Archive AMD event descriptions and test permissions without changing policy."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import platform
import re
import subprocess

from support import PMU, frozen_check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', default='discovery01')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_id) or platform.node().split('.')[0] != 'skylark':
        raise ValueError('Run ID or host mismatch')
    frozen_check()
    data = PMU / 'events/data/skylark' / args.run_id
    result = PMU / 'events/results/skylark' / args.run_id
    if data.exists() or result.exists():
        raise FileExistsError('Choose a fresh discovery run ID')
    data.mkdir(parents=True); result.mkdir(parents=True)
    events = json.loads((PMU / 'skylark/events.json').read_text())
    for filename, cmd in [('perf-list.txt', ['perf', 'list']),
                          ('perf-list-details.txt', ['perf', 'list', '--details'])]:
        p = subprocess.run(cmd, capture_output=True, text=True)
        (data / filename).write_text(p.stdout)
        (data / (filename + '.stderr')).write_text(p.stderr)
        p.check_returncode()
    details = (data / 'perf-list-details.txt').read_text()
    for e in events:
        block = re.search(r'^  ' + re.escape(e['name']) + r'\n(.*?)(?=^  \S|\Z)', details, re.M | re.S)
        encoding = re.search(r'cpu/event=(0x[0-9a-f]+),umask=(0x[0-9a-f]+)', block[1]) if block else None
        if not encoding or (int(encoding[1], 16) | int(encoding[2], 16) << 8) != int(e['config'], 0):
            raise ValueError('Local event definition mismatch: ' + e['name'])
    selected = [e['name'] for e in events] + [
        'ls_refills_from_sys.ls_mabresp_lcl_l2', 'ls_refills_from_sys.ls_mabresp_lcl_cache',
        'ls_refills_from_sys.ls_mabresp_rmt_dram', 'ls_l1_d_tlb_miss.all',
        'ls_dc_accesses', 'l3_comb_clstr_state.request_miss',
        'l3_lookup_state.all_l3_req_typs', 'mem_load_retired.l1_miss']
    probes = []
    commands = [(name, ['perf', 'stat', '--no-big-num', '-x,', '-e', name + ':u',
                         '--', 'taskset', '-c', '32', '/usr/bin/true']) for name in selected]
    spec = '{' + ','.join(e['name'] + ':u' for e in events) + '}'
    commands += [('user_core_group', ['perf', 'stat', '--no-big-num', '-x,', '-e', spec,
                                    '--', 'taskset', '-c', '32', '/usr/bin/true']),
                 ('l3_system_user', ['perf', 'stat', '--no-big-num', '-x,', '-a', '-C', '32',
                                     '-e', 'amd_l3/event=0x6,umask=0x1/u', '--', '/usr/bin/true']),
                 ('l3_system_all_modes', ['perf', 'stat', '--no-big-num', '-x,', '-a', '-C', '32',
                                          '-e', 'amd_l3/event=0x6,umask=0x1/uk', '--', '/usr/bin/true'])]
    for name, cmd in commands:
        p = subprocess.run(cmd, capture_output=True, text=True)
        log = p.stderr + p.stdout
        (data / (name + '.txt')).write_text(log)
        ok = p.returncode == 0 and not any(word in log.lower() for word in
                  ('<not supported>', '<not counted>', 'permission', 'error:'))
        probes.append(dict(name=name, command=cmd, returncode=p.returncode,
                           usable=ok, counting_scope='Availability probe only; not a formal experiment'))
    (data / 'probes.json').write_text(json.dumps(probes, indent=2) + '\n')
    meta = dict(host=platform.node(), isa=platform.machine(), kernel=platform.release(),
                collected_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                perf_version=subprocess.check_output(['perf', '--version'], text=True).strip(),
                perf_event_paranoid=Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip(),
                cpu=32, host_security_settings_changed=False,
                tracefs_warning='perf list stderr includes inaccessible tracepoint listings; core hardware listings/probes are independently saved.')
    (data / 'environment.json').write_text(json.dumps(meta, indent=2) + '\n')
    rows = []
    for match in re.finditer(r'^  ([a-zA-Z0-9_.]+)\n(.*?)(?=^  \S|^\S|\Z)', details, re.M | re.S):
        name, block = match.groups()
        if not any(term in block.lower() for term in ('cache', 'tlb', 'mab', 'load', 'dram')):
            continue
        probe = next((p for p in probes if p['name'] == name), None)
        desc = re.search(r'\[(.*?)\]', block, re.S)
        encoding = re.search(r'(?:cpu|amd_l3)/[^\n]+/', block)
        rows.append(dict(event=name, description=' '.join((desc[1] if desc else block).split()),
                         encoding=encoding[0] if encoding else '',
                         usable=str(probe['usable']) if probe else 'listed; not individually probed'))
    with (result / 'events.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=['event', 'description', 'encoding', 'usable'])
        writer.writeheader(); writer.writerows(rows)
    lines = ['# Skylark AMD PMU discovery', '',
             'The event definitions below were verified against the saved local `perf list --details`.',
             'All four core events run together per thread in user mode. A short probe establishes access, not cache semantics.', '',
             '| Event | Raw config | Interpretation |', '|---|---|---|']
    lines += [f"| `{e['name']}` | `{e['config']}` | {e['meaning']} |" for e in events]
    lines += ['', 'The third core event is **local DRAM/IO demand fills**, not a direct L3 miss event.',
              'Direct L3 events belong to the shared `amd_l3` PMU. The separate user-only and all-mode probes preserve their errors; they are not silently replaced by Intel events.',
              'Intel `mem_load_retired.l1_miss` was also probed to document nonportability.', '',
              '| Probe | Usable |', '|---|---|']
    lines += [f"| `{p['name']}` | {p['usable']} |" for p in probes]
    lines += ['', 'No host settings were changed. Full listings, exact commands, and errors are retained in the matching data directory.', '']
    (result / 'EVENTS.md').write_text('\n'.join(lines))
    if not next(p['usable'] for p in probes if p['name'] == 'user_core_group'):
        raise RuntimeError('Required four-event core group is unavailable')
    print(f'Archived {len(rows)} relevant local events; required AMD group available.')


if __name__ == '__main__':
    main()
