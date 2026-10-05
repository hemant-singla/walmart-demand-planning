"""Fixed early-history sampling and compact company-data preparation. No models."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT/'data'/'raw'
OUT = ROOT/'data'/'prepared'
STORES = ['CA_1','TX_1']
SEED = 20261003
SAMPLE_CUTOFF = 730
IDS = ['id','item_id','dept_id','cat_id','store_id','state_id']

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    calendar = pd.read_csv(RAW/'calendar.csv')
    header = pd.read_csv(RAW/'sales_train_evaluation.csv',nrows=0).columns.tolist()
    days = [c for c in header if c.startswith('d_')]
    require(len(days)==1941, 'Unexpected history length; inspect version before proceeding.')
    require(calendar.d.is_unique, 'Duplicate calendar days.')
    require(set(days).issubset(set(calendar.d)), 'Missing calendar dates.')
    candidate_parts = []
    source_ids = set()
    full_rows, missing, negatives = 0, 0, 0
    for chunk in pd.read_csv(RAW/'sales_train_evaluation.csv',chunksize=512):
        full_rows += len(chunk)
        require(chunk.id.is_unique and not source_ids.intersection(chunk.id), 'Duplicate sales IDs.')
        source_ids.update(chunk.id)
        values = chunk[days].to_numpy()
        missing += int(pd.isna(values).sum())
        negatives += int((values < 0).sum())
        part = chunk.loc[chunk.store_id.isin(STORES) & chunk.cat_id.isin(['FOODS','HOUSEHOLD'])].copy()
        if len(part):
            candidate_parts.append(part)
    require(missing==0 and negatives==0, 'Missing or negative source sales.')
    candidates = pd.concat(candidate_parts,ignore_index=True)
    early_days = [f'd_{i}' for i in range(1,SAMPLE_CUTOFF+1)]
    early = candidates[early_days].to_numpy()
    candidates['selection_units'] = early.sum(axis=1)
    candidates['selection_nonzero_days'] = (early>0).sum(axis=1)
    candidates['selection_zero_share'] = (early==0).mean(axis=1)
    eligible = candidates.loc[(candidates.selection_units>=100) &
                              (candidates.selection_nonzero_days>=100)].copy()
    eligible['volume_group'] = eligible.groupby('store_id').selection_units.transform(
        lambda s: pd.qcut(s.rank(method='first'),3,labels=['low','medium','high']).astype(str))
    eligible['pattern_group'] = np.where(eligible.selection_zero_share>=0.5,'irregular','frequent')
    eligible['stratum'] = eligible.cat_id+'_'+eligible.volume_group+'_'+eligible.pattern_group
    chosen = []
    for store in STORES:
        groups = []
        for label, group in eligible.loc[eligible.store_id==store].groupby('stratum',sort=True):
            groups.append(group.sort_values('id').sample(frac=1,random_state=SEED).index.tolist())
        ordered = []
        while any(groups):
            for group in groups:
                if group:
                    ordered.append(group.pop(0))
        require(len(ordered)>=100, f'Insufficient eligible series in {store}.')
        chosen.extend(ordered[:100])
    panel = eligible.loc[chosen].copy()
    pilot_ids = set(panel.groupby('store_id',sort=False).head(15).id)
    meta_cols = IDS+['selection_units','selection_nonzero_days','selection_zero_share',
                    'volume_group','pattern_group','stratum']
    metadata = panel[meta_cols].copy()
    metadata['pilot'] = metadata.id.isin(pilot_ids)
    metadata['selection_cutoff'] = 'd_730'
    metadata.to_csv(OUT/'panel_metadata.csv',index=False)
    panel[IDS+days].to_csv(OUT/'sales_panel.csv',index=False)
    panel.loc[panel.id.isin(pilot_ids),IDS+days].to_csv(OUT/'sales_pilot.csv',index=False)
    long = panel[IDS+days].melt(id_vars=IDS,var_name='d',value_name='units')
    require(not long.duplicated(['id','d']).any(), 'Duplicate panel daily keys.')
    require(int(long.units.sum())==int(panel[days].to_numpy().sum()), 'Panel totals do not reconcile.')
    long.to_csv(OUT/'daily_sales.csv.gz',index=False,compression='gzip')
    long.loc[long.id.isin(pilot_ids)].to_csv(OUT/'daily_sales_pilot.csv.gz',index=False,compression='gzip')
    price_parts = []
    required_pairs = set(zip(panel.store_id,panel.item_id))
    raw_price_rows = 0
    for chunk in pd.read_csv(RAW/'sell_prices.csv',chunksize=200000):
        raw_price_rows += len(chunk)
        mask = pd.Series([(s,i) in required_pairs for s,i in zip(chunk.store_id,chunk.item_id)],index=chunk.index)
        price_parts.append(chunk.loc[mask])
    prices = pd.concat(price_parts,ignore_index=True)
    require(not prices.duplicated(['store_id','item_id','wm_yr_wk']).any(), 'Duplicate price keys.')
    require(prices.sell_price.notna().all() and (prices.sell_price>0).all(), 'Invalid source prices.')
    prices.to_csv(OUT/'sell_prices_panel.csv',index=False)
    pilot_pairs = set(zip(panel.loc[panel.id.isin(pilot_ids)].store_id,panel.loc[panel.id.isin(pilot_ids)].item_id))
    prices.loc[[(s,i) in pilot_pairs for s,i in zip(prices.store_id,prices.item_id)]].to_csv(OUT/'sell_prices_pilot.csv',index=False)
    shutil.copyfile(RAW/'calendar.csv',OUT/'calendar.csv')
    joined = long.merge(calendar[['d','date','wm_yr_wk']],on='d',how='left',validate='many_to_one')
    joined = joined.merge(prices,on=['store_id','item_id','wm_yr_wk'],how='left',validate='many_to_one')
    require(len(joined)==len(long), 'Join changed observation count.')
    missing_prices = int(joined.sell_price.isna().sum())
    require(not ((joined.sell_price.isna()) & (joined.units>0)).any(), 'Positive sales without price: inspect.')
    actual_calendar = calendar.loc[calendar.d.isin(days)]
    audit = {'status':'data_prepared_no_models_run', 'seed':SEED, 'selection_cutoff_day':SAMPLE_CUTOFF,
             'selection_features':'Only d_1 through d_730; no final-test sales used for selection.',
             'source_sales_rows':full_rows, 'source_price_rows':raw_price_rows,
             'history_days':len(days), 'first_sales_date':actual_calendar.date.min(),
             'last_sales_date':actual_calendar.date.max(), 'panel_series':len(panel),
             'pilot_series':len(pilot_ids), 'daily_panel_rows':len(long),
             'panel_total_units':int(long.units.sum()), 'panel_price_rows':len(prices),
             'source_missing_sales':missing, 'source_negative_sales':negatives,
             'missing_panel_price_days':missing_prices, 'positive_sales_missing_price_days':0,
             'missing_price_policy':'Preserved, not imputed. Does not establish stockouts.',
             'store_counts':metadata.store_id.value_counts().to_dict(),
             'category_counts':metadata.cat_id.value_counts().to_dict(),
             'stratum_counts':metadata.groupby(['store_id','stratum']).size().to_dict()}
    audit['stratum_counts'] = {' / '.join(k):int(v) for k,v in audit['stratum_counts'].items()}
    (ROOT/'data'/'audit_summary.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    schemas = {}
    for p in OUT.iterdir():
        if not p.name.endswith(('.csv','.csv.gz')):
            continue
        cols = pd.read_csv(p,nrows=0).columns.tolist()
        daily_cols = [c for c in cols if c.startswith('d_')]
        description = {'bytes':p.stat().st_size,'column_count':len(cols)}
        if daily_cols:
            description.update({'identifier_columns':[c for c in cols if not c.startswith('d_')],
                                'daily_columns':{'first':daily_cols[0],'last':daily_cols[-1],
                                                 'count':len(daily_cols),'pattern':'d_<integer>, consecutive'}})
        else:
            description['columns'] = cols
        schemas[p.name] = description
    (ROOT/'data'/'prepared_schema.json').write_text(json.dumps(schemas,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='stratum_counts'},indent=2),flush=True)

if __name__=='__main__':
    main()
