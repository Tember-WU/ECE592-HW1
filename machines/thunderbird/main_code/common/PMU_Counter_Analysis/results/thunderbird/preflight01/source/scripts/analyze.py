#!/usr/bin/env python3
"""Analyze explicit run directories; never silently mix smoke/full or duplicate hosts."""
import argparse,csv,gzip,hashlib,json,pathlib,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1]
HOSTS=['sunbird','charnwood','ookay','upgrade','crux','skylark','thunderbird','artemisia']
WORKLOADS=['l1_resident','llc_sized','beyond_llc']
def stats(values):
    q=np.percentile(values,[5,25,50,75,95]); iqr=q[3]-q[1]
    return dict(n=len(values),mean=float(np.mean(values)),std=float(np.std(values)),p5=q[0],q1=q[1],median=q[2],q3=q[3],p95=q[4],outliers=int(np.count_nonzero((values<q[1]-1.5*iqr)|(values>q[3]+1.5*iqr))))
def csvout(path,rows):
    if not rows: return
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
def figures(fig,path,contributor,smoke):
    fig.text(.01,.005,f"Primary contributor: {contributor}"+(' | SMOKE TEST — NOT REPORT DATA' if smoke else ''),fontsize=7)
    fig.tight_layout(rect=(0,.025,1,.96))
    fig.savefig(str(path)+'.pdf'); fig.savefig(str(path)+'.png',dpi=160); plt.close(fig)
