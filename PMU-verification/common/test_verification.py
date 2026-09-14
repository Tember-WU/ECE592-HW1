import copy
import json
import platform
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from run_verification import PMU, denominators, plan, validate_counts, worker_command, selected_events


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
        machine = platform.node().split('.')[0]
        for experiment in ('line_size', 'associativity'):
            path = PMU / experiment / 'configs' / (machine + '.json')
            if not path.exists():
                self.skipTest('No local PMU machine configuration')
            c = json.loads(path.read_text())
            jobs = plan(c)[:len(c.get('event_passes', [None]))]
            c['samples'] = 1000
            for p in jobs:
                self.live_kernel(c, p)

    def live_kernel(self, c, p):
        experiment = c['experiment']
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            for sub in ('raw', 'counts', 'legacy'): (d / sub).mkdir()
            exe = PMU / experiment / 'build' / c['machine'] / (experiment + '_pmu')
            run = subprocess.run(worker_command(c, p, d, exe), capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            raw = np.fromfile(d / 'raw' / (p['name'] + '.u64'), dtype='<u8')
            self.assertEqual(len(raw), 1000)
            self.assertTrue(np.all(raw > 0))
            counts = json.loads((d / 'counts' / (p['name'] + '.json')).read_text())
            validate_counts(counts, c, p)
            for event, count in zip(selected_events(c, p), counts['events']):
                if event['name'].endswith('all_loads'):
                    self.assertGreater(count['count'], counts['chain_loads'])

    def test_frozen_baselines_and_split_plans(self):
        from analyze_verification import baseline
        for experiment in ('line_size', 'associativity'):
            c = json.loads((PMU / experiment / 'configs/sunbird.json').read_text())
            jobs = plan(c)
            self.assertEqual(len(jobs), 24)
            self.assertEqual(len({p['point_name'] for p in jobs}), 12)
            for a, b in zip(jobs[::2], jobs[1::2]):
                self.assertEqual(a['point_name'], b['point_name'])
                self.assertEqual(a['event_indices'] + b['event_indices'], [0, 1, 2, 3])
                self.assertEqual(baseline(c, a), baseline(c, b))
                self.assertGreater(baseline(c, a), 0)
                counts = dict(chain_loads=denominators(c, a)[1], time_enabled_ns=10,
                              time_running_ns=10, events=[dict(config=int(e['config'], 0), count=1)
                              for e in selected_events(c, a)])
                validate_counts(counts, c, a)
                with self.assertRaises(ValueError): validate_counts(counts, c, b)


if __name__ == '__main__':
    unittest.main()
