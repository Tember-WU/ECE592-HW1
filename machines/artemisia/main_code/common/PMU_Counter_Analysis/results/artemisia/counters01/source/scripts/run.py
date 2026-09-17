#!/usr/bin/env python3
"""Native Linux runner: no sudo, no remote logins, no guessed raw events on unknown CPUs."""
import argparse,csv,datetime,gzip,hashlib,json,os,pathlib,platform,random,shutil,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
def save(p,x): p.write_text(json.dumps(x,indent=2)+'\n')
def capture(cmd):
    try:
        p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=ROOT)
        return {'command':cmd,'returncode':p.returncode,'output':p.stdout}
    except OSError as e: return {'command':cmd,'error':str(e)}
def size(s):
    s=s.strip().upper(); return int(s[:-1])*{'K':1024,'M':1048576,'G':1073741824}[s[-1]] if s[-1] in 'KMG' else int(s)
def caches(cpu):
    result=[]
    for p in sorted(pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}/cache').glob('index*')):
        result.append({k:(p/k).read_text().strip() for k in ['level','type','size','coherency_line_size','shared_cpu_list']})
    return result

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--cpu',type=int,help='Default: first CPU in current affinity/allocation')
    a.add_argument('--config',type=pathlib.Path)
    a.add_argument('--run-id',default=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    a.add_argument('--smoke',action='store_true',help='Small functional test; never report as final data')
    a.add_argument('--preflight',action='store_true',help='Inventory and event probes only')
    a.add_argument('--samples',type=int,default=1000000)
    a.add_argument('--batch',type=int,default=64)
    a.add_argument('--repeats',type=int,default=3)
    a.add_argument('--seed',type=int,default=59284)
    a.add_argument('--l1-bytes',type=size); a.add_argument('--llc-bytes',type=size)
    a.add_argument('--capacity-source',default='Linux sysfs cache domain of pinned CPU (Phase II)')
    a.add_argument('--contributor',default='UNASSIGNED')
    args=a.parse_args()
    host=platform.node().split('.')[0].lower()
    if any(x in host for x in ('login','headnode')) and not os.getenv('SLURM_JOB_ID'): a.error('Use a compute allocation; refusing login-node benchmark')
    allowed=sorted(os.sched_getaffinity(0)); cpu=args.cpu if args.cpu is not None else allowed[0]
    if cpu not in allowed: a.error('CPU is outside current allowed affinity')
    if args.samples<1000000 and not args.smoke: a.error('Full runs require >= 1,000,000 timed samples per workload/repeat')
    if args.batch<1 or args.repeats<1: a.error('batch/repeats must be positive')
    if pathlib.Path(args.run_id).name!=args.run_id or args.run_id in ('.','..'): a.error('run-id must be a simple directory name')
    config=args.config or ROOT/'configs'/f'{host}.json'
    if not config.exists(): a.error('Unknown host: supply reviewed --config for actual CPU; generic profiles must have eight slots')
    cfg=json.loads(config.read_text()); model=pathlib.Path('/proc/cpuinfo').read_text()
    if cfg.get('isa')!=platform.machine(): a.error('Config ISA does not match this machine')
    if cfg.get('model_contains') and cfg['model_contains'].lower() not in model.lower(): a.error('Config CPU model does not match /proc/cpuinfo; review config')
    if len(cfg['events'])!=8 or len({e['slot'] for e in cfg['events']})!=8: a.error('Exactly eight distinct event slots required')
    inventory=caches(cpu)
    data=[c for c in inventory if c['type'] in ('Data','Unified')]
    l1=args.l1_bytes or next((size(c['size']) for c in data if c['level']=='1'),0)
    llc=args.llc_bytes or (size(max(data,key=lambda c:int(c['level']))['size']) if data else 0)
    if not l1 or llc<=l1: a.error('Cannot identify L1/LLC: supply --l1-bytes and --llc-bytes with --capacity-source')
    spacing=max(int(c['coherency_line_size']) for c in data) if data else 64
    if l1//2<spacing*2: a.error('Invalid L1 size')
    workloads={'l1_resident':(l1//2//spacing)*spacing,'llc_sized':llc//spacing*spacing,'beyond_llc':4*llc//spacing*spacing}
    out=ROOT/'results'/host/args.run_id; out.mkdir(parents=True,exist_ok=False)
    (out/'raw').mkdir(); (out/'probes').mkdir(); (out/'source').mkdir()
    subprocess.run(['make','all'],cwd=ROOT,check=True)
    for d in ['src','scripts','configs','docs']:
        shutil.copytree(ROOT/d,out/'source'/d)
    for f in ['Makefile','README.md','requirements.txt']:
        if (ROOT/f).exists(): shutil.copy2(ROOT/f,out/'source'/f)
    shutil.copy2(ROOT/'build/bench',out/'source/bench')
    shutil.copy2(ROOT/'build/bench.dis',out/'source/bench.dis')
    hashes={str(p.relative_to(out/'source')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'source').rglob('*') if p.is_file()}
    save(out/'source_sha256.json',hashes)
    topo=pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}')
    meta=dict(host=host,config=cfg,cpu=cpu,allowed_cpus=allowed,cache_inventory=inventory,l1_bytes=l1,llc_bytes=llc,workloads=workloads,spacing=spacing,
        args={k:str(v) if isinstance(v,pathlib.Path) else v for k,v in vars(args).items()},smoke=args.smoke,preflight=args.preflight,
        samples=2000 if args.smoke else args.samples,repeats=1 if args.smoke else args.repeats,batch=args.batch,byteorder=sys.byteorder,
        timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),platform=platform.platform(),page_size=os.sysconf('SC_PAGE_SIZE'),
        topology={k:(topo/'topology'/k).read_text().strip() for k in ['core_id','physical_package_id','thread_siblings_list']},numa_nodes=[p.name for p in topo.glob('node*')],
        locality='First touch after CPU affinity; base pages via MADV_NOHUGEPAGE; automatic NUMA balancing remains system default.',
        slurm={k:v for k,v in os.environ.items() if k.startswith('SLURM_')},status='running')
    for name,cmd in [('compiler',['g++','--version']),('git',['git','rev-parse','HEAD']),('git_status',['git','status','--short']),('perf_list',['perf','list','--details'])]:
        meta[name]=capture(cmd)
    meta['cpuinfo']=model
    meta['paranoid']=pathlib.Path('/proc/sys/kernel/perf_event_paranoid').read_text().strip()
    save(out/'metadata.json',meta)
    (out/'activity_before.txt').write_text(pathlib.Path('/proc/stat').read_text())
    selected=[]
    def execute(prefix,nbytes,n,batch,seed,event=None):
        cmd=[str(ROOT/'build/bench'),str(cpu),str(nbytes),str(spacing),str(n),str(batch),str(seed),str(event['type'] if event else 0),str(event['config'] if event else 0),str(prefix),'0' if event else '1']
        result=capture(cmd); save(prefix.with_suffix('.log.json'),result)
        return result.get('returncode')==0
    for e in cfg['events']:
        chosen=None
        for i,c in enumerate(e['candidates']):
            prefix=out/'probes'/f"{e['slot']}_{i}"
            if execute(prefix,workloads['l1_resident'],10000,64,args.seed,c): chosen=dict(c,slot=e['slot']); break
        selected.append(chosen or dict(slot=e['slot'],unavailable=True))
    save(out/'selected_events.json',selected)
    if any(e.get('unavailable') for e in selected):
        meta['status']='blocked_events'; save(out/'metadata.json',meta)
        print(f'One or more of eight events unavailable. Exact errors: {out}/probes',file=sys.stderr); return 2
    if args.preflight:
        meta['status']='preflight_complete'; save(out/'metadata.json',meta); print(out); return 0
    jobs=[(rep,w,e) for rep in range(meta['repeats']) for w in workloads for e in [None]+selected]
    random.Random(args.seed).shuffle(jobs)
    save(out/'order.json',[dict(repeat=r,workload=w,slot=e['slot'] if e else 'timing') for r,w,e in jobs])
    records=[]
    for idx,(rep,w,e) in enumerate(jobs):
        slot=e['slot'] if e else 'timing'; prefix=out/'raw'/f'{w}__r{rep}__{slot}'
        print(f'[{idx+1}/{len(jobs)}] {host} {w} repeat={rep} {slot}',flush=True)
        if not execute(prefix,workloads[w],meta['samples'],args.batch,args.seed+rep,e):
            meta['status']='failed'; save(out/'metadata.json',meta); print(f'Failed; inspect {prefix}.log.json',file=sys.stderr); return 2
        record=json.loads(prefix.with_suffix('.json').read_text()); record.update(workload=w,repeat=rep,slot=slot,event=e,prefix=str(prefix.relative_to(out)))
        records.append(record); save(out/'records.json',records)
        raw=prefix.with_suffix('.ticks.u64')
        if raw.exists():
            with raw.open('rb') as src,gzip.open(str(raw)+'.gz','wb') as dst: shutil.copyfileobj(src,dst)
            raw.unlink()
    (out/'activity_after.txt').write_text(pathlib.Path('/proc/stat').read_text())
    meta['status']='complete'; save(out/'metadata.json',meta)
    subprocess.run([sys.executable,str(ROOT/'scripts/analyze.py'),str(out)],check=True)
    print(f'Run saved: {out}')
    return 0
if __name__=='__main__': sys.exit(main())
