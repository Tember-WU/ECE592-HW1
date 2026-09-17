#!/usr/bin/env python3
"""Copy experiment evidence into machine-first submission folders.

Never edit sources or measurements. Large raw CSVs are losslessly compressed.
Every archived file has a reversible source path and SHA-256 in manifest.jsonl.
"""
import argparse
from collections import Counter
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

REPO = Path(__file__).resolve().parents[2]
DEST = REPO / 'machines'
MACHINES = ['sunbird', 'artemisia', 'charnwood', 'ookay', 'upgrade', 'crux', 'skylark', 'thunderbird']
ROOTS = ['timing-only', 'PMU-verification', 'PMU_Counter_Analysis', 'software-hit-rate']
EXPERIMENTS = ['capacity', 'line_size', 'associativity', 'inclusion_policy', 'latency', 'pmu', 'software_hit_rate']
CACHE_DIRS = {'.git', '.venv', 'venv', '__pycache__', '.pytest_cache'}
NATIVE = {'.c', '.h', '.cpp', '.hpp', '.cc', '.S'}
CODE = NATIVE | {'.py', '.sh'}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def owners(rel):
    # Outermost owning directory wins over erroneous/nested historical names.
    # In particular, never relabel Thunderbird's misplaced Artemisia JSON.
    for part in rel.parts:
        if part.startswith('comparison_'):
            return ['cross_machine']
        if part in MACHINES:
            return [part]
    named = [m for m in MACHINES if re.search(r'(^|[^a-z])' + m + r'([^a-z]|$)', rel.name.lower())]
    return named if len(named) == 1 else MACHINES


def native_arch(path):
    text = path.read_text(errors='replace')
    arm = '__aarch64__' in text or 'cntvct_el0' in text or 'aarch64' in path.name
    x86 = '__x86_64__' in text or 'rdtsc' in text or '%%rax' in text
    if arm and not x86:
        return 'aarch64'
    if x86 and not arm:
        return 'x86_64'
    return 'common'


def is_build(path, rel):
    name = path.name.lower()
    if 'build' in rel.parts or 'compiled' in rel.parts:
        return True
    if path.suffix in {'.dis', '.bin', '.o', '.asm'}:
        return True
    if name.startswith(('build-', 'build_', 'compile-')) or name in {'build.log', 'compiler.txt', 'compiler-version.txt'}:
        return True
    if path.stat().st_size:
        with path.open('rb') as f:
            return f.read(4) == b'\x7fELF'
    return False


def route(path, rel):
    """Return category, relative destination (below one machine directory)."""
    parts = rel.parts
    # Compiler/build provenance belongs in build; source and processing code are
    # kept separately even when originally embedded inside a raw/results run.
    if is_build(path, rel):
        return 'build', Path('build') / rel
    if path.suffix in CODE:
        arch = native_arch(path) if path.suffix in NATIVE else 'common'
        return 'code', Path('main_code') / arch / rel
    code_context = (len(parts) <= 2 or 'configs' in parts or 'source' in parts or
                    'scripts' in parts or 'src' in parts or 'tests' in parts)
    # Source archives carry their own configs/docs/hash files; preserve them.
    if code_context and not any(a in parts for a in ['raw', 'raw_data', 'raw_data_inclusion']):
        return 'code', Path('main_code/common') / rel
    if parts[0] == 'timing-only':
        ex = 'inclusion_policy' if parts[1] == 'inclusion' else parts[1]
        if ex not in EXPERIMENTS:
            return 'code', Path('main_code/common') / rel
        tail = parts[2:]
        processed = 'results' in tail or 'stats' in tail or path.suffix in {'.pdf', '.png', '.svg'}
        if ex == 'associativity' and path.suffix == '.csv':
            with path.open() as f:
                header = f.readline().replace(' ', '').lower()
            processed |= 'median_latency' in header and 'eviction_probability' in header
        if ex == 'inclusion_policy' and path.name in {'inclusion_report.json', 'capacity_sweep.csv', 'find_conflict_summary.csv'}:
            processed = True
        branch = 'processed' if processed else 'raw'
        return branch, Path(ex) / branch / Path(*tail)
    if parts[0] == 'PMU-verification':
        processed = ('results' in parts or 'reports' in parts or path.suffix in {'.pdf', '.png', '.svg'} and
                     not any(a in parts for a in ['references', 'vendor']))
        branch = 'processed' if processed else 'raw'
        return branch, Path('pmu') / branch / 'verification' / Path(*parts[1:])
    if parts[0] == 'PMU_Counter_Analysis':
        processed = ('analysis' in parts or any(p.startswith('comparison_') for p in parts) or
                     path.name in {'RUN_NOTES.md', 'REPORT.md'} or 'figures' in parts)
        branch = 'processed' if processed else 'raw'
        return branch, Path('pmu') / branch / 'counter_analysis' / Path(*parts[1:])
    processed = 'results' in parts or path.name == 'model.json'
    branch = 'processed' if processed else 'raw'
    return branch, Path('software_hit_rate') / branch / Path(*parts[1:])


