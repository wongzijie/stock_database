from pathlib import Path
import csv,json
import numpy as np

ROOT=Path(__file__).resolve().parent/'research'
def read(name):
    with (ROOT/'results'/name).open() as f:return list(csv.DictReader(f))
selected=read('selected_comparisons.csv');benchmarks=read('benchmarks.csv')
family=read('family_summary.csv');phases=read('phase_sensitivity.csv')
def num(x):return float(x)
def pct(x):return f'{100*num(x):.2f}%'
def row(key,period='later',bps=10):
    return next(x for x in selected if x['key']==key and x['period']==period and num(x['bps'])==bps)
def bm(key,period='later',bps=10):
    return next(x for x in benchmarks if x['benchmark']==key and x['period']==period and num(x['bps'])==bps)
def table(head,rows):
    return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |'for r in rows)

labels={'frozen_all':'开发期主选择，2只','frozen_basket5':'5只家族开发期选择','frozen_daily1':'每日轮换家族开发期选择','full_descriptive':'全期事后最高（非主选择）','original5':'原始12−1公式，5只','original_same_cap':'原始12−1公式，2只'}
later=[]
for key in labels:
    r=row(key)
    later.append([labels[key],f"{r['n']}/{r['m']}/{r['skip']}",pct(r['cagr']),pct(r['max_drawdown']),f"{num(r['sharpe']):.3f}",f"{num(r['final_nav']):.3f}"])
for key,label in [('SPY','SPY买入持有'),('A800_start_eligible_EW','起点641只等权持有'),('start_liquidity_top5_BH','起点流动性前5只持有')]:
    r=bm(key);later.append([label,'—',pct(r['cagr']),pct(r['max_drawdown']),f"{num(r['sharpe']):.3f}",f"{num(r['final_nav']):.3f}"])
fam=[[r['mode'],f"{r['n']}/{r['m']}",pct(r['dev_cagr']),pct(r['later_cagr']),pct(r['later_max_drawdown'])]for r in family]
cost=[]
for bps in [0,5,10,20]:
    cost.append([bps,pct(row('frozen_all',bps=bps)['cagr']),pct(row('frozen_basket5',bps=bps)['cagr']),pct(bm('SPY',bps=bps)['cagr'])if bps!=5 else '未算此费用基准',pct(bm('A800_start_eligible_EW',bps=bps)['cagr'])if bps!=5 else '未算此费用基准'])
long=[]
for period,label in [('long','1991—2025'),('matched','1993—2025现金重置'),('later','2016—2025现金重置')]:
    for key in ['frozen_all','frozen_basket5']:
        r=row(key,period);long.append([label,labels[key],pct(r['cagr']),pct(r['max_drawdown'])])
    for key,label2 in [('SPY','SPY'),('A800_start_eligible_EW','同池起点等权'),('start_liquidity_top5_BH','起点流动性前5只')]:
        if period=='long'and key=='SPY':continue
        r=bm(key,period);long.append([label,label2,pct(r['cagr']),pct(r['max_drawdown'])])
phase=[]
for key in ['frozen_all','frozen_basket5']:
    group=[r for r in phases if r['key']==key and r['period']=='later']
    phase.append([labels[key],f"{pct(min(num(r['cagr'])for r in group))} 至 {pct(max(num(r['cagr'])for r in group))}",f"{pct(min(num(r['max_drawdown'])for r in group))} 至 {pct(max(num(r['max_drawdown'])for r in group))}"])

meta=json.loads((ROOT/'results/meta.json').read_text());dates=np.array(meta['dates']);first=meta['dates'].index('2015-12-31');sub=dates[first:];years=np.array([int(d[:4])for d in sub])
a=np.load(ROOT/'results/selected_paths.npz');b=np.load(ROOT/'results/benchmark_paths.npz')
paths={k:a[k+'__later']for k in ['frozen_all','frozen_basket5','frozen_daily1']}
paths.update({k:b['later__'+k]for k in ['SPY','A800_start_eligible_EW','start_liquidity_top5_BH']})
annual=[]
for year in range(2016,2026):
    item={'year':year};end=np.flatnonzero(years==year)[-1];before=np.flatnonzero(years<year)[-1]
    for k,v in paths.items():
        assert len(v)==len(sub)
        item[k]=float(v[end]/v[before]-1)
    annual.append(item)
with (ROOT/'results/annual_later_reset.csv').open('w')as f:
    w=csv.DictWriter(f,fieldnames=list(annual[0]));w.writeheader();w.writerows(annual)
annualtable=table(['年份','2只','5只','每日轮换','SPY','同池等权'],[[r['year']]+[pct(r[k])for k in ['frozen_all','frozen_basket5','frozen_daily1','SPY','A800_start_eligible_EW']]for r in annual])

