"""Exact float64 ranking with deterministic ticker tie-breaks on RTX 5090."""
from pathlib import Path
import json,time
import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]


def setup():
    torch.cuda.set_per_process_memory_fraction(.024)
    torch.set_num_threads(4)
    assert '5090' in torch.cuda.get_device_name(0)
    return torch.cuda.get_device_name(0)


def stable_top(scores,k):
    values,indices=torch.topk(scores,k+1,dim=-1,largest=True,sorted=True)
    tied=((torch.isfinite(values[...,:k])) & (values[...,:k]==values[...,1:k+1])).any(dim=-1) if k<=5 else torch.isfinite(values[...,k-1])&(values[...,k-1]==values[...,k])
    if tied.any():
        flat=scores.reshape(-1,scores.shape[-1]);out=indices.reshape(-1,k+1)
        rows=tied.reshape(-1).nonzero().flatten()
        # Input columns are in ticker order. Only boundary ties need a stable sort.
        out[rows,:k]=torch.argsort(flat[rows],dim=-1,descending=True,stable=True)[:,:k]
    return indices[...,:k],torch.isfinite(values[...,k-1]),int(tied.sum().item())


def build_pools():
    device=setup();begun=time.monotonic();d=ROOT/'data'
    meta=json.loads((d/'meta.json').read_text());T=len(meta['dates']);S=len(meta['symbols'])
    prefix=np.load(d/'dollar_prefix.npy',mmap_mode='r');eligible=np.load(d/'eligible.npy',mmap_mode='r')
    path=d/'pools.npy';statepath=d/'pools_state.json'
    pools=np.lib.format.open_memmap(path,mode='r+' if path.exists() else 'w+',dtype=np.int16,shape=(196,T,500))
    state=json.loads(statepath.read_text()) if statepath.exists() else dict(completed=[],ties=0)
    for n in range(5,201):
        if n in state['completed']:continue
        for start in range(0,T,512):
            stop=min(start+512,T);ix=np.arange(start,stop)
            a=(prefix[ix+1]-prefix[np.maximum(ix-n+1,0)])/n
            mask=np.array(eligible[start:stop],copy=True)&(ix[:,None]>=252)
            a[~mask]=-np.inf
            liq=torch.as_tensor(a,device='cuda')
            ids,_,ties=stable_top(liq,500);state['ties']+=ties
            real=torch.gather(liq,1,ids).isfinite()
            ids=torch.where(real,ids,S).sort(dim=1).values
            pools[n-5,start:stop]=ids.to(torch.int16).cpu().numpy()
            del liq,ids,real
        pools.flush();state['completed'].append(n)
        temp=statepath.with_suffix('.tmp');temp.write_text(json.dumps(state));temp.replace(statepath)
        if (n-4)%20==0 or n==200:print(json.dumps(dict(stage='pools',n=n,completed=len(state['completed']),elapsed=round(time.monotonic()-begun,1))),flush=True)
    receipt=dict(device=device,completed=len(state['completed']),shape=list(pools.shape),ties=state['ties'],
        allocated_peak_bytes=torch.cuda.max_memory_allocated(),elapsed_seconds=round(time.monotonic()-begun,2))
    (d/'pool_gpu_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)


class Ranker:
    def __init__(self,load_open=True,k=5):
        self.k=k;self.device=setup();d=ROOT/'data';self.meta=json.loads((d/'meta.json').read_text())
        self.T=len(self.meta['dates']);self.S=len(self.meta['symbols'])
        self.adj=torch.as_tensor(np.pad(np.load(d/'adj.npy'),((0,0),(0,1)),constant_values=np.nan),device='cuda')
        self.open=torch.as_tensor(np.pad(np.load(d/'open.npy'),((0,0),(0,1)),constant_values=np.nan),device='cuda') if load_open else None
        self.pools=np.load(d/'pools.npy',mmap_mode='r')
        self.m=torch.arange(20,301,device='cuda')
        self.ties=0

    def block(self,n,days,skip=5,m_values=None,return_ids=False,ids_only=False):
        if np.min(days)<300 or np.max(days)>self.T-7:
            raise ValueError('Signal days must have the full common lookback and completed five-day holding window')
        ms=self.m if m_values is None else torch.as_tensor(m_values,device='cuda')
        t=torch.as_tensor(days,device='cuda',dtype=torch.long)
        candidates=torch.as_tensor(np.array(self.pools[n-5,days],dtype=np.int64),device='cuda')
        denominator=self.adj[(t[:,None]-ms[None,:])[:,:,None],candidates[:,None,:]]
        numerator=self.adj[t[:,None]-skip,candidates]
        score=numerator[:,None,:]/denominator
        score.sub_(1)
        score.masked_fill_(~torch.isfinite(score)|(denominator<=0),-torch.inf)
        del denominator
        ranks,valid,ties=stable_top(score,self.k);self.ties+=ties
        selected=torch.gather(candidates[:,None,:].expand(-1,len(ms),-1),2,ranks)
        selected=torch.where(valid[:,:,None],selected,self.S)
        if ids_only:return selected.permute(1,0,2).to(torch.int16).cpu().numpy()
        entry=self.open[t[:,None,None]+1,selected]
        bought=torch.isfinite(entry)&(entry>0)&valid[:,:,None]
        cash=(~bought).double().mean(dim=2)
        paths=[];missing=[]
        for h in range(6):
            prices=self.open[t[:,None,None]+6,selected] if h==5 else self.adj[t[:,None,None]+1+h,selected]
            ratio=prices/entry
            invalid=bought&(~torch.isfinite(ratio)|(ratio<=0))
            missing.append(invalid.any(dim=2))
            paths.append(torch.where(bought,ratio,0.).mean(dim=2))
        win=((self.open[t[:,None,None]+6,selected]/entry)>1).logical_and(bought).sum(dim=2)
        out=dict(paths=torch.stack(paths,dim=2).permute(1,0,2).cpu().numpy(),cash=cash.T.cpu().numpy(),
            missing=torch.stack(missing,dim=2).any(dim=2).T.cpu().numpy(),gross_winners=win.T.cpu().numpy())
        if return_ids:out['selected']=selected.permute(1,0,2).to(torch.int16).cpu().numpy()
        return out


def benchmark():
    r=Ranker();days=np.arange(300,428);started=time.monotonic()
    for start in range(0,len(days),64):r.block(200,days[start:start+64])
    torch.cuda.synchronize()
    report=dict(device=r.device,signal_days=len(days),momentum_variants=281,seconds=round(time.monotonic()-started,3),
        allocated_peak_bytes=torch.cuda.max_memory_allocated(),reserved_bytes=torch.cuda.memory_reserved(),ties=r.ties)
    (ROOT/'results/gpu_benchmark.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


if __name__=='__main__':
    import sys
    build_pools() if sys.argv[1]=='pools' else benchmark()
