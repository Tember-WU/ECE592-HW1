#!/usr/bin/env python3
"""Run the existing Phase-I collector in an isolated Upgrade output directory."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'data/upgrade'
SETUP = DATA / 'setup'
os.chdir(DATA)
manifest = dict(status='running', started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                reason='Upgrade associativity Phase-I data were missing; collect before freezing Phase I and running formal PMU verification.',
                samples_per_k=1000000, candidate_sets={'L1': [64], 'L2': [256, 512, 1024]},
                cpu=2, numa_node=0, smt_sibling=8,
                memory_policy='Parent launched under numactl --membind=0; original worker uses taskset -c 2.')
try:
    spec = importlib.util.spec_from_file_location('phase1_assoc', ROOT / 'scripts/run_associativity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BENCH = str(SETUP / 'associativity_bench.bin')
    module.PLOT_DIR = str(ROOT / 'results/upgrade/plots')
    Path(module.PLOT_DIR).mkdir(parents=True, exist_ok=True)
    module.collect()
    module.plot()
    module.plot_boundary_boxplots()
    pinning = DATA / 'raw_data/pinning_manifest.txt'
    shutil.copyfile(pinning, SETUP / 'original-generated-pinning.txt')
    pinning.write_text('pinned_cpu=2\npinned_core=2\npinned_socket=0\npinned_node=0\n'
                       'smt_sibling=8 (observed Linux thread_siblings_list=2,8)\n'
                       'affinity_method=taskset -c 2\nmemory_policy=numactl --membind=0 inherited\n'
                       'note=Corrected the original collector\'s hard-coded no-SMT statement.\n')
    manifest['status'] = 'complete'
except BaseException as error:
    manifest.update(status='failed', error=str(error))
    raise
finally:
    manifest['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest['source_sha256'] = {str(p.relative_to(SETUP)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (SETUP / 'source').rglob('*') if p.is_file()}
    manifest['binary_sha256'] = hashlib.sha256((SETUP / 'associativity_bench.bin').read_bytes()).hexdigest()
    (SETUP / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
