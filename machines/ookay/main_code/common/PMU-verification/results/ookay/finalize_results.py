"""Audit preserved Ookay outputs and save post-run reproduction artifacts."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PMU = HERE.parents[1]
REPO = PMU.parent
RUNS = [('capacity', 'capacity01'), ('line_size', 'line_size01'),
        ('associativity', 'associativity01'), ('associativity', 'associativity02'),
        ('line_size', 'line_size02')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


freeze = json.loads((HERE / 'phase1-freeze01/manifest.json').read_text())
for item in freeze['files']:
    assert sha(REPO / item['path']) == item['sha256'], item['path']
    assert sha(HERE / 'phase1-freeze01' / item['snapshot']) == item['sha256']

audits = []
previous_end = ''
for experiment, run in RUNS:
    data = PMU / experiment / 'data/ookay' / run
    result = PMU / experiment / 'results/ookay' / run
    manifest = json.loads((data / 'manifest.json').read_text())
    validation = json.loads((result / 'validation.json').read_text())
    quality = json.loads((result / 'quality.json').read_text())
    rows = list(csv.DictReader((result / 'summary.csv').open()))
    assert manifest['status'] == 'complete' and validation['status'] == 'passed'
    assert manifest['started_utc'] > previous_end
    previous_end = manifest['finished_utc']
    compressed_bytes = 0
    for job in manifest['jobs']:
        raw, counts = data / job['raw_file'], data / job['counts_file']
        assert sha(raw) == job['raw_sha256']
        assert sha(counts) == job['counts_sha256']
        assert len(gzip.decompress(raw.read_bytes())) == 8_000_000
        counter = json.loads(counts.read_text())
        assert counter['time_enabled_ns'] == counter['time_running_ns'] > 0
        assert len(counter['events']) == 4
        assert job['returncode'] == 0 and job['status'] == 'complete'
        compressed_bytes += raw.stat().st_size
    assert len(rows) == len(manifest['jobs']) == validation.get('configurations', validation.get('points'))
    assert all(int(row['n']) == 1_000_000 for row in rows)
    temporal = quality.get('temporal_max_min', quality.get('temporal_median_max_min'))
    worst = max(temporal, key=temporal.get)
    audits.append(dict(experiment=experiment, run_id=run,
        configurations=len(rows), timed_batches=validation['timed_batches'],
        started_utc=manifest['started_utc'], finished_utc=manifest['finished_utc'],
        collection_elapsed_seconds=manifest['elapsed_seconds'],
        compressed_raw_bytes=compressed_bytes,
        worst_temporal_point=worst, worst_decile_median_max_min=temporal[worst],
        max_sibling_busy_percent=quality['max_sibling_busy_percent'],
        minor_faults=quality['total_minor_faults'],
        major_faults=quality['total_major_faults'],
        involuntary_switches=quality['total_involuntary_switches'],
        data=str(data.relative_to(PMU)), results=str(result.relative_to(PMU)),
        integrity_status='passed', all_four_event_groups_without_multiplexing=True))

save(HERE / 'verification_summary.json', dict(
    audited_utc=datetime.now(timezone.utc).isoformat(), machine='ookay',
    phase1_original_and_snapshot_hashes_unchanged=len(freeze['files']),
    serial_collection_verified=True, configurations=sum(x['configurations'] for x in audits),
    timed_batches=sum(x['timed_batches'] for x in audits),
    compressed_raw_bytes=sum(x['compressed_raw_bytes'] for x in audits),
    uncompressed_raw_bytes=sum(x['timed_batches'] * 8 for x in audits),
    status='passed', scope='Integrity and scheduling audit; quality limitations remain in the report.',
    runs=audits))

archive = HERE / 'reproduction01'
entries = []
paths = [Path(__file__)]
for part in ('capacity', 'line_size', 'associativity', 'common', 'events'):
    for path in (PMU / part).rglob('*'):
        rel = path.relative_to(PMU / part)
        if any(x in rel.parts for x in ('data', 'results', 'build', '__pycache__')):
            continue
        if path.is_file() and (path.suffix in ('.c', '.cpp', '.h', '.hpp', '.py') or
                              path.name in ('Makefile', 'requirements.txt') or
                              (path.parent.name == 'configs' and path.name.startswith('ookay'))):
            paths.append(path)
for path in sorted(paths):
    target = archive / 'source' / path.relative_to(PMU)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    entries.append(dict(source=str(path.relative_to(PMU)), snapshot=str(target.relative_to(archive)),
                        sha256=sha(target), bytes=target.stat().st_size))
for experiment, binary in [('capacity', 'cache_capacity_pmu'), ('line_size', 'line_size_pmu'),
                           ('associativity', 'associativity_pmu')]:
    for name in (binary, binary + '.dis'):
        path = PMU / experiment / 'build/ookay' / name
        target = archive / 'build' / experiment / (name + '.gz')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
        entries.append(dict(source=str(path.relative_to(PMU)), snapshot=str(target.relative_to(archive)),
                            sha256=sha(target), uncompressed_sha256=sha(path),
                            bytes=target.stat().st_size))
save(archive / 'manifest.json', dict(created_utc=datetime.now(timezone.utc).isoformat(),
    scope='Post-run source/build archive. Kernel sources were unchanged during collection; '
          'binary hashes were taken after collection, not at process launch. '
          'Analysis was regenerated using these final scripts. Per-run configs/commands/build logs '
          'remain authoritative. Phase-I freeze is a separate pre-run archive.', files=entries))

# Export the comparison table verbatim as CSV for the assignment report.
lines = (HERE / 'SECTION_8_3_REPORT.md').read_text().splitlines()
table = []
for line in lines:
    if line.startswith('| Property |'):
        table = [[s.strip() for s in line.strip('|').split('|')]]
    elif table and line.startswith('|'):
        if not line.startswith('|---'):
            table.append([s.strip() for s in line.strip('|').split('|')])
    elif table:
        break
assert table and all(len(row) == 6 for row in table)
with (HERE / 'comparison.csv').open('w', newline='') as handle:
    csv.writer(handle).writerows(table)
print(json.dumps({'status': 'passed', 'runs': len(audits),
                  'configurations': sum(x['configurations'] for x in audits),
                  'frozen_files_unchanged': len(freeze['files']), 'archived_files': len(entries)}))
