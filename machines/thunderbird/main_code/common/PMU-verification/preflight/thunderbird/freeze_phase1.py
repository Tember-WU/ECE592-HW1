"""Freeze existing evidence before hardware-event and specification verification."""
import datetime as dt,hashlib,json,subprocess
from pathlib import Path
pmu=Path(__file__).resolve().parents[2]; repo=pmu.parent
out=Path(__file__).resolve().parent
assert not (out/'phase1_freeze.json').exists(),'Freeze already exists'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
original={str(Path(name)):digest(pmu/name) for name in subprocess.check_output(['git','ls-files','-z','.'],cwd=pmu).decode().split('\0') if name and (pmu/name).is_file()}
(out/'pmu_original_sha256.json').write_text(json.dumps(original,indent=2)+'\n')
paths=set()
for exp in ('capacity','line_size','associativity','latency','inclusion'):
    root=repo/'timing-only'/exp
    for sub in ('data/thunderbird','results/thunderbird','src','scripts'):
        paths.update(p for p in (root/sub).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.update(root.glob('configs/thunderbird*.json'))
    for name in ('Makefile','README.md','requirements.txt'):
        if (root/name).is_file():paths.add(root/name)
hashes={str(p.relative_to(repo)):dict(sha256=digest(p),bytes=p.stat().st_size) for p in sorted(paths)}
freeze=dict(machine='thunderbird',frozen_utc=dt.datetime.now(dt.timezone.utc).isoformat(),scope='Existing Thunderbird Phase-I evidence and sources; immutable hash inventory, before PMU discovery and new system/vendor comparison',files=hashes,original_pmu_files=len(original),total_bytes=sum(x['bytes'] for x in hashes.values()))
(out/'phase1_freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
print('Frozen Phase-I files:',len(hashes),'bytes:',freeze['total_bytes'],'original PMU files:',len(original))
