"""Read-only frozen A800 source and exact XNYS matrices. No B2466 substitution."""
from pathlib import Path
import hashlib,json,os,shutil,time
import numpy as np,pandas as pd,exchange_calendars as xcals
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('/home/olliee/文档/Agent/stock_raw_data/raw')

def main():
    begun=time.monotonic();d=ROOT/'data';src=d/'sources/archive';src.mkdir(parents=True,exist_ok=True)
    files=sorted(SOURCE.glob('*.csv'));assert len(files)==800
    cutoff='2025-12-31';cal=xcals.get_calendar('XNYS',start='1990-01-01',end='2026-12-31');dates=cal.sessions_in_range('1990-01-02',cutoff);ds=dates.strftime('%Y-%m-%d').tolist()
    shape=(len(dates),800);fields=['adj','open','vendor_close','volume','dollar'];a={key:np.full(shape,np.nan)for key in fields};manifest=[]
    for j,p in enumerate(files):
        target=src/p.name
        if not target.exists():os.link(p,target)
        z=pd.read_csv(target);z.columns=[c.lower()for c in z.columns];z.index=pd.to_datetime(z.pop('date'))
        assert z.index.is_unique and z.index.is_monotonic_increasing and z.index[-1]==pd.Timestamp(cutoff)
        z=z.reindex(dates)
        raw=z.close.to_numpy();adj=z['adj close'].to_numpy();vol=z.volume.to_numpy();op=z.open.to_numpy()*adj/raw
        # A zero-volume stale bar is not an observed executable open.
        op[(vol<=0)|~np.isfinite(vol)|(op<=0)]=np.nan
        for key,x in dict(adj=adj,open=op,vendor_close=raw,volume=vol,dollar=raw*vol).items():a[key][:,j]=x
        manifest.append(dict(symbol=p.stem,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),rows=int(pd.read_csv(target,usecols=['date']).shape[0]),last=cutoff))
    valid=np.isfinite(a['adj'])&np.isfinite(a['vendor_close'])&np.isfinite(a['volume'])&(a['adj']>0)&(a['vendor_close']>0)&(a['volume']>0)
    bad=np.vstack([np.zeros((1,800),dtype=np.int32),np.cumsum(~valid,axis=0,dtype=np.int32)])
    eligible=np.zeros(shape,dtype=bool);eligible[252:]=(bad[253:]-bad[:-253])==0
    prefix=np.vstack([np.zeros((1,800)),np.cumsum(np.where(valid,a['dollar'],0.),axis=0)])
    for key,x in a.items():np.save(d/f'{key}.npy',x)
    np.save(d/'eligible.npy',eligible);np.save(d/'dollar_prefix.npy',prefix)
    calendar_days=np.array(ds,dtype='datetime64[D]').astype(np.int64)
    if (d/'calendar_days.npy').exists():np.testing.assert_array_equal(np.load(d/'calendar_days.npy'),calendar_days)
    np.save(d/'calendar_days.npy',calendar_days)
    meta=dict(symbols=[p.stem for p in files],names=[p.stem for p in files],dates=ds,source_cutoff=cutoff,first_signal_index=300,last_signal_index=len(dates)-7,first_signal=ds[300],last_signal=ds[-7],entry_first=ds[301],terminal_date=cutoff,dev_end='2015-12-31',test_start='2016-01-01')
    (d/'meta.json').write_text(json.dumps(meta,indent=2));(d/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
    prior=Path('/home/olliee/work/momentum-grid-5day-20261026/data/sources/benchmarks/SPY.json.gz');(d/'sources/benchmarks').mkdir(exist_ok=True)
    if not (d/'sources/benchmarks/SPY.json.gz').exists():shutil.copy2(prior,d/'sources/benchmarks/SPY.json.gz')
    # Past XNYS sessions must not be skipped by an index-union calendar.
    missing_open=~np.isfinite(a['open']);exposures=[]
    for h in [1,2,3,4,5,6]:
        ts,ss=np.where(eligible[300:-h]&missing_open[300+h:])
        exposures.extend(dict(symbol=meta['symbols'][s],signal=ds[t+300],missing=ds[t+300+h],lag=h)for t,s in zip(ts,ss))
    (d/'execution_gaps.json').write_text(json.dumps(exposures))
    report=dict(symbols=800,rows=sum(x['rows']for x in manifest),calendar_rows=len(ds),first_signal=ds[300],last_signal=ds[-7],cutoff=cutoff,initial_eligible=int(eligible[300].sum()),last_eligible=int(eligible[-1].sum()),future_open_gap_exposures=len(exposures),missing_open_symbols=sorted(set(x['symbol']for x in exposures)),seconds=round(time.monotonic()-begun,2))
    (d/'preparation_receipt.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
