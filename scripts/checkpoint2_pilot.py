"""Checkpoint 2: 30-series pilot. Three baselines at three pre-holdout origins + temporal tests."""
from pathlib import Path
import json
import subprocess
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.backtest import Runner
from wdp.metrics import summarize


def main():
    w = windows()
    out = ROOT / 'results' / 'checkpoint2'
    out.mkdir(parents=True, exist_ok=True)
    tests = subprocess.run([sys.executable, str(ROOT / 'tests' / 'test_temporal.py')], capture_output=True, text=True)
    (out / 'temporal_tests.txt').write_text(tests.stdout + tests.stderr)
    p = load_panel('pilot', seal_after=1913)
    r = Runner(p, 'tweedie_31')
    fc = r.run(w['pilot_origins'])
    assert fc.d.max() <= 1913 and fc.y.notna().all(), 'pilot evaluation touched holdout'
    fc = fc.merge(p.meta[['volume_group', 'pattern_group', 'store_id', 'cat_id']].reset_index().rename(columns={'index': 'idx'}), on='idx')
    fc.to_csv(out / 'pilot_forecasts.csv.gz', index=False)
    overall = summarize(fc)
    seg = summarize(fc, ['volume_group'])
    perorigin = summarize(fc, ['origin'])
    log = pd.DataFrame(r.log)
    overall.to_csv(out / 'pilot_metrics.csv', index=False)
    pd.concat([seg, perorigin]).to_csv(out / 'pilot_metrics_segments.csv', index=False)
    log.to_csv(out / 'pilot_runtime.csv', index=False)
    summary = {'tests_passed': tests.returncode == 0, 'origins': w['pilot_origins'], 'series': p.n,
               'metrics': overall[['model', 'mean_rmsse', 'wape', 'bias', 'rmsse_undefined']].round(4).to_dict('records'),
               'runtime_s': log.groupby('model').seconds.sum().round(2).to_dict(),
               'lgbm_train_max_target_le_origin': bool((log.dropna(subset=['train_max_target_day']).eval('train_max_target_day <= origin')).all())}
    (out / 'checkpoint2.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=1))
    print(perorigin[['model', 'origin', 'mean_rmsse', 'wape']].round(3).to_string(index=False))


if __name__ == '__main__':
    main()
