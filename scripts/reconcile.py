"""Reconcile DuckDB-recomputed metrics (sql/02_analytics.sql) with Python results files.
Writes results/analytics/reconciliation.csv; exits non-zero on any mismatch > 1e-6."""
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-6


def main():
    sql = pd.read_csv(ROOT / 'results/analytics/sql_forecast_metrics.csv')
    rows = []
    py_val = pd.read_csv(ROOT / 'results/checkpoint3/validation_metrics.csv').assign(segment_type='all', segment='all')
    py_seg = pd.read_csv(ROOT / 'results/checkpoint3/validation_metrics_segments.csv')
    py_val = pd.concat([py_val, py_seg[py_seg.segment_type.isin(['volume_group', 'pattern_group', 'store_id', 'cat_id'])]]).assign(period='validation')
    py_hold = pd.read_csv(ROOT / 'results/holdout/holdout_forecast_metrics.csv')
    py_hold = py_hold[py_hold.segment_type != 'horizon_week'].assign(period='holdout')
    py = pd.concat([py_val, py_hold])
    py['segment'] = py.segment.astype(str)
    sql['segment'] = sql.segment.astype(str)
    m = py.merge(sql, on=['period', 'model', 'segment_type', 'segment'], suffixes=('_py', '_sql'), how='outer', indicator=True)
    for metric in ['wape', 'bias', 'mean_rmsse']:
        m[f'{metric}_absdiff'] = (m[f'{metric}_py'] - m[f'{metric}_sql']).abs()
    m.to_csv(ROOT / 'results/analytics/reconciliation_forecast.csv', index=False)
    bad_f = m[(m._merge != 'both') | (m[['wape_absdiff', 'bias_absdiff', 'mean_rmsse_absdiff']].max(axis=1) > TOL)]
    # priority summaries
    ps = pd.read_csv(ROOT / 'results/analytics/sql_priority_summary.csv')
    pv = pd.read_csv(ROOT / 'results/checkpoint4/validation_rule_summary.csv')
    ph = pd.read_csv(ROOT / 'results/holdout/holdout_rule_summary.csv')
    pp = pd.concat([pv[pv.rule != 'random'].assign(period='validation'), ph[~ph.rule.str.startswith('random')].assign(period='holdout')])
    q = pp.merge(ps, on=['period', 'rule', 'K'], suffixes=('_py', '_sql'), how='outer', indicator=True)
    q['cap_absdiff'] = (q.captured_ae_mean_py - q.captured_ae_mean_sql).abs()
    q['prec_absdiff'] = (q.precision_py - q.precision_sql).abs()
    q.to_csv(ROOT / 'results/analytics/reconciliation_priority.csv', index=False)
    bad_p = q[(q._merge != 'both') | (q[['cap_absdiff', 'prec_absdiff']].max(axis=1) > TOL)]
    print(f'forecast metric rows compared: {len(m)}, mismatches: {len(bad_f)}')
    print(f'priority summary rows compared: {len(q)}, mismatches: {len(bad_p)}')
    if len(bad_f) or len(bad_p):
        print(bad_f.head().to_string(), bad_p.head().to_string())
        sys.exit(1)


if __name__ == '__main__':
    main()
