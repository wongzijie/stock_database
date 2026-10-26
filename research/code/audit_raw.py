"""Independently reconcile chosen trades to original CSVs and a second snapshot."""
from pathlib import Path
import json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'results';selected=out/'selected';trades=pd.read_csv(selected/'frozen_all-later-trades.csv');src=ROOT/'data/sources/archive';errors=[];other=[];anomalies=[]
    b=Path('/home/olliee/work/momentum-grid-5day-20261026/data');bm=json.loads((b/'meta.json').read_text());bo=np.load(b/'open.npy',mmap_mode='r');symidx={s:i for i,s in enumerate(bm['symbols'])};didx={d:i for i,d in enumerate(bm['dates'])}
    for symbol,group in trades.groupby('symbol'):
        frame=pd.read_csv(src/f'{symbol}.csv').set_index('date');price=frame.open*frame['adj close']/frame.close
        for row in group.itertuples():
            raw=float(price.loc[row.exit]/price.loc[row.entry]*(1-.001)/(1+.001)-1);err=abs(raw-row.return_);errors.append(err)
            assert frame.loc[row.entry,'volume']>0 and frame.loc[row.exit,'volume']>0
            if abs(raw)>1:anomalies.append(dict(symbol=symbol,entry=row.entry,exit=row.exit,return_=raw))
            if symbol in symidx:
                j=symidx[symbol];p0=bo[didx[row.entry],j];p1=bo[didx[row.exit],j]
                if np.isfinite(p0)and np.isfinite(p1)and p0>0 and p1>0:
                    r=float(p1/p0*(1-.001)/(1+.001)-1);other.append(dict(symbol=symbol,entry=row.entry,exit=row.exit,legacy_return=raw,other_return=r,abs_difference=abs(raw-r)))
    assert max(errors)<1e-10,max(errors)
    diff=pd.DataFrame(other);diff.to_csv(out/'cross_snapshot_trade_checks.csv',index=False);trades.nlargest(25,'return_').to_csv(out/'top25_realized_trades.csv',index=False);trades.nsmallest(25,'return_').to_csv(out/'worst25_realized_trades.csv',index=False)
    receipt=dict(raw_csv_trades_checked=len(trades),raw_csv_symbols_checked=int(trades.symbol.nunique()),max_raw_return_absolute_error=float(max(errors)),second_snapshot_trades=len(diff),second_snapshot_max_difference=float(diff.abs_difference.max()),second_snapshot_median_difference=float(diff.abs_difference.median()),second_snapshot_differences_over_1bp=int((diff.abs_difference>.0001).sum()),absolute_trade_returns_over100pct=anomalies,max_holding_days=int(trades.holding_days.max()),holding_days_not5=int((trades.holding_days!=5).sum()))
    (out/'raw_source_audit.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
