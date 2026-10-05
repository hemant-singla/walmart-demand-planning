"""Checkpoint 3b: weekly rolling-origin backtest (origins 1493..1906, step 7) on the 200-series panel.
Each origin refits LightGBM (frozen config from tuning) with only then-available history; ETS refit per origin.
Actuals after d_1913 are sealed (NaN). Resumable: one file per origin."""
from pathlib import Path
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from wdp.data import load_panel, windows
from wdp.backtest import Runner


def main():
    w = windows()
    cfg = json.loads((ROOT / 'results' / 'checkpoint3' / 'lgbm_choice.json').read_text())['chosen_config']
    wb = w['weekly_backtest_origins']
    origins = list(range(wb['first'], wb['last'] + 1, wb['step']))
    odir = ROOT / 'results' / 'backtest' / 'origins'
    odir.mkdir(parents=True, exist_ok=True)
    p = load_panel('panel', seal_after=1913)
    r = Runner(p, cfg)
    logs = []
    for T in origins:
        f = odir / f'{T}.csv.gz'
        if f.exists():
            continue
        r.log = []
        fc = r.run([T])
        fc['forecast'] = fc.forecast.round(5)
        fc.to_csv(f, index=False)
        pd.DataFrame(r.log).to_csv(odir / f'{T}_runtime.csv', index=False)
        print(T, {l['model']: round(l.get('seconds', 0), 1) for l in r.log}, flush=True)
    print('done', len(origins))


if __name__ == '__main__':
    main()
