"""Rolling-origin forecast generation shared by pilot, validation, weekly backtest and holdout."""
import time
import numpy as np
import pandas as pd
from .features import FeatureBuilder, seasonal_naive
from .models import ets_forecast, LGBForecaster, FeatureStore
from .metrics import rmsse_scale, mae_scale


class Runner:
    def __init__(self, panel, lgb_config='tweedie_31', seed=20261003, lookback=104):
        self.p = panel
        self.store = FeatureStore(FeatureBuilder(panel))
        self.lgb_config, self.seed, self.lookback = lgb_config, seed, lookback
        self.log = []

    def _frame(self, model, T, F):
        p = self.p
        n, H = F.shape
        hist = p.Y[:, :T]
        d = np.arange(T + 1, T + H + 1)
        y = np.array([p.Y[:, dd - 1] if dd <= p.D else np.full(n, np.nan) for dd in d]).T
        return pd.DataFrame({'model': model, 'origin': T, 'idx': np.repeat(np.arange(n), H),
                             'h': np.tile(np.arange(1, H + 1), n), 'd': np.tile(d, n),
                             'forecast': F.ravel(), 'y': y.ravel(),
                             'scale': np.repeat(rmsse_scale(hist), H),
                             'mae_scale': np.repeat(mae_scale(hist), H)})

    def run(self, origins, models=('snaive', 'ets', 'lgbm'), H=28):
        out = []
        for T in origins:
            hist = self.p.Y[:, :T]
            assert not np.isnan(hist).any(), f'origin {T} reads sealed data'
            if 'snaive' in models:
                t0 = time.perf_counter()
                F = seasonal_naive(hist, H)
                self.log.append({'model': 'snaive', 'origin': T, 'seconds': time.perf_counter() - t0, 'failures': 0})
                out.append(self._frame('snaive', T, F))
            if 'ets' in models:
                t0 = time.perf_counter()
                F, info = ets_forecast(hist, H)
                self.log.append({'model': 'ets', 'origin': T, 'seconds': time.perf_counter() - t0,
                                 'failures': int(info.fallback_snaive.sum()),
                                 'share_ANA': float((info.ets_model == 'ANA').mean())})
                out.append(self._frame('ets', T, F))
            if 'lgbm' in models:
                f = LGBForecaster(self.store, self.lgb_config, self.seed, self.lookback)
                try:
                    pred, info, _ = f.fit_predict(T)
                    F = pred.sort_values(['idx', 'h']).forecast.to_numpy().reshape(self.p.n, H)
                    self.log.append({'model': 'lgbm', **info, 'failures': 0, 'config': self.lgb_config})
                    out.append(self._frame('lgbm', T, F))
                except Exception as e:  # recorded, not hidden
                    self.log.append({'model': 'lgbm', 'origin': T, 'failures': self.p.n, 'error': repr(e)[:300]})
        return pd.concat(out, ignore_index=True)
