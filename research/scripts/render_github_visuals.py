"""Export frozen research evidence as standalone PNGs for the GitHub showcase.

No strategy is reselected and no raw-market-data backtest is rerun.
Requires numpy and matplotlib. Source CSV/NPZ files are included in the repository.
"""
from pathlib import Path
import csv,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager,dates as mdates,ticker,colors
from matplotlib.patches import Ellipse

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'report-assets'
C={'two':'#008780','five':'#2c67b7','pool':'#bf7b2d','spy':'#6f7783',
   'ink':'#172b3a','muted':'#647281','grid':'#e4e9ed'}
for font in ['Arial Unicode MS','Arial','DejaVu Sans']:
    try:
        found=font_manager.findfont(font,fallback_to_default=False)
        plt.rcParams['font.family']=font_manager.FontProperties(fname=found).get_name()
        break
    except ValueError:pass
plt.rcParams.update({'font.size':12,'axes.labelsize':12,'xtick.labelsize':11,
                     'ytick.labelsize':12,'text.color':C['ink'],'axes.labelcolor':C['ink'],
                     'axes.edgecolor':'#bac4cc','axes.spines.top':False,'axes.spines.right':False,
                     'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'})

def rows(name):
    with (ROOT/'results'/name).open()as f:return list(csv.DictReader(f))
selected=rows('selected_comparisons.csv');bench=rows('benchmarks.csv')
annual=rows('annual_later_reset.csv')
def pick(key,bps=10):
    return next(r for r in selected if r['key']==key and r['period']=='later'and float(r['bps'])==bps)
def control(key,bps=10):
    return next(r for r in bench if r['benchmark']==key and r['period']=='later'and float(r['bps'])==bps)
def percent(x):return f'{float(x)*100:.2f}%'
def blossom(fig):
    for angle in (0,90):
        fig.add_artist(Ellipse((.967,.95),.017,.034,angle=angle,
                              transform=fig.transFigure,color=C['two'],alpha=.65,lw=0))
def header(fig,title,subtitle):
    fig.text(.07,.95,title,fontsize=23,fontweight='bold',ha='left',va='center')
    fig.text(.07,.902,subtitle,fontsize=11.5,color=C['muted'],ha='left')
    blossom(fig)
def footer(fig,text):fig.text(.07,.035,text,fontsize=10,color=C['muted'],ha='left')
manifest=[]
def save(fig,name,sources,question,notes,dpi=180):
    path=OUT/name;fig.savefig(path,dpi=dpi);plt.close(fig)
    manifest.append({'file':name,'sources':sources,'question':question,'notes':notes,
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})

# 1. A shareable research cover: returns and drawdowns have equal context.
fig=plt.figure(figsize=(12,6.75))
fig.text(.07,.9,'A800 / MOMENTUM RESEARCH',fontsize=14,color=C['two'],fontweight='bold')
fig.text(.07,.785,'5 days. Up to 5 stocks.',fontsize=38,fontweight='bold')
fig.text(.07,.705,'A complete search, with the drawdowns left visible.',fontsize=17,color=C['muted'])
items=[('2-stock basket',pick('frozen_all'),C['two']),
       ('5-stock basket',pick('frozen_basket5'),C['five']),
       ('SPY buy & hold',control('SPY'),C['spy'])]
for x,(label,r,color)in zip([.07,.375,.68],items):
    fig.text(x,.56,label,fontsize=16,color=color,fontweight='bold')
    fig.text(x,.425,percent(r['cagr']),fontsize=39,color=color,fontweight='bold')
    fig.text(x,.365,'annualized return',fontsize=12,color=C['muted'])
    fig.text(x,.275,percent(r['max_drawdown'])+' max drawdown',fontsize=14,fontweight='bold')
fig.text(.07,.165,'2016–2025 reset accounts · 10 bps per side · No leverage',fontsize=12)
fig.text(.07,.112,'Parameters chosen on 1991–2015. Later years were used in earlier research.',fontsize=10.5,color=C['muted'])
fig.text(.07,.07,'Static universe and vendor price proxies remain limitations. Historical results, not forecasts.',fontsize=10.5,color=C['muted'])
blossom(fig)
save(fig,'research-cover.png',['selected_comparisons.csv','benchmarks.csv'],
     'What is the historical return/risk tradeoff?',{'period':'2016–2025','bps_oneway':10,'rates':'CAGR and daily maximum drawdown'})

# 2. Matched return and drawdown comparison, with zero anchored bars.
data=[('2 stocks / n164 m99',pick('frozen_all'),C['two']),
      ('5 stocks / n184 m197',pick('frozen_basket5'),C['five']),
      ('SPY buy & hold',control('SPY'),C['spy']),
      ('Same-pool buy & hold',control('A800_start_eligible_EW'),C['pool'])]
