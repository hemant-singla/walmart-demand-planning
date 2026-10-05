"""Verify representative prepared records and package compact files, excluding raw data."""
from pathlib import Path
import hashlib
import json
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
panel = pd.read_csv(ROOT/'data/prepared/sales_panel.csv')
pilot = pd.read_csv(ROOT/'data/prepared/sales_pilot.csv')
meta = pd.read_csv(ROOT/'data/prepared/panel_metadata.csv')
assert len(panel)==200 and len(pilot)==30
assert set(pilot.id).issubset(set(panel.id))
assert set(meta.loc[meta.pilot,'id'])==set(pilot.id)
assert set(panel.id)==set(meta.id)
sample_days = ['d_1','d_365','d_730','d_1914','d_1941']
original = pd.read_csv(ROOT/'data/raw/sales_train_evaluation.csv',usecols=['id']+sample_days)
original = original.set_index('id').loc[panel.id]
assert (original[sample_days].to_numpy()==panel[sample_days].to_numpy()).all()
files = []
for path in ROOT.rglob('*'):
    if not path.is_file():
        continue
    relative = path.relative_to(ROOT)
    if 'raw' in relative.parts or '__pycache__' in relative.parts or path.suffix in ['.zip','.part']:
        continue
    files.append(path)
manifest = {'status':'prepared_data_verified_models_not_started',
            'verification':'Pilot membership and source-to-panel equality checked for all 200 series on five representative days, including final holdout.',
            'files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,
                      'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)
                     if p.name!='handoff_manifest.json']}
manifest_path = ROOT/'handoff_manifest.json'
manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if manifest_path not in files:
    files.append(manifest_path)
archive = ROOT.parent/'Walmart_Claude_Starter.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(files):
        z.write(path,arcname='Walmart_Demand_Planning/'+path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any('/data/raw/' in name for name in z.namelist())
print(json.dumps({'archive':str(archive),'archive_bytes':archive.stat().st_size,
                  'prepared_bytes':sum(p.stat().st_size for p in (ROOT/'data/prepared').iterdir()),
                  'verified_panel_series':len(panel),'pilot_series':len(pilot),
                  'files_packaged':len(files)},indent=2))
