"""Checkpoint 4a: equal-budget priority experiment on pre-holdout weeks, then freeze all choices.

Pre-registered decisions (written before running):
- event threshold = 90th percentile of normalised 7-day error over calibration origins 1584-1661;
- proposed score = weighted sum of normalised recent_error, bias, uncertainty; normalisation in
  {rank, median} and weights on a 0.1 simplex grid chosen on validation origins 1668-1906 by mean
  captured absolute-error share at K=5 (ties: precision@5, then fewer non-zero weights);
- recommend the proposed rule only if it beats the best simple baseline (volume or recent_error) at K=5
  on the full validation window AND when weights are re-chosen on the first half and scored on the
  second half; otherwise recommend the simpler baseline.
"""
from pathlib import Path
import datetime as dt
import hashlib
import json
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.priority import build_signals, weight_grid, score, evaluate, evaluate_random, SIGNALS

OUT = ROOT / 'results' / 'checkpoint4'


def rng_origins(d):
    return list(range(d['first'], d['last'] + 1, 7))


def run_rules(s, Ks, thr, weights_by_norm=None):
    """Evaluate fixed baselines (+ proposed grid if requested)."""
    res = [evaluate(s, score(s, r), Ks, thr, r) for r in ['volume', 'recent_error', 'bias', 'uncertainty', 'recent_error_norm']]
    for norm, grid in (weights_by_norm or {}).items():
        for wts in grid:
            res.append(evaluate(s, score(s, 'proposed', wts, norm), Ks, thr, f'proposed_{norm}_{wts[0]}_{wts[1]}_{wts[2]}'))
    return pd.concat(res, ignore_index=True)


def pick(ev, K=5):
    m = ev[(ev.K == K) & ev.rule.str.startswith('proposed_')].groupby('rule').agg(cap=('captured_ae_share', 'mean'), prec=('precision', 'mean')).reset_index()
    m['nonzero'] = m.rule.apply(lambda r: sum(float(x) > 0 for x in r.split('_')[2:]))
    return m.sort_values(['cap', 'prec', 'nonzero'], ascending=[False, False, True]).iloc[0]


