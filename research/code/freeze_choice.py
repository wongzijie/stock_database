"""Development columns only. Save selection before interpreting later performance."""
from pathlib import Path
import json,pandas as pd
r=Path(__file__).resolve().parents[1]/'results'
d=pd.read_csv(r/'all_330456_net_scenarios.csv')
s=d.sort_values(['dev_cagr','dev_sharpe','n','m','mode'],ascending=[False,False,True,True,True])
cols=['n','m','mode','dev_cagr','dev_sharpe'];choice={'frozen_all':s.iloc[0][cols].to_dict()}
for name,mode in [('frozen_basket5','basket5'),('frozen_daily1','daily1')]:choice[name]=s[s['mode']==mode].iloc[0][cols].to_dict()
p=r/'development_frozen_choice.json'
if p.exists():assert json.loads(p.read_text())==choice,'Existing frozen choice differs; do not silently replace'
else:p.write_text(json.dumps(choice,indent=2))
print(json.dumps(dict(frozen_choice_verified=True,choices=choice)))
