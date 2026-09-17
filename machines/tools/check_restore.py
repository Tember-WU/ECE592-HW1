#!/usr/bin/env python3
"""Check relocation with a real host package; never execute a benchmark."""
import csv
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]


def main():
    records = []
    with tempfile.TemporaryDirectory(prefix='ece592-machine-layout-') as tmp:
        restored = Path(tmp) / 'restored'
        log = PACKAGE / 'restore_verification.log'
        def run(command, cwd=None):
            p = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            with log.open('a') as f:
                f.write(json.dumps(command) + '\n' + p.stdout + '\n')
            records.append({'command': command, 'returncode': p.returncode})
            if p.returncode:
                raise RuntimeError(f'Restoration check failed: {command}; see {log}')
            print('Passed:', ' '.join(command[:4]), flush=True)
        log.write_text('Package-only restoration and offline analysis check. No experiment collection.\n')
        run([sys.executable, str(PACKAGE / 'tools/restore_layout.py'), '--machine', 'artemisia', '--output', str(restored)])
        # A real newly compressed CSV must still be consumable by the old workflow.
        ex = restored / 'timing-only/line_size/data/artemisia'
        name = 'dense_stride64_align0_moderandom_lines.csv'
        values = np.loadtxt(ex / 'raw_data' / name) / 1024
        with (ex / 'stats/all_stats.csv').open() as f:
            original = next(row for row in csv.DictReader(f) if row['file'] == name)
        if len(values) != 1000000 or not np.isclose(np.median(values), float(original['median']), rtol=0, atol=1e-12):
            raise RuntimeError('Restored raw CSV does not reproduce the recorded median')
        # Compile the copied source, then run only its offline analyzer. The
        # collectors and resulting benchmark executables are never invoked.
        run(['make', '-C', str(restored / 'software-hit-rate'), 'MACHINE=artemisia', 'all'])
        run([sys.executable, str(restored / 'software-hit-rate/scripts/analyze.py'), '--machine', 'artemisia', '--run-id', 'hitrate01'])
        validation = json.loads((restored / 'software-hit-rate/results/artemisia/hitrate01/validation.json').read_text())
        if validation['status'] != 'passed' or validation['timed_samples'] != 54000000:
            raise RuntimeError('Restored binary-array analysis did not pass')
        report = {'status': 'passed', 'checked_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                  'restored_machine': 'artemisia', 'restoration': json.loads((restored / 'RESTORATION.json').read_text()),
                  'csv_samples_reloaded': len(values), 'csv_median_matches_existing_result': True,
                  'software_hit_rate_samples_revalidated': validation['timed_samples'],
                  'native_source_compilation': 'passed', 'offline_analysis': 'passed',
                  'benchmarks_executed': False, 'commands': records,
                  'scope': 'Full export integrity is in verification.json; this is one representative restoration/build/analysis check'}
    # Only the temporary restored tree is deleted by TemporaryDirectory.
    (PACKAGE / 'restore_verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
