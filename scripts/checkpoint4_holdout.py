"""Checkpoint 4b: final holdout, run once after config/frozen_choices.json exists.

- 28-day forecasts from origin 1913 (days 1914-1941) for snaive, ETS and the frozen LightGBM config.
- Weekly lists at origins 1913, 1920, 1927, 1934 using frozen rules/threshold/multipliers; each list is
  evaluated on its own next 7 days. Holdout actuals enter only as already-observed history for later
  weekly origins (rolling operation), never for choices.
"""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.backtest import Runner
from wdp.metrics import summarize
from wdp.intervals import residual_quantiles, apply_intervals, coverage, bucket
from wdp.priority import build_signals, score, evaluate, evaluate_random

OUT = ROOT / 'results' / 'holdout'
SEGS = ['volume_group', 'pattern_group', 'store_id', 'cat_id']


def main():
    frozen_path = ROOT / 'config' / 'frozen_choices.json'
    if not frozen_path.exists():
        sys.exit('Refusing to touch holdout: config/frozen_choices.json missing (run checkpoint4_priority.py first).')
    fz = json.loads(frozen_path.read_text())
    w = windows()
    OUT.mkdir(parents=True, exist_ok=True)
    p = load_panel('panel', seal_after=None)                 # unsealed: holdout actuals available
    meta = p.meta[SEGS].reset_index().rename(columns={'index': 'idx'})
    model = fz['forecast_model']
    hold_o = w['holdout']['weekly_priority_origins']
    r = Runner(p, fz['lgbm_config'])
    fc = r.run(hold_o)
    errs = [l for l in r.log if l.get('error')]
    if errs:
        sys.exit(f'Model failures in holdout run (nothing evaluated): {errs}')
    assert set(fc[fc.model == model].origin) == set(hold_o), 'forecast model missing for a holdout origin'
    fc.to_csv(OUT / 'holdout_forecasts.csv.gz', index=False)
    pd.DataFrame(r.log).to_csv(OUT / 'holdout_runtime.csv', index=False)
    # --- 28-day forecast comparison at origin 1913
    f28 = fc[fc.origin == w['holdout']['forecast_origin']].merge(meta, on='idx')
    assert f28.d.min() == 1914 and f28.d.max() == 1941 and f28.y.notna().all()
    tabs = [summarize(f28).assign(segment_type='all', segment='all')]
    for s in SEGS:
        tabs.append(summarize(f28, [s]).rename(columns={s: 'segment'}).assign(segment_type=s))
    f28 = f28.assign(horizon_week=bucket(f28.h))
    tabs.append(summarize(f28, ['horizon_week']).rename(columns={'horizon_week': 'segment'}).assign(segment_type='horizon_week'))
    m28 = pd.concat(tabs, ignore_index=True)
    m28.to_csv(OUT / 'holdout_forecast_metrics.csv', index=False)
    # --- backtest history with actuals now filled in (for error signals & residual pools)
    odir = ROOT / 'results' / 'backtest' / 'origins'
    bt = pd.concat([pd.read_csv(f) for f in sorted(odir.glob('[0-9]*.csv.gz'))])
    bt['y'] = p.Y[bt.idx.to_numpy(), bt.d.to_numpy() - 1]          # fill sealed actuals (all <= 1941)
    full = pd.concat([bt, fc], ignore_index=True)
    fm = full[full.model == model]
    mult = {int(k): v for k, v in fz['interval_multipliers'].items()}
    ivs = []
    for T in hold_o:
        q = residual_quantiles(fm, T)
        ivs.append(apply_intervals(fm[fm.origin == T], q, mult))
    iv_h = pd.concat(ivs, ignore_index=True)
    iv_prev = pd.read_csv(ROOT / 'results' / 'backtest' / f'intervals_{model}.csv.gz')
    iv_all = pd.concat([iv_prev, iv_h], ignore_index=True)
    iv_h.merge(meta, on='idx').to_csv(OUT / 'holdout_intervals.csv.gz', index=False)
    c28 = iv_h[iv_h.origin == 1913].merge(meta, on='idx')
    cov = [coverage(c28).rename('all')]
    for s in SEGS + ['b']:
        for k, g in c28.groupby(s):
            cov.append(coverage(g).rename(f'{s}={k}'))
    cov = pd.DataFrame(cov)
    cov.loc['weekly_holdout_h1-7'] = coverage(iv_h[(iv_h.h <= 7) & iv_h.y.notna()])
    cov.to_csv(OUT / 'holdout_interval_coverage.csv')
    # --- weekly priority lists
    s = build_signals(fm, iv_all, p.Y, hold_o)
    assert s.outcome_ae.notna().all()
    s.to_csv(OUT / 'holdout_signals.csv.gz', index=False)
    thr, Ks = fz['event_threshold_normalised_error'], w['capacities']
    pr = fz['proposed_rule']
    wts = tuple(pr['weights'][k] for k in ['recent_error', 'bias', 'uncertainty'])
    ev = pd.concat([evaluate(s, score(s, r_), Ks, thr, r_) for r_ in ['volume', 'recent_error', 'bias', 'uncertainty', 'recent_error_norm']] +
                   [evaluate(s, score(s, 'proposed', wts, pr['normalisation']), Ks, thr, pr['label'])], ignore_index=True)
    rnd = evaluate_random(s, Ks, thr, w['random_priority_repeats'], w['seed'] + 1)
    ev.to_csv(OUT / 'holdout_rule_weekly.csv', index=False)
    summ = ev.groupby(['rule', 'K']).agg(captured_ae_mean=('captured_ae_share', 'mean'), captured_ae_min=('captured_ae_share', 'min'),
                                         captured_ae_max=('captured_ae_share', 'max'), captured_ne_mean=('captured_ne_share', 'mean'),
                                         precision=('precision', 'mean'), recall=('recall', 'mean'), events=('events', 'mean')).reset_index()
    rs = rnd.groupby('K').agg(captured_ae_mean=('captured_ae_share', 'mean'), captured_ae_min=('captured_ae_share', lambda x: x.quantile(.05)),
                              captured_ae_max=('captured_ae_share', lambda x: x.quantile(.95)), captured_ne_mean=('captured_ne_share', 'mean'),
                              precision=('precision', 'mean'), recall=('recall', 'mean'), events=('events', 'mean')).reset_index().assign(rule='random (5-95% for min/max)')
    summ = pd.concat([summ, rs], ignore_index=True)
    summ.to_csv(OUT / 'holdout_rule_summary.csv', index=False)
    res = {'holdout_forecast_origin': 1913, 'weekly_origins': hold_o, 'frozen_sha256': fz['sha256_of_choices'],
           'forecast_metrics_all': m28[m28.segment_type == 'all'][['model', 'mean_rmsse', 'wape', 'bias']].round(4).to_dict('records'),
           'interval_coverage_28d': round(float(cov.loc['all', 'coverage']), 4),
           'interval_coverage_weekly_h1_7': round(float(cov.loc['weekly_holdout_h1-7', 'coverage']), 4),
           'priority_k5': summ[summ.K == 5][['rule', 'captured_ae_mean', 'captured_ne_mean', 'precision', 'recall']].round(4).to_dict('records'),
           'recommended_rule': fz['recommended_rule']}
    (OUT / 'holdout_summary.json').write_text(json.dumps(res, indent=2, default=float))
    print(m28[m28.segment_type == 'all'][['model', 'mean_rmsse', 'wape', 'bias']].round(4).to_string(index=False))
    print(cov.round(3).head(3).to_string())
    print(summ.round(3).to_string(index=False))


if __name__ == '__main__':
    main()
