"""Stage an independent rerun without modifying archived code or results."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--workspace', required=True, type=Path)
ap.add_argument('--csv-dir', required=True, type=Path)
ap.add_argument('--spy-json', required=True, type=Path)
ap.add_argument('--require-original-hashes', action='store_true')
args = ap.parse_args()
root = Path(__file__).resolve().parents[1]
work = args.workspace.expanduser().resolve()
if work.exists() and any(work.iterdir()):
    raise SystemExit('Workspace must be absent or empty; archived results must not be overwritten.')
manifest = json.loads((root/'data/source_manifest.json').read_text())
source = args.csv_dir.expanduser().resolve()
files = sorted(source.glob('*.csv'))
expected = {r['symbol']: r for r in manifest}
if {p.stem for p in files} != set(expected):
    raise SystemExit('CSV filenames must match the exact 800-symbol manifest.')
hashes = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
different = [s for s in sorted(expected) if hashes[s] != expected[s]['sha256']]
spy = args.spy_json.expanduser().resolve()
spy_hash = hashlib.sha256(spy.read_bytes()).hexdigest()
spy_expected = json.loads((root/'results/benchmark_receipt.json').read_text())['spy_source_sha256']
if args.require_original_hashes and (different or spy_hash != spy_expected):
    raise SystemExit(f'Original input hashes differ: {len(different)} CSVs, SPY match={spy_hash == spy_expected}')
work.mkdir(parents=True, exist_ok=True)
shutil.copytree(root/'code', work/'code')
shutil.copy2(root/'PROTOCOL.json', work/'PROTOCOL.json')
staged = work/'inputs/archive'
staged.mkdir(parents=True)
for p in files:
    shutil.copy2(p, staged/p.name)
bench = work/'data/sources/benchmarks'
bench.mkdir(parents=True)
shutil.copy2(spy, bench/'SPY.json.gz')
spec = importlib.util.spec_from_file_location('archived_prepare', work/'code/prepare.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.SOURCE = staged
module.main()
receipt = {'workspace': str(work), 'different_original_csv_hashes': different,
           'spy_original_hash_matches': spy_hash == spy_expected,
           'archived_source_modified': False}
(work/'input_staging_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
