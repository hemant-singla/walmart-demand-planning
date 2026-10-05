"""Download only the three required public M5 files and verify published MD5s."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'calendar.csv': '3ffeab2991b0c8e861d008b39ea4c95c',
    'sales_train_evaluation.csv': 'b806dfc9f30a745102b708c09951f6aa',
    'sell_prices.csv': '08c591caa99e55daf3e0ccac913f7c85',
}

def digest(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            md5.update(block)
            sha.update(block)
    return md5.hexdigest(), sha.hexdigest()

def acquire(entry):
    name, expected = entry
    raw = ROOT / 'data' / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    dest = raw / name
    url = f'https://zenodo.org/records/10203108/files/{name}?download=1'
    if dest.exists():
        actual, sha = digest(dest)
        if actual != expected:
            raise RuntimeError(f'Existing {name} differs from published checksum; preserve and inspect it.')
        print(f'Already verified: {name}', flush=True)
    else:
        partial = raw / (name + '.part')
        request = urllib.request.Request(url, headers={'User-Agent':'M5-Portfolio-Data-Acquisition/1.0'})
        print(f'Downloading: {name}', flush=True)
        with urllib.request.urlopen(request, timeout=60) as response, partial.open('wb') as target:
            for block in iter(lambda: response.read(1024*1024), b''):
                target.write(block)
        actual, sha = digest(partial)
        if actual != expected:
            raise RuntimeError(f'Checksum mismatch: {name}; partial retained for inspection.')
        partial.replace(dest)
        print(f'Verified: {name} ({dest.stat().st_size:,} bytes)', flush=True)
    return {'file':name, 'url':url, 'bytes':dest.stat().st_size, 'published_md5':expected,
            'verified_md5':actual, 'sha256':sha}

if __name__ == '__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(acquire, FILES.items()))
    manifest = {'verified_at_utc':datetime.now(timezone.utc).isoformat(),
                'original_source':'https://www.kaggle.com/competitions/m5-forecasting-accuracy/data',
                'download_source':'https://zenodo.org/records/10203108',
                'provenance':'Record lists University of Nicosia and states taken over from Kaggle.',
                'redistribution':'Keep raw files local. Verify original data terms before redistributing.',
                'files':records}
    (ROOT/'data'/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('All three source files verified; manifest saved.', flush=True)
