#!/usr/bin/env python3
"""Reconstruct selected original experiment trees using only machines/ files."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def safe(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Unsafe archive path: {relative}')
    return root / path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--machine', required=True, help='one machine, or all')
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        p.error('Output must be a new directory; existing files are never overwritten')
    folders = sorted(d for d in PACKAGE.iterdir() if (d / 'manifest.jsonl').exists()) if args.machine == 'all' else [PACKAGE / args.machine]
    rows = {}
    for directory in folders:
        manifest = directory / 'manifest.jsonl'
        if not manifest.is_file():
            p.error(f'No exported measurements for {directory.name}')
        for line in manifest.read_text().splitlines():
            row = json.loads(line)
            previous = rows.get(row['source'])
            if previous and previous[1]['source_sha256'] != row['source_sha256']:
                raise ValueError('Shared source snapshots disagree')
            rows[row['source']] = (directory, row)
    args.output.mkdir(parents=True)
    restored = 0
    for directory, row in rows.values():
        src = safe(directory, row['destination']); dst = safe(args.output, row['source'])
        dst.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256(); size = 0
        stream = gzip.open(src, 'rb') if row['encoding'] == 'gzip' else src.open('rb')
        with stream, dst.open('xb') as target:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(chunk); size += len(chunk); target.write(chunk)
        if sha.hexdigest() != row['source_sha256'] or size != row['source_bytes']:
            raise ValueError(f'Restored hash/count mismatch: {row["source"]}')
        os.chmod(dst, row['source_mode'])
        restored += 1
        if restored % 2000 == 0:
            print(f'Restored {restored}/{len(rows)} files', flush=True)
    (args.output / 'RESTORATION.json').write_text(json.dumps({
        'status': 'passed', 'machine_selection': args.machine, 'files_restored_and_sha256_verified': restored,
        'source': str(PACKAGE), 'measurements_executed': False}, indent=2) + '\n')
    print(f'Restored and verified {restored} files to {args.output}; no measurements executed.')


if __name__ == '__main__':
    main()
