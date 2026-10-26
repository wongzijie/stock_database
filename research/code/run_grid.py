"""Rank each n,m once on5090; reuse top5 across six cashbook families."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json,os,subprocess,time
import numpy as np,pandas as pd,torch
from gpu_core import ROOT,Ranker

MODES=['basket1','basket2','basket3','basket4','basket5','daily1']
METRICS=['cagr','total_return','max_drawdown','volatility','sharpe','final_nav']
STATS={18:'buys',19:'trades',20:'wins',21:'sum_trade_return',22:'delayed_exits',23:'missing_entries',24:'max_lots',25:'terminal_lots',26:'terminal_value',27:'holding_days_sum',28:'max_holding_days',29:'stale_marks',31:'max_distinct',32:'minimum_cash',33:'max_exposure',34:'fees_paid',35:'cohorts',36:'blocked_renewals'}

def book(picks,stem,meta,first=None,fees=(0.,.001),phase=0,save_nav=False):
    first=meta['first_signal_index']if first is None else int(first);last=meta['last_signal_index'];T=len(meta['dates']);M=picks.shape[0];F=len(fees)
    out=stem.with_suffix('.stats.npy');z=np.lib.format.open_memmap(out,mode='w+',dtype=np.float64,shape=(6,M,F,64));z.flush();del z
    pp=Path(picks.filename)
    if first!=meta['first_signal_index']:
        pp=stem.with_suffix('.picks.npy');np.save(pp,np.array(picks[:,first-meta['first_signal_index']:]))
    navpath=stem.with_suffix('.nav.npy')
    if save_nav:
        nav=np.lib.format.open_memmap(navpath,mode='w+',dtype=np.float64,shape=(6,M,T-first,F));nav.flush();del nav
    dev=int(np.flatnonzero(np.array(meta['dates'])<='2015-12-31')[-1]);match=meta['dates'].index('1993-01-29')
    subprocess.run([str(ROOT/'code/book'),str(ROOT/'data'),str(pp),str(out),str(first),str(last),','.join(map(str,fees)),str(phase),str(dev),str(match),str(navpath)if save_nav else '-'],env=dict(os.environ,OMP_NUM_THREADS='8',OMP_DYNAMIC='FALSE'),check=True)
    if first!=meta['first_signal_index']:pp.unlink()
    return np.load(out),np.load(navpath,mmap_mode='r')if save_nav else None

def compute(n,meta):
    out=ROOT/'results';picks=np.load(out/'selections'/f'n{n:03d}.npy',mmap_mode='r');before=time.monotonic()
    full,_=book(picks,out/'stats'/f'n{n:03d}',meta)
    laterfirst=int(np.flatnonzero(np.array(meta['dates'])<='2015-12-31')[-1]);later,_=book(picks,out/'stats'/f'n{n:03d}-later',meta,first=laterfirst)
    assert np.all(full[:,:,:,24]<=5)and np.all(later[:,:,:,24]<=5)
    assert np.all(full[:,:,:,33]<=1+1e-10)and np.all(later[:,:,:,33]<=1+1e-10)
    records=[]
    for mode,name in enumerate(MODES):
        for mi,m in enumerate(range(20,301)):
            for f,bps in enumerate([0,10]):
                x=full[mode,mi,f];y=later[mode,mi,f];rec=dict(n=n,m=m,mode=name,bps=bps)
                for prefix,source,offset in [('full',x,0),('dev',x,6),('matched_running',x,12),('later',y,0)]:
                    rec.update({prefix+'_'+key:float(source[offset+j])for j,key in enumerate(METRICS)})
                rec.update({key:float(x[j])for j,key in STATS.items()});rec['later_terminal_lots']=float(y[25]);rec['later_max_lots']=float(y[24]);records.append(rec)
    frame=pd.DataFrame(records);assert np.isfinite(frame[['full_cagr','dev_cagr','later_cagr','full_max_drawdown']]).all().all()
    zero=frame[frame.bps==0].sort_values(['mode','m']);net=frame[frame.bps==10].sort_values(['mode','m']);assert np.all(zero.full_final_nav.to_numpy()>=net.full_final_nav.to_numpy()-1e-12)
    frame.to_csv(out/'metrics'/f'n{n:03d}.csv',index=False)
    return dict(n=n,seconds=round(time.monotonic()-before,2))

def main():
    start=time.monotonic();o=ROOT/'results'
    for d in ['selections','metrics','stats']:(o/d).mkdir(parents=True,exist_ok=True)
    r=Ranker(load_open=False,k=5);meta=r.meta;days=np.arange(meta['first_signal_index'],meta['last_signal_index']+1)
    path=o/'progress.json';state=json.loads(path.read_text())if path.exists()else dict(completed=[])
    pool=ThreadPoolExecutor(max_workers=1);pending=[];batch=128;times=[]
    def finish(fut):
        value=fut.result();times.append(value);state['completed'].append(value['n']);state.update(completed_pairs=281*len(state['completed']),portfolio_scenarios=6*281*len(state['completed']),updated_at=datetime.now(timezone.utc).isoformat());tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.replace(path)
        if len(state['completed'])%20==0 or len(state['completed'])==196:print(json.dumps(dict(completed_n=len(state['completed']),portfolio_scenarios=state['portfolio_scenarios'],seconds=round(time.monotonic()-start,1))),flush=True)
    for n in range(5,201):
        if n in state['completed']:continue
        p=np.lib.format.open_memmap(o/'selections'/f'n{n:03d}.npy',mode='w+',dtype=np.int16,shape=(281,len(days),5));i=0
        while i<len(days):
            try:block=r.block(n,days[i:i+batch],ids_only=True)
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache();batch//=2
                if batch<8:raise
                continue
            p[:,i:i+block.shape[1]]=block;i+=block.shape[1]
        p.flush();del p;pending.append(pool.submit(compute,n,meta))
        if len(pending)>=2:finish(pending.pop(0))
    for f in pending:finish(f)
    pool.shutdown();frame=pd.concat([pd.read_csv(o/'metrics'/f'n{n:03d}.csv')for n in range(5,201)],ignore_index=True)
    assert len(frame)==55076*6*2 and frame[['n','m','mode','bps']].drop_duplicates().shape[0]==len(frame)
    frame.to_csv(o/'all_metrics_long.csv',index=False);frame[frame.bps==10].to_csv(o/'all_330456_net_scenarios.csv',index=False)
    receipt=dict(complete=True,parameter_pairs=55076,portfolio_families=6,portfolio_scenarios=55076*6,fee_rows=len(frame),device=r.device,seconds=round(time.monotonic()-start,2),peak_allocated_bytes=torch.cuda.max_memory_allocated(),ties=r.ties,batch=batch,book_timings=times)
    (o/'run_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:v for k,v in receipt.items()if k!='book_timings'}),flush=True)

if __name__=='__main__':main()
