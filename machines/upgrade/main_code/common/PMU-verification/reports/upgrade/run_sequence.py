#!/usr/bin/env python3
"""Run the Upgrade PMU experiments serially and preserve their provenance."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
VENV = ROOT.parent / 'timing-only/capacity/.venv'
os.environ['PATH'] = f'{VENV}/bin:{VENV}/native/root/usr/bin:' + os.environ['PATH']


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def archive(experiment, run_id, binary):
    data = ROOT / experiment / 'data/upgrade' / run_id
    paths = set()
    for folder in (experiment + '/src', experiment + '/scripts', experiment + '/tests',
                   'common', 'capacity/scripts'):
        paths.update(p for p in (ROOT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts)
    paths.update(p for p in (ROOT / experiment / 'Makefile', ROOT / 'requirements.txt') if p.exists())
    records = []
    for source in sorted(paths):
        target = data / 'source' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        records.append(dict(path=str(target.relative_to(data)),
                            sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    executable = ROOT / experiment / 'build/upgrade' / binary
    target = data / (binary + '.bin')
    shutil.copy2(executable, target)
    records.append(dict(path=target.name, sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    with (data / 'disassembly.txt').open('w') as f:
        subprocess.run(['objdump', '-d', '-Mintel', str(target)], stdout=f, check=True)
    check = ROOT / experiment / 'build/upgrade/check.log'
    if not check.exists():
        check = ROOT / 'associativity/build/upgrade/check.log'
    if check.exists():
        shutil.copy2(check, data / 'check.log')
    save(data / 'source_provenance.json', dict(archived_utc=now(), files=records))


def main():
    ledger_path = REPORT / 'execution.json'
    ledger = json.loads(ledger_path.read_text())
    for experiment, run_id, binary in [
            ('capacity', 'capacity02', 'cache_capacity_pmu'),
            ('line_size', 'line_size01', 'line_size_pmu'),
            ('associativity', 'associativity01', 'associativity_pmu')]:
        data = ROOT / experiment / 'data/upgrade' / run_id
        if data.exists() or (ROOT / experiment / 'results/upgrade' / run_id).exists():
            raise FileExistsError(f'Choose a new run ID: {experiment}/{run_id}')
        entry = dict(experiment=experiment, run_id=run_id, status='running', started_utc=now())
        ledger['runs'].append(entry)
        save(ledger_path, ledger)
        args = ['--machine', 'upgrade', '--run-id', run_id]
        log = ROOT / experiment / 'build/upgrade' / (run_id + '-console.log')
        print(f'START {experiment}/{run_id} {now()}', flush=True)
        with log.open('w') as f:
            run = subprocess.run([str(VENV / 'bin/python3'), str(ROOT / experiment / 'scripts' /
                                  ('run_' + experiment + '.py')), *args], stdout=f, stderr=subprocess.STDOUT)
        entry['collection_returncode'] = run.returncode
        if data.exists():
            shutil.copy2(log, data / 'console.log')
            archive(experiment, run_id, binary)
        if run.returncode:
            entry.update(status='failed', finished_utc=now())
            save(ledger_path, ledger)
            raise RuntimeError(f'Collection failed: {log}')
        with (data / 'analysis.log').open('w') as f:
            analysis = subprocess.run([str(VENV / 'bin/python3'), str(ROOT / experiment / 'scripts' /
                                       ('analyze_' + experiment + '.py')), *args], stdout=f, stderr=subprocess.STDOUT)
        entry.update(analysis_returncode=analysis.returncode,
                     status='complete' if analysis.returncode == 0 else 'analysis_failed', finished_utc=now())
        save(ledger_path, ledger)
        if analysis.returncode:
            raise RuntimeError(f'Analysis failed: {data / "analysis.log"}')
        print(f'DONE {experiment}/{run_id} {now()}', flush=True)
    ledger['finished_utc'] = now()
    save(ledger_path, ledger)


if __name__ == '__main__':
    main()
