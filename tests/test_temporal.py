"""Temporal-cutoff, baseline-equivalence and metric edge-case checks.

Run: python tests/test_temporal.py  (also pytest-compatible). Uses the pilot panel.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from wdp.data import load_panel
from wdp.features import FeatureBuilder, seasonal_naive, FEATURES
from wdp.models import ets_forecast, LGBForecaster, FeatureStore
from wdp.metrics import rmsse_scale, summarize

P = load_panel('pilot', seal_after=1913)


def test_seal():
    assert np.isnan(P.Y[:, 1913:]).all() and not np.isnan(P.Y[:, :1913]).any()
    fb = FeatureBuilder(P)
    try:
        fb.origin_block(1920)
        raise AssertionError('origin after seal should fail')
    except ValueError:
        pass


def test_features_ignore_future():
    t = 1801
    base = FeatureBuilder(P).origin_block(t)
    rng = np.random.default_rng(0)
    Q = load_panel('pilot', seal_after=1913)
    Q.Y[:, t:] = rng.integers(0, 500, Q.Y[:, t:].shape)          # future sales scrambled
    wk_t = P.week[t - 1]
    future_price_cols = P.week[:P.D] >= wk_t                              # every day of origin week and later
    Q.P[:, future_price_cols] = rng.uniform(1, 99, (Q.n, future_price_cols.sum()))
    pert = FeatureBuilder(Q).origin_block(t)
    pd.testing.assert_frame_equal(base[FEATURES], pert[FEATURES])


def test_training_targets_before_origin():
    store = FeatureStore(FeatureBuilder(P))
    f = LGBForecaster(store, lookback=10)
    tr = f.training_frame(1801)
    assert tr.d.max() <= 1801 and (tr.t + tr.h == tr.d).all()
    assert set(tr.t.unique()) <= {1801 - 7 * j for j in range(1, 11)}


def test_seasonal_naive_equivalence():
    t = 1801
    hist = P.Y[:, :t]
    sn = seasonal_naive(hist)
    blk = FeatureBuilder(P).origin_block(t)
    for h in (1, 3, 7, 8, 14, 28):
        np.testing.assert_array_equal(blk.loc[blk.h == h, 'sn_val'].to_numpy(), sn[:, h - 1])
        np.testing.assert_array_equal(sn[:, h - 1], hist[:, t - 7 + (h - 1) % 7])
    # day-of-week alignment: forecast for day t+h uses day t+h-7k with the same weekday
    for h in range(1, 29):
        src_day = t - 7 + (h - 1) % 7 + 1
        assert P.wday[src_day - 1] == P.wday[t + h - 1]


def test_origin_near_end_of_data():
    # regression: holdout weekly origins 1920/1927/1934 forecast past d_1941 (crashed before fix)
    U = load_panel('pilot', seal_after=None)
    blk = FeatureBuilder(U).origin_block(1934)
    assert blk.d.max() == 1962 and blk.loc[blk.d > 1941, 'y'].isna().all()
    assert blk.loc[blk.d <= 1941, 'y'].notna().all() and len(U.wday) == 1969


def test_ets_toy():
    pat = np.array([5, 1, 1, 2, 3, 8, 9], float)
    y = np.tile(pat, 120)[None, :]
    f, info = ets_forecast(y, 14)
    nxt = np.tile(pat, 3)[y.shape[1] % 7: y.shape[1] % 7 + 14]
    assert np.abs(f[0] - nxt).max() < 0.05, (f[0], nxt)
    const = np.full((1, 800), 4.0)
    f2, _ = ets_forecast(const, 7)
    assert np.allclose(f2, 4.0)


def test_metric_edges():
    assert np.isnan(rmsse_scale(np.array([[0, 0, 0, 0.]])))[0]
    assert np.isnan(rmsse_scale(np.array([[0, 3, 3, 3.]])))[0]           # constant after first sale
    df = pd.DataFrame({'model': 'm', 'origin': 1, 'idx': [0, 0], 'h': [1, 2], 'y': [0., 0.],
                       'forecast': [1., 0.], 'scale': [np.nan, np.nan]})
    s = summarize(df)
    assert np.isnan(s.wape[0]) and np.isnan(s.bias[0]) and s.rmsse_undefined[0] == 1


def test_weekly_windows_disjoint():
    import json
    w = json.loads((Path(__file__).resolve().parents[1] / 'config' / 'windows.json').read_text())
    origins = list(range(w['weekly_backtest_origins']['first'], w['weekly_backtest_origins']['last'] + 1, 7))
    spans = [set(range(o + 1, o + 8)) for o in origins]
    assert all(not (a & b) for a, b in zip(spans, spans[1:]))
    assert max(max(s) for s in spans) <= 1913
    v = w['forecast_validation_origins'] + [w['holdout']['forecast_origin']]
    assert all(b - a == 28 for a, b in zip(v, v[1:]))
    assert max(w['forecast_tuning_origins']) + 28 <= min(w['forecast_validation_origins'])


if __name__ == '__main__':
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            try:
                fn(); print('PASS', name)
            except Exception as e:
                fails += 1; print('FAIL', name, repr(e)[:300])
    sys.exit(1 if fails else 0)
