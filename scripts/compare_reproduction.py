"""Compare a clean re-run of the pipeline (other project folder) with this folder's saved results.

Usage: python scripts/compare_reproduction.py <path-to-rerun-folder>
Writes results/reproduction_check.csv and prints a summary. Numeric tolerance 1e-9 unless stated.
"""
from pathlib import Path
import json
import sys
import numpy as np
import pandas as pd

A = Path(__file__).resolve().parents[1]
B = Path(sys.argv[1]).resolve()
rows = []


def add(item, ok, detail=''):
    rows.append({'item': item, 'match': bool(ok), 'detail': detail})


def csv_equal(rel, keys=None, tol=1e-9):
    a, b = pd.read_csv(A / rel), pd.read_csv(B / rel)
    if keys:
        a, b = a.sort_values(keys).reset_index(drop=True), b.sort_values(keys).reset_index(drop=True)
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return add(rel, False, f'shape {a.shape} vs {b.shape}')
    worst = 0.0
    for c in a.columns:
        if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
            d = np.nanmax(np.abs(a[c].to_numpy(float) - b[c].to_numpy(float))) if len(a) else 0
            if not (np.isnan(a[c]) == np.isnan(b[c])).all():
                return add(rel, False, f'NaN pattern differs in {c}')
            worst = max(worst, 0 if np.isnan(d) else d)
        elif not (a[c].astype(str) == b[c].astype(str)).all():
            return add(rel, False, f'text differs in {c}')
    add(rel, worst <= tol, f'max abs diff {worst:.3g}')


for rel in ['results/checkpoint1/sql_audit.csv', 'results/checkpoint1/sql_audit_pilot.csv', 'results/checkpoint1/reconciliation_checks.csv']:
    csv_equal(rel)
csv_equal('results/checkpoint2/pilot_metrics.csv', ['model'])
csv_equal('results/checkpoint3/tuning_metrics.csv', ['model'])
for f in ['lgbm_choice.json', 'forecast_choice.json']:
    a, b = json.loads((A / 'results/checkpoint3' / f).read_text()), json.loads((B / 'results/checkpoint3' / f).read_text())
    add(f'results/checkpoint3/{f}', json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
# backtest forecasts
worst, n = 0.0, 0
for fa in sorted((A / 'results/backtest/origins').glob('[0-9]*.csv.gz')):
    fb = B / 'results/backtest/origins' / fa.name
    if not fb.exists():
        add('backtest ' + fa.name, False, 'missing in rerun')
        continue
    a, b = pd.read_csv(fa), pd.read_csv(fb)
    k = ['model', 'origin', 'idx', 'h']
    m = a.merge(b, on=k, suffixes=('_a', '_b'))
    if len(m) != len(a):
        add('backtest ' + fa.name, False, 'row mismatch')
    worst = max(worst, (m.forecast_a - m.forecast_b).abs().max())
    n += 1
add(f'backtest forecasts ({n} origins, all models)', worst <= 1e-4, f'max abs diff {worst:.3g} units (files store 5 decimals)')
csv_equal('results/checkpoint3/validation_metrics.csv', ['model'], tol=1e-6)
ca, cb = json.loads((A / 'results/checkpoint3/checkpoint3.json').read_text()), json.loads((B / 'results/checkpoint3/checkpoint3.json').read_text())
add('interval width multipliers', ca['width_multipliers_by_horizon_week'] == cb['width_multipliers_by_horizon_week'], str(cb['width_multipliers_by_horizon_week']))
# frozen choices: compare substance, not timestamp/hash
fa, fb = json.loads((A / 'config/frozen_choices.json').read_text()), json.loads((B / 'config/frozen_choices.json').read_text())
for key in ['forecast_model', 'lgbm_config', 'interval_multipliers', 'proposed_rule', 'recommended_rule']:
    add(f'frozen choice: {key}', json.dumps(fa[key], sort_keys=True) == json.dumps(fb[key], sort_keys=True), str(fb[key])[:80])
add('frozen choice: event threshold', abs(fa['event_threshold_normalised_error'] - fb['event_threshold_normalised_error']) < 1e-9,
    f"{fb['event_threshold_normalised_error']:.6f}")
csv_equal('results/checkpoint4/validation_rule_summary.csv', ['rule', 'K'], tol=1e-9)
csv_equal('results/holdout/holdout_forecast_metrics.csv', ['model', 'segment_type', 'segment'], tol=1e-6)
csv_equal('results/holdout/holdout_rule_summary.csv', ['rule', 'K'], tol=1e-6)
csv_equal('results/analytics/sql_forecast_metrics.csv', ['period', 'model', 'segment_type', 'segment'], tol=1e-6)
for f in ['ctx_guard', 'ctx_store_summary', 'ctx_dept_summary', 'ctx_snap', 'ctx_panel_vs_m5']:
    csv_equal(f'results/dashboard/{f}.csv', tol=1e-9)
csv_equal('results/dashboard/review_lists.csv', ['origin', 'rank'], tol=1e-6)
out = pd.DataFrame(rows)
out.to_csv(A / 'results' / 'reproduction_check.csv', index=False)
print(out.to_string(index=False))
print(f'\n{int(out.match.sum())}/{len(out)} items match')
