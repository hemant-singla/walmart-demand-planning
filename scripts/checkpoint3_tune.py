"""Checkpoint 3a: limited LightGBM tuning (3 configs) on tuning origins only (1661/1689/1717).
Selection rule fixed in advance: lowest mean RMSSE over tuning origins; no early stopping."""
from pathlib import Path
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.backtest import Runner
from wdp.models import LGB_CONFIGS
from wdp.metrics import summarize


def main():
    w = windows()
    out = ROOT / 'results' / 'checkpoint3'
    out.mkdir(parents=True, exist_ok=True)
    p = load_panel('panel', seal_after=1913)
    origins = w['forecast_tuning_origins']
    assert max(origins) + 28 <= min(w['forecast_validation_origins'])
    frames, logs = [], []
    base = Runner(p)
    f = base.run(origins, models=('snaive', 'ets'))
    frames.append(f); logs += base.log
    for cfg in LGB_CONFIGS:
        r = Runner(p, cfg)
        r.store = base.store                      # share cached features
        fc = r.run(origins, models=('lgbm',))
        fc['model'] = f'lgbm_{cfg}'
        frames.append(fc); logs += r.log
    fc = pd.concat(frames)
    assert fc.d.max() <= 1913
    res = summarize(fc).sort_values('mean_rmsse')
    res.to_csv(out / 'tuning_metrics.csv', index=False)
    pd.DataFrame(logs).to_csv(out / 'tuning_runtime.csv', index=False)
    lg = res[res.model.str.startswith('lgbm_')]
    chosen = lg.iloc[0].model.replace('lgbm_', '')
    (out / 'lgbm_choice.json').write_text(json.dumps({'chosen_config': chosen, 'rule': 'lowest mean RMSSE on tuning origins',
                                                       'tuning_origins': origins}, indent=2))
    print(res[['model', 'mean_rmsse', 'wape', 'bias']].round(4).to_string(index=False))
    print('chosen', chosen)


if __name__ == '__main__':
    main()
