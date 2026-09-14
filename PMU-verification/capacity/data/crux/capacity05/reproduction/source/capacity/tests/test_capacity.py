import copy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import event_encoding, plan, summarize, validate_counts
from run_capacity import launch

MACHINE = os.environ.get('MACHINE', 'artemisia')


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs' / (MACHINE + '.json')).read_text())

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

    def test_local_event_aliases_and_missing_event(self):
        for unit in ('cpu', 'default_core'):
            listing = f'  mem_load_retired.l1_miss\n    [Retired L1 misses]\n    {unit}/event=0xd1,period=0x10,umask=0x8/\n'
            self.assertEqual(event_encoding(listing, 'mem_load_retired.l1_miss'), 0x08d1)
            with self.assertRaises(ValueError): event_encoding(listing, 'mem_load_retired.l2_miss')

    def test_allocation_retry_preserves_failure_and_does_not_retry_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            log, raw, counts = p / 'point.txt', p / 'raw', p / 'counts'
            marker = p / 'first-launch'
            script = ('import pathlib,sys; p=pathlib.Path(sys.argv[1]); '
                      'first=not p.exists(); p.touch(); '
                      'print("MADV_COLLAPSE: Cannot allocate memory" if first else "measurement complete"); '
                      'sys.exit(1 if first else 0)')
            attempts = []
            with patch('run_capacity.time.sleep'):
                run = launch([sys.executable, '-c', script, str(marker)], log, raw, counts, 2, attempts)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(len(attempts), 2)
            self.assertTrue((p / 'point.allocation-attempt1.txt').exists())
            # Even the same error must not be retried if measurement output exists.
            raw.touch(); marker.unlink(); attempts = []
            run = launch([sys.executable, '-c', script, str(marker)], log, raw, counts, 2, attempts)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(len(attempts), 1)
            self.assertFalse(attempts[0]['premeasurement_allocation_failure'])

    @unittest.skipUnless(platform.node().split('.')[0] == MACHINE, 'Selected machine hardware smoke test')
    def test_live_counter_group_and_raw_samples(self):
        c = dict(self.config, samples=1000, pages='base')
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            cmd = ['numactl', '--membind=' + str(c['numa_node']),
                   str(ROOT / 'build' / MACHINE / 'cache_capacity_pmu'), '8192',
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
