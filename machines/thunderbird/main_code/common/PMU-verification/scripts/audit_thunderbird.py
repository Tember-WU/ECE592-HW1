#!/usr/bin/env python3
"""Read-only final audit of frozen evidence, source preservation and serial runs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    preflight = ROOT / 'preflight/thunderbird'
    frozen = json.loads((preflight / 'phase1_freeze.json').read_text())
    originals = json.loads((preflight / 'pmu_original_sha256.json').read_text())
    for name, info in frozen['files'].items():
        p = ROOT.parent / name
        assert p.stat().st_size == info['bytes'] and digest(p) == info['sha256'], name
    for name, expected in originals.items():
        assert digest(ROOT / name) == expected, name
    runs, previous_end = [], frozen['frozen_utc']
    for experiment, run_id in [('capacity', 'capacity01'), ('line_size', 'line_size01'),
                               ('associativity', 'associativity01'), ('capacity', 'll_diagnostic01')]:
        data = ROOT / experiment / 'data/thunderbird' / run_id
        result = ROOT / experiment / 'results/thunderbird' / run_id
        m = json.loads((data / 'manifest.json').read_text())
        v = json.loads((result / 'validation.json').read_text())
        assert m['status'] == 'complete' and v['status'] == 'passed'
        assert m['started_utc'] > previous_end
        previous_end = m['finished_utc']
        provenance = json.loads((data / 'provenance.json').read_text())
        for name, expected in provenance['source_sha256'].items():
            assert digest(data / 'source_snapshot' / name) == expected, name
        assert digest(data / 'build_snapshot' / (experiment + '_pmu')) == provenance['binary_sha256']
        assert digest(preflight / 'phase1_freeze.json') == provenance['phase1_freeze_sha256']
        runs.append(dict(experiment=experiment, run_id=run_id, points=v['configurations'],
                         timed_batches=v['timed_batches'], started_utc=m['started_utc'],
                         finished_utc=m['finished_utc'], validation='passed'))
    old = (ROOT.parent / 'timing-only/capacity/src/cache_bench_aarch64.c').read_text()
    new = (ROOT / 'capacity/src/cache_bench_aarch64.c').read_text()
    def kernel(s):
        return s[s.index('static uint64_t time_batch'):s.index('static void fail')]
    assert kernel(old) == kernel(new), 'Capacity timed assembly changed'
    for experiment in ('line_size', 'associativity'):
        assert (ROOT.parent / 'timing-only' / experiment / 'src/timer_compat.h').read_bytes() == (ROOT / experiment / 'src/timer_compat.h').read_bytes()
    audit = dict(status='passed', frozen_phase1_files_unchanged=len(frozen['files']),
                 original_pmu_files_unchanged=len(originals), runs= runs,
                 all_runs_serial=True, source_and_binary_snapshots_verified=True,
                 capacity_timed_kernel_identical_to_phase1=True, cpp_timer_headers_identical_to_phase1=True,
                 primary_timed_batches=sum(r['timed_batches'] for r in runs[:3]),
                 diagnostic_timed_batches=runs[3]['timed_batches'])
    out = ROOT / 'results/thunderbird'; out.mkdir(parents=True, exist_ok=True)
    (out / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
