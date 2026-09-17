"""Short native checks; these samples are excluded from formal evidence."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from run_verification import PMU, plan, validate_counts, worker_command
from analyze_verification import baseline
from support import frozen_check
from common import validate_counts as capacity_counts


class SkylarkTests(unittest.TestCase):
    def test_frozen_baselines_and_selected_points(self):
        frozen_check()
        for experiment in ('line_size', 'associativity'):
            c = json.loads((PMU / experiment / 'configs/skylark.json').read_text())
            self.assertEqual(len(plan(c)), 12)
            for point in c['points']:
                self.assertGreater(baseline(c, point), 0)

    def test_native_kernels(self):
        for experiment in ('capacity', 'line_size', 'associativity'):
            c = json.loads((PMU / experiment / 'configs/skylark.json').read_text())
            c['samples'] = 1000
            with tempfile.TemporaryDirectory() as directory:
                d = Path(directory)
                for sub in ('raw', 'counts', 'legacy'):
                    (d / sub).mkdir()
                if experiment == 'capacity':
                    raw_path, count_path = d / 'raw/probe.u64', d / 'counts/probe.json'
                    exe = PMU / 'capacity/build/skylark/cache_capacity_pmu'
                    cmd = ['numactl', '--membind=' + str(c['numa_node']), str(exe),
                           '32768', str(c['spacing']), c['mode'], str(c['samples']),
                           str(c['batch']), str(c['seed']), str(c['cpu']), c['pages'],
                           str(raw_path), ','.join(e['config'] for e in c['events']), str(count_path)]
                else:
                    p = c['points'][0]
                    exe = PMU / experiment / 'build/skylark' / (experiment + '_pmu')
                    cmd = worker_command(c, p, d, exe)
                    raw_path = d / 'raw' / (p['name'] + '.u64')
                    count_path = d / 'counts' / (p['name'] + '.json')
                run = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
                self.assertIn('cpu_end=' + str(c['cpu']), run.stderr + run.stdout)
                raw = np.fromfile(raw_path, dtype='<u8')
                self.assertEqual(len(raw), 1000)
                self.assertTrue(np.all(raw > 0))
                counts = json.loads(count_path.read_text())
                if experiment == 'capacity':
                    capacity_counts(counts, c)
                else:
                    validate_counts(counts, c, p)
                self.assertGreater(counts['events'][3]['count'], counts['chain_loads'])


if __name__ == '__main__':
    unittest.main()
