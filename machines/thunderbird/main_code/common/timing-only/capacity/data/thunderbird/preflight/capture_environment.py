import datetime,json,os,platform,subprocess,time
from pathlib import Path
p=Path(__file__).resolve().parent
cpu=32
def stat():
    return {a[0]:list(map(int,a[1:])) for line in Path('/proc/stat').read_text().splitlines() if (a:=line.split())[0].startswith('cpu') and a[0][3:].isdigit()}
a=stat(); time.sleep(2); b=stat()
busy={}
for key,first in a.items():
    d=[last-start for start,last in zip(first,b[key])]
    busy[key]=round(100*(1-(d[3]+d[4])/max(1,sum(d[:8]))),3)
metadata=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hostname=platform.node(),isa=platform.machine(),kernel=platform.release(),selected_cpu=cpu,numa_node=0,inherited_affinity=sorted(os.sched_getaffinity(0)),cpu_busy_percent_over_two_seconds=busy)
for key,cmd in [('uname',['uname','-a']),('gcc',['gcc','--version']),('meminfo',['cat','/proc/meminfo']),('uptime',['uptime'])]:
    metadata[key]=subprocess.check_output(cmd,text=True)
for name in ('scaling_governor','scaling_cur_freq','scaling_min_freq','scaling_max_freq'):
    metadata[name]=(Path(f'/sys/devices/system/cpu/cpu{cpu}/cpufreq')/name).read_text().strip()
(p/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n')
print('Prelaunch CPU32 busy:',busy['cpu32'])
