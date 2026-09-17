import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from run_verification import PMU, denominators, plan, validate_counts, worker_command


class VerificationTests(unittest.TestCase):
    def config(self, experiment):
        return json.loads((PMU / experiment / 'configs/artemisia.json').read_text())

    def test_plans(self):
        for experiment in ('line_size', 'associativity'):
            c = self.config(experiment)
            self.assertEqual(len(plan(c)), 12)
            self.assertEqual(plan(c), plan(c))

    def test_unsafe_layout_and_missing_samples(self):
        c = self.config('line_size'); c['points'][0]['stride'] = 60
        with self.assertRaises(ValueError): plan(c)
        c = self.config('associativity'); c['samples'] = 999999
        with self.assertRaises(ValueError): plan(c)

    def test_associativity_actual_load_denominators(self):
        c = self.config('associativity'); p = c['points'][0]
        self.assertEqual(p['k'], 10)
        self.assertEqual(denominators(c, p), (129, 138000000))

    def test_multiplex_and_wrong_denominator_rejected(self):
        c = self.config('associativity'); p = c['points'][0]
        counts = dict(chain_loads=denominators(c, p)[1], time_enabled_ns=10, time_running_ns=10,
                      events=[dict(config=int(e['config'], 0), count=0) for e in c['events']])
        validate_counts(counts, c, p)
        bad = copy.deepcopy(counts); bad['time_running_ns'] = 9
        with self.assertRaises(ValueError): validate_counts(bad, c, p)
        bad = copy.deepcopy(counts); bad['chain_loads'] = 128000000
        with self.assertRaises(ValueError): validate_counts(bad, c, p)

    def test_two_live_kernels(self):
        for experiment in ('line_size', 'associativity'):
            c = self.config(experiment); c['samples'] = 1000
            p = c['points'][0]
            with tempfile.TemporaryDirectory() as directory:
                d = Path(directory)
                for sub in ('raw', 'counts', 'legacy'): (d / sub).mkdir()
                exe = PMU / experiment / 'build/artemisia' / (experiment + '_pmu')
                run = subprocess.run(worker_command(c, p, d, exe), capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
                raw = np.fromfile(d / 'raw' / (p['name'] + '.u64'), dtype='<u8')
                self.assertEqual(len(raw), 1000)
                self.assertTrue(np.all(raw > 0))
                counts = json.loads((d / 'counts' / (p['name'] + '.json')).read_text())
                validate_counts(counts, c, p)
                self.assertGreater(counts['events'][3]['count'], counts['chain_loads'])


if __name__ == '__main__':
    unittest.main()
