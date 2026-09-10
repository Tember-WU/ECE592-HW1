"""Final plan, original-file preservation, and runtime summary audit."""
import datetime as dt
import hashlib,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'scripts'))
from common import GROUPS,plan
preflight=Path(__file__).resolve().parent
data=root/'data/thunderbird/latency01'
out=root/'results/thunderbird/latency01'
config=json.loads((data/'config.json').read_text())
manifest=json.loads((data/'manifest.json').read_text())
env=json.loads((data/'environment.json').read_text())
validation=json.loads((out/'validation.json').read_text())
assert validation['passed'] and validation['full_seven_groups']
assert validation['configurations']==30 and validation['timed_batches']==30000000 and validation['recorded_intervals']==39000000
assert manifest['status']=='complete'
expected=plan(config)
assert len(expected)==len(manifest['jobs'])
for a,b in zip(expected,manifest['jobs']):
    assert all(a[k]==b[k] for k in ('name','group','parameters','columns')) and b['status']=='complete'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
old=json.loads((preflight/'original_files_sha256.json').read_text())
unchanged=[]; archived=[]
for name,digest in old.items():
    if sha(root/name)==digest:unchanged.append(name)
    else:
        backup=preflight/'source_before'/name
        assert name=='tests/test_latency.py' and backup.is_file() and sha(backup)==digest,name
        archived.append(dict(file=name,original_sha256=digest,original_copy=str(backup.relative_to(root)),current_sha256=sha(root/name)))
assert sha(root.parent/config['capacity_basis']['inference_file'])==config['capacity_basis']['inference_sha256']
assert sha(preflight/'capacity_inference.json')==config['capacity_basis']['inference_sha256']
records=[json.loads(p.read_text()) for p in sorted((data/'logs').glob('*.json'))]
for d in records:
    text=(data/'logs'/f'{d["name"]}.txt').read_text()
    mapped=int(re.search(r'\bmapped_bytes=(\d+)',text)[1])
    for mapping in re.findall(r'^numa_mapping:.*$',text,re.M):
        assert ' bind:0 ' in mapping
        nodes={int(n):int(k) for n,k in re.findall(r'\bN(\d+)=(\d+)',mapping)}
        assert nodes=={0:mapped//env['page_size']},nodes
quality=json.loads((out/'quality.json').read_text())
seconds=(dt.datetime.fromisoformat(manifest['finished_utc'])-dt.datetime.fromisoformat(manifest['started_utc'])).total_seconds()
keys=('measurement_minor_faults','major_faults','voluntary_switches','involuntary_switches')
events={k:dict(total=sum(d['runtime_events'][k] for d in records),maximum=max(d['runtime_events'][k] for d in records)) for k in keys}
report=dict(passed=True,checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),run_id='latency01',machine='thunderbird',all_planned_points_and_order_verified=True,group_counts={g:sum(d['group']==g for d in records) for g in GROUPS},original_files_unchanged=len(unchanged),modified_test_original_archived=archived,all_mapping_pages_accounted_for_on_node0=True,capacity_basis_hash_verified=True,wall_seconds=seconds,raw_bytes=validation['recorded_intervals']*8,raw_gzip_bytes=sum((data/d['raw_file']).stat().st_size for d in records),runtime_events=events,drift_flagged_points=[q['name'] for q in quality['records'] if q['drift_flag']],timer_frequency_hz=env['timer_frequency_hz'],timer_tick_ns=1e9/env['timer_frequency_hz'],cpu_frequency_khz={when:sorted({d[f'cpu_frequency_{when}'].get('scaling_cur_freq') for d in records}) for when in ('before','after')},audit_script_sha256=sha(Path(__file__)))
(out/'run_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
