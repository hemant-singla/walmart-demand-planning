"""Cross-check the hand-written ETS (src/wdp/models.py) against statsmodels on the 6 validation origins only.

Needs statsmodels (pip install statsmodels). Uses sealed data (no holdout). Runtime: a few minutes.
For each series and origin it fits statsmodels Holt-Winters with an additive weekly season (no trend) on the same
last-728-day window, forecasts 28 days, clips at zero, and compares mean RMSSE with the in-house ETS.
Output: results/checkpoint3/ets_crosscheck.json
"""
from pathlib import Path
import json
import sys
import warnings
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.models import ets_forecast
from wdp.metrics import rmsse_scale


def main():
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    warnings.filterwarnings('ignore')
    w = windows()
    p = load_panel('panel', seal_after=1913)
    rows = []
    for T in w['forecast_validation_origins']:
        hist = p.Y[:, :T]
        y = p.Y[:, T:T + 28]
        scale = rmsse_scale(hist)
        ours, _ = ets_forecast(hist, 28)
        sm = np.zeros_like(ours)
        for i in range(p.n):
            try:
                fit = ExponentialSmoothing(hist[i, -728:], trend=None, seasonal='add', seasonal_periods=7,
                                           initialization_method='estimated').fit()
                sm[i] = np.clip(fit.forecast(28), 0, None)
            except Exception:
                sm[i] = np.nan
        for name, F in [('in_house_ets', ours), ('statsmodels_hw', sm)]:
            r = np.sqrt(np.mean((F - y) ** 2, axis=1) / scale)
            rows.append({'origin': T, 'model': name, 'mean_rmsse': float(np.nanmean(r)),
                         'failed_series': int(np.isnan(F).any(axis=1).sum())})
        corr = np.corrcoef(ours.ravel(), np.nan_to_num(sm).ravel())[0, 1]
        rows.append({'origin': T, 'model': 'forecast_correlation', 'value': float(corr)})
        print(T, [(r['model'], round(r.get('mean_rmsse', r.get('value')), 4)) for r in rows[-3:]], flush=True)
    summ = {m: float(np.mean([r['mean_rmsse'] for r in rows if r['model'] == m])) for m in ['in_house_ets', 'statsmodels_hw']}
    out = {'rows': rows, 'mean_rmsse': summ, 'note': 'Validation origins only; holdout untouched. Report this comparison as-is.'}
    (ROOT / 'results' / 'checkpoint3' / 'ets_crosscheck.json').write_text(json.dumps(out, indent=2))
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    main()
