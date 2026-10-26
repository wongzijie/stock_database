"""Evaluate frozen choices, matched resets, phases, fees and independent accounts."""
import json,time
from pathlib import Path
import numpy as np,pandas as pd
from gpu_core import ROOT,Ranker
from run_grid import book,MODES,METRICS
from benchmarks import metrics

def replay(picks,nav,mode,meta,first,phase=0):
    o=np.load(ROOT/'data/open.npy',mmap_mode='r');c=np.load(ROOT/'data/adj.npy',mmap_mode='r');v=np.load(ROOT/'data/volume.npy',mmap_mode='r')
    cash=np.full(5,.2)if mode==5 else np.array([1.,0,0,0,0]);lots=[];path=[1.];K=1 if mode==5 else mode+1;peak_lots=0;fee=.001;last=meta['last_signal_index'];trades=[]
    for t in range(first+1,len(meta['dates'])):
        kept=[]
        for lot in lots:
            sym,sl,en,due,px,units,mark=lot;exitpx=o[t,sym]
            if t>=due and np.isfinite(exitpx)and exitpx>0:
                cash[sl]+=units*exitpx*(1-fee);trades.append((meta['dates'][en],meta['dates'][t],meta['symbols'][sym],exitpx/px*(1-fee)/(1+fee)-1,t-en))
            else:kept.append(lot)
        lots=kept;signal=t-1
        if signal<=last and (mode==5 or (signal-300)%5==phase):
            sl=(signal-300)%5 if mode==5 else 0;blocked=any(mode!=5 or p[1]==sl for p in lots)
            if not blocked:
                budget=cash[sl];cash[sl]=0.
                for sym in picks[signal-meta['first_signal_index'],:K]:
                    px=o[t,sym]if sym<800 else np.nan
                    if not np.isfinite(px)or px<=0:cash[sl]+=budget/K
                    else:lots.append([sym,sl,t,t+5,px,budget/K/(1+fee)/px,px])
        assert len(lots)<= (5 if mode==5 else K)
        value=cash.sum();peak_lots=max(peak_lots,len(lots))
        for p in lots:
            px=c[t,p[0]]
            if np.isfinite(px)and px>0 and v[t,p[0]]>0:p[6]=px
            value+=p[5]*p[6]
        path.append(value)
    error=float(np.max(np.abs(np.array(path)/nav-1)));assert error<2e-11,error
    frame=pd.DataFrame(trades,columns=['entry','exit','symbol','return_','holding_days'])
    return dict(passed=True,max_daily_relative_error=error,max_open_lots=peak_lots,terminal_lots=len(lots),stock_trade_count=len(frame),trade_win_rate=float((frame.return_>0).mean()),mean_trade_return=float(frame.return_.mean()),max_holding_days=int(frame.holding_days.max())),frame

