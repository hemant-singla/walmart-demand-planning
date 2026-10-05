"""Empirical prediction intervals from past out-of-sample errors (no fitted residuals).

For origin T, series i and horizon bucket b (h 1-7, 8-14, 15-21, 22-28), residuals
r = y - f come from earlier weekly origins o of the same model with outcome day d <= T and
o >= T - 7*lookback_weeks. Interval = [f + c_b * q_lo, f + c_b * q_hi] clipped at 0, with
per-bucket width multipliers c_b fixed on the calibration window only.
Fewer than MIN_RESID residuals -> interval undefined (NaN), counted.
"""
import numpy as np
import pandas as pd

MIN_RESID = 35


def bucket(h):
    return (np.asarray(h) - 1) // 7 + 1


def residual_quantiles(bt: pd.DataFrame, T: int, lookback_weeks=26, lo=0.05, hi=0.95):
    """bt: backtest rows for one model with columns origin, idx, h, d, y, forecast."""
    r = bt[(bt.d <= T) & (bt.origin >= T - 7 * lookback_weeks) & bt.y.notna()]
    assert (r.d <= T).all()
    r = r.assign(b=bucket(r.h), resid=r.y - r.forecast)
    g = r.groupby(['idx', 'b']).resid
    q = pd.DataFrame({'q_lo': g.quantile(lo), 'q_hi': g.quantile(hi), 'n_resid': g.size()}).reset_index()
    q.loc[q.n_resid < MIN_RESID, ['q_lo', 'q_hi']] = np.nan
    return q


def apply_intervals(fc: pd.DataFrame, q: pd.DataFrame, mult: dict | None = None):
    """fc: forecasts at one origin (idx, h, forecast). Adds lower/upper."""
    out = fc.assign(b=bucket(fc.h)).merge(q, on=['idx', 'b'], how='left')
    c = out.b.map(mult or {}).fillna(1.0)
    out['lower'] = np.clip(out.forecast + c * out.q_lo, 0, None)
    out['upper'] = np.clip(out.forecast + c * out.q_hi, 0, None)
    return out


def coverage(df):
    ok = df.lower.notna()
    d = df[ok]
    return pd.Series({'coverage': ((d.y >= d.lower) & (d.y <= d.upper)).mean(),
                      'mean_width': (d.upper - d.lower).mean(), 'n': len(d), 'undefined': int((~ok).sum())})
