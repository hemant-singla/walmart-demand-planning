"""Weekly review-priority signals, rules and evaluation.

At list origin T every signal uses only information known at T:
  recent_error : mean weekly absolute error (units, h=1..7) of forecasts from origins T-7..T-28
                 (each evaluated on its own first 7 days, all <= T)
  bias         : |mean weekly signed error| (forecast - actual, h=1..7) over origins T-7..T-56
  uncertainty  : sum over the next 7 days of the calibrated interval width issued at T
  volume       : units sold in the 28 days up to T
Outcome for the list at T: absolute error of the forecasts issued at T over days T+1..T+7
(unit exposure), and the same divided by 7 x mean absolute daily change (normalised error).
Adjacent weekly lists therefore have non-overlapping outcome windows.
"""
import itertools
import numpy as np
import pandas as pd

SIGNALS = ['recent_error', 'bias', 'uncertainty']


def build_signals(bt, iv, Y, origins, scale_col='mae_scale'):
    """bt: backtest of the forecast model (origin, idx, h, d, y, forecast, mae_scale).
    iv: intervals (origin, idx, h, lower, upper). Y: n x D actual array (sealed where unknown)."""
    w1 = bt[bt.h <= 7].assign(ae=lambda x: (x.forecast - x.y).abs(), se=lambda x: x.forecast - x.y)
    wk = w1.groupby(['origin', 'idx']).agg(ae=('ae', 'sum'), signed=('se', 'sum'), last_d=('d', 'max'),
                                           n=('y', 'count'), scale=(scale_col, 'first')).reset_index()
    wk.loc[wk.n < 7, ['ae', 'signed']] = np.nan        # outcome not fully observed
    width = iv[iv.h <= 7].assign(wd=lambda x: x.upper - x.lower).groupby(['origin', 'idx']).wd.sum(min_count=7)
    n = Y.shape[0]
    rows = []
    for T in origins:
        past = wk[(wk.origin <= T - 7) & (wk.origin >= T - 56)]
        assert (past.last_d <= T).all(), 'signal uses unobserved outcome'
        rec = past[past.origin >= T - 28].groupby('idx').ae.agg(['mean', 'count'])
        bia = past.groupby('idx').signed.agg(['mean', 'count'])
        cur = wk[wk.origin == T].set_index('idx')
        f = pd.DataFrame({'origin': T, 'idx': np.arange(n)})
        f['recent_error'] = rec['mean'].where(rec['count'] >= 2).reindex(f.idx).to_numpy()
        f['bias_signed'] = bia['mean'].where(bia['count'] >= 4).reindex(f.idx).to_numpy()
        f['bias'] = f.bias_signed.abs()
        f['uncertainty'] = width.xs(T, level='origin').reindex(f.idx).to_numpy() if T in width.index.get_level_values(0) else np.nan
        f['volume'] = Y[:, T - 28:T].sum(axis=1)
        f['scale'] = cur['scale'].reindex(f.idx).to_numpy()
        f['recent_error_norm'] = f.recent_error / (7 * f.scale)
        f['outcome_ae'] = cur['ae'].reindex(f.idx).to_numpy()
        f['outcome_signed'] = cur['signed'].reindex(f.idx).to_numpy()
        f['outcome_ne'] = f.outcome_ae / (7 * f.scale)
        rows.append(f)
    return pd.concat(rows, ignore_index=True)


def normalise(s: pd.DataFrame, method: str) -> pd.DataFrame:
    """Cross-sectional normalisation within each origin. Missing signal -> 0 contribution."""
    g = s.groupby('origin')
    out = pd.DataFrame(index=s.index)
    for c in SIGNALS:
        if method == 'rank':
            out[c] = g[c].rank(pct=True)
        elif method == 'median':
            out[c] = s[c] / g[c].transform('median').replace(0, np.nan)
        else:
            raise ValueError(method)
    return out.fillna(0.0)


def weight_grid(step=0.1):
    k = int(round(1 / step))
    return [tuple(np.round(np.array(c) / k, 3)) for c in itertools.product(range(k + 1), repeat=3) if sum(c) == k]


def score(s, rule, weights=None, norm='rank'):
    if rule == 'proposed':
        z = normalise(s, norm)
        return z[SIGNALS].to_numpy() @ np.asarray(weights)
    return s[rule].fillna(-np.inf).to_numpy()


def top_k(scores, idx, K):
    order = np.lexsort((idx, -scores))       # highest score, ties -> lower idx (deterministic)
    return idx[order[:K]]


def evaluate(s, scores, Ks, threshold, label):
    s = s.assign(_score=scores)
    out = []
    for T, g in s.groupby('origin'):
        g = g[g.outcome_ae.notna()]
        if g.empty:
            continue
        ev = g.outcome_ne > threshold
        tot_ae, n_ev = g.outcome_ae.sum(), ev.sum()
        for K in Ks:
            sel = top_k(g._score.to_numpy(), g.idx.to_numpy(), K)
            m = g.idx.isin(sel)
            out.append({'rule': label, 'origin': T, 'K': K,
                        'captured_ae_share': g.outcome_ae[m].sum() / tot_ae if tot_ae > 0 else np.nan,
                        'captured_ae_units': g.outcome_ae[m].sum(), 'total_ae_units': tot_ae,
                        'captured_ne_share': g.outcome_ne[m].sum() / g.outcome_ne.sum(),
                        'precision': ev[m].mean(), 'recall': ev[m].sum() / n_ev if n_ev else np.nan,
                        'events': int(n_ev), 'selected': ','.join(map(str, sel))})
    return pd.DataFrame(out)


def evaluate_random(s, Ks, threshold, repeats, seed):
    rng = np.random.default_rng(seed)
    res = []
    for r in range(repeats):
        sc = rng.random(len(s))
        e = evaluate(s, sc, Ks, threshold, 'random')
        e['repeat'] = r
        res.append(e.drop(columns='selected'))
    return pd.concat(res, ignore_index=True)
