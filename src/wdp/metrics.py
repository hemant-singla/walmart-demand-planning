"""Forecast metrics with explicit handling of zero / undefined denominators.

RMSSE (per series and origin): sqrt(mean_h (y-f)^2 / scale), scale = mean squared
one-day difference of in-sample history from the first non-zero sale up to the origin
(M5 convention). scale == 0 -> RMSSE undefined (NaN, counted, excluded from means).
WAPE = sum|y-f| / sum y ; bias = sum(f-y) / sum y (positive = over-forecast).
sum y == 0 -> undefined (NaN, counted).
This panel metric is NOT the official full-hierarchy M5 WRMSSE.
"""
import numpy as np
import pandas as pd


def rmsse_scale(hist: np.ndarray) -> np.ndarray:
    out = np.full(hist.shape[0], np.nan)
    for i, row in enumerate(hist):
        nz = np.flatnonzero(row > 0)
        if len(nz) == 0:
            continue
        r = row[nz[0]:]
        if len(r) < 2:
            continue
        out[i] = np.mean(np.diff(r) ** 2)
    out[out == 0] = np.nan
    return out


def mae_scale(hist: np.ndarray) -> np.ndarray:
    """Mean absolute one-day difference since first sale; used to normalise weekly errors."""
    out = np.full(hist.shape[0], np.nan)
    for i, row in enumerate(hist):
        nz = np.flatnonzero(row > 0)
        if len(nz) and len(row) - nz[0] > 1:
            out[i] = np.mean(np.abs(np.diff(row[nz[0]:])))
    out[out == 0] = np.nan
    return out


def safe_ratio(num, den):
    return np.nan if den == 0 else num / den


def summarize(df: pd.DataFrame, by=None) -> pd.DataFrame:
    """df columns: model, origin, idx, h, y, forecast, scale (RMSSE scale per idx/origin)."""
    keys = ['model'] + (by or [])
    d = df.assign(e=df.forecast - df.y, ae=(df.forecast - df.y).abs(), se=(df.forecast - df.y) ** 2)
    per = d.groupby(list(dict.fromkeys(keys + ['origin', 'idx'])), observed=True).agg(mse=('se', 'mean'), scale=('scale', 'first')).reset_index()
    per['rmsse'] = np.sqrt(per.mse / per.scale)
    g = d.groupby(keys, observed=True)
    out = g.agg(n_obs=('y', 'size'), actual_units=('y', 'sum'), abs_error=('ae', 'sum'), signed_error=('e', 'sum')).reset_index()
    out['wape'] = [safe_ratio(a, s) for a, s in zip(out.abs_error, out.actual_units)]
    out['bias'] = [safe_ratio(e, s) for e, s in zip(out.signed_error, out.actual_units)]
    pr = per.groupby(keys, observed=True).agg(mean_rmsse=('rmsse', 'mean'), median_rmsse=('rmsse', 'median'),
                                               n_series_origins=('rmsse', 'size'),
                                               rmsse_undefined=('rmsse', lambda s: int(s.isna().sum()))).reset_index()
    return out.merge(pr, on=keys)
