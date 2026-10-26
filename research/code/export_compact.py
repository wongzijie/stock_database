from pathlib import Path
import pandas as pd
r=Path(__file__).resolve().parents[1]
p=r/'results/all_330456_net_scenarios.csv'
if not p.exists():p=p.with_suffix('.csv.gz')
cols=['n','m','mode','full_cagr','full_max_drawdown','full_sharpe','dev_cagr','later_cagr','later_max_drawdown','later_sharpe','max_lots','max_distinct','delayed_exits','max_holding_days','terminal_lots','max_exposure']
d=pd.read_csv(p,usecols=cols);assert len(d)==330456 and d[['n','m','mode']].drop_duplicates().shape[0]==330456;assert(d.groupby('mode').size()==55076).all();assert d.max_lots.max()<=5 and d.max_exposure.max()<=1+1e-12 and d.terminal_lots.sum()==0
names={'n':'流动性天数n','m':'动量分母天数m','mode':'持仓方式','full_cagr':'1991至2025净年化_单边10bps','full_max_drawdown':'全期最大回撤','full_sharpe':'全期夏普_rf0','dev_cagr':'1991至2015净年化','later_cagr':'2016至2025重置账户净年化','later_max_drawdown':'后段最大回撤','later_sharpe':'后段夏普_rf0','max_lots':'最多同时仓位','max_distinct':'最多不同代码','delayed_exits':'延期卖出笔数','max_holding_days':'最长实际持有交易间隔','terminal_lots':'期末未平仓数','max_exposure':'最大投资比例'}
d.rename(columns=names).to_csv(r/'全部330456种组合_单边10基点.csv',index=False,encoding='utf-8-sig');print('compact330456_verified')
