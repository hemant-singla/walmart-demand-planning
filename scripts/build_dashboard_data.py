"""Checkpoint 5a: build dashboard tables (plain CSV, Power BI ready) from saved results (no model refits),
then reconcile them against the results files. Output: results/dashboard/."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.features import _ffill_past
from wdp.priority import score

OUT = ROOT / 'results' / 'dashboard'
TOL = 1e-9


def investigation_text(r, unc_hi):
    """Plain description of observed evidence. Never asserts stockouts, supplier issues or causes."""
    notes = []
    if pd.notna(r.bias_signed) and abs(r.bias_signed) >= max(3.0, 0.25 * r.recent_error if pd.notna(r.recent_error) else 3.0):
        if r.bias_signed > 0:
            notes.append(f'Forecasts ran above recorded sales by {r.bias_signed:.1f} units/week on average over the last 8 weeks; '
                         'check whether the sales level has dropped before relying on the forecast.')
        else:
            notes.append(f'Recorded sales ran above forecasts by {-r.bias_signed:.1f} units/week on average over the last 8 weeks; '
                         'check for a demand increase or promotion not yet reflected in history.')
    if pd.notna(r.uncertainty) and r.uncertainty >= unc_hi:
        notes.append(f'Wide 90% range: daily interval widths sum to {r.uncertainty:.0f} units over the next 7 days; treat the point forecast as low-confidence.')
    if pd.notna(r.price_chg4) and abs(r.price_chg4) >= 0.05:
        notes.append(f'Observed shelf price changed {100 * r.price_chg4:+.0f}% versus 4 weeks earlier (association only, not an estimated promotional effect).')
    if r.sales_ratio_7_28 >= 1.5 or (r.sales_ratio_7_28 <= 0.5 and r.volume > 0):
        notes.append(f'Last-7-day sales are {r.sales_ratio_7_28:.1f}x the 28-day daily average.')
    if r.days_since_sale >= 7:
        notes.append(f'No recorded sales for {int(r.days_since_sale)} days; zero sales may reflect demand, availability or recording, which this data cannot distinguish.')
    if not notes:
        notes.append('Large recent forecast errors in units; review the latest sales against the forecast.')
    return ' '.join(notes)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    w = windows()
    fz = json.loads((ROOT / 'config' / 'frozen_choices.json').read_text())
    p = load_panel('panel', seal_after=None)
    meta = p.meta[['id', 'item_id', 'dept_id', 'cat_id', 'store_id', 'volume_group', 'pattern_group']].reset_index().rename(columns={'index': 'idx'})
    # ---- source coverage
    audit = json.loads((ROOT / 'data' / 'audit_summary.json').read_text())
    cp1 = json.loads((ROOT / 'results' / 'checkpoint1' / 'checkpoint1.json').read_text())
    coverage = {'audit': {k: v for k, v in audit.items() if k != 'stratum_counts'}, 'checkpoint1': cp1,
                'strata': audit['stratum_counts'], 'windows': w,
                'checks': pd.read_csv(ROOT / 'results' / 'checkpoint1' / 'reconciliation_checks.csv').to_dict('records')}
    (OUT / 'coverage.json').write_text(json.dumps(coverage, indent=1, default=str))
    kv = {**{k: v for k, v in coverage['audit'].items() if not isinstance(v, (dict, list))},
          **{f'cp1_{k}': v for k, v in cp1.items() if not isinstance(v, (dict, list))}}
    pd.DataFrame({'metric': list(kv), 'value': [str(v) for v in kv.values()]}).to_csv(OUT / 'coverage_summary.csv', index=False)
    pd.DataFrame([{'store_stratum': k, 'series': v} for k, v in audit['stratum_counts'].items()]).to_csv(OUT / 'strata.csv', index=False)
    pd.DataFrame(coverage['checks']).to_csv(OUT / 'data_checks.csv', index=False)
    meta.to_csv(OUT / 'series.csv', index=False)
    # ---- model comparison (copied from results; reconciled below)
    v = pd.read_csv(ROOT / 'results/checkpoint3/validation_metrics.csv').assign(period='validation (6 origins)', segment_type='all', segment='all')
    vs = pd.read_csv(ROOT / 'results/checkpoint3/validation_metrics_segments.csv').assign(period='validation (6 origins)')
    hs = pd.read_csv(ROOT / 'results/holdout/holdout_forecast_metrics.csv').assign(period='holdout (origin 1913)')
    cols = ['period', 'model', 'segment_type', 'segment', 'mean_rmsse', 'median_rmsse', 'wape', 'bias', 'actual_units', 'rmsse_undefined']
    mc = pd.concat([v, vs, hs])[cols]
    mc['segment'] = mc.segment.astype(str)
    mc.to_csv(OUT / 'model_comparison.csv', index=False)
    rt = pd.read_csv(ROOT / 'results/checkpoint3/validation_runtime.csv')
    rt.to_csv(OUT / 'runtime.csv', index=False)
    cov_v = pd.read_csv(ROOT / 'results/checkpoint3/interval_coverage_validation.csv', index_col=0).assign(period='validation')
    cov_h = pd.read_csv(ROOT / 'results/holdout/holdout_interval_coverage.csv', index_col=0).assign(period='holdout')
    pd.concat([cov_v, cov_h]).rename_axis('slice').reset_index().to_csv(OUT / 'interval_coverage.csv', index=False)
    # ---- review lists (frozen proposed rule) for validation + holdout origins
    sig = pd.concat([pd.read_csv(ROOT / 'results/checkpoint4/signals_preholdout.csv.gz'),
                     pd.read_csv(ROOT / 'results/holdout/holdout_signals.csv.gz')], ignore_index=True)
    val_o = list(range(w['priority_validation_origins']['first'], w['priority_validation_origins']['last'] + 1, 7))
    hold_o = w['holdout']['weekly_priority_origins']
    sig = sig[sig.origin.isin(val_o + hold_o)].reset_index(drop=True)
    pr = fz['proposed_rule']
    wts = tuple(pr['weights'][k] for k in ['recent_error', 'bias', 'uncertainty'])
    sig['score'] = np.nan
    for T, g in sig.groupby('origin'):
        sig.loc[g.index, 'score'] = score(g, 'proposed', wts, pr['normalisation'])
    sig['rank'] = sig.groupby('origin').score.rank(ascending=False, method='first').astype(int)
    # tie-break identical to priority.top_k (score desc, idx asc)
    sig = sig.sort_values(['origin', 'score', 'idx'], ascending=[True, False, True])
    sig['rank'] = sig.groupby('origin').cumcount() + 1
    for b in ['volume', 'recent_error']:
        s2 = sig.assign(_s=sig[b].fillna(-np.inf)).sort_values(['origin', '_s', 'idx'], ascending=[True, False, True])
        sig.loc[s2.index, f'rank_{b}'] = s2.groupby('origin').cumcount().to_numpy() + 1
    Pf = _ffill_past(p.P)
    extra = []
    for T in sig.origin.unique():
        hist = p.Y[:, :T]
        nz = hist > 0
        extra.append(pd.DataFrame({'origin': T, 'idx': np.arange(p.n),
                                   'price_chg4': Pf[:, T - 8] / Pf[:, T - 36] - 1,
                                   'sales_ratio_7_28': (hist[:, -7:].mean(1) + 1e-9) / (hist[:, -28:].mean(1) + 1e-9),
                                   'days_since_sale': np.where(nz.any(1), np.argmax(nz[:, ::-1], axis=1), 365)}))
    sig = sig.merge(pd.concat(extra), on=['origin', 'idx'])
    iv = pd.concat([pd.read_csv(ROOT / f'results/backtest/intervals_{fz["forecast_model"]}.csv.gz'),
                    pd.read_csv(ROOT / 'results/holdout/holdout_intervals.csv.gz')], ignore_index=True)
    iv = iv[iv.origin.isin(val_o + hold_o)]
    nxt = iv[iv.h <= 7].groupby(['origin', 'idx']).forecast.sum().rename('forecast_next7').reset_index()
    sig = sig.merge(nxt, on=['origin', 'idx'], how='left').merge(meta, on='idx')
    unc_hi = sig.groupby('origin').uncertainty.transform(lambda s: s.quantile(0.9))
    sig['suggested_investigation'] = [investigation_text(r, u) for r, u in zip(sig.itertuples(), unc_hi)]
    sig['period'] = np.where(sig.origin.isin(hold_o), 'holdout', 'validation (weights chosen on these weeks)')
    sig['event'] = sig.outcome_ne > fz['event_threshold_normalised_error']
    keep = ['origin', 'period', 'rank', 'rank_volume', 'rank_recent_error', 'idx', 'id', 'item_id', 'store_id', 'cat_id', 'dept_id',
            'volume_group', 'pattern_group', 'score', 'recent_error', 'bias_signed', 'uncertainty', 'volume', 'forecast_next7',
            'price_chg4', 'sales_ratio_7_28', 'days_since_sale', 'suggested_investigation',
            'outcome_ae', 'outcome_signed', 'outcome_ne', 'event']
    sig[keep].round(4).to_csv(OUT / 'review_lists.csv', index=False)
    # ---- product forecast data
    iv[['origin', 'idx', 'h', 'd', 'forecast', 'lower', 'upper']].round(3).to_csv(OUT / 'forecast_intervals.csv', index=False)
    first = min(val_o) - 120
    hist = pd.DataFrame(p.Y[:, first - 1:], columns=range(first, p.D + 1))
    hist['idx'] = np.arange(p.n)
    hist.melt(id_vars='idx', var_name='d', value_name='units').to_csv(OUT / 'sales_history.csv', index=False)
    cal = pd.read_csv(ROOT / 'data/prepared/calendar.csv')[['d', 'date']]
    cal['d'] = cal.d.str.replace('d_', '', regex=False).astype(int)
    cal.to_csv(OUT / 'calendar_dates.csv', index=False)
    # ---- retrospective rule results
    rv = pd.read_csv(ROOT / 'results/checkpoint4/validation_rule_weekly_selected.csv').assign(period='validation')
    rh = pd.read_csv(ROOT / 'results/holdout/holdout_rule_weekly.csv').assign(period='holdout')
    rr = pd.concat([rv, rh]).drop(columns=['selected'])
    rr.to_csv(OUT / 'rule_weekly.csv', index=False)
    rs = pd.concat([pd.read_csv(ROOT / 'results/checkpoint4/validation_rule_summary.csv').assign(period='validation'),
                    pd.read_csv(ROOT / 'results/holdout/holdout_rule_summary.csv').assign(period='holdout')])
    rs.to_csv(OUT / 'rule_summary.csv', index=False)
    (OUT / 'frozen_choices.json').write_text(json.dumps(fz, indent=1))
    # ---- reconciliation: dashboard tables vs results
    checks = []
    lab = pr['label']
    for K in w['capacities']:
        for T, g in sig.groupby('origin'):
            top = g[g['rank'] <= K]
            cap = top.outcome_ae.sum() / g.outcome_ae.sum()
            ref = rr[(rr.rule == lab) & (rr.origin == T) & (rr.K == K)].captured_ae_share
            checks.append({'check': f'list captured share K={K} origin={T}', 'dashboard': cap,
                           'results': float(ref.iloc[0]) if len(ref) else np.nan})
            for b in ['volume', 'recent_error']:
                topb = g[g[f'rank_{b}'] <= K]
                capb = topb.outcome_ae.sum() / g.outcome_ae.sum()
                refb = rr[(rr.rule == b) & (rr.origin == T) & (rr.K == K)].captured_ae_share
                checks.append({'check': f'{b} captured K={K} origin={T}', 'dashboard': capb, 'results': float(refb.iloc[0])})
    ck = pd.DataFrame(checks)
    ck['pass'] = (ck.dashboard - ck.results).abs() < TOL
    ck.to_csv(OUT / 'dashboard_reconciliation.csv', index=False)
    print(f'dashboard tables written; reconciliation checks {int(ck["pass"].sum())}/{len(ck)} pass')
    if not ck['pass'].all():
        print(ck[~ck['pass']].head())
        sys.exit(1)


if __name__ == '__main__':
    main()