fig,axs=plt.subplots(1,2,figsize=(12,6),sharey=True,gridspec_kw={'wspace':.18})
fig.subplots_adjust(left=.25,right=.94,bottom=.2,top=.79)
header(fig,'Higher return came with deeper drawdowns','2016–2025 reset accounts | 10 bps per side | percentages')
y=np.arange(4)
for ax,field,title in zip(axs,['cagr','max_drawdown'],['Annualized return','Maximum daily drawdown']):
    values=np.array([float(r[field])*100 for _,r,_ in data])
    ax.barh(y,values,color=[c for _,_,c in data],height=.56)
    ax.set_title(title,fontsize=14,pad=15)
    ax.axvline(0,color='#708090',lw=.8);ax.grid(axis='x',color=C['grid']);ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(100,decimals=0))
    ax.set_xlim((0,62)if field=='cagr'else(-90,0))
    for yi,v in zip(y,values):
        if field=='cagr':ax.text(v+1,yi,f'{v:.2f}%',va='center',fontsize=12,fontweight='bold')
        else:ax.text(v+2,yi,f'{v:.2f}%',va='center',fontsize=12,fontweight='bold',color='white')
axs[0].set_yticks(y,[x[0]for x in data]);axs[0].invert_yaxis()
footer(fig,'Same-pool control holds the 641 names eligible at the start. Risk is calculated from daily NAV.')
save(fig,'return-and-risk.png',['selected_comparisons.csv','benchmarks.csv'],
     'How much drawdown accompanied the return advantage?',{'period':'2016–2025','bps_oneway':10,'bar_baseline':0})

# 3. Export the report's wealth comparison as a portable static image.
meta=json.loads((ROOT/'results/meta.json').read_text());first=meta['dates'].index('2015-12-31')
dates=np.array(meta['dates'][first:],dtype='datetime64[D]')
a=np.load(ROOT/'results/selected_paths.npz');b=np.load(ROOT/'results/benchmark_paths.npz')
paths=[('2-stock basket',a['frozen_all__later'],C['two']),
       ('5-stock basket',a['frozen_basket5__later'],C['five']),
       ('Same-pool buy & hold',b['later__A800_start_eligible_EW'],C['pool']),
       ('SPY buy & hold',b['later__SPY'],C['spy'])]
months=dates.astype('datetime64[M]');ix=np.r_[0,np.flatnonzero(months[1:]!=months[:-1]),len(dates)-1];ix=np.unique(ix)
fig,ax=plt.subplots(figsize=(12,6.4));fig.subplots_adjust(left=.085,right=.86,bottom=.2,top=.76)
header(fig,'How one unit of capital evolved','2016–2025 reset accounts | month-end observations | 10 bps per side | log scale')
for j,(label,values,color)in enumerate(paths):
    assert len(values)==len(dates)and np.all(values>0)
    ax.plot(dates[ix],values[ix],color=color,lw=2.1,ls='--'if j==3 else '-',label=label)
    ax.annotate(f'{values[-1]:.2f}×',(mdates.date2num(dates[-1]),values[-1]),xytext=(10,0),textcoords='offset points',color=color,fontsize=12,fontweight='bold',va='center')
ax.set_yscale('log');ax.set_ylim(.7,90);ax.set_xlim(dates[0],dates[-1]);ax.set_ylabel('Net wealth / starting capital')
ax.set_yticks([1,2,5,10,20,50],['1×','2×','5×','10×','20×','50×'])
ticks=np.array(['2015-12-31','2018-01-01','2020-01-01','2022-01-01','2024-01-01','2025-12-31'],dtype='datetime64[D]')
ax.set_xticks(ticks,['2015-12-31','2018','2020','2022','2024','2025-12-31'])
ax.grid(axis='y',which='major',color=C['grid']);ax.legend(loc='upper left',ncol=2,frameon=False,bbox_to_anchor=(0,1.16),fontsize=10.5)
footer(fig,'Monthly sampling is for display only. CAGR and maximum drawdown use the original daily accounts.')
save(fig,'later-wealth.png',['selected_paths.npz','benchmark_paths.npz','meta.json'],
     'How did the later-period reset accounts compound?',{'period':'2016–2025','bps_oneway':10,'wealth_scale':'logarithmic','sampling':'first baseline and month ends'})

# 4. Export the interactive fee-sensitivity chart; missing benchmark 5 bps is not fabricated.
fig,ax=plt.subplots(figsize=(12,6));fig.subplots_adjust(left=.085,right=.86,bottom=.2,top=.76)
header(fig,'Transaction costs materially reduce the return','2016–2025 reset accounts | annualized return | fee charged on both entry and exit')
for label,key,color,is_control in [('2-stock basket','frozen_all',C['two'],False),('5-stock basket','frozen_basket5',C['five'],False),('Same-pool buy & hold','A800_start_eligible_EW',C['pool'],True),('SPY buy & hold','SPY',C['spy'],True)]:
    xs=[0,10,20]if is_control else[0,5,10,20]
    ys=[float((control(key,x)if is_control else pick(key,x))['cagr'])*100 for x in xs]
    ax.plot(xs,ys,'o--'if is_control else'o-',color=color,lw=2,ms=6,label=label)
    ax.annotate(f'{ys[-1]:.2f}%',(xs[-1],ys[-1]),xytext=(10,0),textcoords='offset points',color=color,va='center',fontsize=12,fontweight='bold')
