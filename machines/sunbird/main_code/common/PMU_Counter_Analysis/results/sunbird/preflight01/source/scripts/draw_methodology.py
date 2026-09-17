#!/usr/bin/env python3
"""Generate the report's vector methodology diagram without external rendering tools."""
import argparse,pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
p=argparse.ArgumentParser(); p.add_argument('--contributor',default='UNASSIGNED'); a=p.parse_args()
out=pathlib.Path(__file__).resolve().parents[1]/'docs/figures'; out.mkdir(exist_ok=True)
fig,ax=plt.subplots(figsize=(12,6)); ax.set(xlim=(0,12),ylim=(0,6)); ax.axis('off')
nodes=[(2,5,'Pin allowed CPU\nIdentify local cache domain'),(6,5,'Half L1D / LLC / 4 × LLC\nRandom dependent cycle'),(10,5,'First-touch base pages\nWarm up two full traversals'),(3,3,'Timing passes\n1,000,000 batches per workload'),(9,3,'Eight single-event passes\nIdentical chain and load count'),(3,1,'Save raw timing distributions\nStatistics and box plots'),(9,1,'Normalize per 1,000 chain loads\nRank within each workload')]
for x,y,t in nodes:
 ax.add_patch(FancyBboxPatch((x-1.8,y-.5),3.6,1,boxstyle='round,pad=.06',facecolor='#eef3fa',edgecolor='#365a7b'))
 ax.text(x,y,t,ha='center',va='center',fontsize=10)
for start,end in [((3.9,5),(4.1,5)),((7.9,5),(8.1,5)),((10,4.4),(9,3.6)),((9,4.4),(3,3.6)),((3,2.4),(3,1.6)),((9,2.4),(9,1.6))]:
 ax.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='->',color='#365a7b',lw=1.5))
fig.suptitle('Section 8.4: same workload protocol, explicit PMU semantic limits')
fig.text(.02,.02,'Compare Intel / AMD / Arm and generations only with event-definition caveats.  |  Primary contributor: '+a.contributor,fontsize=9)
for ext in ['pdf','svg','png']: fig.savefig(out/f'methodology.{ext}',dpi=160)