def main():
    started=time.monotonic();out=ROOT/'results';sel=out/'selected';sel.mkdir(exist_ok=True);meta=json.loads((ROOT/'data/meta.json').read_text());allrows=pd.read_csv(out/'all_330456_net_scenarios.csv');frozen=json.loads((out/'development_frozen_choice.json').read_text())
    fullbest=allrows.sort_values(['full_cagr','full_sharpe','n','m','mode'],ascending=[False,False,True,True,True]).iloc[0]
    choices={**frozen,'full_descriptive':dict(n=int(fullbest.n),m=int(fullbest.m),mode=fullbest['mode'])}
    choices['original5']=dict(n=200,m=252,mode='basket5',skip=21);choices['original_same_cap']=dict(n=200,m=252,mode=frozen['frozen_all']['mode'],skip=21)
    r=Ranker(load_open=False,k=5);days=np.arange(meta['first_signal_index'],meta['last_signal_index']+1)
    original=np.lib.format.open_memmap(out/'selections/original.npy',mode='w+',dtype=np.int16,shape=(1,len(days),5))
    for a in range(0,len(days),128):original[:,a:a+128]=r.block(200,days[a:a+128],skip=21,m_values=[252],ids_only=True)
    original.flush();del original,r
    import torch;torch.cuda.empty_cache()
    dates=np.array(meta['dates']);firsts=dict(long=meta['first_signal_index'],matched=meta['dates'].index('1993-01-29'),later=int(np.flatnonzero(dates<='2015-12-31')[-1]));controls=[];paths={};audits={};phaserecords=[];annual=[]
    for key,choice in choices.items():
        n=int(choice['n']);m=int(choice['m']);mode=MODES.index(choice['mode']);p=sel/f'{key}.picks.npy'
        source=np.load(out/'selections/original.npy',mmap_mode='r')if choice.get('skip')==21 else np.load(out/'selections'/f'n{n:03d}.npy',mmap_mode='r')[m-20:m-19]
        np.save(p,np.asarray(source));picks=np.load(p,mmap_mode='r')
        for period,first in firsts.items():
            stats,nav=book(picks,sel/f'{key}-{period}',meta,first=first,fees=(0,.0005,.001,.002),save_nav=True)
            for f,bps in enumerate([0,5,10,20]):
                result=metrics(nav[mode,0,:,f],dates[first:]);row=dict(key=key,n=n,m=m,mode=choice['mode'],skip=choice.get('skip',5),period=period,bps=bps,**result,max_lots=int(stats[mode,0,f,24]),max_distinct=int(stats[mode,0,f,31]),terminal_lots=int(stats[mode,0,f,25]),delayed_exits=int(stats[mode,0,f,22]),missing_entries=int(stats[mode,0,f,23]),max_holding_days=int(stats[mode,0,f,28]),stale_marks=int(stats[mode,0,f,29]),blocked_renewals=int(stats[mode,0,f,36]))
                # Independent Python metric calculation must match native incremental metrics.
                np.testing.assert_allclose([result[x]for x in METRICS],stats[mode,0,f,:6],rtol=2e-10,atol=2e-11);controls.append(row)
            path=np.array(nav[mode,0,:,2]);paths[f'{key}__{period}']=path
            if period=='later' or (key=='frozen_all'and period=='matched'):
                receipt,trades=replay(picks[0],path,mode,meta,first);audits[f'{key}__{period}']=receipt;trades.to_csv(sel/f'{key}-{period}-trades.csv',index=False)
            if period=='long':
                dt=pd.to_datetime(dates[first:]);before=1.
                for year in np.unique(dt.year):
                    end=path[np.flatnonzero(dt.year==year)[-1]];annual.append(dict(key=key,year=int(year),return_=float(end/before-1)));before=end
        if key in ['frozen_all','frozen_basket5']:
            for period in ['matched','later']:
                for phase in range(5):
                    st,_=book(picks,sel/f'phase-{key}-{period}-{phase}',meta,first=firsts[period],fees=(.001,),phase=phase)
                    phaserecords.append(dict(key=key,period=period,phase=phase,n=n,m=m,mode=choice['mode'],**{metric:float(st[mode,0,0,j])for j,metric in enumerate(METRICS)},max_lots=int(st[mode,0,0,24]),terminal_lots=int(st[mode,0,0,25])))
    pd.DataFrame(controls).to_csv(out/'selected_comparisons.csv',index=False);pd.DataFrame(phaserecords).to_csv(out/'phase_sensitivity.csv',index=False);pd.DataFrame(annual).to_csv(out/'annual_selected.csv',index=False);np.savez_compressed(out/'selected_paths.npz',**paths);(out/'independent_replay.json').write_text(json.dumps(audits,indent=2))
    family=[]
    for mode in MODES:
        group=allrows[allrows['mode']==mode];winner=group.sort_values(['dev_cagr','dev_sharpe','n','m'],ascending=[False,False,True,True]).iloc[0];family.append(dict(mode=mode,n=int(winner.n),m=int(winner.m),dev_cagr=float(winner.dev_cagr),later_cagr=float(winner.later_cagr),later_max_drawdown=float(winner.later_max_drawdown),full_cagr=float(winner.full_cagr),median_cagr=float(group.full_cagr.median()),median_later_cagr=float(group.later_cagr.median()),min_cagr=float(group.full_cagr.min()),max_cagr=float(group.full_cagr.max())))
    pd.DataFrame(family).to_csv(out/'family_summary.csv',index=False);allrows.sort_values(['dev_cagr','dev_sharpe','n','m','mode'],ascending=[False,False,True,True,True]).head(100).to_csv(out/'top100_development.csv',index=False)
    # Exact heatmap/query data for the development-frozen family; other family distributions stay in CSV.
    selected_family=allrows[allrows['mode']==frozen['frozen_all']['mode']];selected_family.to_csv(out/'frozen_family_55076.csv',index=False)
    bm=pd.read_csv(out/'benchmarks.csv');comp=pd.DataFrame(controls);primary=comp[(comp.key=='frozen_all')&(comp.bps==10)];goal=[]
    for period in ['matched','later']:
        value=primary[primary.period==period].iloc[0]
        for b in ['SPY','A800_start_eligible_EW','start_liquidity_top5_BH']:
            base=bm[(bm.period==period)&(bm.benchmark==b)&(bm.bps==10)].iloc[0];goal.append(dict(period=period,benchmark=b,strategy_cagr=float(value.cagr),benchmark_cagr=float(base.cagr),excess_cagr_pp=float((value.cagr-base.cagr)*100),beat=bool(value.cagr>base.cagr),terminal_lots=int(value.terminal_lots)))
    result=dict(choices=choices,goal_comparisons=goal,all_scenarios=len(allrows),max_observed_lots=int(allrows.max_lots.max()),max_observed_exposure=float(allrows.max_exposure.max()),terminal_illiquid_scenarios=int((allrows.terminal_lots>0).sum()),delayed_exit_scenarios=int((allrows.delayed_exits>0).sum()),independent_accounts=len(audits),seconds=round(time.monotonic()-started,2))
    (out/'analysis_summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':main()