def plan():
    entries, excluded = [], []
    for root in ROOTS:
        if not (REPO / root).is_dir():
            raise RuntimeError(f'Missing source directory: {root}')
        for directory, dirs, files in os.walk(REPO / root):
            for d in dirs:
                if d in CACHE_DIRS:
                    excluded.append({'source': str((Path(directory) / d).relative_to(REPO)), 'reason': 'virtual environment or tool cache'})
            dirs[:] = sorted(d for d in dirs if d not in CACHE_DIRS)
            for name in sorted(files):
                p = Path(directory) / name; rel = p.relative_to(REPO)
                if p.is_symlink():
                    raise RuntimeError(f'Review source symlink before packaging: {rel}')
                if name == 'AGENTS.md' or name.endswith(('.pyc', '.pyo')):
                    excluded.append({'source': str(rel), 'reason': 'agent instructions or Python cache'})
                    continue
                # Live unowned binaries next to shared source do not establish
                # the executable used on a particular machine. Run archives do.
                if 'src' in rel.parts and len(rel.parts) <= 4 and not p.suffix:
                    with p.open('rb') as f:
                        if f.read(4) == b'\x7fELF':
                            excluded.append({'source': str(rel), 'reason': 'unowned rebuildable working binary; per-run binaries/source retained'})
                            continue
                category, target = route(p, rel)
                compress = category == 'raw' and p.suffix == '.csv' and p.stat().st_size >= 1024 * 1024
                if compress:
                    target = target.with_name(target.name + '.gz')
                for machine in owners(rel):
                    entries.append({'machine': machine, 'source': str(rel), 'destination': str(target),
                                    'category': category, 'encoding': 'gzip' if compress else 'identity',
                                    'source_bytes': p.stat().st_size, 'source_mode': p.stat().st_mode & 0o777})
    keys = [(e['machine'], e['destination']) for e in entries]
    if len(keys) != len(set(keys)):
        raise RuntimeError('Destination collision in packaging plan')
    return entries, excluded


def copy_one(e):
    src, dst = REPO / e['source'], DEST / e['machine'] / e['destination']
    if dst.exists():
        raise RuntimeError(f'Refusing to overwrite {dst}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    before = src.stat(); sha = hashlib.sha256()
    with src.open('rb') as stream, dst.open('wb') as target:
        encoded = gzip.GzipFile(filename='', mode='wb', fileobj=target, mtime=0, compresslevel=6) if e['encoding'] == 'gzip' else target
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            sha.update(chunk); encoded.write(chunk)
        if encoded is not target:
            encoded.close()
    after = src.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f'Source changed while copying {src}')
    if e['encoding'] == 'identity':
        shutil.copystat(src, dst)
    e.update(source_sha256=sha.hexdigest(), archive_bytes=dst.stat().st_size)
    return e


def command_records(entries):
    """Index exact recorded values; never invent missing historical commands."""
    for e in entries:
        p = REPO / e['source']
        if p.suffix != '.json' or p.stat().st_size > 5 * 1024 * 1024:
            continue
        try:
            obj = json.loads(p.read_text())
        except (ValueError, UnicodeError):
            continue
        def walk(value, pointer=''):
            if isinstance(value, dict):
                for k, v in value.items():
                    key = pointer + '/' + k
                    if k in {'command', 'commands', 'build_command', 'compile_command', 'compiler', 'cflags', 'cxxflags', 'build_flags', 'argv'}:
                        yield {'source': e['source'], 'archive_file': e['destination'], 'json_pointer': key, 'value': v}
                    else:
                        yield from walk(v, key)
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    yield from walk(v, pointer + '/' + str(i))
        yield from walk(obj)


def coverage(machine):
    def files(path):
        return sum(1 for p in (REPO / path).rglob('*') if p.is_file() and p.name != '.gitkeep') if (REPO / path).exists() else 0
    result = {e: files(f'timing-only/{e}/data/{machine}') for e in ['capacity', 'line_size', 'associativity', 'latency', 'inclusion']}
    result['pmu_verification'] = sum(files(f'PMU-verification/{e}/data/{machine}') for e in ['capacity', 'line_size', 'associativity'])
    result['counter_analysis'] = files(f'PMU_Counter_Analysis/results/{machine}')
    result['software_hit_rate'] = files(f'software-hit-rate/data/{machine}')
    return result


