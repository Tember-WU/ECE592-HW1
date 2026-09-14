#!/usr/bin/env python3
"""End-to-end plotting/ranking check with temporary SYNTHETIC data, never real results."""
import csv,gzip,json,pathlib,subprocess,sys,tempfile
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='pmu84-synthetic-') as td:
    base=pathlib.Path(td); runs=[]
    for i,profile in enumerate(sorted((ROOT/'configs').glob('*.json'))):
        cfg=json.loads(profile.read_text()); p=base/cfg['host']; p.mkdir(); (p/'raw').mkdir(); runs.append(str(p))
        events=[dict(e['candidates'][0],slot=e['slot']) for e in cfg['events']]
        meta=dict(host=cfg['host'],config=cfg,smoke=True,status='complete',batch=64,spacing=64,byteorder='little',repeats=1,args={'contributor':'SYNTHETIC TEST FIXTURE'})
        (p/'metadata.json').write_text(json.dumps(meta)); (p/'selected_events.json').write_text(json.dumps(events)); records=[]
        for w in ['l1_resident','llc_sized','beyond_llc']:
            for e in [None]+events:
                slot=e['slot'] if e else 'timing'; prefix='raw/'+w+'__'+slot
                r=dict(workload=w,repeat=0,slot=slot,event=e,prefix=prefix,bytes=4096,samples=32,batch=64,chain_loads=2048,count=(i+1)*2048,enabled_ns=1,running_ns=1,minor_faults=0,major_faults=0,involuntary_switches=0,timer_unit='SYNTHETIC_ticks')
                records.append(r)
                if not e:
                    with gzip.open(p/(prefix+'.ticks.u64.gz'),'wb') as f: f.write(np.array([64]*31+[640],dtype='<u8').tobytes())
        (p/'records.json').write_text(json.dumps(records))
    out=base/'comparison'
    subprocess.run([sys.executable,str(ROOT/'scripts/analyze.py')]+runs+['--output',str(out)],check=True,stdout=subprocess.DEVNULL)
    rows=list(csv.DictReader((out/'rankings.csv').open()))
    assert len(rows)==8*8*3
    for w in ['l1_resident','llc_sized','beyond_llc']:
        for slot in [e['slot'] for e in events]:
            selected=[r for r in rows if r['workload']==w and r['slot']==slot]
            assert [float(r['median_per_1000']) for r in selected]==[1000.*i for i in range(1,9)]
        assert (out/('ranked_'+w+'.pdf')).stat().st_size>1000
    assert 'SMOKE TEST' in (out/'REPORT.md').read_text()
    print('PASS: temporary synthetic eight-host analysis, 192 ranks, PDF/PNG plots, smoke labels. Fixtures removed.')