def main():
    source_at_start=pathlib.Path(__file__).read_bytes()
    a=argparse.ArgumentParser(description=__doc__); a.add_argument('runs',nargs='+',type=pathlib.Path); a.add_argument('--output',type=pathlib.Path); args=a.parse_args()
    out=args.output or args.runs[0]/'analysis'; out.mkdir(parents=True,exist_ok=True)
    bundles=[(p,json.loads((p/'metadata.json').read_text()),json.loads((p/'records.json').read_text())) for p in args.runs]
    if len({m['host'] for _,m,_ in bundles})!=len(bundles): a.error('Choose one run per host explicitly')
    if len({m['smoke'] for _,m,_ in bundles})!=1: a.error('Cannot combine smoke and full runs')
    if any(m['status']!='complete' for _,m,_ in bundles): a.error('Incomplete run cannot be reported')
    if len({(m['batch'],m['spacing']) for _,m,_ in bundles})!=1: a.error('Batch/spacing differ: standardize the protocol before comparing')
    smoke=bundles[0][1]['smoke']; contributor=', '.join(sorted({m['args']['contributor'] for _,m,_ in bundles}))
    counters=[]; timings=[]; semantics=[]; coverage=[]; summaries=[]
    for path,m,records in bundles:
        events=json.loads((path/'selected_events.json').read_text())
        for e in events:
            semantics.append(dict(host=m['host'],slot=e['slot'],event=e['name'],type=e['type'],config=e['config'],meaning=e['meaning'],comparability=e['comparability']))
        for r in records:
            common=dict(host=m['host'],vendor=m['config']['vendor'],year=m['config']['year'],workload=r['workload'],repeat=r['repeat'],bytes=r['bytes'])
            if r['slot']=='timing':
                with gzip.open(path/(r['prefix']+'.ticks.u64.gz'),'rb') as f: values=np.frombuffer(f.read(),dtype='<u8' if m['byteorder']=='little' else '>u8').astype(float)/r['batch']
                if len(values)!=r['samples']: raise ValueError('Raw timing sample count mismatch')
                row=dict(common,unit=r['timer_unit']+'/access',**stats(values)); timings.append(row)
                # Exact summary-derived box, all samples contribute; display hides fliers only.
                fig,ax=plt.subplots(figsize=(5,4)); q=row
                ax.bxp([dict(label=r['workload'],med=q['median'],q1=q['q1'],q3=q['q3'],whislo=q['p5'],whishi=q['p95'],fliers=[])],showfliers=False)
                ax.set_ylabel(row['unit']); ax.set_title(f"{m['host']} / repeat {r['repeat']}\nWhiskers: 5th–95th percentiles")
                figures(fig,out/f"box_{m['host']}_{r['workload']}_r{r['repeat']}",contributor,smoke)
            else:
                if r['enabled_ns']<=0 or r['enabled_ns']!=r['running_ns']: raise ValueError('Invalid PMU scheduling')
                counters.append(dict(common,slot=r['slot'],event=r['event']['name'],count=r['count'],chain_loads=r['chain_loads'],per_1000_accesses=1000*r['count']/r['chain_loads'],enabled_ns=r['enabled_ns'],running_ns=r['running_ns'],minor_faults=r['minor_faults'],major_faults=r['major_faults'],involuntary_switches=r['involuntary_switches']))
        expected=m['repeats']*3*9
        keys={(r['repeat'],r['workload'],r['slot']) for r in records}
        required={(rep,w,slot) for rep in range(m['repeats']) for w in WORKLOADS for slot in ['timing']+[e['slot'] for e in events]}
        ok=keys==required and len(records)==expected and all(r['samples']>=1000000 and r['chain_loads']==r['samples']*r['batch'] for r in records)
        coverage.append(dict(host=m['host'],records=len(records),expected=expected,full_sample_coverage=ok and not smoke,contributor=m['args']['contributor']))
    csvout(out/'raw_counts.csv',counters); csvout(out/'timing_statistics.csv',timings); csvout(out/'event_semantics.csv',semantics); csvout(out/'coverage.csv',coverage)
    slots=[e['slot'] for e in json.loads((bundles[0][0]/'selected_events.json').read_text())]
    for mhost in [m['host'] for _,m,_ in bundles]:
        for w in WORKLOADS:
            for slot in slots:
                rows=[r for r in counters if r['host']==mhost and r['workload']==w and r['slot']==slot]
                v=[r['per_1000_accesses'] for r in rows]
                summaries.append(dict(host=mhost,workload=w,slot=slot,event=rows[0]['event'],vendor=rows[0]['vendor'],year=rows[0]['year'],repeats=len(v),median=float(np.median(v)),minimum=min(v),maximum=max(v)))
    csvout(out/'normalized_summary.csv',summaries)
    for host in sorted({r['host'] for r in summaries}):
        fig,axes=plt.subplots(2,4,figsize=(13,7))
        fig.suptitle(f'{host}: workload response, events per 1,000 chain accesses')
        for slot,ax in zip(slots,axes.flat):
            rows=[next(r for r in summaries if r['host']==host and r['slot']==slot and r['workload']==w) for w in WORKLOADS]
            y=[r['median'] for r in rows]
            ax.errorbar(range(3),y,yerr=[[r['median']-r['minimum'] for r in rows],[r['maximum']-r['median'] for r in rows]],fmt='o-',capsize=3)
            ax.set_xticks(range(3)); ax.set_xticklabels(['half L1D','1 × LLC','4 × LLC'])
            ax.set_title(rows[0]['event'],fontsize=9); ax.grid(False)
            ax.set_ylim(bottom=0); ax.ticklabel_format(useOffset=False,axis='y')
        figures(fig,out/f'workload_comparison_{host}',contributor,smoke)
    ranks=[]; colors={'Intel':'#2864b4','AMD':'#cf5b24','Arm':'#26936e'}
    for w in WORKLOADS:
        fig,axes=plt.subplots(2,4,figsize=(15,8)); fig.suptitle(f'{w}: ascending event counts per 1,000 chain accesses\nOrdinal comparison of configured slots; event definitions may differ')
        fig2,axes2=plt.subplots(2,4,figsize=(15,8)); fig2.suptitle(f'{w}: generation launch year (observations only; no fitted trend)')
        for slot,ax,ax2 in zip(slots,axes.flat,axes2.flat):
            rows=sorted([r for r in summaries if r['workload']==w and r['slot']==slot],key=lambda r:(r['median'],r['host']))
            ax.plot(range(1,len(rows)+1),[r['median'] for r in rows],color='.65',linewidth=1)
            for i,r in enumerate(rows,1):
                ax.errorbar(i,r['median'],yerr=[[r['median']-r['minimum']],[r['maximum']-r['median']]],fmt='o',color=colors.get(r['vendor'],'black'),capsize=3)
                ax.annotate(r['host'],(i,r['median']),xytext=(2,5),textcoords='offset points',fontsize=7,rotation=25)
                ax2.scatter(r['year'],r['median'],color=colors.get(r['vendor'],'black'))
                ax2.annotate(r['host'],(r['year'],r['median']),fontsize=7,xytext=(2,5),textcoords='offset points',rotation=25)
                ranks.append(dict(workload=w,slot=slot,rank=i,host=r['host'],vendor=r['vendor'],year=r['year'],event=r['event'],median_per_1000=r['median'],minimum=r['minimum'],maximum=r['maximum']))
            for axis in [ax,ax2]: axis.set_title(slot.replace('_',' ')); axis.grid(False); axis.margins(.25)
            ax.set_xticks(range(1,len(rows)+1)); ax.set_xlim(.5,len(rows)+.5)
            ax.set_xlabel('Ascending rank (ties alphabetical)'); ax2.set_xlabel('Generation launch year'); ax2.ticklabel_format(useOffset=False,axis='x'); ax2.set_xticks(sorted({r['year'] for r in rows})); ax2.tick_params(axis='x',labelrotation=45)
        figures(fig,out/f'ranked_{w}',contributor,smoke); figures(fig2,out/f'generations_{w}',contributor,smoke)
        # Compact ordinal heatmap: display values as ranks, not comparable PMU magnitudes.
        ordered=sorted({r['host'] for r in summaries}); matrix=np.array([[next(r['rank'] for r in ranks if r['host']==h and r['workload']==w and r['slot']==s) for s in slots] for h in ordered])
        fig,ax=plt.subplots(figsize=(12,max(3,len(ordered)*.5))); im=ax.imshow(matrix,cmap='Blues',vmin=1,vmax=max(2,len(ordered)))
        ax.set_xticks(range(8)); ax.set_xticklabels(slots,rotation=25,ha='right'); ax.set_yticks(range(len(ordered))); ax.set_yticklabels(ordered)
        for i in range(len(ordered)):
            for j in range(8): ax.text(j,i,str(matrix[i,j]),ha='center',va='center')
        ax.set_title(w+' — ordinal rank only (1 = smallest count; not a performance score)')
        figures(fig,out/f'rank_matrix_{w}',contributor,smoke)
    csvout(out/'rankings.csv',ranks)
    missing=sorted(set(HOSTS)-{m['host'] for _,m,_ in bundles})
    lines=['# Section 8.4 generated analysis','',f"Primary contributor: {contributor}",'',f"Mode: {'SMOKE TEST; not submission data' if smoke else 'full collection'}",f"Missing ECE hosts: {', '.join(missing) or 'none'}",'',
        'Counts are divided by the exact number of dependent pointer loads, then multiplied by 1,000. Timing samples are batches divided by batch length; they are not individually timed loads. Counter passes omit timers and sample-buffer writes. Initialization and two full warm-up traversals are excluded. Remaining user-space call/loop overhead is included; no baseline subtraction or multiplex scaling is applied.',
        '', 'See docs/generic_mapping_review.md for upstream mappings (including cache-level differences under identical generic names). Ranks compare the configured event slots numerically, NOT necessarily identical physical phenomena. Read event_semantics.csv before interpreting any ordering. Same generic event spelling does not establish equivalent PMU semantics. Error bars are min/max across repeated counter passes, not confidence intervals. No ratio is called a hit/miss probability because numerator/denominator semantics may differ.', '',
        'Intel retired-load proxies differ from AMD dispatch/MAB/refill proxies and Arm speculative/refill events. AMD local-DRAM fills exclude remote service. Thunderbird 0x36/0x37 have not been validated as SLC accesses/misses by section 8.3. LLC-sized means capacity-relative working set, not proof of LLC residency. Base-page TLB pressure, shared cache contention, prefetching, NUMA, and cache organization can change results.', '',
        '## Compact ranked tables','']
    for w in WORKLOADS:
        lines+=['### '+w,'','| Event slot | Ascending machines: median events / 1,000 accesses |','|---|---|']
        for s in slots:
            rr=[r for r in ranks if r['workload']==w and r['slot']==s]
            lines.append('| '+s+' | '+' → '.join(f"{r['host']}: {r['median_per_1000']:.4g}" for r in rr)+' |')
        lines+=['']
    lines+=['## Interpretation to finish after collecting all hosts','',
        '- Describe whether each workload produced the intended L1/deeper-cache/above-LLC behavior using normalized counters and timing distributions.',
        '- For each architecture-specific proxy, cite the copied event inventory and explain exactly which rankings permit a comparison and which are only descriptive.',
        '- Compare older/newer Intel systems within semantically matched event definitions, then discuss AMD and Arm separately. Launch year alone does not control server/desktop class, cache domain, memory or process differences.',
        '- Inspect raw_counts.csv faults/switches and activity logs. Record actual SMT sibling activity/reservation and reasons for noisy reruns; never discard inconvenient observations silently.',
        '- Fill actual contributor identity, repository/Overleaf links and AI disclosure in the overall submission. Include final source listings and docs/methodology.md diagram.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))
    (out/'inputs.json').write_text(json.dumps([str(p.resolve()) for p in args.runs],indent=2)+'\n')
    source=source_at_start
    (out/'analyze_source.py').write_bytes(source)
    provenance={'analyzer_sha256':hashlib.sha256(source).hexdigest(),'numpy':np.__version__,'matplotlib':matplotlib.__version__,'inputs':{str(f.resolve()):hashlib.sha256(f.read_bytes()).hexdigest() for p in args.runs for f in p.rglob('*') if f.is_file() and ('raw' in f.relative_to(p).parts or f.name in ['metadata.json','records.json','selected_events.json'])}}
    (out/'analysis_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(f'Analysis: {out}; missing hosts: {missing}')
if __name__=='__main__': main()