ax.set_xlim(-.5,20.5);ax.set_ylim(0,70);ax.set_xticks([0,5,10,20]);ax.set_xlabel('One-way trading fee (basis points)')
ax.yaxis.set_major_formatter(ticker.PercentFormatter(100,decimals=0));ax.grid(axis='y',color=C['grid'])
ax.legend(ncol=2,frameon=False,loc='upper left',bbox_to_anchor=(0,1.16),fontsize=10.5)
footer(fig,'Markers are calculated scenarios. Benchmarks: 0/10/20 bps only. Market impact and taxes are not modeled.')
save(fig,'cost-sensitivity.png',['selected_comparisons.csv','benchmarks.csv'],
     'Does the return advantage survive higher assumed fees?',{'period':'2016–2025','strategy_bps':[0,5,10,20],'benchmark_bps':[0,10,20]})

# 5. Exact annual values expose concentration, losses and benchmark comparisons.
keys=['frozen_all','frozen_basket5','SPY','A800_start_eligible_EW'];labels=['2-stock basket','5-stock basket','SPY buy & hold','Same-pool buy & hold']
matrix=np.array([[float(r[k])*100 for r in annual]for k in keys])
cmap=colors.LinearSegmentedColormap.from_list('signed_returns',['#c57931','#fffdfa','#2769ad'])
norm=colors.TwoSlopeNorm(vmin=-35,vcenter=0,vmax=550)
fig,ax=plt.subplots(figsize=(12,5.5));fig.subplots_adjust(left=.21,right=.91,bottom=.25,top=.76)
header(fig,'The annual path is uneven','2016–2025 calendar-year returns | reset accounts | 10 bps per side | exact cell labels')
im=ax.imshow(matrix,cmap=cmap,norm=norm,aspect='auto')
ax.set_yticks(range(4),labels);ax.set_xticks(range(10),[r['year']for r in annual]);ax.tick_params(length=0,pad=10)
for y in range(4):
    for x in range(10):
        rgba=cmap(norm(matrix[y,x]));luma=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
        ax.text(x,y,f'{matrix[y,x]:+.1f}%',ha='center',va='center',fontsize=10.5,color='white'if luma<.55 else C['ink'],fontweight='bold')
ax.set_xticks(np.arange(-.5,10,1),minor=True);ax.set_yticks(np.arange(-.5,4,1),minor=True);ax.grid(which='minor',color='white',linewidth=3);ax.tick_params(which='minor',length=0)
cax=fig.add_axes([.935,.25,.014,.51]);cb=fig.colorbar(im,cax=cax);cb.set_ticks([-35,0,100,300,550]);cb.set_ticklabels(['−35%','0%','100%','300%','550%']);cb.ax.tick_params(labelsize=9)
footer(fig,'2020 drove a large share of historical compounding; 2021 was a loss for the 2-stock basket.')
save(fig,'annual-returns.png',['annual_later_reset.csv'],
     'Were the returns consistent each year?',{'period':'2016–2025','bps_oneway':10,'measure':'calendar-year return','palette':'diverging around zero; values are not confidence intervals'})

# 6. A separate 1280x640 share card, with central safe margins for previews.
fig=plt.figure(figsize=(12,6))
fig.text(.5,.9,'A800 / MOMENTUM RESEARCH',ha='center',fontsize=12,color=C['two'],fontweight='bold')
fig.text(.5,.78,'5 days. Up to 5 stocks.',ha='center',fontsize=29,fontweight='bold')
fig.text(.5,.69,'2016–2025 reset accounts · 10 bps per side',ha='center',fontsize=11,color=C['muted'])
for x,(label,r,color)in zip([.24,.5,.76],items):
    short={'2-stock basket':'2-stock basket','5-stock basket':'5-stock basket','SPY buy & hold':'SPY buy & hold'}[label]
    fig.text(x,.55,short,ha='center',fontsize=11,color=color)
    fig.text(x,.435,percent(r['cagr']),ha='center',fontsize=30,color=color,fontweight='bold')
    fig.text(x,.365,'annualized return',ha='center',fontsize=10,color=C['muted'])
    fig.text(x,.285,'DD '+percent(r['max_drawdown']),ha='center',fontsize=12,fontweight='bold')
fig.text(.5,.175,'Parameters chosen on 1991–2015 · No leverage',ha='center',fontsize=10)
fig.text(.5,.115,'Historical snapshot. Static universe, prior research reuse and execution limits remain.',ha='center',fontsize=8.7,color=C['muted'])
save(fig,'social-preview.png',['selected_comparisons.csv','benchmarks.csv'],
     'What should a shared repository link communicate?',{'period':'2016–2025','bps_oneway':10,'dimensions':[1280,640],'purpose':'repository social preview; central safe area'},dpi=1280/12)

OUT.mkdir(exist_ok=True)
(OUT/'visualization-manifest.json').write_text(json.dumps({'purpose':'GitHub image showcase of frozen A800 results','generated_date':'2026-10-26','new_images':manifest,'archival_images':['wealth.png','drawdown.png','full-grid.png'],'original_numeric_results_modified':False},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'rendered':len(manifest),'images':[r['file']for r in manifest]}))
