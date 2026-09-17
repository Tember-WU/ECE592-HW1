#!/usr/bin/env python3
"""Serial Charnwood collection; preserve launch context and binaries on failure too."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PREP = Path(__file__).resolve().parent
ROOT = PREP.parents[2]
os.sched_setaffinity(0, {1, 5})
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                  MALLOC_TRIM_THRESHOLD_='0', MALLOC_MMAP_THRESHOLD_='131072')
os.environ['PATH'] = str(Path(sys.executable).parent) + ':' + os.environ['PATH']
for specification in sys.argv[1:]:
    experiment, run_id = specification.split(':')
    assert experiment in ('capacity', 'line_size', 'associativity')
    data = ROOT / experiment / 'data/charnwood' / run_id
    context = dict(started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                   runner_affinity=sorted(os.sched_getaffinity(0)),
                   environment={k: os.environ[k] for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS',
                                'MALLOC_TRIM_THRESHOLD_', 'MALLOC_MMAP_THRESHOLD_')},
                   processes=subprocess.check_output(['ps', '-eo', 'pid,user,psr,pcpu,comm',
                                                       '--sort=-pcpu'], text=True).splitlines()[:16])
    command = [sys.executable, str(ROOT / experiment / 'scripts' / f'run_{experiment}.py'),
               '--machine', 'charnwood', '--run-id', run_id]
    if experiment == 'capacity':
        command += ['--allocation-attempts', '6']
    context['command'] = command
    with (PREP / f'{run_id}-launch.json').open('x') as f:
        json.dump(context, f, indent=2)
    print(f'Starting {experiment} / {run_id}', flush=True)
    log = PREP / f'{run_id}-collect.log'
    with log.open('x') as f:
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='', flush=True); f.write(line); f.flush()
        status = process.wait()
    if data.exists():
        shutil.copy2(log, data / 'collector.log')
        shutil.copy2(PREP / f'{run_id}-launch.json', data / 'launch-context.json')
        executable = 'cache_capacity_pmu' if experiment == 'capacity' else f'{experiment}_pmu'
        for source, destination in ((executable, executable + '.bin'),
                                    (executable + '.dis', 'disassembly.txt')):
            shutil.copy2(ROOT / experiment / 'build/charnwood' / source, data / destination)
        (data / 'binary-sha256.json').write_text(json.dumps({name: hashlib.sha256((data / name).read_bytes()).hexdigest()
            for name in (executable + '.bin', 'disassembly.txt')}, indent=2) + '\n')
    if status:
        print(f'{experiment} failed (exit {status}); evidence retained. Continuing next experiment.', flush=True)
        continue
    command = [sys.executable, str(ROOT / experiment / 'scripts' / f'analyze_{experiment}.py'),
               '--machine', 'charnwood', '--run-id', run_id]
    with (PREP / f'{run_id}-analyze.log').open('x') as f:
        status = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
    print(f'{experiment} analysis exit {status}', flush=True)
