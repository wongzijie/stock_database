"""Verify and restore the published result archives using only Python stdlib."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import shutil
import tempfile

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    archive = root/'archives'
    manifest = json.loads((archive/'manifest.json').read_text())
    output = (args.output or root/'restored').expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    for item in manifest['archives']:
        target = output/item['destination']
        if target.parent != output:
            raise ValueError('Unsafe archive destination')
        if target.exists():
            if digest(target) != item['original_sha256']:
                raise ValueError(f'Refusing to overwrite different file: {target}')
            print(json.dumps({'file': target.name, 'status': 'already_verified'}, ensure_ascii=False))
            continue
        with tempfile.TemporaryDirectory(dir=output) as work:
            packed = Path(work)/'packed'
            with packed.open('wb') as sink:
                for part in item['parts']:
                    path = archive/part['file']
                    if path.parent != archive or not path.is_file():
                        raise ValueError('Missing or unsafe part path')
                    if path.stat().st_size != part['bytes'] or digest(path) != part['sha256']:
                        raise ValueError(f'Archive part checksum mismatch: {path.name}')
                    with path.open('rb') as stream:
                        shutil.copyfileobj(stream, sink)
            if digest(packed) != item['packed_sha256']:
                raise ValueError(f'Combined archive checksum mismatch: {item["id"]}')
            unpacked = Path(work)/'restored'
            if item['codec'] == 'gzip':
                with gzip.open(packed, 'rb') as stream, unpacked.open('wb') as sink:
                    shutil.copyfileobj(stream, sink)
            elif item['codec'] == 'raw':
                packed.rename(unpacked)
            else:
                raise ValueError('Unknown archive codec')
            if unpacked.stat().st_size != item['original_bytes'] or digest(unpacked) != item['original_sha256']:
                raise ValueError(f'Restored file checksum mismatch: {target.name}')
            unpacked.rename(target)
        print(json.dumps({'file': target.name, 'status': 'restored_and_verified',
                          'bytes': target.stat().st_size}, ensure_ascii=False))

if __name__ == '__main__':
    main()
