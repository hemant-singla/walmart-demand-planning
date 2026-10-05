"""Checkpoint 3c: 28-day forecast comparison on 6 validation origins + interval calibration/coverage.
Pre-registered rules: primary forecast model = lowest mean RMSSE over validation origins;
interval width multipliers per horizon bucket chosen on calibration origins (1584-1661) only."""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.metrics import summarize
from wdp.intervals import residual_quantiles, apply_intervals, coverage, bucket

OUT = ROOT / 'results' / 'checkpoint3'
SEGS = ['volume_group', 'pattern_group', 'store_id', 'cat_id']


def load_backtest():
    odir = ROOT / 'results' / 'backtest' / 'origins'
    bt = pd.concat([pd.read_csv(f) for f in sorted(odir.glob('[0-9]*.csv.gz'))], ignore_index=True)
    rt = pd.concat([pd.read_csv(f) for f in sorted(odir.glob('*_runtime.csv'))], ignore_index=True)
    assert not bt.duplicated(['model', 'origin', 'idx', 'h']).any()
    assert bt.loc[bt.d > 1913, 'y'].isna().all(), 'holdout actuals present in backtest'
    return bt, rt


def intervals_for(bt_m, origins, mult=None):
    parts = []
    for T in origins:
        q = residual_quantiles(bt_m, T)
        fc = bt_m[bt_m.origin == T]
        parts.append(apply_intervals(fc, q, mult))
    return pd.concat(parts, ignore_index=True)


def calibrate(iv):
    grid = np.round(np.arange(0.5, 2.51, 0.05), 2)
    mult = {}
    for b, g in iv[iv.y.notna() & iv.q_lo.notna()].groupby('b'):
        covs = [(((g.y >= np.clip(g.forecast + c * g.q_lo, 0, None)) & (g.y <= np.clip(g.forecast + c * g.q_hi, 0, None))).mean(), c) for c in grid]
        mult[int(b)] = float(min(covs, key=lambda x: (abs(x[0] - 0.90), x[1]))[1])
    return mult


def main():
    w = windows()
    p = load_panel('panel', seal_after=1913)
    meta = p.meta[SEGS].reset_index().rename(columns={'index': 'idx'})
    bt, rt = load_backtest()
    bt = bt.merge(meta, on='idx')
    val = bt[bt.origin.isin(w['forecast_validation_origins'])]
    assert val.y.notna().all() and val.d.max() <= 1913
    res = {'overall': summarize(val)}
    for s in SEGS:
        res[s] = summarize(val, [s]).rename(columns={s: 'segment'}).assign(segment_type=s)
    val = val.assign(horizon_week=bucket(val.h))
    res['horizon_week'] = summarize(val, ['horizon_week']).rename(columns={'horizon_week': 'segment'}).assign(segment_type='horizon_week')
    res['origin'] = summarize(val, ['origin']).rename(columns={'origin': 'segment'}).assign(segment_type='origin')
    overall = res['overall'].sort_values('mean_rmsse')
    overall.to_csv(OUT / 'validation_metrics.csv', index=False)
    pd.concat([res[k] for k in res if k != 'overall']).to_csv(OUT / 'validation_metrics_segments.csv', index=False)
    rts = rt[rt.origin.isin(w['forecast_validation_origins'])].groupby('model').seconds.agg(['mean', 'sum']).reset_index()
    rts.to_csv(OUT / 'validation_runtime.csv', index=False)
    # per-origin win counts and paired RMSSE differences (series-origin level)
    d = val.assign(se=(val.forecast - val.y) ** 2).groupby(['model', 'origin', 'idx']).agg(mse=('se', 'mean'), scale=('scale', 'first')).reset_index()
    d['rmsse'] = np.sqrt(d.mse / d.scale)
    wide = d.pivot_table(index=['origin', 'idx'], columns='model', values='rmsse')
    paired = {f'{a}_minus_{b}': {'mean': float((wide[a] - wide[b]).mean()), 'share_series_origins_a_better': float((wide[a] < wide[b]).mean())}
              for a, b in [('lgbm', 'ets'), ('lgbm', 'snaive'), ('ets', 'snaive')]}
    per_origin = res['origin'].pivot(index='segment', columns='model', values='mean_rmsse')
    chosen = overall.iloc[0].model
    choice = {'rule': 'lowest mean RMSSE over 6 validation origins (pre-registered)', 'chosen_model': chosen,
              'validation_origins': w['forecast_validation_origins'],
              'mean_rmsse': overall.set_index('model').mean_rmsse.round(4).to_dict(),
              'wape': overall.set_index('model').wape.round(4).to_dict(),
              'bias': overall.set_index('model').bias.round(4).to_dict(),
              'origins_won_by_lgbm_vs_ets': int((per_origin['lgbm'] < per_origin['ets']).sum()),
              'paired': paired}
    (OUT / 'forecast_choice.json').write_text(json.dumps(choice, indent=2))
    # intervals for chosen model
    bm = bt[bt.model == chosen]
    cal_o = list(range(w['priority_calibration_origins']['first'], w['priority_calibration_origins']['last'] + 1, 7))
    later_o = list(range(w['priority_validation_origins']['first'], w['priority_validation_origins']['last'] + 1, 7))
    iv_cal_raw = intervals_for(bm, cal_o)
    cal_end = w['priority_validation_origins']['first']        # calibration outcomes must precede validation window
    iv_cal_raw = iv_cal_raw[iv_cal_raw.d <= cal_end]
    mult = calibrate(iv_cal_raw)
    raw_cov = iv_cal_raw[iv_cal_raw.y.notna()].groupby('b').apply(coverage, include_groups=False)
    iv_all = intervals_for(bm, cal_o + later_o, mult)
    iv_all.drop(columns=SEGS).to_csv(ROOT / 'results' / 'backtest' / f'intervals_{chosen}.csv.gz', index=False)
    iv_val = iv_all[iv_all.origin.isin(w['forecast_validation_origins']) & iv_all.y.notna()]
    cov_rows = [coverage(iv_val).rename('all')]
    for s in SEGS + ['b']:
        for k, g in iv_val.groupby(s):
            cov_rows.append(coverage(g).rename(f'{s}={k}'))
    cov = pd.DataFrame(cov_rows)
    wk = iv_all[iv_all.origin.isin(later_o) & (iv_all.h <= 7) & iv_all.y.notna()]
    cov.loc['weekly_validation_h1-7'] = coverage(wk)
    cov.to_csv(OUT / 'interval_coverage_validation.csv')
    raw_cov.to_csv(OUT / 'interval_coverage_calibration_raw.csv')
    summary = {**choice, 'interval_nominal': 0.90, 'width_multipliers_by_horizon_week': mult,
               'calibration_raw_coverage_by_week': raw_cov.coverage.round(3).to_dict(),
               'validation_coverage_all': round(float(cov.loc['all', 'coverage']), 4),
               'validation_coverage_by_segment': cov.coverage.round(3).to_dict()}
    (OUT / 'checkpoint3.json').write_text(json.dumps(summary, indent=2, default=float))
    print(overall[['model', 'mean_rmsse', 'median_rmsse', 'wape', 'bias', 'rmsse_undefined']].round(4).to_string(index=False))
    print(per_origin.round(3).to_string())
    print(json.dumps({k: summary[k] for k in ['chosen_model', 'width_multipliers_by_horizon_week', 'calibration_raw_coverage_by_week', 'validation_coverage_all']}, indent=1))
    print(cov.round(3).to_string())


if __name__ == '__main__':
    main()
