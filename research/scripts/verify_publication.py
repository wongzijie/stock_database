"""Check archived publication integrity; this does not rerun the GPU research."""
from pathlib import Path
import csv,gzip,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
def sha(path):
    h=hashlib.sha256()
    with path.open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    manifest=json.loads((ROOT/'archives/manifest.json').read_text())
    parts=0
    for archive in manifest['archives']:
        for part in archive['parts']:
            path=ROOT/'archives'/part['file']
            assert path.stat().st_size==part['bytes']
            assert sha(path)==part['sha256']
            parts+=1
    sources=json.loads((ROOT/'data/source_manifest.json').read_text())
    symbols=(ROOT/'data/universe_800.txt').read_text().splitlines()
    assert len(symbols)==len(set(symbols))==len(sources)==800
    assert symbols==[x['symbol']for x in sources]
    assert sum(x['rows']for x in sources)==5071038
    assert all(x['last']=='2025-12-31'for x in sources)
    invalid=[];links=0
    for p in list((ROOT/'docs').glob('*.md'))+list((ROOT/'reports').glob('*.md'))+[ROOT.parent/'README.md']:
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://'in target or target.startswith('#'):continue
            path=(p.parent/target.split('#')[0]).resolve();links+=1
            if not path.exists():invalid.append([str(p.relative_to(ROOT.parent)),target])
    assert not invalid,invalid
    frozen=json.loads((ROOT/'results/development_frozen_choice.json').read_text())
    assert (frozen['frozen_all']['n'],frozen['frozen_all']['m'],frozen['frozen_all']['mode'])==(164,99,'basket2')
    ledger=ROOT/'results/trades/frozen_all-later-trades.csv'
    with ledger.open()as f:trades=list(csv.DictReader(f))
    assert len(trades)==1004 and all(int(x['holding_days'])==5 for x in trades)
    result={'archive_parts_verified':parts,'local_markdown_links_verified':links,'symbols':800,
            'source_rows':5071038,'primary_later_trades':len(trades),'primary_trade_holding_intervals':5}
    full=ROOT/'restored/all_660912_cost_results.csv.gz'
    if full.exists():
        modes=['basket1','basket2','basket3','basket4','basket5','daily1'];seen=bytearray(196*281*6*2)
        count=0;maxlots=0;exposure=0.;terminal=0;delayed=0
        with gzip.open(full,'rt',newline='')as f:
            for r in csv.DictReader(f):
                n,m,bps=int(r['n']),int(r['m']),int(r['bps'])
                assert 5<=n<=200 and 20<=m<=300 and bps in (0,10)
                key=(((n-5)*281+(m-20))*6+modes.index(r['mode']))*2+(bps==10)
                assert not seen[key];seen[key]=1;count+=1
                maxlots=max(maxlots,float(r['max_lots']));exposure=max(exposure,float(r['max_exposure']))
                assert float(r['minimum_cash'])>=-1e-10
                terminal+=float(r['terminal_lots'])>0
                if bps==10:delayed+=float(r['delayed_exits'])>0
        assert count==len(seen)==660912 and all(seen)
        assert maxlots<=5 and exposure<=1+1e-10 and terminal==0 and delayed==11792
        result.update(full_rows_verified=count,max_lots=maxlots,max_exposure=exposure,
                      terminal_illiquid_rows=terminal,net_scenarios_with_delayed_exit=delayed)
    else:result['full_row_check']='Restore archives first to run this check.'
    print(json.dumps(result,ensure_ascii=False))
    return result

if __name__=='__main__':
    main()