def write_processing_indexes(machine, entries):
    for experiment in EXPERIMENTS:
        subset = [e for e in entries if e['destination'].startswith(experiment + '/')]
        if not subset:
            continue
        processed = [e for e in subset if e['category'] == 'processed']
        if not processed:
            continue
        destination = DEST / machine / experiment / 'processed' / 'README.md'
        text = [f'# {machine}: {experiment} processed evidence', '',
                'These are the original statistics, figures and interpretation records. '
                'No scientific result was recalculated or relabeled during packaging.', '',
                '[Machine overview](../../README.md) · [File mapping and hashes](../../manifest.jsonl) · '
                '[Exact recorded commands](../../build/recorded_commands.jsonl) · [Raw inputs and provenance](../raw/)', '',
                'Use the manifest to translate original file paths in a plot/report/analysis provenance record '
                'to their packaged locations. The original analysis source and per-run source snapshots are '
                'under `../../main_code/`. To run an original plotting script or follow its original relative '
                'links, restore the layout with `machines/tools/restore_layout.py` as described in the machine README.', '',
                f'This experiment contains {len(processed)} processed files and '
                f'{sum(e["category"] == "raw" for e in subset)} raw/provenance files in the export. '
                'Historical missing inputs and ambiguous conclusions remain the limitations of the original run.', '']
        destination.write_text('\n'.join(text))


