#!/usr/bin/env python3
"""Verify law arithmetic, preserved predictions, provenance and figure artifacts."""
import csv, hashlib, json, math, re, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
P=Path(__file__).resolve().parent
S=P.parent/'section9_moore_analysis'
def rows(p):
    with p.open() as f: return list(csv.DictReader(f))
def close(a,b): assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10),(a,b)
m=json.loads((P/'laws.json').read_text()); data=rows(P/'tables/lab_evidence.csv')
assert len(data)==16
for metric,model in m.items():
    d=[r for r in data if r['metric']==metric]; assert len({r['host'] for r in d})==8
    assert model==json.loads((S/'predictions/model_parameters.json').read_text())[metric]
    if metric=='l2_capacity_KiB':
        x=np.array([int(r['year'])-2023 for r in d]); y=np.log2([float(r['value'])/2048 for r in d])
        close(model['log2_slope_per_year'],x@y/(x@x)); close(model['doubling_years'],1/model['log2_slope_per_year'])
    else: close(model['central'],np.median([float(r['value']) for r in d]))
pred=rows(P/'tables/hazel_predictions.csv')
assert len(pred)==18 and pred==[r for r in rows(S/'predictions/hazel_predictions.csv') if r['metric'] in m]
for r in rows(P/'tables/conditional_forecast.csv'):
    model=m[r['metric']]; assert int(r['year'])==2028
    expected=2048*2**(model['log2_slope_per_year']*5) if r['metric']=='l2_capacity_KiB' else model['central']
    close(r['prediction'],expected); assert float(r['low'])<=expected<=float(r['high'])
    assert 'conditional' in r['status']
for p,h in json.loads((P/'provenance.json').read_text())['source_sha256'].items(): assert hashlib.sha256((S/p).read_bytes()).hexdigest()==h
for i in [1,2]:
    info=subprocess.check_output(['pdfinfo',str(P/f'figures/law_{i}.pdf')],text=True)
    assert re.search(r'Pages:\s+1\b',info)
    with Image.open(P/f'figures/law_{i}.png') as im: assert im.width>1000 and im.height>600
print('PASS: 16 lab observations, 18 unchanged Hazel predictions, two models, two forecasts, source hashes, and four figure files.')
