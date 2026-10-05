"""Load the DuckDB-built model input into aligned numpy arrays.

Day d (1-based, M5 d_<d>) is column d-1. History known at origin T is columns [0, T).
`seal_after` replaces actual sales after that day with NaN so pre-holdout code
cannot read the final 28 days even by mistake.
"""
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVENT_CODES = {'Cultural': 1, 'National': 2, 'Religious': 3, 'Sporting': 4}


def windows():
    return json.loads((ROOT / 'config' / 'windows.json').read_text())


@dataclass
class Panel:
    ids: list
    meta: pd.DataFrame          # aligned to ids
    Y: np.ndarray               # n x D float, units (NaN after seal)
    P: np.ndarray               # n x D daily sell price of the day's week (NaN = missing, not imputed)
    snap: np.ndarray            # n x D
    wday: np.ndarray            # D, 1=Saturday .. 7=Friday (M5 convention)
    month: np.ndarray           # D
    event: np.ndarray           # D, 0 none else EVENT_CODES of event_type_1
    week: np.ndarray            # D, wm_yr_wk
    sealed_after: int

    @property
    def n(self):
        return len(self.ids)

    @property
    def D(self):
        return self.Y.shape[1]


def load_panel(scope: str = 'panel', seal_after: int | None = 1913) -> Panel:
    sfx = '' if scope == 'panel' else '_pilot'
    mi = pd.read_csv(ROOT / 'data' / 'derived' / f'model_input{sfx}.csv.gz')
    meta = pd.read_csv(ROOT / 'data' / 'prepared' / 'panel_metadata.csv')
    if scope == 'pilot':
        meta = meta[meta.pilot]
    meta = meta.sort_values('id').reset_index(drop=True)
    ids = meta.id.tolist()
    assert set(ids) == set(mi.id.unique()), 'model input ids differ from metadata'
    D = int(mi.d_num.max())
    assert mi.groupby('id').d_num.nunique().eq(D).all(), 'missing id/day rows'
    mi = mi.set_index(['id', 'd_num']).sort_index()
    def arr(col):
        return np.array(mi[col].unstack('d_num').reindex(ids).to_numpy(dtype=float), copy=True)
    Y, P = arr('units'), arr('sell_price')
    # Calendar fields come from the full calendar (d_1..d_1969): future dates/events/SNAP are
    # known in advance, so forecasts whose 28-day window passes d_1941 still get target-day features.
    cal = pd.read_csv(ROOT / 'data' / 'prepared' / 'calendar.csv')
    cal['d_num'] = cal.d.str.replace('d_', '', regex=False).astype(int)
    cal = cal.sort_values('d_num').reset_index(drop=True)
    assert cal.d_num.tolist() == list(range(1, len(cal) + 1)) and len(cal) >= D
    wday = cal.wday.to_numpy(int)
    month = cal.month.to_numpy(int)
    event = cal.event_type_1.map(EVENT_CODES).fillna(0).to_numpy(int)
    week = cal.wm_yr_wk.to_numpy(int)
    snap_by_state = {s: cal[f'snap_{s}'].to_numpy(float) for s in ['CA', 'TX', 'WI']}
    snap = np.vstack([snap_by_state[s] for s in meta.state_id])
    assert np.array_equal(snap[:, :D], arr('snap')), 'calendar SNAP disagrees with DuckDB model input'
    sealed = D if seal_after is None else seal_after
    if seal_after is not None:
        Y[:, seal_after:] = np.nan
    return Panel(ids, meta, Y, P, snap, wday, month, event, week, sealed)