def write_readme(machine, entries):
    base = DEST / machine
    isa = 'aarch64' if machine == 'thunderbird' else 'x86_64'
    counts = Counter(e['category'] for e in entries)
    info = coverage(machine)
    text = [f'# {machine}: machine-organized experiment evidence', '',
            f'Platform: **{isa}**. This is a byte-preserving export of the repository material for Sections 8.2–8.5. '
            'Large raw CSV files are stored as lossless gzip; their hashes refer to the original uncompressed bytes. '
            'Packaging does not rerun experiments, correct measurements or certify scientific conclusions.', '',
            '| Folder | Contents |', '|---|---|',
            '| `main_code/x86_64`, `main_code/aarch64`, `main_code/common` | Architecture-specific native code, portable code, scripts/configs, and per-run source snapshots; original paths distinguish versions |',
            '| `build` | Existing compiler/build logs, archived executables/disassembly, and an index of exact recorded commands |',
            '| `capacity`, `line_size`, `associativity`, `inclusion_policy`, `latency` | Section 8.2; raw measurements/provenance versus derived statistics/figures |',
            '| `pmu/raw/verification`, `pmu/processed/verification` | Section 8.3 events, capacity/stride/conflict verification, references and reports |',
            '| `pmu/raw/counter_analysis`, `pmu/processed/counter_analysis` | Section 8.4 per-machine eight-event measurements and analysis |',
            '| `software_hit_rate/raw`, `software_hit_rate/processed` | Section 8.5 estimator calibration, frozen parameters, PMU comparison and uncertainty |', '',
            '## Exact provenance and commands', '',
            '[manifest.jsonl](manifest.jsonl) maps every packaged file to its repository-relative original path, '
            'SHA-256, compression method and byte count. '
            '[build/recorded_commands.jsonl](build/recorded_commands.jsonl) indexes original build/run command values '
            'and compiler descriptions with the source file and JSON pointer. Original absolute paths are evidence; '
            'they have not been rewritten or presented as commands that can be executed verbatim on another host.', '',
            'Environment and pinning may differ between experiments and runs. Read the archived per-run '
            '`environment.json`, `metadata.json`, pinning manifests and build logs rather than assuming one CPU/NUMA '
            'binding for every experiment. The current shared source and older per-run source snapshots are both '
            'preserved; the latter identifies the implementation used by an existing run. Match report listings to '
            'the appropriate snapshot before submission.', '',
            '## Restore a runnable original layout', '',
            'The classification intentionally separates source, build records and data. Existing scripts and report '
            'links expect their original relative layout. The restoration tool copies files and decompresses CSVs '
            'into a **new** directory without depending on the four original experiment directories:', '',
            '```bash', '# Run from ECE592-HW1; choose a new output directory',
            f'python3 machines/tools/restore_layout.py --machine {machine} --output /tmp/ece592-{machine}-restored',
            f'cd /tmp/ece592-{machine}-restored', '```', '',
            'Restoration starts no experiments. Typical entry points below use the restored layout. Native collection '
            f'must run on **{machine}**, using its saved configs and a new run ID. For exact historical arguments '
            'and compilers, follow the command index above. Some collectors require a Git checkout for provenance; '
            'when collecting outside the original repository, initialize and commit the restored source/configs '
            'in a new repository first. The export records the original commit but does not embed Git history.', '',
            '```bash', f'make -C timing-only/capacity MACHINE={machine}',
            f'(cd timing-only/capacity && python3 scripts/run_capacity.py --machine {machine} --run-id NEW_RUN)',
            f'make -C timing-only/latency MACHINE={machine}',
            f'(cd timing-only/latency && python3 scripts/run_latency.py --machine {machine} --run-id NEW_RUN)',
            '# Section 8.4 (uses the actual host and its configuration)',
            'make -C PMU_Counter_Analysis',
            '(cd PMU_Counter_Analysis && python3 scripts/run.py --run-id NEW_RUN)', '```', '',
            'Line-size/associativity/inclusion scripts have legacy working-directory assumptions; their exact source '
            'and configs are supplied. See the original script headers and archived run commands. '
            'Do not blindly run the copied line-size Makefile: its current default target references the associativity '
            'source. The direct compile command/source record is the appropriate entry point. Missing historical '
            'compiler/command evidence is not reconstructed by guessing.', '',
            'Section 8.3 uses host-specific workflows. In the restored `PMU-verification/`, start with '
            '`README.md`, `SKYLARK.md` (AMD), or `THUNDERBIRD.md` (Arm), and the relevant per-host run notes. '
            'Do not transfer raw PMU event encodings between architectures.', '',
            '## Coverage and preserved limitations', '',
            '| Source experiment | Existing evidence files |', '|---|---:|']
    text += [f'| {k} | {v} |' for k, v in info.items()]
    text += ['', 'Counts indicate material present, not a passing experiment. Failed/retried/preflight runs are retained '
             'with their original status. Association sweep files containing only medians/eviction probabilities '
             'are classified as processed data; packaging cannot recreate missing raw distributions. '
             'Inclusion verdicts and low sample counts remain unchanged and require the limitations documented '
             'in the experiment/PMU reports.', '']
    if not info['software_hit_rate']:
        text += ['**Section 8.5: no machine-specific configuration/run was found in the supplied source tree.** '
                 'The raw/processed folders are placeholders; shared estimator code is included for later adaptation. '
                 'No results from another host have been substituted.', '']
    elif machine == 'sunbird':
        text += ['Section 8.5 has a completed collection but also a documented large classification error. '
                 'Read the preserved `SUNBIRD_NOTES.md`; this export does not label it an accurate estimator.', '']
    if machine == 'thunderbird':
        text += ['The original inclusion directory contains an inner `artemisia` path and JSON machine label. '
                 'It remains under the outer Thunderbird owner with its original name and content; ownership is '
                 'ambiguous and is not repaired by relabeling.', '']
    text += ['Cross-machine Section 8.4 comparisons, including historical partial comparisons and the final '
             'eight-host comparison, are under `../cross_machine/pmu/processed/counter_analysis/`. '
             'Restore with `--machine all` to reproduce their multi-host analysis.', '',
             f'Exported files: {len(entries)}; categories: {dict(counts)}.', '']
    (base / 'README.md').write_text('\n'.join(text))
    (base / 'build' / 'README.md').write_text(
        '# Build and execution provenance\n\n'
        '`recorded_commands.jsonl` is an index of exact command/compiler values already present in the source evidence. '
        'It is not a script to execute. Each entry records the original file, packaged file and JSON pointer. '
        'This folder also preserves existing build logs and binary/disassembly snapshots under their original paths. '
        'Shared Makefiles and source files are under `../main_code/`; restore the original layout to build them. '
        'No compiler version or historical command has been invented when the source did not record one.\n')
    with (base / 'build' / 'recorded_commands.jsonl').open('w') as f:
        for row in command_records(entries):
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    write_processing_indexes(machine, entries)


