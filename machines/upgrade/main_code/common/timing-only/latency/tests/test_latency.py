import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import plan, decode, statistics, load_record


class DataTests(unittest.TestCase):
    def test_all_machine_configurations(self):
        for path in sorted((ROOT / 'configs').glob('*.json')):
            c = json.loads(path.read_text())
            jobs = plan(c)
            self.assertEqual(len(jobs), 30)
            self.assertEqual(sum(j['parameters']['samples'] * len(j['columns']) for j in jobs), 39000000)
            self.assertEqual(jobs, plan(c))
            self.assertEqual(len(plan(c, ['l1_hit'])), 3)

    def test_reject_underfilled_and_ambiguous_configs(self):
        c = json.loads((ROOT / 'configs/artemisia.json').read_text())
        cases = []
        bad = copy.deepcopy(c); bad['defaults']['samples'] = 999999; cases.append(bad)
        bad = copy.deepcopy(c); bad['groups']['l1_hit'].append(bad['groups']['l1_hit'][0]); cases.append(bad)
        bad = copy.deepcopy(c); bad['groups']['l1_miss'][0]['bytes'] = 4096; cases.append(bad)
        bad = copy.deepcopy(c); bad['groups']['l1_hit'][0]['mode'] = 'independent'; cases.append(bad)
        for bad in cases:
            with self.assertRaises(ValueError): plan(bad)

    def test_paired_columns_and_signed_differences(self):
        p = dict(mode='paired', samples=20, batch=16)
        a = np.array([[16, 32], [64, 32]] * 10, dtype='<u8')
        raw = decode(a.tobytes(), p)
        s = statistics(raw, p)
        self.assertEqual(s['first']['median'], 2.5)
        self.assertEqual(s['reread']['median'], 2)
        self.assertEqual(s['first_minus_reread']['minimum'], -1)
        self.assertEqual(s['first_slower_fraction'], .5)
        with self.assertRaises(ValueError): decode(a.tobytes()[:-8], p)

    def test_zero_intervals_only_for_empty_timer(self):
        payload = np.zeros(20, dtype='<u8').tobytes()
        self.assertEqual(decode(payload, dict(mode='empty', samples=20)).shape, (20, 1))
        with self.assertRaises(ValueError): decode(payload, dict(mode='chase', samples=20))

    def test_tampered_archive_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'logs').mkdir(); (root / 'raw').mkdir()
            payload = np.arange(1, 21, dtype='<u8').tobytes()
            (root / 'raw/a.gz').write_bytes(gzip.compress(payload))
            record = dict(raw_file='raw/a.gz', raw_sha256=hashlib.sha256(payload).hexdigest(),
                          parameters=dict(mode='chase', samples=20, batch=16))
            path = root / 'logs/a.json'; path.write_text(json.dumps(record))
            self.assertEqual(load_record(path)['stats']['first']['n'], 20)
            (root / 'raw/a.gz').write_bytes(gzip.compress(payload[:-8] + b'\xff' * 8))
            with self.assertRaises(ValueError): load_record(path)


class KernelTests(unittest.TestCase):
    def test_kernel_modes_and_cursor_verification(self):
        binary = ROOT / 'build' / os.environ.get('MACHINE', os.uname().nodename.split('.')[0]) / 'latency_bench'
        cpu = min(os.sched_getaffinity(0))
        # Sixteen fast loads can finish within one 40 ns ARM counter tick.
        # Use the formal batch length on ARM; paired mode still has four
        # distinct batches in this 64 KiB / 64 B fixture.
        batch = 256 if os.uname().machine == 'aarch64' else 16
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ('chase', 'sequential', 'paired', 'independent', 'empty'):
                target = Path(tmp) / (mode + '.u64')
                cmd = [str(binary), '65536', '64', mode, '1000', str(batch), '59221', str(cpu), 'base', str(target)]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                self.assertIn('dependency_result_verified=1', result.stderr)
                raw = decode(target.read_bytes(), dict(mode=mode, samples=1000))
                self.assertEqual(raw.shape, (1000, 2 if mode == 'paired' else 1))


if __name__ == '__main__':
    unittest.main()
