from pathlib import Path
import tempfile,json,subprocess,os
import numpy as np
from gpu_core import ROOT,Ranker,stable_top

def fixture(T,last,bad_entry=False,bad_exit=False,lookahead=False,blocking=False):
    with tempfile.TemporaryDirectory()as folder:
        d=Path(folder);o=np.full((T,8),100.);c=o.copy();v=np.full_like(o,1000.)
        if bad_entry:o[301,0]=np.nan
        if bad_exit:o[306,0]=np.nan;o[307,0]=c[307,0]=120.
        if lookahead:c[300]=10.;o[306]=c[306]=200.
        if blocking:o[306:311,0]=np.nan
        for name,x in [('open',o),('adj',c),('volume',v),('calendar_days',np.arange(T,dtype=np.int64))]:np.save(d/f'{name}.npy',x)
        np.save(d/'picks.npy',np.tile(np.arange(5,dtype=np.int16),(1,last-299,1)))
        z=np.lib.format.open_memmap(d/'out.npy',mode='w+',dtype=np.float64,shape=(6,1,2,64));z.flush();del z
        z=np.lib.format.open_memmap(d/'nav.npy',mode='w+',dtype=np.float64,shape=(6,1,T-300,2));z.flush();del z
        subprocess.run([str(ROOT/'code/book'),str(d),str(d/'picks.npy'),str(d/'out.npy'),'300',str(last),'0,.001','0','318','300',str(d/'nav.npy')],check=True,env=dict(os.environ,OMP_NUM_THREADS='4'))
        return np.load(d/'out.npy'),np.load(d/'nav.npy')

checks=[];s,a=fixture(331,324);q=(1-.001)/(1+.001)
np.testing.assert_allclose(a[:,0,-1,0],1,atol=1e-12);np.testing.assert_allclose(a[:,0,-1,1],q**5,atol=1e-12)
np.testing.assert_array_equal(s[:,0,0,24],[1,2,3,4,5,5]);assert s[5,0,0,31]==1
checks.append('All six families self-finance; exact five-day fee compounding; daily repeated ticker still at most5 lots')
s,a=fixture(307,300,lookahead=True);np.testing.assert_allclose(a[:5,0,-1,0],2.,atol=1e-12);assert abs(a[5,0,-1,0]-1.2)<1e-12
checks.append('Next-open fills and five-open-interval exit; no same-close fills')
s,a=fixture(307,300,bad_entry=True);assert s[4,0,0,18]==4 and s[4,0,0,23]==1;assert abs(a[4,0,-1,1]-(.2+.8*q))<1e-12
checks.append('Missing entry slot retained as cash without redistribution')
s,a=fixture(308,300,bad_exit=True);assert abs(a[4,0,-1,0]-1.04)<1e-12 and s[4,0,0,22]==1 and s[4,0,0,28]==6
checks.append('Missing exit waits for observed open rather than fabricating a fill')
s,a=fixture(320,313,blocking=True);assert np.max(s[:,:,:,24])<=5 and s[5,0,0,36]>0
checks.append('Overdue sleeve blocks replacement and cannot exceed the5-position cap')

import torch
r=Ranker(load_open=False,k=5);meta=r.meta;adj=np.load(ROOT/'data/adj.npy',mmap_mode='r');dol=np.load(ROOT/'data/dollar.npy',mmap_mode='r');elig=np.load(ROOT/'data/eligible.npy',mmap_mode='r')
scores=torch.tensor([[1.,1.,1.,.5,.4,.3,.2],[1.,.9,.9,.9,.8,.8,.1]],device='cuda',dtype=torch.float64)
ids,_,_=stable_top(scores,5);np.testing.assert_array_equal(ids.cpu().numpy(),[[0,1,2,3,4],[0,1,2,3,4]])
checks.append('Exact internal and boundary ties preserve ticker order for every K=1..5')
days=np.array([meta['dates'].index(t)for t in ['1991-03-11','1995-06-30','2000-03-10','2008-09-15','2015-08-24','2020-03-23','2024-06-10','2025-08-01','2025-12-22']]);ms=[20,21,50,126,252,300];count=0
for n in [5,17,50,123,200]:
    gpu=r.block(n,days,m_values=ms,ids_only=True)
    for j,t in enumerate(days):
        liq=np.asarray(dol[t-n+1:t+1]).mean(0);univ=np.flatnonzero(elig[t]);univ=univ[np.lexsort((univ,-liq[univ]))][:500]
        for k,m in enumerate(ms):
            score=adj[t-5,univ]/adj[t-m,univ]-1;good=np.isfinite(score);ids=univ[good];score=score[good];cpu=ids[np.lexsort((ids,-score))][:5]
            np.testing.assert_array_equal(gpu[k,j],cpu);count+=1
checks.append(f'{count} ordered top5 GPU rankings exactly match independent direct-mean CPU implementation')
receipt=dict(passed=True,synthetic_fixtures=5,real_ranking_samples=count,checks=checks,device=r.device)
(ROOT/'results/tests.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)