def build(entries, excluded):
    for m in MACHINES + ['cross_machine']:
        if (DEST / m / 'manifest.jsonl').exists():
            raise RuntimeError('An export already exists; verify it or build a new export after explicit review')
    # Establish the requested skeleton before adding evidence.
    for m in MACHINES + ['hazel_haswell', 'hazel_genoa']:
        for d in ['main_code/x86_64', 'main_code/aarch64', 'main_code/common', 'build'] + [f'{e}/{b}' for e in EXPERIMENTS for b in ['raw', 'processed']]:
            (DEST / m / d).mkdir(parents=True, exist_ok=True)
        if m.startswith('hazel_'):
            (DEST / m / 'slurm').mkdir(exist_ok=True)
            (DEST / m / 'README.md').write_text('# ' + m + '\n\nEmpty template matching the assignment example. '
                'No measurements, allocation, job submission or machine availability are claimed.\n')
    manifests = {}
    for m in MACHINES + ['cross_machine']:
        (DEST / m).mkdir(exist_ok=True)
        manifests[m] = (DEST / m / 'manifest.jsonl').open('w')
    start = time.monotonic(); last = start
    try:
        for i, e in enumerate(entries, 1):
            row = copy_one(e)
            manifests[e['machine']].write(json.dumps(row, ensure_ascii=False) + '\n')
            if time.monotonic() - last > 8:
                print(f'Copied {i}/{len(entries)} files ({time.monotonic()-start:.0f}s)', flush=True)
                last = time.monotonic()
    finally:
        for f in manifests.values():
            f.close()
    for m in MACHINES:
        write_readme(m, [e for e in entries if e['machine'] == m])
    (DEST / 'cross_machine' / 'README.md').write_text(
        '# Cross-machine evidence\n\nAll existing Section 8.4 comparison outputs are retained, including the earlier subsets. '
        'The final eight-machine comparison is `pmu/processed/counter_analysis/results/'
        'comparison_artemisia_skylark_sunbird_thunderbird_charnwood_crux_ookay_upgrade01/`. '
        'Its analysis provenance identifies input runs. Restore `--machine all` to supply the original eight input directories. '
        'The source/destination mapping is in `manifest.jsonl`.\n')
    # Empty branches remain visible in Git without claiming data exist.
    for directory, dirs, files in os.walk(DEST):
        if not dirs and not files:
            (Path(directory) / '.gitkeep').touch()
    save(DEST / 'export_summary.json', {
        'created_utc': now(), 'source_git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
        'source_roots': ROOTS, 'file_count': len(entries), 'by_machine': dict(Counter(e['machine'] for e in entries)),
        'source_bytes_with_shared_copies': sum(e['source_bytes'] for e in entries),
        'archive_bytes': sum(e['archive_bytes'] for e in entries), 'coverage': {m: coverage(m) for m in MACHINES},
        'source_directories_modified': False, 'experiments_rerun': False})
    save(DEST / 'excluded.json', excluded)
    print('Export complete', flush=True)


def verify():
    count = 0; sources = {}; start = time.monotonic(); last = start
    for m in MACHINES + ['cross_machine']:
        for line in (DEST / m / 'manifest.jsonl').read_text().splitlines():
            e = json.loads(line); p = DEST / m / e['destination']
            sha = hashlib.sha256(); size = 0
            stream = gzip.open(p, 'rb') if e['encoding'] == 'gzip' else p.open('rb')
            with stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    sha.update(chunk); size += len(chunk)
            if sha.hexdigest() != e['source_sha256'] or size != e['source_bytes']:
                raise RuntimeError(f'Archive mismatch: {p}')
            if e['source'] not in sources:
                original = hashlib.sha256()
                with (REPO / e['source']).open('rb') as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b''):
                        original.update(chunk)
                sources[e['source']] = original.hexdigest()
            if sources[e['source']] != e['source_sha256']:
                raise RuntimeError(f'Source changed: {e["source"]}')
            count += 1
            if time.monotonic() - last > 8:
                print(f'Verified {count} files ({time.monotonic()-start:.0f}s)', flush=True); last = time.monotonic()
    expected, _ = plan()
    actual = set()
    for m in MACHINES + ['cross_machine']:
        actual.update((m, json.loads(s)['source']) for s in (DEST / m / 'manifest.jsonl').read_text().splitlines())
    if actual != {(e['machine'], e['source']) for e in expected}:
        raise RuntimeError('Input coverage changed or a planned source is missing')
    report = {'status': 'passed', 'checked_utc': now(), 'archived_files_verified': count,
              'unique_source_files_verified_unchanged': len(sources), 'source_coverage_complete': True,
              'verification': 'All archived files decoded and hashed; compared to source bytes and live source SHA-256',
              'scope': 'Packaging integrity and input coverage, not validity of scientific conclusions'}
    save(DEST / 'verification.json', report); print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('action', choices=['plan', 'build', 'verify']); args = p.parse_args()
    if args.action == 'verify':
        verify()
    else:
        entries, excluded = plan()
        print(json.dumps({'files': len(entries), 'machines': dict(Counter(e['machine'] for e in entries)),
                          'source_MiB_with_copies': round(sum(e['source_bytes'] for e in entries)/2**20, 1),
                          'gzip_csv_files': sum(e['encoding']=='gzip' for e in entries),
                          'excluded': len(excluded)}, indent=2), flush=True)
        if args.action == 'build':
            build(entries, excluded)
