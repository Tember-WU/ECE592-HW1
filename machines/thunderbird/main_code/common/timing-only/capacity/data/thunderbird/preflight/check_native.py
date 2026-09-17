"""Short native compatibility checks; these are not formal experiment points."""
import gzip, hashlib, json, os, re, subprocess, time
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[3]
out=Path(__file__).resolve().parent
binary=root/'build/thunderbird/cache_capacity'
numactl=root/'build/thunderbird/deps/usr/bin/numactl'
os.sched_setaffinity(0,{32})
info=json.loads(subprocess.check_output([str(binary),'--timer-info'],text=True))
assert abs(info['observed_frequency_hz']/info['timer_frequency_hz']-1)<.01
checks=[]
for size,spacing,mode,batch,pages in [(65536,64,'random',256,'huge'),(65536,64,'random',1024,'huge'),(2048,64,'empty',256,'huge'),(2097152,64,'random',256,'base'),(2097152,8,'random',256,'huge'),(536870912,64,'random',256,'huge')]:
    name=f'w{size}_s{spacing}_{mode}_b{batch}_{pages}'
    raw=out/f'{name}.u64'
    cmd=[str(numactl),'--membind=0',str(binary),str(size),str(spacing),mode,'10000',str(batch),'59201','32',pages,str(raw)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    (out/f'{name}.log').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    payload=raw.read_bytes()
    data=np.frombuffer(payload,dtype='<u8')
    assert len(data)==10000 and (mode=='empty' or np.all(data>0))
    assert 'cpu_start=32 cpu_end=32' in result.stderr
    with gzip.open(str(raw)+'.gz','wb') as f: f.write(payload)
    raw.unlink()
    checks.append(dict(name=name,command=cmd,samples=len(data),zero_count=int(np.sum(data==0)),median_ticks=float(np.median(data)),sha256=hashlib.sha256(payload).hexdigest()))
    print(name,checks[-1]['median_ticks'],flush=True)
asm=(root/'build/thunderbird/cache_capacity.dis').read_text().split('<time_batch>:',1)[1].split('\n\n',1)[0]
timed=asm.split('cntvct_el0',1)[1].split('cntvct_el0',1)[0]
loads=re.findall(r'\bldr\s+(x\d+), \[(x\d+)\]',timed)
assert len(loads)==16 and len(set(loads))==1 and loads[0][0]==loads[0][1]
assert '[sp' not in timed and not re.search(r'\b(?:str|bl)\s',timed)
(out/'time_batch.dis').write_text(asm+'\n')
(out/'native_checks.json').write_text(json.dumps(dict(status='passed',timer=info,checks=checks,assembly='16 dependent loads; no stack traffic or calls between counter reads'),indent=2)+'\n')
