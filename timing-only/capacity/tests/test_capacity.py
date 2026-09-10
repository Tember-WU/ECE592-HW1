"""Check adaptive planning and raw-data provenance using synthetic measurements."""
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
import plan_capacity as planner


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.config = runner.load_config(ROOT / 'configs/artemisia.json')

    def test_arm_uses_the_same_round1_protocol(self):
        arm = runner.load_config(ROOT / 'configs/thunderbird.json')
        self.assertEqual(runner.plan(arm, ['all']), runner.plan(self.config, ['all']))
        arm['isa'] = 'unsupported'
        with self.assertRaisesRegex(ValueError, 'supports'):
            runner.plan(arm, ['all'])

    def test_timer_quantization_allows_zero_only_for_empty_controls(self):
        raw = np.array([0, 1, 0, 2], dtype='<u8')
        self.assertTrue(runner.valid_intervals(raw, dict(samples=4, mode='empty')))
        self.assertFalse(runner.valid_intervals(raw, dict(samples=4, mode='random')))
        self.assertFalse(runner.valid_intervals(raw, dict(samples=4, mode='sequential')))
        self.assertFalse(runner.valid_intervals(raw, dict(samples=5, mode='empty')))

    def test_arm_units_and_frequency_mismatch_are_not_treated_as_tsc(self):
        env = dict(cpu=32, numa_node=0, source_sha256='arm', timer='CNTVCT', flags='-O0',
                   model='arm', kernel='test', page_size=4096,
                   timer_unit='CNTVCT ticks', timer_frequency_hz=25000000)
        first = dict(record_id='r1/p', environment=env)
        second = dict(record_id='r2/p', environment=dict(env, timer_frequency_hz=100000000))
        self.assertEqual(analyzer.timing_units(first), 'CNTVCT ticks / dependent load')
        self.assertEqual(analyzer.timing_units(first, empty=True), 'CNTVCT ticks / timer interval')
        self.assertEqual(analyzer.timing_units({}), 'TSC ticks / dependent load')
        with patch.object(analyzer, 'load_records', side_effect=[[first], [second]]):
            with self.assertRaisesRegex(ValueError, 'timer_frequency_hz'):
                analyzer.load_study(ROOT, 'thunderbird', ['r1', 'r2'])

    def test_shared_first_round_is_broad_and_deterministic(self):
        original = copy.deepcopy(self.config)
        jobs = runner.plan(self.config, ['all'])
        self.assertEqual(len(jobs), 39)
        self.assertEqual(jobs, runner.plan(self.config, ['all']))
        self.assertEqual(self.config, original)
        self.assertEqual(sum(j['parameters']['samples'] for j in jobs), 39000000)
        self.assertEqual({j['parameters']['bytes'] for j in jobs}, {2**i for i in range(11, 30)})
        self.assertEqual(list(self.config['capacity']['sweeps']), ['coarse'])

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
            for name in runner.SOURCE_FILES:
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

    def test_affinity_checks_actual_permission_and_restores_inherited_mask(self):
        with patch.object(runner.os, 'sched_getaffinity', return_value={0, 1}), \
                patch.object(runner.os, 'sched_setaffinity') as bind:
            runner.check_affinity(32)
        self.assertEqual([call.args for call in bind.call_args_list], [(0, {32}), (0, {0, 1})])
        with patch.object(runner.os, 'sched_getaffinity', return_value={0, 1}), \
                patch.object(runner.os, 'sched_setaffinity', side_effect=OSError('restricted')):
            with self.assertRaisesRegex(ValueError, 'Cannot bind'):
                runner.check_affinity(32)

    def test_round2_uses_measured_intervals_and_combines_controls(self):
        records = [dict(parameters=j['parameters']) for j in runner.plan(self.config, ['coarse'])]
        # Synthetic choices deliberately differ from the old Artemisia answer.
        intervals = dict(l1=(16 * 1024, 32 * 1024), l2=(512 * 1024, 1024 * 1024),
                         llc=(8 * 1024**2, 16 * 1024**2))
        config = planner.make_plan(self.config, records, 2, intervals)
        jobs = runner.plan(config, ['all'])
        self.assertEqual(len(jobs), 57)
        self.assertTrue(all(j['suite'] == 'round2' for j in jobs))
        self.assertEqual({j['parameters']['samples'] for j in jobs}, {1000000})
        self.assertEqual({j['parameters']['spacing'] for j in jobs}, {8, 64})
        self.assertEqual({j['parameters']['batch'] for j in jobs}, {256, 1024})
        self.assertEqual({j['parameters']['pages'] for j in jobs}, {'huge', 'base'})
        for level in ('l1', 'l2'):
            lo, hi = intervals[level]
            primary = [j['parameters'] for j in jobs if lo <= j['parameters']['bytes'] <= hi and
                       analyzer.family(j) == (64, 256, 'huge') and j['parameters']['mode'] == 'random']
            self.assertEqual(len(primary), 12)  # 9 sizes plus 3 independently rebuilt rings
            self.assertEqual(len({p['bytes'] for p in primary}), 9)
        with self.assertRaisesRegex(ValueError, 'must be measured'):
            planner.make_plan(self.config, records, 2, dict(intervals, l1=(17 * 1024, 32 * 1024)))
        with self.assertRaisesRegex(ValueError, 'needs the observed'):
            planner.make_plan(self.config, records, 2, {'llc': intervals['llc']})
        expanded = planner.make_plan(self.config, records, 2, intervals, [1024**3])
        self.assertEqual(len(runner.plan(expanded, ['all'])), 59)

    def test_round3_only_refines_selected_interval(self):
        records = [dict(parameters=j['parameters']) for j in runner.plan(self.config, ['coarse'])]
        config = planner.make_plan(self.config, records, 3, dict(l1=(16 * 1024, 32 * 1024)))
        jobs = runner.plan(config, ['all'])
        self.assertEqual(len(jobs), 11)
        self.assertTrue(all(16 * 1024 <= j['parameters']['bytes'] <= 32 * 1024 for j in jobs))
        self.assertEqual(planner.interval('2MiB:2.0625MiB'), (2097152, 2162688))

    def test_combining_rounds_preserves_repeat_identity_and_rejects_environment_changes(self):
        def record(run_id, cpu=32):
            return dict(name='same_point_name', record_id=f'{run_id}/same_point_name', run_id=run_id,
                        suite='round2', parameters=dict(bytes=32768, seed=1),
                        stats=dict(median=5 if run_id == 'r1' else 8),
                        environment=dict(cpu=cpu, numa_node=1, source_sha256='same source', timer='TSC',
                                         flags='-O0', model='synthetic', kernel='synthetic', page_size=4096))
        with patch.object(analyzer, 'load_records', side_effect=[[record('r1')], [record('r2')]]):
            ds = analyzer.load_study(ROOT, 'artemisia', ['r1', 'r2'])
        points = analyzer.representative(ds)
        self.assertEqual(points[0]['runs'], ['r1/same_point_name', 'r2/same_point_name'])
        self.assertEqual((points[0]['repeat_low'], points[0]['repeat_high']), (5, 8))
        with patch.object(analyzer, 'load_records', side_effect=[[record('r1')], [record('r2', cpu=4)]]):
            with self.assertRaisesRegex(ValueError, 'Incompatible rounds'):
                analyzer.load_study(ROOT, 'artemisia', ['r1', 'r2'])
        with self.assertRaisesRegex(ValueError, 'same run ID'):
            analyzer.load_study(ROOT, 'artemisia', ['r1', 'r1'])

    def test_planner_cli_and_combined_analysis_from_verified_raw_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / 'data/artemisia/r1'
            (data / 'raw').mkdir(parents=True)
            (data / 'logs').mkdir()
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/run_capacity.py', root / 'scripts/run_capacity.py')
            config = copy.deepcopy(self.config)
            sizes = [16 * 1024, 32 * 1024, 512 * 1024, 1024**2, 8 * 1024**2, 16 * 1024**2]
            config['capacity']['sweeps']['coarse']['points'] = [dict(bytes=w) for w in sizes]
            jobs = runner.plan(config, ['coarse'])
            payload = np.full(1000000, 1280, dtype='<u8').tobytes()
            for j in jobs:
                filename = f'raw/{j["name"]}.u64.gz'
                (data / filename).write_bytes(gzip.compress(payload))
                d = dict(**j, machine='artemisia', elapsed_seconds=1, raw_file=filename,
                         raw_sha256=hashlib.sha256(payload).hexdigest(),
                         environment=dict(cpu=32, numa_node=1, source_sha256='synthetic', timer='TSC',
                                          flags='-O0', model='synthetic', kernel='synthetic', page_size=4096))
                (data / 'logs' / f'{j["name"]}.json').write_text(json.dumps(d))
                j['status'] = 'complete'
            manifest = dict(status='complete', jobs=jobs)
            (data / 'manifest.json').write_text(json.dumps(manifest))
            (data / 'config.json').write_text(json.dumps(config))
            generated = root / 'configs/round2.json'
            argv = ['plan_capacity.py', '--machine', 'artemisia', '--from-runs', 'r1', '--round', '2',
                    '--l1', '16KiB:32KiB', '--l2', '512KiB:1MiB', '--llc', '8MiB:16MiB',
                    '--output', str(generated)]
            with patch.object(planner, 'ROOT', root), patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                planner.main()
                resolved = runner.load_config(generated)
                self.assertEqual(len(runner.plan(resolved, ['all'])), 57)
                self.assertEqual(len(resolved['planning']['evidence']), 6)
                with self.assertRaises(FileExistsError):
                    planner.main()
                generated.unlink()
                manifest['status'] = 'failed'
                (data / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'incomplete'):
                    planner.main()
                self.assertFalse(generated.exists())
            manifest['status'] = 'complete'
            (data / 'manifest.json').write_text(json.dumps(manifest))
            # Same point filenames across separate runs must remain distinct.
            shutil.copytree(data, root / 'data/artemisia/r2')
            argv = ['analyze_capacity.py', '--machine', 'artemisia', '--run-id', 'r1', 'r2', '--output-id', 'combined']
            with patch.object(analyzer, 'ROOT', root), patch.object(sys, 'argv', argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                analyzer.main()
            output = root / 'results/artemisia/combined'
            provenance = json.loads((output / 'provenance.json').read_text())
            self.assertEqual(provenance['run_ids'], ['r1', 'r2'])
            self.assertEqual(len(provenance['inputs']), 12)
            points = json.loads((output / 'capacity_points.json').read_text())["(64, 256, 'huge')"]['random']
            self.assertTrue(all(len(p['runs']) == 2 and p['runs'][0] != p['runs'][1] for p in points))
            self.assertTrue((output / 'transitions.csv').exists())
            self.assertTrue((output / 'figures/temporal_stability.pdf').exists())


if __name__ == '__main__':
    unittest.main()