def main():
    w = windows()
    OUT.mkdir(parents=True, exist_ok=True)
    choice = json.loads((ROOT / 'results' / 'checkpoint3' / 'forecast_choice.json').read_text())
    cp3 = json.loads((ROOT / 'results' / 'checkpoint3' / 'checkpoint3.json').read_text())
    model = choice['chosen_model']
    p = load_panel('panel', seal_after=1913)
    odir = ROOT / 'results' / 'backtest' / 'origins'
    bt = pd.concat([pd.read_csv(f) for f in sorted(odir.glob('[0-9]*.csv.gz'))])
    bt = bt[bt.model == model]
    iv = pd.read_csv(ROOT / 'results' / 'backtest' / f'intervals_{model}.csv.gz')
    cal_o, val_o = rng_origins(w['priority_calibration_origins']), rng_origins(w['priority_validation_origins'])
    s = build_signals(bt, iv, p.Y, cal_o + val_o)
    assert s[s.origin.isin(val_o)].outcome_ae.notna().all(), 'missing validation outcomes'
    s.to_csv(OUT / 'signals_preholdout.csv.gz', index=False)
    cal, val = s[s.origin.isin(cal_o)], s[s.origin.isin(val_o)]
    thr = float(np.nanquantile(cal.outcome_ne, 0.90))
    Ks = w['capacities']
    grid = weight_grid(0.1)
    ev = run_rules(val, Ks, thr, {'rank': grid, 'median': grid})
    rnd = evaluate_random(val, Ks, thr, w['random_priority_repeats'], w['seed'])
    best = pick(ev)
    norm, *wts = best.rule.split('_')[1:]
    wts = tuple(float(x) for x in wts)
    # validation-internal honesty check: choose on first half, score on second half
    half = len(val_o) // 2
    first, second = val[val.origin.isin(val_o[:half])], val[val.origin.isin(val_o[half:])]
    ev1 = ev[ev.origin.isin(val_o[:half])]
    b1 = pick(ev1)
    n1, *w1 = b1.rule.split('_')[1:]
    ev2 = ev[ev.origin.isin(val_o[half:])]
    def mean_cap(e, rule, K=5):
        return float(e[(e.rule == rule) & (e.K == K)].captured_ae_share.mean())
    base_full = {r: mean_cap(ev, r) for r in ['volume', 'recent_error']}
    best_base = max(base_full, key=base_full.get)
    split = {'chosen_on_first_half': b1.rule, 'second_half_proposed': mean_cap(ev2, b1.rule),
             'second_half_volume': mean_cap(ev2, 'volume'), 'second_half_recent_error': mean_cap(ev2, 'recent_error')}
    beats_full = best.cap > base_full[best_base]
    beats_split = split['second_half_proposed'] > max(split['second_half_volume'], split['second_half_recent_error'])
    recommended = best.rule if (beats_full and beats_split) else best_base
    # summary table
    keep = ['volume', 'recent_error', 'bias', 'uncertainty', 'recent_error_norm', best.rule]
    summ = ev[ev.rule.isin(keep)].groupby(['rule', 'K']).agg(
        captured_ae_mean=('captured_ae_share', 'mean'), captured_ae_p10=('captured_ae_share', lambda x: x.quantile(.1)),
        captured_ae_p90=('captured_ae_share', lambda x: x.quantile(.9)), captured_ne_mean=('captured_ne_share', 'mean'),
        precision=('precision', 'mean'), recall=('recall', 'mean'), weeks=('origin', 'nunique')).reset_index()
    rs = rnd.groupby(['K']).agg(captured_ae_mean=('captured_ae_share', 'mean'), captured_ae_p10=('captured_ae_share', lambda x: x.quantile(.1)),
                                 captured_ae_p90=('captured_ae_share', lambda x: x.quantile(.9)), captured_ne_mean=('captured_ne_share', 'mean'),
                                 precision=('precision', 'mean'), recall=('recall', 'mean')).reset_index().assign(rule='random', weeks=len(val_o))
    summ = pd.concat([summ, rs], ignore_index=True)
    # weekly win rate of proposed vs baselines at K=5
    pv = ev[(ev.K == 5) & ev.rule.isin(['volume', 'recent_error', best.rule])].pivot(index='origin', columns='rule', values='captured_ae_share')
    win = {f'{best.rule}_beats_{b}_weeks': int((pv[best.rule] > pv[b]).sum()) for b in ['volume', 'recent_error']}
    win['ties_with_recent_error_weeks'] = int((pv[best.rule] == pv['recent_error']).sum())
    win['weeks'] = len(pv)
    ev.drop(columns='selected').to_csv(OUT / 'validation_rule_weekly.csv.gz', index=False)
    ev[ev.rule.isin(keep)].to_csv(OUT / 'validation_rule_weekly_selected.csv', index=False)
    summ.to_csv(OUT / 'validation_rule_summary.csv', index=False)
    grid_summary = ev[(ev.K == 5) & ev.rule.str.startswith('proposed_')].groupby('rule').captured_ae_share.mean().sort_values(ascending=False)
    grid_summary.to_csv(OUT / 'validation_weight_grid_k5.csv')
    frozen = {
        'frozen_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'forecast_model': model, 'lgbm_config': json.loads((ROOT / 'results' / 'checkpoint3' / 'lgbm_choice.json').read_text())['chosen_config'],
        'interval_multipliers': cp3['width_multipliers_by_horizon_week'],
        'event_threshold_normalised_error': thr,
        'proposed_rule': {'normalisation': norm, 'weights': dict(zip(SIGNALS, wts)), 'label': best.rule},
        'recommended_rule': recommended,
        'recommendation_logic': {'proposed_k5_validation': float(best.cap), 'best_simple_baseline': best_base,
                                 'baseline_k5_validation': base_full, 'beats_full_window': bool(beats_full),
                                 'split_check': split, 'beats_split_check': bool(beats_split)},
        'holdout_status': 'not yet evaluated at freeze time',
    }
    blob = json.dumps(frozen, indent=2, sort_keys=True)
    frozen['sha256_of_choices'] = hashlib.sha256(blob.encode()).hexdigest()
    (ROOT / 'config' / 'frozen_choices.json').write_text(json.dumps(frozen, indent=2))
    (OUT / 'checkpoint4_validation.json').write_text(json.dumps({**frozen, 'weekly_wins_k5': win}, indent=2, default=float))
    print(summ.round(3).to_string(index=False))
    print(json.dumps({'threshold': thr, 'best_proposed': best.rule, 'cap5': round(best.cap, 4), 'recommended': recommended,
                      'split': split, 'wins': win}, indent=1, default=float))


if __name__ == '__main__':
    main()
