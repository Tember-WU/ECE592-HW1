import copy
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import plan, summarize, validate_counts, selected_events


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs' / 'artemisia.json').read_text())

    def test_plan_matches_fourteen_unique_points(self):
        a = plan(self.config)
        self.assertEqual(len(a), 14)
        self.assertEqual(a, plan(self.config))
        self.assertEqual(sum(j['region'] == 'L1' for j in a), 5)

    def test_reject_insufficient_samples_and_duplicate_points(self):
        bad = copy.deepcopy(self.config); bad['samples'] = 999999
        with self.assertRaises(ValueError): plan(bad)
        bad = copy.deepcopy(self.config); bad['regions']['L1'].append(32768)
        with self.assertRaises(ValueError): plan(bad)

    def test_counter_scope_validation(self):
        c = self.config
        counts = dict(chain_loads=c['samples'] * c['batch'], time_enabled_ns=100, time_running_ns=100,
                      events=[dict(config=int(e['config'], 0), count=5) for e in c['events']])
        validate_counts(counts, c)
        for field, value in [('time_running_ns', 90), ('chain_loads', 1000000)]:
            bad = copy.deepcopy(counts); bad[field] = value
            with self.assertRaises(ValueError): validate_counts(bad, c)
        bad = copy.deepcopy(counts); bad['events'][0]['config'] = 1
        with self.assertRaises(ValueError): validate_counts(bad, c)

    def test_split_passes_preserve_workloads_and_reject_wrong_events(self):
        c = json.loads((ROOT / 'configs/sunbird.json').read_text())
        jobs = plan(c)
        self.assertEqual(len(jobs), 28)
        self.assertEqual(len({j['point_name'] for j in jobs}), 14)
        for a, b in zip(jobs[::2], jobs[1::2]):
            self.assertEqual((a['point_name'], a['bytes']), (b['point_name'], b['bytes']))
            counts = dict(chain_loads=c['samples'] * c['batch'], time_enabled_ns=10,
                          time_running_ns=10, events=[dict(config=int(e['config'], 0), count=1)
                          for e in selected_events(c, a)])
            validate_counts(counts, c, a)
            with self.assertRaises(ValueError): validate_counts(counts, c, b)
        for indices in ([1, 3], [2], [2, 4]):
            bad = copy.deepcopy(c); bad['event_passes'][1]['event_indices'] = indices
            with self.assertRaises(ValueError): plan(bad)

    def test_stats_keep_outliers(self):
        raw = np.array([16] * 19 + [1600], dtype=np.uint64)
        s = summarize(raw, 16)
        self.assertEqual(s['n'], 20)
        self.assertEqual(s['median'], 1)
        self.assertEqual(s['maximum'], 100)
        self.assertEqual(s['outliers'], 1)
        self.assertGreater(s['mean'], s['median'])

    def test_live_counter_group_and_raw_samples(self):
        machine = platform.node().split('.')[0]
        c = json.loads((ROOT / 'configs' / (machine + '.json')).read_text())
        jobs = plan(c)[:len(c.get('event_passes', [None]))]
        c.update(samples=1000, pages='base')
        for job in jobs:
            self.live_group(c, job)

    def live_group(self, c, job):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            cmd = ['numactl', '--membind=' + str(c['numa_node']),
                   str(ROOT / 'build' / c['machine'] / 'cache_capacity_pmu'), '8192',
                   str(c['spacing']), c['mode'], str(c['samples']), str(c['batch']),
                   str(c['seed']), str(c['cpu']), c['pages'], str(p / 'raw.u64'),
                   ','.join(e['config'] for e in selected_events(c, job)), str(p / 'counts.json')]
            run = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            raw = np.fromfile(p / 'raw.u64', dtype='<u8')
            self.assertEqual(len(raw), c['samples'])
            self.assertTrue(np.all(raw > 0))
            counts = json.loads((p / 'counts.json').read_text())
            validate_counts(counts, c, job)
            for event, actual in zip(selected_events(c, job), counts['events']):
                if event['name'].endswith('all_loads'):
                    self.assertGreater(actual['count'], counts['chain_loads'])


if __name__ == '__main__':
    unittest.main()
