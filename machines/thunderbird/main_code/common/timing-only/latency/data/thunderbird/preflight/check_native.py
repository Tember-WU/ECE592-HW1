"""Native architecture and page checks; excluded from formal latency samples."""
import gzip,hashlib,json,os,re,subprocess,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'scripts'))
from common import decode
from run_latency import verify_log
config=json.loads((root/'configs/thunderbird.json').read_text())
binary=root/'build/thunderbird/latency_bench'
numactl=root.parent/'capacity/build/thunderbird/deps/usr/bin/numactl'
info=json.loads(subprocess.check_output([str(binary),'--timer-info'],text=True))
assert abs(info['observed_frequency_hz']/info['timer_frequency_hz']-1)<.01
assembly=(root/'build/thunderbird/latency_bench.dis').read_text()
kernels={}
for name,streams in [('time_batch',1),('time_independent',4)]:
    body=assembly.split(f'<{name}>:',1)[1].split('\n\n',1)[0]
    timed=body.split('cntvct_el0',1)[1].split('cntvct_el0',1)[0]
    loads=re.findall(r'\bldr\s+(x\d+), \[(x\d+)\]',timed)
    assert len(loads)==16 and len(set(loads))==streams and all(a==b for a,b in loads)
    assert '[sp' not in timed and not re.search(r'\b(?:str|bl)\s',timed)
    (out/f'{name}.dis').write_text(body+'\n')
    kernels[name]=dict(load_instructions=16,dependency_streams=streams,no_timed_stack_access_or_calls=True)
cases=[(65536,mode,256,'huge') for mode in ('chase','sequential','independent','paired','empty')]
cases += [(4194304,'chase',1024,'huge'),(536870912,'paired',256,'huge'),(65536,'paired',256,'base')]
checks=[]
for size,mode,batch,pages in cases:
    name=f'w{size}_{mode}_b{batch}_{pages}'
    raw_path=out/f'{name}.u64'
    cmd=[str(numactl),'--membind=0',str(binary),str(size),'64',mode,'10000',str(batch),'59221','32',pages,str(raw_path)]
    r=subprocess.run(cmd,capture_output=True,text=True,check=True)
    (out/f'{name}.log').write_text(r.stderr)
    payload=raw_path.read_bytes()
    parameters=dict(mode=mode,samples=10000,batch=batch,pages=pages)
    raw=decode(payload,parameters)
    events=verify_log(r.stderr,config,parameters)
    with gzip.open(str(raw_path)+'.gz','wb') as f:f.write(payload)
    raw_path.unlink()
    checks.append(dict(name=name,command=cmd,shape=list(raw.shape),zero_intervals=int(np.sum(raw==0)),median_ticks=np.median(raw,axis=0).tolist(),events=events,raw_sha256=hashlib.sha256(payload).hexdigest()))
    print(name,'passed',checks[-1]['median_ticks'],flush=True)
report=dict(passed=True,timer=info,kernels=kernels,checks=checks,numactl_path=str(numactl),numactl_sha256=hashlib.sha256(numactl.read_bytes()).hexdigest(),python=sys.executable,numpy_version=np.__version__,cpu=32,numa_node=0)
(out/'native_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('All native checks passed',flush=True)
