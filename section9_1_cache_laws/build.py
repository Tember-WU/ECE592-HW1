#!/usr/bin/env python3
"""Build Section 9.1 from the existing lab-only snapshot; no remote operations."""
import csv, hashlib, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'section9_moore_analysis'
METRICS = ['l2_capacity_KiB', 'l2_l1_latency_ratio']
def read(path):
    with path.open() as f: return list(csv.DictReader(f))
def write(name, rows):
    with (ROOT/'tables'/name).open('w', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
models=json.loads((SOURCE/'predictions/model_parameters.json').read_text())
training=[r for r in read(SOURCE/'predictions/model_training_points.csv') if r['metric'] in METRICS]
predictions=[r for r in read(SOURCE/'predictions/hazel_predictions.csv') if r['metric'] in METRICS]
write('lab_evidence.csv', training)
write('hazel_predictions.csv', predictions)
(ROOT/'laws.json').write_text(json.dumps({k:models[k] for k in METRICS},indent=2)+'\n')
def predict(metric,t):
    m=models[metric]
    if metric==METRICS[1]: return m['central'],m['low'],m['high']
    p=m['anchor_KiB']*2**(m['log2_slope_per_year']*(t-m['anchor_year']))
    variants=[v['anchor_KiB']*2**(v['log2_slope_per_year']*(t-v['anchor_year'])) for v in m['sensitivity_models']]
    e=m['max_abs_leave_one_host_out_error_log2']; variants += [p,p*2**(-e),p*2**e]
    return p,min(variants),max(variants)
forecast=[]; diagnostics=[]
for metric in METRICS:
    data=[r for r in training if r['metric']==metric]
    x=np.array([float(r['year']) for r in data]); y=np.array([float(r['value']) for r in data])
    modeled=np.array([predict(metric,t)[0] for t in x])
    residual=np.log2(y/modeled) if metric==METRICS[0] else y-modeled
    diagnostics.append(dict(metric=metric,n=8,rmse=float(np.sqrt(np.mean(residual**2))),error_unit='log2 ratio' if metric==METRICS[0] else 'ratio',observed_min=min(y),observed_max=max(y)))
    p,lo,hi=predict(metric,2028)
    forecast.append(dict(metric=metric,year=2028,prediction=p,low=lo,high=hi,status='conditional lab-only scenario; not post-Hazel forecast',coverage='uncalibrated sensitivity envelope'))
    fig,ax=plt.subplots(figsize=(10,5.7),layout='constrained')
    for group,marker,color in [('Intel x86','o','#225588'),('AMD x86','s','#aa4422'),('Arm / Ampere','^','#338855')]:
        rs=[r for r in data if r['group']==group]
        xx=np.array([float(r['year']) for r in rs]); yy=np.array([float(r['value']) for r in rs])
        ax.errorbar(xx,yy,yerr=[yy-np.array([float(r['low']) for r in rs]),np.array([float(r['high']) for r in rs])-yy],fmt=marker,color=color,capsize=4,label=group+' lab observations',ms=7)
        for r in rs: ax.annotate(r['host'],(float(r['year']),float(r['value'])),xytext=(3,9 if r['host']!='thunderbird' else -18),textcoords='offset points',fontsize=8)
    past=np.linspace(2014,2023,120); future=np.linspace(2023,2028,100)
    ax.plot(past,[predict(metric,t)[0] for t in past],'-',color='black',lw=1.4,label='Pooled model (observed years)')
    values=np.array([predict(metric,t) for t in future])
    ax.plot(future,values[:,0],'--',color='black',label='Conditional extrapolation')
    ax.fill_between(future,values[:,1],values[:,2],color='gray',alpha=.16,label='Sensitivity envelope (not 95% CI)')
    if metric==METRICS[0]: ax.set_yscale('log',base=2); ax.set_ylabel('Timing-inferred private L2 capacity (KiB/core; log2 scale)')
    else: ax.set_ylabel('L2-resident / L1-resident median latency (dimensionless)')
    ax.set_xlabel('Processor-generation introduction year')
    ax.set_title('Patel–Wu L2 Capacity Growth Law' if metric==METRICS[0] else 'Patel–Wu Relative Cache Latency Law')
    ax.set_xlim(2013.6,2028.6); ax.grid(alpha=.22); ax.legend(fontsize=8,loc='upper center',bbox_to_anchor=(0.5,-0.15),ncol=3)
    fig.savefig(ROOT/'figures'/f'law_{METRICS.index(metric)+1}.pdf'); fig.savefig(ROOT/'figures'/f'law_{METRICS.index(metric)+1}.png',dpi=180); plt.close(fig)
write('conditional_forecast.csv',forecast); write('fit_diagnostics.csv',diagnostics)
# Never overwrite eventual observations during a rebuild.
template=ROOT/'hazel_results_template.csv'
if not template.exists():
    with template.open('w',newline='') as f:
        fields=['constraint','metric','observed','low','high','unit','raw_source','measurement_utc','freeze_commit','interpretation']
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in predictions: w.writerow(dict(constraint=r['constraint'],metric=r['metric'],unit=r['unit']))
paths=['predictions/model_parameters.json','predictions/model_training_points.csv','predictions/hazel_predictions.csv','tables/trend_summary.csv']
(ROOT/'provenance.json').write_text(json.dumps({'source_package':'../section9_moore_analysis','source_sha256':{p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in paths},'hazel_used':False,'github_freeze_verified':False},indent=2)+'\n')
print(json.dumps({'observations':len(training),'hazel_predictions':len(predictions),'forecast':forecast,'diagnostics':diagnostics},indent=2))
