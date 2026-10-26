"""Buy-and-hold controls with fixed at-start membership, next-open entry and end-open exit."""
from pathlib import Path
import json,gzip,hashlib
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def metrics(nav,dates):
    a=np.asarray(nav,dtype=float);r=a[1:]/a[:-1]-1;years=(pd.Timestamp(str(dates[-1]))-pd.Timestamp(str(dates[0]))).days/365.25
    vol=float(r.std(ddof=1)*np.sqrt(252));cagr=float((a[-1]/a[0])**(1/years)-1);dd=float((a/np.maximum.accumulate(a)-1).min())
    return dict(cagr=cagr,total_return=float(a[-1]/a[0]-1),max_drawdown=dd,volatility=vol,sharpe=float(r.mean()*252/vol)if vol else 0.,final_nav=float(a[-1]/a[0]))

def hold(op,close,volume,first,ids,fee):
    ids=np.array(ids);entry=op[first+1,ids];ok=np.isfinite(entry)&(entry>0);bought=ids[ok];q=np.full(len(bought),1/len(ids)/(1+fee))/entry[ok];cash=float((~ok).sum()/len(ids))
    marks=np.array(close[first+1:,bought]);vol=volume[first+1:,bought];marks[(~np.isfinite(marks))|(marks<=0)|(vol<=0)]=np.nan
    marks[0]=np.where(np.isfinite(marks[0]),marks[0],entry[ok]);marks=pd.DataFrame(marks).ffill().to_numpy();assert np.isfinite(marks).all()
    nav=np.r_[1.,cash+marks@q];exitop=op[-1,bought];exitok=np.isfinite(exitop)&(exitop>0)
    nav[-1]=cash+np.sum(q*np.where(exitok,exitop*(1-fee),marks[-1]))
    return nav,dict(eligible_at_start=len(ids),bought=int(ok.sum()),unfilled_entry=int((~ok).sum()),terminal_unliquidated=int((~exitok).sum()))

def main():
    d=ROOT/'data';out=ROOT/'results';meta=json.loads((d/'meta.json').read_text());dates=np.array(meta['dates']);T=len(dates)
    op=np.load(d/'open.npy',mmap_mode='r');close=np.load(d/'adj.npy',mmap_mode='r');volume=np.load(d/'volume.npy',mmap_mode='r');eligible=np.load(d/'eligible.npy',mmap_mode='r');dollar=np.load(d/'dollar.npy',mmap_mode='r')
    raw=json.load(gzip.open(d/'sources/benchmarks/SPY.json.gz','rt'))['chart']['result'][0];q=raw['indicators']['quote'][0];adj=np.array(raw['indicators']['adjclose'][0]['adjclose'],float);vendor=np.array(q['close'],float)
    bd=pd.to_datetime(raw['timestamp'],unit='s',utc=True).tz_convert('America/New_York').strftime('%Y-%m-%d');frame=pd.DataFrame(dict(adj=adj,open=np.array(q['open'],float)*adj/vendor,volume=q['volume']),index=bd).reindex(dates)
    spo=frame.open.to_numpy(copy=True)[:,None];spc=frame.adj.to_numpy()[:,None];spv=frame.volume.to_numpy()[:,None];spo[(spv<=0)|~np.isfinite(spv)]=np.nan
    starts=dict(long=meta['first_signal_index'],matched=meta['dates'].index('1993-01-29'),later=int(np.flatnonzero(dates<='2015-12-31')[-1]));records=[];paths={}
    for period,first in starts.items():
        ids=np.flatnonzero(eligible[first]);liq=np.array(dollar[first-199:first+1]).mean(0);top=ids[np.lexsort((ids,-liq[ids]))][:5]
        for name,oo,cc,vv,members in [('A800_start_eligible_EW',op,close,volume,ids),('start_liquidity_top5_BH',op,close,volume,top),('SPY',spo,spc,spv,[0])]:
            if name=='SPY' and period=='long':continue
            for bps in [0,10,20]:
                nav,st=hold(oo,cc,vv,first,members,bps/10000);record=dict(period=period,benchmark=name,bps=bps,start=dates[first],entry=dates[first+1],end=dates[-1],**st,**metrics(nav,dates[first:]));records.append(record)
                if bps==10:paths[f'{period}__{name}']=nav
    pd.DataFrame(records).to_csv(out/'benchmarks.csv',index=False);np.savez_compressed(out/'benchmark_paths.npz',**paths)
    receipt=dict(stock_universe=800,source_cutoff=meta['source_cutoff'],controls=len(records),spy_source_sha256=hashlib.sha256((d/'sources/benchmarks/SPY.json.gz').read_bytes()).hexdigest(),start_eligible_by_period={p:int(eligible[f].sum())for p,f in starts.items()})
    (out/'benchmark_receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
