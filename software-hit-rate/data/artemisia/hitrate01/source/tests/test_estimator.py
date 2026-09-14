import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from estimator import fit, estimate, read_raw
from analyze import pmu_reference


class EstimatorTests(unittest.TestCase):
    def test_unseen_mixture_uses_timing_only(self):
        model = fit(np.array([30, 32, 34] * 100), np.array([50, 52, 54] * 100))
        mixed = np.array([31] * 250 + [53] * 750)
        result = estimate(mixed, model)
        self.assertEqual(result['classified_hits'], 250)
        self.assertEqual(result['software_hit_rate'], .25)

    def test_bad_calibration_is_rejected(self):
        with self.assertRaises(ValueError):
            fit(np.array([60, 61]), np.array([30, 31]))

    def test_incomplete_raw_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'broken.u64'; p.write_bytes(b'123')
            with self.assertRaises(ValueError): read_raw(p)

    def test_reference_rejects_polluted_denominator_and_multiplexing(self):
        m = {'pmu': {'retired_loads': 1000020, 'l1_misses': 250000,
                     'time_running_ns': 100, 'time_enabled_ns': 100}}
        self.assertAlmostEqual(pmu_reference(m, 1000000, .001), 1 - 250000 / 1000020)
        m['pmu']['retired_loads'] = 2000000
        with self.assertRaises(ValueError): pmu_reference(m, 1000000, .001)
        m['pmu']['retired_loads'] = 1000000
        m['pmu']['time_running_ns'] = 50
        with self.assertRaises(ValueError): pmu_reference(m, 1000000, .001)

    def test_binary_kernel_matches_and_estimator_has_no_pmu_interface(self):
        host = subprocess.check_output(['hostname', '-s'], text=True).strip()
        pure = ROOT / 'build' / host / 'hit_rate'
        verify = ROOT / 'build' / host / 'verify_hit_rate'
        def instructions(p):
            text = subprocess.check_output(['objdump', '-d', '--no-show-raw-insn', str(p)], text=True)
            body = text.split('<sample_loop_begin>:', 1)[1].split('<sample_loop_end>:', 1)[0]
            # Branch addresses differ between binaries; mnemonic/operands and register allocation must match.
            import re
            return [re.sub(r'\b[0-9a-f]+ <[^>]+>', '<branch>', line.split('\t', 1)[-1].strip())
                    for line in body.splitlines() if '\t' in line]
        self.assertEqual(instructions(pure), instructions(verify))
        imports = subprocess.check_output(['nm', '-u', str(pure)], text=True)
        self.assertNotIn('syscall', imports)
        self.assertNotIn('ioctl', imports)
        self.assertNotIn('rdpmc', subprocess.check_output(['objdump', '-d', str(pure)], text=True))


if __name__ == '__main__':
    unittest.main()
