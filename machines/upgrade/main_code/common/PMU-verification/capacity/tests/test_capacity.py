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
from common import event_encoding, plan, raw_event_encoding, selected_events, summarize, validate_counts
from run_capacity import launch

MACHINE = os.environ.get('MACHINE', 'artemisia')


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs' / (MACHINE + '.json')).read_text())

    def test_plan_matches_fourteen_unique_points(self):
        a = plan(self.config)
        passes = len(self.config.get('event_passes', [None]))
        self.assertEqual(len(a), 14 * passes)
        self.assertEqual(len({j['bytes'] for j in a}), 14)
        self.assertEqual(a, plan(self.config))
        self.assertEqual(sum(j['region'] == 'L1' for j in a), 5 * passes)

    def test_reject_insufficient_samples_and_duplicate_points(self):
        bad = copy.deepcopy(self.config); bad['samples'] = 999999
        with self.assertRaises(ValueError): plan(bad)
        bad = copy.deepcopy(self.config); bad['regions']['L1'].append(bad['regions']['L1'][0])
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

    def test_local_core_event_aliases_and_ambiguity(self):
        for pmu in ('cpu', 'default_core', 'cpu_core'):
            listing = f'  mem_load_retired.l1_miss\n    [Local description]\n    {pmu}/event=0xd1,period=0x186a3,umask=0x8/\n'
            self.assertEqual(raw_event_encoding(listing, 'mem_load_retired.l1_miss'), 0x08d1)
        with self.assertRaises(ValueError):
            raw_event_encoding(listing, 'mem_load_retired.l2_miss')
        with self.assertRaises(ValueError):
            raw_event_encoding(listing + '    cpu_atom/event=0xd1,umask=0x10/\n', 'mem_load_retired.l1_miss')

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

    def test_allocation_retry_limit_preserves_every_failure_before_waiting(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            log, raw, counts = p / 'point.txt', p / 'raw', p / 'counts'
            script = 'import sys; print("MADV_COLLAPSE: Cannot allocate memory"); sys.exit(1)'
            attempts, saved = [], []

            def record_attempt():
                saved.append(copy.deepcopy(attempts))
                self.assertTrue((p / Path(attempts[-1]['log_file']).name).exists())

            def wait(seconds):
                self.assertEqual(seconds, 10)
                self.assertEqual(saved[-1], attempts)

            with patch('run_capacity.time.sleep', side_effect=wait) as sleep:
                run = launch([sys.executable, '-c', script], log, raw, counts, 2, attempts,
                             retry_delay=10, on_attempt=record_attempt)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(len(attempts), 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual([len(snapshot) for snapshot in saved], [1, 2, 3])
            self.assertTrue(all(entry['premeasurement_allocation_failure'] for entry in attempts))
            self.assertTrue(log.exists())

    def test_live_counter_group_and_raw_samples(self):
        machine = os.environ.get('MACHINE', platform.node().split('.')[0])
        config_path = ROOT / 'configs' / (machine + '.json')
        if (not config_path.exists() or platform.machine() != 'x86_64' or
                platform.node().split('.')[0] != machine):
            self.skipTest('No configured local x86-64 machine')
        c = json.loads(config_path.read_text())
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
