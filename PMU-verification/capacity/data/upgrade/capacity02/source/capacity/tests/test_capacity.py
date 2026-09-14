import copy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import plan, raw_event_encoding, summarize, validate_counts


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

    def test_stats_keep_outliers(self):
        raw = np.array([16] * 19 + [1600], dtype=np.uint64)
        s = summarize(raw, 16)
        self.assertEqual(s['n'], 20)
        self.assertEqual(s['median'], 1)
        self.assertEqual(s['maximum'], 100)
        self.assertEqual(s['outliers'], 1)
        self.assertGreater(s['mean'], s['median'])

    def test_local_core_event_aliases_and_ambiguity(self):
        for pmu in ('cpu', 'default_core', 'cpu_core'):
            listing = f'  mem_load_retired.l1_miss\n    [Local description]\n    {pmu}/event=0xd1,period=0x186a3,umask=0x8/\n'
            self.assertEqual(raw_event_encoding(listing, 'mem_load_retired.l1_miss'), 0x08d1)
        with self.assertRaises(ValueError):
            raw_event_encoding(listing, 'mem_load_retired.l2_miss')
        with self.assertRaises(ValueError):
            raw_event_encoding(listing + '    cpu_atom/event=0xd1,umask=0x10/\n', 'mem_load_retired.l1_miss')

    def test_live_counter_group_and_raw_samples(self):
        machine = os.environ.get('MACHINE', platform.node().split('.')[0])
        config_path = ROOT / 'configs' / (machine + '.json')
        if not config_path.exists() or platform.machine() != 'x86_64':
            self.skipTest('No configured local x86-64 machine')
        c = dict(json.loads(config_path.read_text()), samples=1000, pages='base')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            cmd = ['numactl', '--membind=' + str(c['numa_node']),
                   str(ROOT / 'build' / machine / 'cache_capacity_pmu'), '8192',
                   str(c['spacing']), c['mode'], str(c['samples']), str(c['batch']),
                   str(c['seed']), str(c['cpu']), c['pages'], str(p / 'raw.u64'),
                   ','.join(e['config'] for e in c['events']), str(p / 'counts.json')]
            run = subprocess.run(cmd, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            raw = np.fromfile(p / 'raw.u64', dtype='<u8')
            self.assertEqual(len(raw), c['samples'])
            self.assertTrue(np.all(raw > 0))
            counts = json.loads((p / 'counts.json').read_text())
            validate_counts(counts, c)
            self.assertGreater(counts['events'][3]['count'], counts['chain_loads'])


if __name__ == '__main__':
    unittest.main()
