"""Skylark provenance helpers; no changes to the frozen Phase-I files."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil

PMU = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_check():
    frozen = json.loads((PMU / 'skylark/phase1_frozen.json').read_text())
    changed = [p for p, h in frozen['sha256'].items()
               if not (PMU.parent / p).is_file() or sha(PMU.parent / p) != h]
    if changed:
        raise ValueError(f'Frozen Phase-I inputs changed: {changed}')
    return frozen


def snapshot_run(data, executable, config, manifest):
    frozen_check()
    snapshot = data / 'source'
    files = []
    for experiment in ('capacity', 'line_size', 'associativity'):
        files += list((PMU / experiment / 'src').glob('*'))
        files += list((PMU / experiment / 'scripts').glob('*.py'))
        files += [PMU / experiment / 'Makefile', PMU / experiment / 'configs/skylark.json', PMU / experiment / 'configs/skylark-refills.json']
    files += list((PMU / 'common').glob('*'))
    files += list((PMU / 'skylark').glob('*.py')) + list((PMU / 'skylark').glob('events*.json'))
    for source in files:
        if not source.is_file():
            continue
        target = snapshot / source.relative_to(PMU)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copy2(executable, data / 'benchmark.bin')
    shutil.copyfile(executable.with_suffix('.dis'), data / 'disassembly.txt')
    shutil.copyfile(PMU / 'skylark/phase1_frozen.json', data / 'phase1_frozen.json')
    provenance = dict(binary_sha256=sha(data / 'benchmark.bin'),
                      config_sha256=sha(data / 'config.json'),
                      phase1_freeze_sha256=sha(data / 'phase1_frozen.json'),
                      source_hashes={str(p.relative_to(snapshot)): sha(p)
                                     for p in snapshot.rglob('*') if p.is_file()})
    (data / 'snapshot_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    manifest['snapshot_provenance_sha256'] = sha(data / 'snapshot_provenance.json')


def analysis_provenance(data, output, script):
    frozen_check()
    source = json.loads((data / 'snapshot_provenance.json').read_text())
    manifest = json.loads((data / 'manifest.json').read_text())
    if sha(data / 'snapshot_provenance.json') != manifest['snapshot_provenance_sha256']:
        raise ValueError('Snapshot provenance changed')
    for key, filename in [('binary_sha256', 'benchmark.bin'), ('config_sha256', 'config.json'),
                          ('phase1_freeze_sha256', 'phase1_frozen.json')]:
        if sha(data / filename) != source[key]:
            raise ValueError('Snapshot checksum mismatch: ' + filename)
    for name, checksum in source['source_hashes'].items():
        if sha(data / 'source' / name) != checksum:
            raise ValueError('Source snapshot checksum mismatch: ' + name)
    target = output / 'analysis_source'
    target.mkdir(exist_ok=True)
    for path in (PMU / 'skylark').glob('*.py'):
        shutil.copyfile(path, target / path.name)
    record = dict(generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                  analysis_sha256=sha(script), manifest_sha256=sha(data / 'manifest.json'),
                  config_sha256=sha(data / 'config.json'), frozen_phase1_unchanged=True,
                  all_source_and_executable_snapshots_verified=True,
                  event_definitions=json.loads((data / 'config.json').read_text())['events'],
                  analysis_source_hashes={p.name: sha(p) for p in target.glob('*.py')})
    (output / 'provenance.json').write_text(json.dumps(record, indent=2) + '\n')
