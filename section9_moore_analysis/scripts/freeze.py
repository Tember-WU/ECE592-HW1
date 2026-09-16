#!/usr/bin/env python3
"""Save a local prediction snapshot with hashes. Never stage, commit, tag, or push."""
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def main():
    directory = HERE / 'freeze'
    directory.mkdir(exist_ok=True)
    path = directory / 'manifest.json'
    if path.exists():
        raise SystemExit('A local snapshot manifest already exists; it will not be overwritten.')
    validation = json.loads(subprocess.check_output(
        [sys.executable, str(HERE/'scripts/validate.py'), '--check-upstream'],
        cwd=HERE.parent, text=True))
    (HERE/'tables/output_validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    files = {}
    for item in sorted(HERE.rglob('*')):
        rel = item.relative_to(HERE)
        if not item.is_file() or any(v in rel.parts for v in ['.cache','.venv','__pycache__']):
            continue
        if str(rel) == 'freeze/manifest.json':
            continue
        data = item.read_bytes()
        files[str(rel)] = {'sha256':hashlib.sha256(data).hexdigest(), 'bytes':len(data)}
    manifest = {
        'schema_version':2,
        'snapshot_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'local_file_snapshot_only',
        'git_commit':None,
        'git_tag':None,
        'git_action_policy':'No staging, commits, tags, or pushes; user requested no commits.',
        'scope':'Chronological lab results, quantitative trends, and lab-only Hazel predictions',
        'training_hosts':['sunbird','charnwood','ookay','upgrade','crux','skylark','thunderbird','artemisia'],
        'hazel_observations_used':0,
        'target_cache_specifications_used_in_model':False,
        'experiment_ordering_basis':'Team declaration in inputs/pre_freeze_declaration.json; not independently audited',
        'python':platform.python_version(),
        'packages':{name:importlib.metadata.version(name) for name in ['numpy','matplotlib','Pillow']},
        'hash_scope':'All payload files except this manifest and ignored caches',
        'files':files,
    }
    path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':'local_snapshot_saved','files_hashed':len(files),'git_commit':None,'git_tag':None}))


if __name__ == '__main__':
    main()
