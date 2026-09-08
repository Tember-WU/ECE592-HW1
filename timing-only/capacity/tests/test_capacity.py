"""Check migration behavior using synthetic samples and mocked collection."""
import contextlib
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_capacity as runner
import analyze_capacity as analyzer


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'configs/artemisia.json').read_text())

    def test_plan_retains_all_sweeps_and_is_deterministic(self):
        original = copy.deepcopy(self.config)
        jobs = runner.plan(self.config, ['all'])
        self.assertEqual(len(jobs), 167)
        self.assertEqual(jobs, runner.plan(self.config, ['all']))
        self.assertEqual(self.config, original)
        self.assertEqual(sum(j['parameters']['samples'] for j in jobs), 167000000)

    def test_invalid_points_are_rejected_before_collection(self):
        for changes in ({'samples': 999999}, {'batch': 17}, {'spacing': 7},
                        {'bytes': 17}, {'mode': 'typo'}, {'sample': 1000000}):
            with self.subTest(changes=changes):
                config = copy.deepcopy(self.config)
                config['capacity']['sweeps']['coarse']['points'][0].update(changes)
                with self.assertRaises(ValueError):
                    runner.plan(config, ['coarse'])

    def test_dry_run_does_not_build_or_create_output_and_protects_existing_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'configs').mkdir()
            (root / 'configs/artemisia.json').write_text(json.dumps(self.config))
            argv = ['run_capacity.py', '--machine', 'artemisia', '--run-id', 'check', '--dry-run']
            with patch.object(runner, 'ROOT', root), patch.object(sys, 'argv', argv), \
                    patch.object(runner.subprocess, 'run') as execute, contextlib.redirect_stdout(io.StringIO()):
                runner.main()
                execute.assert_not_called()
                self.assertFalse((root / 'data').exists())
                existing = root / 'data/artemisia/check'
                existing.mkdir(parents=True)
                marker = existing / 'keep.txt'
                marker.write_text('existing measurements')
                with self.assertRaises(FileExistsError):
                    runner.main()
                self.assertEqual(marker.read_text(), 'existing measurements')

    def test_multiple_collected_points_keep_cpu_and_separate_raw_from_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('src/cache_bench.c', 'Makefile',
                         'scripts/run_capacity.py', 'scripts/analyze_capacity.py', 'requirements.txt'):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            out = root / 'data/artemisia/synthetic'
            (out / 'raw').mkdir(parents=True)
            (out / 'logs').mkdir()
            jobs = runner.plan(self.config, ['coarse'])[:2]
            manifest = {'jobs': jobs}
            commands = []

            def execute(cmd, **kwargs):
                if cmd[0] == 'make':
                    build = root / 'build/artemisia'
                    build.mkdir(parents=True)
                    (build / 'cache_capacity').write_text('synthetic binary; never executed')
                    (build / 'cache_capacity.dis').write_text('synthetic disassembly')
                else:
                    commands.append(cmd)
                    np.full(int(cmd[6]), 320, dtype='<u8').tofile(cmd[-1])
                return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='synthetic log')

            with patch.object(runner, 'ROOT', root), patch.object(runner.subprocess, 'run', side_effect=execute), \
                    patch.object(runner, 'environment', return_value={}), \
                    patch.object(runner, 'cpu_stat', return_value={'cpu0': [1] * 10}), \
                    contextlib.redirect_stdout(io.StringIO()):
                runner.collect(self.config, jobs, out, manifest)
            self.assertEqual([cmd[9] for cmd in commands], ['32', '32'])
            self.assertEqual(len(list((out / 'raw').glob('*.u64.gz'))), 2)
            self.assertFalse((root / 'results').exists())
            self.assertTrue((out / 'source/scripts/run_capacity.py').exists())
            records = analyzer.load_records(out, 'artemisia')
            self.assertEqual(len(records), 2)
            self.assertTrue(all(d['stats']['n'] == 1000000 for d in records))
            self.assertTrue(all(j['status'] == 'complete' for j in jobs))

    def test_analysis_recomputes_raw_and_handles_custom_layout_and_one_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / 'data/custom/synthetic'
            (data / 'raw').mkdir(parents=True)
            (data / 'logs').mkdir()
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/run_capacity.py', root / 'scripts/run_capacity.py')
            for index, size in enumerate((1024, 2048, 4096)):
                payload = np.arange(32, 672, 32, dtype='<u8').tobytes()
                filename = f'raw/point{index}.u64.gz'
                with gzip.open(data / filename, 'wb') as f:
                    f.write(payload)
                d = dict(name=f'point{index}', machine='custom', suite='new_sweep',
                         parameters=dict(bytes=size, spacing=16, batch=32, samples=20,
                                         pages='base', mode='random', seed=index + 1),
                         stats={'median': -123}, elapsed_seconds=1,
                         raw_file=filename, raw_sha256=hashlib.sha256(payload).hexdigest())
                (data / f'logs/point{index}.json').write_text(json.dumps(d))
            boundary = root / 'boundary.json'
            boundary.write_text(json.dumps([dict(level='Synthetic boundary', spacing=16, batch=32,
                                                pages='base', unit=1024, estimate=2048,
                                                interval=[1024, 4096], zoom=[1024, 4096],
                                                box_points=[1024, 2048, 4096])]))
            argv = ['analyze_capacity.py', '--machine', 'custom', '--run-id', 'synthetic',
                    '--boundaries', str(boundary)]
            before = {p: p.read_bytes() for p in data.rglob('*') if p.is_file()}
            with patch.object(analyzer, 'ROOT', root), patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                analyzer.main()
            output = root / 'results/custom/synthetic'
            self.assertTrue((output / 'figures/capacity_s16_b32_base.pdf').exists())
            self.assertTrue((output / 'figures/boundary_boxplots.pdf').exists())
            self.assertEqual(before, {p: p.read_bytes() for p in data.rglob('*') if p.is_file()})
            self.assertEqual(analyzer.load_records(data, 'custom')[0]['stats']['median'], 10.5)
            (data / 'raw/point0.u64.gz').write_bytes(gzip.compress(b'corrupted'))
            with self.assertRaisesRegex(ValueError, 'checksum'):
                analyzer.load_records(data, 'custom')


if __name__ == '__main__':
    unittest.main()