text='''# 回测结果与比较

数据实际截止2025-12-31。主要表均为扣除单边10基点（0.1%）的美元名义回报；比例按实际日历年长年化。

## 主选择与后段表现

只按1991—2015年开发期净CAGR，跨六家族选择n=164、m=99、basket2，开发期净CAGR52.64%。新动量固定排除5日，因此主信号是A[t−5]/A[t−99]−1，流动性取过去164日均值。5只家族独立选出n=184、m=197。

后段全部从2015-12-31现金1重置，保留原换仓锚点，2016年起交易，终点2025-12-31开盘。基准下一交易日开盘买入。参数列依次为n/m/排除天数。

'''+table(['策略','n/m/排除','净CAGR','最大回撤','夏普rf=0','终值/初值'],later)+'''

2只与5只候选后段净CAGR均高于三类买入持有；2只候选相对SPY高32.76个百分点，相对同池等权高29.11个百分点。每日轮换家族候选8.22%没有达到目标。全期事后最高的n187/m99只作诊断，不能作为提前选中的证据。

## 六个家族都保留，包括失败方案

'''+table(['家族','开发期所选n/m','开发期净CAGR','后段净CAGR','后段最大回撤'],fam)+'''

单只整批家族的开发期最优后段为负；不能据2只的高收益概括为越集中越好，也不能据这一daily1候选断言所有每日策略无效。

## 长历史与同期重置

'''+table(['时期','策略/基准','净CAGR','最大回撤'],long)+'''

1991年没有SPY数据，所以不列虚构的1991起点SPY收益。起点等权持有的成员数依时期分别为225、247、641；没有倒填后续IPO。完整网格的matched_running只是连续账户归一化，不能替代此表的现金重置matched。

![长期净值](../report-assets/wealth.png)

## 费用敏感性：后段净CAGR

'''+table(['单边基点','2只候选','5只候选','SPY','同池等权'],cost)+'''

单边20基点下两候选仍高于同费用基准，但扣费损耗明显。5基点只对选定策略重跑，未计算该费用基准，不以插值补数。未计冲击、税费、资金规模和现金利息。

## 五个独立换仓相位

'''+table(['候选','后段CAGR范围','后段最大回撤范围（负值）'],phase)+'''

主结果固定phase=0，没有按后段选相位。每行范围来自5个各自满足持仓上限的独立账户，不能把它们叠成25只或额外杠杆的账户。

## 参数邻域与全网格

n=154…174、m=89…109的441个basket2邻域方案，后段净CAGR中位数33.13%，最低18.15%，最高56.10%，441个均高于SPY；未声称全部高于同池等权。邻域为看完历史后的诊断，不是独立检验。

![主家族全部参数](../report-assets/full-grid.png)

所有55,076组n/m在6个家族中的结果均保留在完整归档，包含失败值；主家族完整热力图不是只抽最优附近。全网格最多5个lot、投资比例最高1.0、期末全部清仓。11,792个方案发生过目标日之后卖出的例外；主冻结候选主相位实际5日持有，无延期。

## 收益路径和深度回撤

主2只候选后段年化波动59.84%、夏普0.952；同池等权夏普0.971，收益优势并未转化为更高夏普。2只候选从2021-02-09高点至2022-06-23低点回撤75.37%，2024-02-15才恢复该高点。其1991起点全期最大回撤78.43%。

2020年2只候选上涨548.79%，高收益集中于少数强年；2021年下跌29.23%，同期SPY上涨28.73%，并非每年跑赢。

![后段逐日回撤](../report-assets/drawdown.png)

以下年度收益直接从后段重置日净值计算，另存annual_later_reset.csv；没有把原annual_selected.csv的连续长账户年度列冒充后段重置。

'''+annualtable+'''

## 交易层面

主2只候选后段共1,004笔股票往返，胜率53.49%，平均扣费单笔收益约1.17%，实际持有间隔均为5；5只候选共2,510笔，胜率52.63%。单笔平均收益不是账户CAGR，也不能把多只并行交易的收益相加得到净值。全部复算成交在results/trades。

## 结果的实际含义

历史收益目标在给定输入和模型内达到；同时回撤很深，静态股票池、供应商价格口径、历史复用和大规模搜索均未消除。本研究没有统计显著性或实盘可复制性结论。详见[验证与限制](06-validation.md)。

原始数值证据：selected_comparisons.csv、benchmarks.csv、family_summary.csv、phase_sensitivity.csv、selected_paths.npz、benchmark_paths.npz及完整660,912行归档。文档表由这些冻结文件生成，未重新选参。
'''
(ROOT/'docs/05-results.md').write_text(text)
print(json.dumps({'results_document_written':True,'annual_reset_years':len(annual),'last_year':annual[-1]},ensure_ascii=False))
