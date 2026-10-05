"""Origin-based direct multi-horizon features.

For origin t and horizon h, every sales/price feature is computed from days <= t only.
Target-day calendar fields (weekday, month, event type, SNAP) are known in advance.
Price uses the last observed weekly price from the completed week containing day t-7,
carried forward from earlier weeks when missing; no future price is used
(operational "last available price" scenario).
"""
import numpy as np
import pandas as pd

H = 28
FEATURES = ['h', 't_wday', 't_month', 't_event', 't_snap',
            'last1', 'mean7', 'mean14', 'mean28', 'mean56', 'mean112', 'mean364',
            'std28', 'zero28', 'zero112', 'days_since_sale', 'trend7_28',
            'sn_val', 'dow_mean4', 'dow_mean12', 'dow_ratio12',
            'price_last', 'price_rel52', 'price_chg4', 'price_missing_share28',
            'store', 'cat', 'dept']
CATEGORICAL = ['t_wday', 't_event', 'store', 'cat', 'dept']


def _ffill_past(P):
    """Forward-fill along time using only earlier values."""
    out = P.copy()
    n, D = out.shape
    idx = np.where(~np.isnan(out), np.arange(D), -1)
    np.maximum.accumulate(idx, axis=1, out=idx)
    filled = out[np.arange(n)[:, None], np.maximum(idx, 0)]
    filled[idx < 0] = np.nan
    return filled


class FeatureBuilder:
    def __init__(self, panel):
        self.p = panel
        self.Pf = _ffill_past(panel.P)
        m = panel.meta
        self.static = np.column_stack([
            m.store_id.astype('category').cat.codes.to_numpy(),
            m.cat_id.astype('category').cat.codes.to_numpy(),
            m.dept_id.astype('category').cat.codes.to_numpy()])

    def origin_block(self, t: int, horizons=range(1, H + 1)) -> pd.DataFrame:
        """Rows for every series x horizon at origin t (history = days 1..t)."""
        p = self.p
        hist = p.Y[:, :t]
        if np.isnan(hist).any():
            raise ValueError(f'origin {t}: history contains sealed/missing sales')
        n = p.n
        def mean_last(k):
            return hist[:, -k:].mean(axis=1)
        nz = hist > 0
        dsl = np.where(nz.any(axis=1), np.argmax(nz[:, ::-1], axis=1), 365)
        dsl = np.minimum(dsl, 365)          # 0 = sold on day t
        base = {
            'last1': hist[:, -1], 'mean7': mean_last(7), 'mean14': mean_last(14),
            'mean28': mean_last(28), 'mean56': mean_last(56), 'mean112': mean_last(112),
            'mean364': mean_last(364), 'std28': hist[:, -28:].std(axis=1),
            'zero28': (hist[:, -28:] == 0).mean(axis=1), 'zero112': (hist[:, -112:] == 0).mean(axis=1),
            'days_since_sale': dsl,
        }
        base['trend7_28'] = (base['mean7'] + 0.1) / (base['mean28'] + 0.1)
        # price from the completed week containing day t-7 (column t-8), carried forward
        pc = t - 8
        price_last = self.Pf[:, pc]
        past_weeks = self.Pf[:, max(0, pc - 364):pc + 1:7]
        with np.errstate(all='ignore'):
            ref = np.nanmean(past_weeks, axis=1)
            base['price_last'] = price_last
            base['price_rel52'] = price_last / ref
            base['price_chg4'] = price_last / self.Pf[:, pc - 28] - 1
        base['price_missing_share28'] = np.isnan(p.P[:, pc - 27:pc + 1]).mean(axis=1)
        mean84 = mean_last(84)
        rows = []
        for h in horizons:
            k = (h - 1) % 7
            col = t - 7 + k              # 0-based column of same weekday in last observed week
            dow_cols4 = [col - 7 * j for j in range(4)]
            dow_cols12 = [col - 7 * j for j in range(12)]
            td = t + h - 1               # 0-based column of target day
            blk = dict(base)
            blk.update({
                'h': np.full(n, h), 't_wday': np.full(n, p.wday[td]), 't_month': np.full(n, p.month[td]),
                't_event': np.full(n, p.event[td]), 't_snap': p.snap[:, td],
                'sn_val': hist[:, col], 'dow_mean4': hist[:, dow_cols4].mean(axis=1),
                'dow_mean12': hist[:, dow_cols12].mean(axis=1),
                'dow_ratio12': (hist[:, dow_cols12].mean(axis=1) + 0.1) / (mean84 + 0.1),
                'store': self.static[:, 0], 'cat': self.static[:, 1], 'dept': self.static[:, 2],
                'idx': np.arange(n), 't': np.full(n, t), 'd': np.full(n, t + h),
            })
            blk['y'] = p.Y[:, td] if td < p.D else np.full(n, np.nan)
            rows.append(pd.DataFrame(blk))
        return pd.concat(rows, ignore_index=True)


def seasonal_naive(hist: np.ndarray, H: int = 28) -> np.ndarray:
    """Repeat last observed week: f(t+h) = y(t-7+((h-1) mod 7)+1)."""
    last_week = hist[:, -7:]
    return np.column_stack([last_week[:, (h - 1) % 7] for h in range(1, H + 1)])
