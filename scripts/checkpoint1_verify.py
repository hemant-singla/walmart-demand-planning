"""Checkpoint 1: reconcile DuckDB audit tables against the supplied audit, record environment."""
from pathlib import Path
import json
import platform
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel


def versions():
    out = {'python': platform.python_version(), 'platform': platform.platform()}
    for m in ['pandas', 'numpy', 'scipy', 'sklearn', 'lightgbm', 'duckdb', 'statsmodels', 'streamlit']:
        try:
            out[m] = __import__(m).__version__
        except Exception:
            out[m] = 'not installed'
    return out


def main():
    audit = json.loads((ROOT / 'data' / 'audit_summary.json').read_text())
    res = {}
    checks = []
    for scope, sfx, n_ser in [('panel', '', 200), ('pilot', '_pilot', 30)]:
        a = pd.read_csv(ROOT / 'results' / 'checkpoint1' / f'sql_audit{sfx}.csv').iloc[0]
        c = {
            f'{scope}: ids': (int(a.n_ids), n_ser),
            f'{scope}: days': (int(a.n_days), audit['history_days']),
            f'{scope}: rows = ids x days': (int(a.n_rows), n_ser * audit['history_days']),
            f'{scope}: duplicate id/day keys': (int(a.dup_id_day), 0),
            f'{scope}: duplicate store/item/week price keys': (int(a.dup_price_key), 0),
            f'{scope}: wide vs long cell mismatches': (int(a.wide_long_mismatch), 0),
            f'{scope}: wide total = long total': (int(a.wide_total_units), int(a.total_units)),
            f'{scope}: join keeps rows': (int(a.joined_rows), int(a.n_rows)),
            f'{scope}: join keeps units': (int(a.joined_units), int(a.total_units)),
            f'{scope}: positive sales with missing price': (int(a.positive_sales_missing_price), 0),
            f'{scope}: null/negative units': (int(a.null_units + a.neg_units), 0),
            f'{scope}: selection stats match metadata': (int(a.selection_units_mismatch), 0),
        }
        if scope == 'panel':
            c['panel: total units = audit'] = (int(a.total_units), audit['panel_total_units'])
            c['panel: missing price days = audit'] = (int(a.missing_price_days), audit['missing_panel_price_days'])
        for k, (got, exp) in c.items():
            checks.append({'check': k, 'observed': got, 'expected': exp, 'pass': got == exp})
        res[scope] = a.to_dict()
    # Missing-price structure (descriptive only; not evidence of stockouts)
    p = load_panel('panel', seal_after=None)
    miss = np.isnan(p.P)
    first_price = np.argmax(~miss, axis=1)
    before_launch = sum(miss[i, :first_price[i]].sum() for i in range(p.n))
    res['missing_price'] = {'total_days': int(miss.sum()), 'before_first_priced_week': int(before_launch),
                            'after_first_priced_week': int(miss.sum() - before_launch),
                            'series_with_any_missing': int(miss.any(axis=1).sum()),
                            'series_missing_after_launch': int(sum(miss[i, first_price[i]:].any() for i in range(p.n)))}
    zero_days = (p.Y == 0)
    res['zero_sales_share_all_days'] = float(zero_days.mean())
    out = ROOT / 'results' / 'checkpoint1'
    pd.DataFrame(checks).to_csv(out / 'reconciliation_checks.csv', index=False)
    env = versions()
    env['duckdb_engine'] = 'duckdb-cli v1.4.1 (Python package unavailable in this execution environment)'
    (ROOT / 'environment').mkdir(exist_ok=True)
    (ROOT / 'environment' / 'executed_versions.json').write_text(json.dumps(env, indent=2))
    summary = {'all_pass': all(c['pass'] for c in checks), 'n_checks': len(checks),
               'failed': [c['check'] for c in checks if not c['pass']], **res['missing_price'],
               'zero_sales_share_all_days': res['zero_sales_share_all_days']}
    (out / 'checkpoint1.json').write_text(json.dumps(summary, indent=2, default=int))
    print(json.dumps(summary, indent=1, default=int))


if __name__ == '__main__':
    main()
