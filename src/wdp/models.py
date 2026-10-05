"""Forecast models: seasonal naive, ETS (in-house), global direct-horizon LightGBM.

ETS note: statsmodels could not be installed in the execution environment (package
index blocked), so ETS is implemented here with numpy: additive-error state-space
ETS(A,N,A) with weekly seasonality (m=7) and ETS(A,N,N), smoothing parameters chosen
per series by grid search on in-sample one-step SSE, model chosen per series by AIC.
Initial states come from the first 28 fitted days (not optimised). Fit window is the
last 728 days before the origin. Forecasts are clipped at zero. Fallback: if a series'
fit is non-finite it receives the seasonal-naive forecast (counted and reported).
"""
import time
import numpy as np
import pandas as pd
from .features import FEATURES, CATEGORICAL, seasonal_naive

ALPHAS = np.array([0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5])
GAMMAS = np.array([0.01, 0.05, 0.1, 0.2])


def ets_forecast(hist: np.ndarray, H: int = 28, window: int = 728):
    """Vectorised ETS over series. Returns (forecast n x H, info DataFrame)."""
    y = hist[:, -window:].astype(float)
    n, T = y.shape
    m = 7
    # combos: ANA for every (alpha, gamma) plus ANN for every alpha (gamma=0, no season)
    a = np.concatenate([np.repeat(ALPHAS, len(GAMMAS)), ALPHAS])
    g = np.concatenate([np.tile(GAMMAS, len(ALPHAS)), np.zeros(len(ALPHAS))])
    seasonal = np.concatenate([np.ones(len(ALPHAS) * len(GAMMAS), bool), np.zeros(len(ALPHAS), bool)])
    G = len(a)
    init = y[:, :28]
    l0 = init.mean(axis=1)
    s0 = np.stack([init[:, k::7].mean(axis=1) - l0 for k in range(7)], axis=1)  # n x 7, phase k = day index mod 7
    lvl = np.repeat(l0[:, None], G, axis=1)
    S = np.repeat(s0[:, None, :], G, axis=1) * seasonal[None, :, None]
    sse = np.zeros((n, G))
    for tt in range(T):
        k = tt % m
        fc = lvl + S[:, :, k]
        e = y[:, [tt]] - fc
        sse += e ** 2
        lvl = lvl + a[None, :] * e
        S[:, :, k] = S[:, :, k] + g[None, :] * e
    npar = np.where(seasonal, 2 + 1 + 6, 1 + 1)
    with np.errstate(divide='ignore', invalid='ignore'):
        aic = T * np.log(sse / T + 1e-12) + 2 * npar[None, :]
    aic[~np.isfinite(aic)] = np.inf
    best = np.argmin(aic, axis=1)
    rows = np.arange(n)
    lv = lvl[rows, best]
    fcst = np.empty((n, H))
    for h in range(1, H + 1):
        k = (T + h - 1) % m
        fcst[:, h - 1] = lv + S[rows, best, k]
    fcst = np.clip(fcst, 0, None)
    fallback = ~np.isfinite(fcst).all(axis=1) | ~np.isfinite(aic[rows, best])
    if fallback.any():
        fcst[fallback] = seasonal_naive(hist[fallback], H)
    info = pd.DataFrame({'ets_model': np.where(seasonal[best], 'ANA', 'ANN'),
                         'alpha': a[best], 'gamma': g[best], 'fallback_snaive': fallback})
    return fcst, info


LGB_CONFIGS = {
    'tweedie_31': dict(objective='tweedie', tweedie_variance_power=1.1, learning_rate=0.05,
                       num_leaves=31, min_data_in_leaf=100, feature_fraction=0.8,
                       bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, num_boost_round=500),
    'poisson_31': dict(objective='poisson', learning_rate=0.05, num_leaves=31, min_data_in_leaf=100,
                       feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
                       num_boost_round=500),
    'tweedie_63': dict(objective='tweedie', tweedie_variance_power=1.1, learning_rate=0.03,
                       num_leaves=63, min_data_in_leaf=100, feature_fraction=0.8,
                       bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, num_boost_round=800),
}


class LGBForecaster:
    """Global model; one fit per origin on rows (t, h) with t + h <= origin."""

    def __init__(self, store, config='tweedie_31', seed=20261003, lookback=104, step=7, threads=2):
        self.store, self.cfg, self.seed = store, dict(LGB_CONFIGS[config]), seed
        self.lookback, self.step, self.threads = lookback, step, threads

    def training_frame(self, T):
        ts = [T - self.step * j for j in range(1, self.lookback + 1)]
        df = self.store.rows(ts)
        df = df[df.d <= T]                       # target must be observed by origin T
        assert df.d.max() <= T and df.y.notna().all(), 'training target leakage or missing target'
        return df

    def fit_predict(self, T):
        import lightgbm as lgb
        t0 = time.perf_counter()
        tr = self.training_frame(T)
        params = {k: v for k, v in self.cfg.items() if k != 'num_boost_round'}
        params.update(seed=self.seed, deterministic=True, num_threads=self.threads, verbose=-1)
        ds = lgb.Dataset(tr[FEATURES], tr.y, categorical_feature=CATEGORICAL, free_raw_data=True)
        model = lgb.train(params, ds, num_boost_round=self.cfg['num_boost_round'])
        te = self.store.rows([T])
        pred = np.clip(model.predict(te[FEATURES]), 0, None)
        out = te[['idx', 'h', 'd']].copy()
        out['forecast'] = pred
        return out, {'origin': T, 'train_rows': len(tr), 'train_max_target_day': int(tr.d.max()),
                     'seconds': time.perf_counter() - t0}, model


class FeatureStore:
    """Caches origin blocks so features for origin t are computed once."""

    def __init__(self, builder):
        self.b, self.cache = builder, {}

    def rows(self, ts):
        parts = []
        for t in ts:
            if t not in self.cache:
                self.cache[t] = self.b.origin_block(t)
            parts.append(self.cache[t])
        return pd.concat(parts, ignore_index=True)
