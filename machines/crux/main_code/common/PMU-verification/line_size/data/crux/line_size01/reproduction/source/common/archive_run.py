#!/usr/bin/env python3
"""Archive the retained source/build state after a completed PMU run."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--experiment', choices=['capacity', 'line_size', 'associativity'], required=True)
    ap.add_argument('--machine', required=True)
    ap.add_argument('--run-id', required=True)
    args = ap.parse_args()
    for value in (args.machine, args.run_id):
        if not value or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value):
            ap.error('Invalid machine or run ID')
    data = ROOT / args.experiment / 'data' / args.machine / args.run_id
    manifest = json.loads((data / 'manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError('Only complete runs can be archived with this helper')
    config = json.loads((data / 'config.json').read_text())
    basis = config.get('verification_basis', {})
    if basis and sha(ROOT / basis['freeze_manifest']) != basis['freeze_manifest_sha256']:
        raise ValueError('Frozen baseline manifest has changed')
    out = data / 'reproduction'
    if out.exists():
        raise FileExistsError(out)
    out.mkdir()
    files = set()
    for part in ('src', 'scripts', 'tests'):
        folder = ROOT / args.experiment / part
        files.update(p for p in folder.rglob('*') if p.is_file() and p.suffix in ('.py', '.c', '.cpp', '.h'))
    files.update(p for p in (ROOT / 'common').iterdir() if p.suffix in ('.py', '.hpp'))
    files.update([ROOT / args.experiment / 'Makefile', ROOT / 'capacity/scripts/common.py',
                  ROOT / 'capacity/requirements.txt'])
    for source in sorted(files):
        target = out / 'source' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    binary_name = {'capacity': 'cache_capacity_pmu', 'line_size': 'line_size_pmu',
                   'associativity': 'associativity_pmu'}[args.experiment]
    (out / 'bin').mkdir()
    for name in (binary_name, binary_name + '.dis'):
        shutil.copy2(ROOT / args.experiment / 'build' / args.machine / name, out / 'bin' / name)
    shutil.copy2(data / 'config.json', out / 'config.json')
    info = dict(captured_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                experiment=args.experiment, machine=args.machine, run_id=args.run_id,
                git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                run_manifest_sha256=sha(data / 'manifest.json'), verification_basis=basis,
                note='Post-collection snapshot of retained source/build files, not an automatic pre-run snapshot. '
                     'For these Crux runs the measurement sources and compiler flags were unchanged during collection. '
                     'The archive helper itself was added after collection began. Frozen Phase-I evidence is separate.',
                files={str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    (out / 'provenance.json').write_text(json.dumps(info, indent=2) + '\n')
    print(out)


if __name__ == '__main__':
    main()
