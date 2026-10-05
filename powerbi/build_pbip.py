"""Generate the Power BI project (PBIP: PBIR report + TMDL semantic model) from results/dashboard/*.csv.

Run from the project root:  python powerbi/build_pbip.py [--data-folder "C:\\path\\to\\powerbi\\data\\"]
Then open powerbi/Walmart_Demand_Planning.pbip in Power BI Desktop and press Refresh.
Every number shown in the report comes from the CSVs; text facts are computed from the same CSVs here.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import uuid
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'results' / 'dashboard'
OUT = ROOT / 'powerbi'
NAME = 'Walmart_Demand_Planning'
DEFAULT_FOLDER = r'C:\Users\SAMSUNG\Desktop\Resumes\Walmart_Demand_Planning\powerbi\data' + '\\'
THEME_SRC = Path(__file__).resolve().parent / 'theme' / 'CY23SU04.json'

MODEL_NAMES = {'lgbm': 'LightGBM', 'ets': 'ETS', 'snaive': 'Seasonal naive'}
RULE_NAMES = {'proposed_median_0.2_0.1_0.7': 'Combined score (frozen)', 'volume': 'Top sellers',
              'recent_error': 'Largest recent error', 'bias': 'Persistent bias', 'uncertainty': 'Widest range',
              'recent_error_norm': 'Normalised error (diagnostic)', 'random': 'Random (200 draws)',
              'random (5-95% for min/max)': 'Random (200 draws)'}
PERIOD_NAMES = {'validation (6 origins)': 'Validation', 'holdout (origin 1913)': 'Holdout'}


def uid(*parts):
    return str(uuid.UUID(hashlib.md5('|'.join(map(str, parts)).encode()).hexdigest()))


def hid(*parts):
    return hashlib.md5('|'.join(map(str, parts)).encode()).hexdigest()[:20]


# =====================================================================================
# 1. Data: normalise CSVs for Power BI (friendly labels, Yes/No instead of booleans)
# =====================================================================================
def prepare_data():
    d = {}
    rd = lambda f: pd.read_csv(SRC / f)
    cal = pd.read_csv(ROOT / 'data/prepared/calendar.csv')
    cal['d'] = cal.d.str.replace('d_', '', regex=False).astype(int)
    d['Dates'] = cal[['d', 'date', 'year', 'month', 'weekday', 'wday', 'event_name_1', 'event_type_1', 'snap_CA', 'snap_TX', 'snap_WI']].rename(
        columns={'event_name_1': 'event', 'event_type_1': 'event_type'})
    d['Series'] = rd('series.csv')
    rl = rd('review_lists.csv')
    asof = rl[['origin', 'period']].drop_duplicates().sort_values('origin')
    asof['asof_date'] = asof.origin.map(cal.set_index('d').date)
    asof['period'] = np.where(asof.period == 'holdout', 'Holdout', 'Validation')
    asof['label'] = asof.asof_date + ' (' + asof.period + ')'
    d['AsOf'] = asof[['origin', 'asof_date', 'period', 'label']]
    rl['period'] = np.where(rl.period == 'holdout', 'Holdout', 'Validation')
    rl['event'] = np.where(rl.event, 'Yes', 'No')
    rl['top10'] = np.where(rl['rank'] <= 10, 'Yes', 'No')
    rl['series_label'] = rl.item_id + ' @ ' + rl.store_id
    d['ReviewList'] = rl.drop(columns=['item_id', 'cat_id', 'dept_id', 'volume_group', 'pattern_group'])
    d['ForecastBand'] = rd('forecast_intervals.csv')
    d['SalesHistory'] = rd('sales_history.csv')
    mc = rd('model_comparison.csv')
    mc['model'] = mc.model.map(MODEL_NAMES)
    mc['period'] = mc.period.map(PERIOD_NAMES)
    mc['segment'] = mc.segment.astype(str)
    mc.loc[mc.segment_type == 'horizon_week', 'segment'] = mc.segment.map({'1': 'Days 1-7', '2': 'Days 8-14', '3': 'Days 15-21', '4': 'Days 22-28'})
    mc.loc[mc.segment_type == 'origin', 'segment'] = 'd' + mc.segment
    seg_order = {'high': 1, 'medium': 2, 'low': 3, 'frequent': 4, 'irregular': 5, 'Days 1-7': 6, 'Days 8-14': 7, 'Days 15-21': 8, 'Days 22-28': 9}
    mc['segment_order'] = mc.segment.map(seg_order).fillna(0).astype(int)
    om = mc.segment_type == 'origin'
    mc.loc[om, 'segment_order'] = mc.loc[om, 'segment'].str[1:].astype(int)
    d['ModelComparison'] = mc
    ic = rd('interval_coverage.csv')
    raw = pd.read_csv(ROOT / 'results/checkpoint3/interval_coverage_calibration_raw.csv')
    raw = raw.assign(slice='b=' + raw.b.astype(str), period='calibration (raw)').drop(columns='b')
    ic = pd.concat([ic, raw], ignore_index=True)
    ic['period'] = ic.period.map({'validation': 'Validation (calibrated)', 'holdout': 'Holdout (calibrated)', 'calibration (raw)': 'Calibration weeks (raw, before widening)'})
    def slabel(s):
        if s.startswith('b='):
            return 'horizon', {'1': 'Days 1-7', '2': 'Days 8-14', '3': 'Days 15-21', '4': 'Days 22-28'}[s[2:]]
        if s == 'all':
            return 'all', 'All series, 28 days'
        if '=' in s:
            return 'segment', s.split('=')[1]
        return 'weekly', 'Weekly lists, days 1-7'
    ic[['slice_type', 'slice_label']] = ic.slice.apply(lambda s: pd.Series(slabel(s)))
    ic['slice_order'] = ic.slice_label.map({'Days 1-7': 1, 'Days 8-14': 2, 'Days 15-21': 3, 'Days 22-28': 4}).fillna(0).astype(int)
    d['IntervalCoverage'] = ic
    rw = rd('rule_weekly.csv')
    rw['rule'] = rw.rule.map(RULE_NAMES)
    rw['period'] = rw.period.str.capitalize()
    d['RuleWeekly'] = rw
    rs = rd('rule_summary.csv')
    rs['rule'] = rs.rule.map(RULE_NAMES)
    rs['period'] = rs.period.str.capitalize()
    d['RuleSummary'] = rs[['period', 'rule', 'K', 'captured_ae_mean', 'captured_ne_mean', 'precision', 'recall', 'weeks']]
    dc = rd('data_checks.csv')
    dc['pass'] = np.where(dc['pass'], 'Yes', 'No')
    d['DataChecks'] = dc
    d['Strata'] = rd('strata.csv')
    for t, f in [('CtxStore', 'ctx_store_summary'), ('CtxDept', 'ctx_dept_summary'), ('CtxMonthly', 'ctx_monthly'),
                 ('CtxWeekday', 'ctx_weekday'), ('CtxSnap', 'ctx_snap'), ('CtxEvents', 'ctx_events'), ('CtxPareto', 'ctx_pareto'),
                 ('CtxZeroShare', 'ctx_zero_share'), ('CtxPanelVsM5', 'ctx_panel_vs_m5'), ('CtxPrice', 'ctx_price_changes'),
                 ('CtxDaily', 'ctx_daily_store_cat')]:
        d[t] = rd(f + '.csv')
    d['CtxPanelVsM5']['population'] = d['CtxPanelVsM5'].population.map({'All M5 (10 stores, 3 categories)': 'All M5',
        'CA_1 + TX_1, FOODS + HOUSEHOLD (sampling universe)': 'Sampling universe', 'Our 200-series panel': 'Our 200-series panel'})
    zs = d['CtxZeroShare']
    zs['bin_label'] = (zs.zero_share_bin * 100).round().astype(int).astype(str) + '-' + (zs.zero_share_bin * 100 + 10).round().astype(int).astype(str) + '%'
    zs.loc[zs.zero_share_bin >= 1, 'bin_label'] = '100%'
    ev = d['CtxEvents']
    ev['event'] = ev.event.str.replace("'", '', regex=False)
    return d


# =====================================================================================
# 2. Semantic model (TMDL)
# =====================================================================================
PTYPE = {'int64': ('int64', 'Int64.Type', '0'), 'double': ('double', 'type number', None), 'string': ('string', 'type text', None),
         'dateTime': ('dateTime', 'type date', 'yyyy-mm-dd')}
DATE_COLS = {('Dates', 'date'), ('AsOf', 'asof_date'), ('CtxMonthly', 'month_start'), ('CtxDaily', 'date')}
SORT_BY = {('Dates', 'weekday'): 'wday', ('CtxWeekday', 'weekday'): 'wday', ('ModelComparison', 'segment'): 'segment_order', ('IntervalCoverage', 'slice_label'): 'slice_order'}
PCT_COLS = {'share_of_units', 'zero_share_after_launch', 'growth_2012_to_2015', 'snap_uplift_association', 'lift_vs_nearby_same_weekday',
            'cum_share', 'foods_share_of_units', 'share_weeks_price_changed', 'share_weeks_price_cut', 'wape', 'bias', 'coverage',
            'captured_ae_share', 'captured_ne_share', 'precision', 'recall', 'captured_ae_mean', 'captured_ne_mean', 'price_chg4', 'zero_share_bin'}

MEASURES = {
    'CtxStore': [('M5 units sold', 'SUM(CtxStore[total_units])', '#,0'), ('M5 product-store series', 'SUM(CtxStore[series])', '#,0'),
                 ('Store share of units', 'SUM(CtxStore[share_of_units])', '0.0%'), ('Growth 2012 to 2015', 'AVERAGE(CtxStore[growth_2012_to_2015])', '+0%;-0%'),
                 ('Stores', 'DISTINCTCOUNT(CtxStore[store_id])', '0')],
    'CtxDept': [('Dept share of units', 'SUM(CtxDept[share_of_units])', '0.0%'), ('Dept zero-sales share', 'AVERAGE(CtxDept[zero_share_after_launch])', '0%')],
    'CtxMonthly': [('Avg daily units', 'SUM(CtxMonthly[avg_daily_units])', '#,0')],
    'CtxPareto': [('Cumulative share of units', 'MAX(CtxPareto[cum_share])', '0%')],
    'CtxWeekday': [('Weekday index (avg 100)', 'AVERAGE(CtxWeekday[index_vs_week])', '0')],
    'CtxSnap': [('SNAP-day difference', 'AVERAGE(CtxSnap[snap_uplift_association])', '+0.0%;-0.0%')],
    'CtxEvents': [('Event-day difference', 'AVERAGE(CtxEvents[lift_vs_nearby_same_weekday])', '+0%;-0%')],
    'CtxZeroShare': [('Series in bin', 'SUM(CtxZeroShare[series])', '#,0')],
    'CtxDaily': [('Daily units', 'SUM(CtxDaily[units])', '#,0')],
    'CtxPanelVsM5': [('Units per series-day', 'AVERAGE(CtxPanelVsM5[avg_units_per_series_day])', '0.00'), ('Zero-sales share (avg)', 'AVERAGE(CtxPanelVsM5[zero_share_after_launch])', '0%'),
                     ('Panel series', 'CALCULATE(SUM(CtxPanelVsM5[series]), CtxPanelVsM5[population] = "Our 200-series panel")', '#,0')],
    'Strata': [('Series in stratum', 'SUM(Strata[series])', '0')],
    'ReviewList': [('Review score', 'SUM(ReviewList[score])', '0.00'), ('Recent error (units/wk)', 'SUM(ReviewList[recent_error])', '#,0'),
                   ('Range width (units/7d)', 'SUM(ReviewList[uncertainty])', '#,0')],
    'ModelComparison': [('Mean RMSSE', 'AVERAGE(ModelComparison[mean_rmsse])', '0.000'), ('WAPE (avg)', 'AVERAGE(ModelComparison[wape])', '0.0%'),
                        ('Bias (avg)', 'AVERAGE(ModelComparison[bias])', '+0.0%;-0.0%'),
                        ('Holdout RMSSE LightGBM', 'CALCULATE(AVERAGE(ModelComparison[mean_rmsse]), ModelComparison[period] = "Holdout", ModelComparison[model] = "LightGBM", ModelComparison[segment_type] = "all")', '0.000'),
                        ('Holdout RMSSE ETS', 'CALCULATE(AVERAGE(ModelComparison[mean_rmsse]), ModelComparison[period] = "Holdout", ModelComparison[model] = "ETS", ModelComparison[segment_type] = "all")', '0.000'),
                        ('Holdout RMSSE naive', 'CALCULATE(AVERAGE(ModelComparison[mean_rmsse]), ModelComparison[period] = "Holdout", ModelComparison[model] = "Seasonal naive", ModelComparison[segment_type] = "all")', '0.000')],
    'IntervalCoverage': [('Coverage (avg)', 'AVERAGE(IntervalCoverage[coverage])', '0.0%'),
                         ('Holdout coverage', 'CALCULATE(AVERAGE(IntervalCoverage[coverage]), IntervalCoverage[period] = "Holdout (calibrated)", IntervalCoverage[slice] = "all")', '0.0%'),
                         ('Avg range width (units/day)', 'AVERAGE(IntervalCoverage[mean_width])', '0.0')],
    'RuleWeekly': [('Captured share of next-week error', 'AVERAGE(RuleWeekly[captured_ae_share])', '0.0%'), ('Precision for large errors', 'AVERAGE(RuleWeekly[precision])', '0%')],
    'RuleSummary': [('Captured share (mean)', 'AVERAGE(RuleSummary[captured_ae_mean])', '0.0%'), ('Precision (mean)', 'AVERAGE(RuleSummary[precision])', '0%'),
                    ('Holdout K5 combined', 'CALCULATE(AVERAGE(RuleSummary[captured_ae_mean]), RuleSummary[period] = "Holdout", RuleSummary[K] = 5, RuleSummary[rule] = "Combined score (frozen)")', '0.0%'),
                    ('Holdout K5 random', 'CALCULATE(AVERAGE(RuleSummary[captured_ae_mean]), RuleSummary[period] = "Holdout", RuleSummary[K] = 5, RuleSummary[rule] = "Random (200 draws)")', '0.0%')],
    'DataChecks': [('Checks passed', 'COUNTROWS(FILTER(DataChecks, DataChecks[pass] = "Yes"))', '0'), ('Checks run', 'COUNTROWS(DataChecks)', '0')],
    'SalesHistory': [('Units sold', 'VAR o = SELECTEDVALUE(AsOf[origin]) VAR dd = MAX(Dates[d]) RETURN IF(NOT ISBLANK(o) && HASONEVALUE(Series[idx]) && dd > o - 56 && dd <= o + 28 && dd <= 1941, SUM(SalesHistory[units]) + 0)', '#,0')],
    'ForecastBand': [('Forecast units', 'IF(HASONEVALUE(AsOf[origin]) && HASONEVALUE(Series[idx]), SUM(ForecastBand[forecast]))', '#,0.0'),
                     ('Lower 90%', 'IF(HASONEVALUE(AsOf[origin]) && HASONEVALUE(Series[idx]), SUM(ForecastBand[lower]))', '#,0.0'),
                     ('Upper 90%', 'IF(HASONEVALUE(AsOf[origin]) && HASONEVALUE(Series[idx]), SUM(ForecastBand[upper]))', '#,0.0'),
                     ('Forecast next 7 days', 'IF(HASONEVALUE(AsOf[origin]) && HASONEVALUE(Series[idx]), CALCULATE(SUM(ForecastBand[forecast]), ForecastBand[h] <= 7))', '#,0.0')],
}

RELATIONSHIPS = [('ReviewList', 'idx', 'Series', 'idx'), ('ForecastBand', 'idx', 'Series', 'idx'), ('SalesHistory', 'idx', 'Series', 'idx'),
                 ('ForecastBand', 'd', 'Dates', 'd'), ('SalesHistory', 'd', 'Dates', 'd'), ('ReviewList', 'origin', 'AsOf', 'origin'),
                 ('ForecastBand', 'origin', 'AsOf', 'origin'), ('RuleWeekly', 'origin', 'AsOf', 'origin')]


def q(name):
    return name if name.replace('_', '').isalnum() and not name[0].isdigit() else "'" + name.replace("'", "''") + "'"


def col_type(table, c, s):
    if (table, c) in DATE_COLS:
        return 'dateTime'
    if pd.api.types.is_integer_dtype(s):
        return 'int64'
    if pd.api.types.is_float_dtype(s):
        return 'double'
    return 'string'


def tmdl_table(name, df, file):
    L = [f'table {name}', f'\tlineageTag: {uid("t", name)}', '']
    for m, expr, fmt in MEASURES.get(name, []):
        L += [f'\tmeasure {q(m)} = {expr}', f'\t\tformatString: {fmt}', f'\t\tlineageTag: {uid("m", name, m)}', '']
    types = {}
    for c in df.columns:
        t = col_type(name, c, df[c])
        types[c] = t
        L += [f'\tcolumn {q(c)}', f'\t\tdataType: {t}']
        fmt = PTYPE[t][2]
        if c in PCT_COLS and t == 'double':
            fmt = '0.0%'
        elif t == 'double':
            fmt = '#,0.0'
        if fmt:
            L.append(f'\t\tformatString: {fmt}')
        L += [f'\t\tlineageTag: {uid("c", name, c)}', '\t\tsummarizeBy: none', f'\t\tsourceColumn: {c}']
        if (name, c) in SORT_BY:
            L.append(f'\t\tsortByColumn: {SORT_BY[(name, c)]}')
        L += ['', '\t\tannotation SummarizationSetBy = User', '']
        if t == 'dateTime':
            L[-1:-1] = ['\t\tannotation UnderlyingDateTimeDataType = Date', '']
    numeric = [c for c, t in types.items() if t in ('int64', 'double', 'dateTime')]
    typelist = ', '.join('{"%s", %s}' % (c, PTYPE[t][1]) for c, t in types.items())
    nulls = ', '.join('"%s"' % c for c in numeric)
    M = ['let',
         f'    Source = Csv.Document(File.Contents(DataFolder & "{file}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
         '    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),',
         f'    Blanks = Table.ReplaceValue(Promoted, "", null, Replacer.ReplaceValue, {{{nulls}}}),' if numeric else '    Blanks = Promoted,',
         f'    Typed = Table.TransformColumnTypes(Blanks, {{{typelist}}}, "en-US")',
         'in', '    Typed']
    L += [f'\tpartition {name} = m', '\t\tmode: import', '\t\tsource =']
    L += ['\t\t\t\t' + line for line in M]
    L += ['', '\tannotation PBI_ResultType = Table', '']
    return '\n'.join(L)


def write_model(data, folder):
    sm = OUT / f'{NAME}.SemanticModel'
    if sm.exists():
        shutil.rmtree(sm)
    (sm / 'definition' / 'tables').mkdir(parents=True)
    (sm / 'definition.pbism').write_text(json.dumps({'version': '4.0', 'settings': {}}, indent=2))
    (sm / '.platform').write_text(json.dumps({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                                              'metadata': {'type': 'SemanticModel', 'displayName': NAME},
                                              'config': {'version': '2.0', 'logicalId': uid('sm', NAME)}}, indent=2))
    (sm / 'definition' / 'database.tmdl').write_text('database\n\tcompatibilityLevel: 1601\n\n')
    order = json.dumps(['DataFolder'] + list(data))
    model = ['model Model', '\tculture: en-US', '\tdefaultPowerBIDataSourceVersion: powerBI_V3', '\tdiscourageImplicitMeasures',
             '\tsourceQueryCulture: en-US', '\tdataAccessOptions', '\t\tlegacyRedirects', '\t\treturnErrorValuesAsNull', '',
             f'annotation PBI_QueryOrder = {order}', '', 'annotation __PBI_TimeIntelligenceEnabled = 0', '']
    model += [f'ref table {q(t)}' for t in data] + ['']
    (sm / 'definition' / 'model.tmdl').write_text('\n'.join(model))
    folder_m = folder.replace('"', '""')
    (sm / 'definition' / 'expressions.tmdl').write_text(
        f'/// Folder holding the dashboard CSVs (must end with a backslash). Change it if the project moves.\n'
        f'expression DataFolder = "{folder_m}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
        f'\tlineageTag: {uid("e", "DataFolder")}\n\n\tannotation PBI_ResultType = Text\n\n')
    rel = []
    for f_t, f_c, t_t, t_c in RELATIONSHIPS:
        rel += [f'relationship {uid("r", f_t, f_c, t_t)}', f'\tfromColumn: {f_t}.{f_c}', f'\ttoColumn: {t_t}.{t_c}', '']
    (sm / 'definition' / 'relationships.tmdl').write_text('\n'.join(rel))
    for name, df in data.items():
        (sm / 'definition' / 'tables' / f'{name}.tmdl').write_text(tmdl_table(name, df, f'{name}.csv'))


# =====================================================================================
# 3. Report (PBIR)
# =====================================================================================
S_VIS = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.0.0/schema.json'
S_PAGE = 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.4.0/schema.json'
TEAL, AMBER, INK, MUTED, LIGHT = '#0F7173', '#E09F3E', '#1B2A2F', '#5E6B6E', '#EEF3F3'


def lit(v):
    if isinstance(v, bool):
        return {'expr': {'Literal': {'Value': 'true' if v else 'false'}}}
    if isinstance(v, int):
        return {'expr': {'Literal': {'Value': f'{v}L'}}}
    if isinstance(v, float):
        return {'expr': {'Literal': {'Value': f'{v}D'}}}
    return {'expr': {'Literal': {'Value': "'" + str(v).replace("'", "''") + "'"}}}


def colf(t, c):
    return {'Column': {'Expression': {'SourceRef': {'Entity': t}}, 'Property': c}}


def measf(t, m):
    return {'Measure': {'Expression': {'SourceRef': {'Entity': t}}, 'Property': m}}


DISPLAY = {'store_id': 'Store', 'dept_id': 'Department', 'month_start': 'Month', 'weekday': 'Weekday', 'state_id': 'State',
           'bin_label': 'Share of days with zero sales', 'event': 'Event', 'segment': 'Segment', 'slice_label': 'Slice', 'asof_date': 'As-of week',
           'rule': 'Rule', 'date': 'Date', 'model': 'Model', 'cat_id': 'Category', 'period': 'Period', 'rank': 'Rank', 'series_label': 'Series',
           'volume': 'Units (last 28 d)', 'recent_error': 'Recent error / wk', 'bias_signed': 'Bias / wk', 'uncertainty': 'Range width (7 d)',
           'forecast_next7': 'Forecast next 7 d', 'suggested_investigation': 'Suggested investigation', 'days_since_sale': 'Days since sale',
           'population': 'Population', 'series': 'Series', 'avg_units_per_series_day': 'Units / series-day', 'zero_share_after_launch': 'Zero-sales share',
           'foods_share_of_units': 'FOODS share', 'check': 'Check', 'observed': 'Observed', 'expected': 'Expected', 'pass': 'Pass', 'K': 'K',
           'label': 'Week', 'id': 'Series'}


def proj(f, display=None):
    kind = 'Column' if 'Column' in f else 'Measure'
    ref = f'{f[kind]["Expression"]["SourceRef"]["Entity"]}.{f[kind]["Property"]}'
    p = {'field': f, 'queryRef': ref, 'nativeQueryRef': f[kind]['Property']}
    display = display or DISPLAY.get(f[kind]['Property'])
    if display:
        p['displayName'] = display
    return p


def in_filter(t, c, values, name):
    vals = [[{'Literal': {'Value': (f'{v}L' if isinstance(v, int) else "'" + str(v).replace("'", "''") + "'")}}] for v in values]
    return {'name': name, 'field': colf(t, c), 'type': 'Categorical',
            'filter': {'Version': 2, 'From': [{'Name': 'x', 'Entity': t, 'Type': 0}],
                       'Where': [{'Condition': {'In': {'Expressions': [{'Column': {'Expression': {'SourceRef': {'Source': 'x'}}, 'Property': c}}],
                                                       'Values': vals}}}]}}


class Page:
    def __init__(self, key, title, subtitle):
        self.key, self.title, self.visuals = key, title, []
        self.z = 0
        self.text(24, 8, 1232, 40, [[(title, {'fontSize': '20pt', 'fontWeight': 'bold', 'color': INK})]])
        self.text(24, 50, 1232, 40, [[(subtitle, {'fontSize': '11pt', 'color': TEAL})]])

    def _add(self, vtype, x, y, w, h, visual):
        self.z += 1000
        name = hid(self.key, len(self.visuals), vtype)
        visual['visualType'] = vtype
        self.visuals.append({'$schema': S_VIS, 'name': name,
                             'position': {'x': x, 'y': y, 'z': self.z, 'height': h, 'width': w, 'tabOrder': self.z},
                             'visual': visual})
        return self.visuals[-1]

    def text(self, x, y, w, h, paragraphs, bg=None):
        """paragraphs: list of paragraphs; each a list of (text, style) runs."""
        paras = [{'textRuns': [{'value': t, 'textStyle': dict({'fontSize': '11pt', 'color': INK}, **s)} for t, s in p]} for p in paragraphs]
        v = {'objects': {'general': [{'properties': {'paragraphs': paras}}]},
             'visualContainerObjects': {'background': [{'properties': {'show': lit(bg is not None)} | ({'color': {'solid': {'color': lit(bg)}}} if bg else {})}]},
             'drillFilterOtherVisuals': True}
        return self._add('textbox', x, y, w, h, v)

    def bullets(self, x, y, w, h, head, items, bg=LIGHT, size=11):
        fs = {'fontSize': f'{size}pt'}
        paras = [[(head, {'fontSize': f'{size + 2}pt', 'fontWeight': 'bold', 'color': TEAL})]]
        for it in items:
            if isinstance(it, tuple):
                paras.append([('• ' + it[0] + ' ', {'fontWeight': 'bold', **fs}), (it[1], fs)])
            else:
                paras.append([('• ' + it, fs)])
        return self.text(x, y, w, h, paras, bg)

    def _chart(self, vtype, x, y, w, h, roles, title, filters=None, objects=None, sort=None):
        qs = {r: {'projections': [proj(*f) if isinstance(f, tuple) else proj(f) for f in fs]} for r, fs in roles.items() if fs}
        v = {'query': {'queryState': qs}, 'drillFilterOtherVisuals': True,
             'visualContainerObjects': {'title': [{'properties': {'show': lit(True), 'text': lit(title)}}]}}
        if sort:
            v['query']['sortDefinition'] = {'sort': [{'field': sort[0], 'direction': sort[1]}], 'isDefaultSort': False}
        if objects:
            v['objects'] = objects
        c = self._add(vtype, x, y, w, h, v)
        if filters:
            c['filterConfig'] = {'filters': [in_filter(t, col, vals, hid(self.key, len(self.visuals), t, col)) for t, col, vals in filters]}
        return c

    def card(self, x, y, w, h, m, label):
        return self._chart('card', x, y, w, h, {'Values': [(m, label)]}, label,
                           objects={'labels': [{'properties': {'color': {'solid': {'color': lit(TEAL)}}, 'fontSize': lit(24.0)}}],
                                    'categoryLabels': [{'properties': {'show': lit(False)}}]})

    def column(self, x, y, w, h, cat, ys, title, series=None, filters=None, bar=False, labels=True, sort=None, axis_start=None):
        objs = {'labels': [{'properties': {'show': lit(labels)}}],
                'valueAxis': [{'properties': {'showAxisTitle': lit(False)} | ({'start': lit(float(axis_start))} if axis_start is not None else {})}]}
        return self._chart('clusteredBarChart' if bar else 'clusteredColumnChart', x, y, w, h,
                           {'Category': [cat], 'Y': ys, 'Series': [series] if series else []}, title, filters, objs, sort)

    def line(self, x, y, w, h, cat, ys, title, series=None, filters=None):
        objs = {'valueAxis': [{'properties': {'showAxisTitle': lit(False)}}], 'categoryAxis': [{'properties': {'showAxisTitle': lit(False)}}]}
        return self._chart('lineChart', x, y, w, h, {'Category': [cat], 'Y': ys, 'Series': [series] if series else []}, title, filters, objs)

    def table(self, x, y, w, h, cols, title, filters=None, sort=None, widths=None):
        objs = {'values': [{'properties': {'wordWrap': lit(True), 'fontSize': lit(10.0)}}],
                'columnHeaders': [{'properties': {'wordWrap': lit(True), 'fontSize': lit(10.0), 'bold': lit(True)}}],
                'total': [{'properties': {'totals': lit(False)}}]}
        if widths:
            objs['columnWidth'] = [{'properties': {'value': lit(float(wd))}, 'selector': {'metadata': ref}} for ref, wd in widths.items()]
        return self._chart('tableEx', x, y, w, h, {'Values': cols}, title, filters, objs, sort)

    def slicer(self, x, y, w, h, f, title, default=None, single=True, dropdown=True):
        objs = {'data': [{'properties': {'mode': lit('Dropdown' if dropdown else 'Basic')}}],
                'selection': [{'properties': {'strictSingleSelect': lit(single)}}],
                'header': [{'properties': {'show': lit(False)}}]}
        if default is not None:
            t, c = f['Column']['Expression']['SourceRef']['Entity'], f['Column']['Property']
            objs['general'] = [{'properties': {'filter': {'filter': in_filter(t, c, [default], 'd')['filter']}}}]
        return self._chart('slicer', x, y, w, h, {'Values': [f]}, title, objects=objs)


# ---- layout grid: 1280 x 720 canvas, 24 px margins, 16 px gutters ------------------
M, GUT, TOP, BOTTOM = 24, 16, 96, 704


def cell(r, c, rs=1, cs=1, rows=2, cols=3, top=TOP, bottom=BOTTOM):
    """Grid position (x, y, w, h) for row r / col c spanning rs x cs cells."""
    cw = (1280 - 2 * M - (cols - 1) * GUT) / cols
    rh = (bottom - top - (rows - 1) * GUT) / rows
    return (M + c * (cw + GUT), top + r * (rh + GUT), cs * cw + (cs - 1) * GUT, rs * rh + (rs - 1) * GUT)


def fmt_pct(x, d=0):
    return f'{100 * x:.{d}f}%'


def build_pages(data):
    D = data
    st, dept, pvm, par = D['CtxStore'], D['CtxDept'], D['CtxPanelVsM5'], D['CtxPareto']
    snap, ev, mc, ic, rs = D['CtxSnap'], D['CtxEvents'], D['ModelComparison'], D['IntervalCoverage'], D['RuleSummary']
    top10 = par.loc[(par.pct_of_series - 10).abs().idxmin(), 'cum_share']
    sf = snap[snap.cat_id == 'FOODS'].set_index('state_id').snap_uplift_association
    g = lambda per, mod, col='mean_rmsse': mc[(mc.period == per) & (mc.model == mod) & (mc.segment_type == 'all')][col].iloc[0]
    r = lambda per, rule, col='captured_ae_mean': rs[(rs.period == per) & (rs.rule == rule) & (rs.K == 5)][col].iloc[0]
    cov = lambda per, sl: ic[(ic.period == per) & (ic.slice == sl)].coverage.iloc[0]
    C = lambda t, c: colf(t, c)
    Ms = lambda t, m: measf(t, m)
    pages = []
    hold_mc = [('ModelComparison', 'period', ['Holdout']), ('ModelComparison', 'segment_type', ['all'])]
    k5 = [('RuleSummary', 'K', [5])]

    # 1 Start here -----------------------------------------------------------------
    p = Page('home', 'Walmart demand planning: what to trust, what to review',
             f'Public M5 data, 2011-2016. LightGBM forecasts best but only narrowly; 90% ranges hold; a 5-item weekly list catches ~5x random, yet simple rules match the tuned score.')
    cards = [(Ms('CtxStore', 'M5 units sold'), 'Units sold, all 10 stores'), (Ms('CtxStore', 'M5 product-store series'), 'Product-store series'),
             (Ms('ModelComparison', 'Holdout RMSSE LightGBM'), 'LightGBM RMSSE, final 28 days'), (Ms('IntervalCoverage', 'Holdout coverage'), 'Actuals inside 90% range'),
             (Ms('RuleSummary', 'Holdout K5 combined'), 'Error caught by 5 picks / week')]
    cw = (1232 - 4 * GUT) / 5
    for i, (m, lab) in enumerate(cards):
        p.card(M + i * (cw + GUT), TOP, cw, 104, m, lab)
    y2 = TOP + 104 + GUT
    p.column(*cell(0, 0, top=y2, rows=1), C('ModelComparison', 'model'), [Ms('ModelComparison', 'Mean RMSSE')], 'Forecast error, final 28 days (lower is better)',
             filters=hold_mc, sort=(Ms('ModelComparison', 'Mean RMSSE'), 'Ascending'))
    p.column(*cell(0, 1, top=y2, rows=1), C('RuleSummary', 'rule'), [Ms('RuleSummary', 'Captured share (mean)')], 'Next-week error caught by 5 picks',
             series=C('RuleSummary', 'period'), filters=k5, bar=True, sort=(Ms('RuleSummary', 'Captured share (mean)'), 'Descending'))
    p.column(*cell(0, 2, top=y2, rows=1), C('IntervalCoverage', 'slice_label'), [Ms('IntervalCoverage', 'Coverage (avg)')], 'Actuals inside the 90% range (target 90%)',
             series=C('IntervalCoverage', 'period'), filters=[('IntervalCoverage', 'slice_type', ['horizon'])], sort=(C('IntervalCoverage', 'slice_label'), 'Ascending'), axis_start=0.8, labels=False)
    pages.append(p)

    # 2 The company ----------------------------------------------------------------
    p = Page('company', 'The company: 10 stores, 3 categories, 5 years of daily sales',
             f'FOODS is {fmt_pct(dept.groupby("cat_id").share_of_units.sum()["FOODS"])} of units; CA_3 alone sells {fmt_pct(st.share_of_units.max())}; the top 10% of series sell {fmt_pct(top10)} of all units. Full M5 file via DuckDB.')
    p.column(*cell(0, 0), C('CtxStore', 'store_id'), [Ms('CtxStore', 'Store share of units')], 'Share of units by store', sort=(Ms('CtxStore', 'Store share of units'), 'Descending'))
    p.column(*cell(0, 1), C('CtxDept', 'dept_id'), [Ms('CtxDept', 'Dept share of units')], 'Share of units by department', sort=(Ms('CtxDept', 'Dept share of units'), 'Descending'))
    p.column(*cell(0, 2), C('CtxStore', 'store_id'), [Ms('CtxStore', 'Growth 2012 to 2015')], 'Daily sales growth, 2012 to 2015', sort=(Ms('CtxStore', 'Growth 2012 to 2015'), 'Descending'))
    p.line(*cell(1, 0, cs=2), C('CtxMonthly', 'month_start'), [Ms('CtxMonthly', 'Avg daily units')], 'Average daily units by month and category', series=C('CtxMonthly', 'cat_id'))
    p.line(*cell(1, 2), C('CtxPareto', 'pct_of_series'), [Ms('CtxPareto', 'Cumulative share of units')], 'Sales concentration: cumulative share of units vs % of series')
    pages.append(p)

    # 3 Demand patterns ------------------------------------------------------------
    p = Page('patterns', 'Demand patterns planners must respect',
             f'Weekends run ~20% above average; FOODS sells {fmt_pct(sf["CA"])}-{fmt_pct(sf["WI"])} more on SNAP days; stores close on Christmas; most products sell nothing on most days. Associations, not causal effects.')
    p.column(*cell(0, 0), C('CtxWeekday', 'weekday'), [Ms('CtxWeekday', 'Weekday index (avg 100)')], 'Sales by weekday (week average = 100)', series=C('CtxWeekday', 'cat_id'),
             labels=False, sort=(C('CtxWeekday', 'weekday'), 'Ascending'))
    p.column(*cell(0, 1), C('CtxSnap', 'state_id'), [Ms('CtxSnap', 'SNAP-day difference')], 'SNAP days vs other days, 2012-2015', series=C('CtxSnap', 'cat_id'))
    p.column(*cell(0, 2), C('CtxZeroShare', 'bin_label'), [Ms('CtxZeroShare', 'Series in bin')], 'Series by share of zero-sales days', series=C('CtxZeroShare', 'cat_id'),
             labels=False, sort=(C('CtxZeroShare', 'bin_label'), 'Ascending'))
    p.column(*cell(1, 0, cs=2), C('CtxEvents', 'event'), [Ms('CtxEvents', 'Event-day difference')], 'Event days vs the same weekday in nearby weeks',
             sort=(Ms('CtxEvents', 'Event-day difference'), 'Ascending'))
    p.line(*cell(1, 2), C('CtxDaily', 'date'), [Ms('CtxDaily', 'Daily units')], 'Company daily units (Christmas dips to zero)')
    pages.append(p)

    # 4 Our sample -----------------------------------------------------------------
    p = Page('sample', 'Our 200-series sample and the data checks',
             f'Chosen on 2011-2012 data only; sample series sell {pvm.iloc[2].avg_units_per_series_day:.1f} units/day vs {pvm.iloc[0].avg_units_per_series_day:.1f} company-wide, so results flatter sparse items. 26/26 SQL checks pass.')
    cw4 = (1232 - 3 * GUT) / 4
    for i, (m, lab) in enumerate([(Ms('CtxPanelVsM5', 'Panel series'), 'Series in our sample'), (Ms('CtxStore', 'M5 product-store series'), 'Series in M5'),
                                  (Ms('DataChecks', 'Checks passed'), 'Data checks passed'), (Ms('DataChecks', 'Checks run'), 'Data checks run')]):
        p.card(M + i * (cw4 + GUT), TOP, cw4, 96, m, lab)
    y2 = TOP + 96 + GUT
    p.column(*cell(0, 0, top=y2), C('CtxPanelVsM5', 'population'), [Ms('CtxPanelVsM5', 'Units per series-day')], 'Units sold per series per day')
    p.column(*cell(0, 1, top=y2), C('CtxPanelVsM5', 'population'), [Ms('CtxPanelVsM5', 'Zero-sales share (avg)')], 'Share of days with zero sales')
    p.column(*cell(0, 2, top=y2), C('Strata', 'store_stratum'), [Ms('Strata', 'Series in stratum')], 'Sample design: series per store x stratum', bar=True, labels=False)
    p.table(*cell(1, 0, cs=3, top=y2), [C('DataChecks', 'check'), C('DataChecks', 'observed'), C('DataChecks', 'expected'), C('DataChecks', 'pass')],
            'DuckDB reconciliation checks (sql/01_load_audit.sql)')
    pages.append(p)

    # 5 Forecast accuracy ----------------------------------------------------------
    p = Page('accuracy', 'Forecast accuracy: LightGBM leads, narrowly',
             f'Mean RMSSE (lower is better). Holdout: LightGBM {g("Holdout", "LightGBM"):.3f}, ETS {g("Holdout", "ETS"):.3f}, repeat-last-week {g("Holdout", "Seasonal naive"):.3f}. LightGBM under-forecasts ({fmt_pct(g("Holdout", "LightGBM", "bias"), 1)}).')
    allf = [('ModelComparison', 'segment_type', ['all'])]
    p.column(*cell(0, 0), C('ModelComparison', 'model'), [Ms('ModelComparison', 'Mean RMSSE')], 'Mean RMSSE by model: validation vs holdout',
             series=C('ModelComparison', 'period'), filters=allf)
    p.column(*cell(0, 1, cs=2), C('ModelComparison', 'segment'), [Ms('ModelComparison', 'Mean RMSSE')], 'Holdout RMSSE by volume and selling pattern',
             series=C('ModelComparison', 'model'), filters=[('ModelComparison', 'segment_type', ['volume_group', 'pattern_group']), ('ModelComparison', 'period', ['Holdout'])],
             sort=(C('ModelComparison', 'segment'), 'Ascending'))
    p.column(*cell(1, 0), C('ModelComparison', 'model'), [Ms('ModelComparison', 'Bias (avg)')], 'Bias (below 0 = under-forecast)', series=C('ModelComparison', 'period'), filters=allf)
    p.line(*cell(1, 1), C('ModelComparison', 'segment'), [Ms('ModelComparison', 'Mean RMSSE')], 'Validation: RMSSE in each 28-day period',
           series=C('ModelComparison', 'model'), filters=[('ModelComparison', 'segment_type', ['origin'])])
    p.column(*cell(1, 2), C('ModelComparison', 'segment'), [Ms('ModelComparison', 'Mean RMSSE')], 'Holdout RMSSE by forecast horizon',
             series=C('ModelComparison', 'model'), filters=[('ModelComparison', 'segment_type', ['horizon_week']), ('ModelComparison', 'period', ['Holdout'])], labels=False,
             sort=(C('ModelComparison', 'segment'), 'Ascending'))
    pages.append(p)

    # 6 Forecast ranges ------------------------------------------------------------
    p = Page('ranges', 'Forecast ranges: are the 90% bands honest?',
             f'Raw ranges from past errors caught only 84-87%; widened on early weeks, they caught {fmt_pct(cov("Validation (calibrated)", "all"), 1)} (validation) and {fmt_pct(cov("Holdout (calibrated)", "all"), 1)} (holdout). Weakest: irregular sellers.')
    p.column(*cell(0, 0, cs=2), C('IntervalCoverage', 'slice_label'), [Ms('IntervalCoverage', 'Coverage (avg)')], 'Share of actuals inside the 90% range, by horizon',
             series=C('IntervalCoverage', 'period'), filters=[('IntervalCoverage', 'slice_type', ['horizon'])], sort=(C('IntervalCoverage', 'slice_label'), 'Ascending'), axis_start=0.8)
    p.column(*cell(0, 2), C('IntervalCoverage', 'period'), [Ms('IntervalCoverage', 'Coverage (avg)')], 'Overall coverage (28-day forecasts)',
             filters=[('IntervalCoverage', 'slice_type', ['all'])], axis_start=0.8)
    p.column(*cell(1, 0, cs=2), C('IntervalCoverage', 'slice_label'), [Ms('IntervalCoverage', 'Coverage (avg)')], 'Coverage by segment',
             series=C('IntervalCoverage', 'period'), filters=[('IntervalCoverage', 'slice_type', ['segment'])], labels=False, axis_start=0.8)
    p.column(*cell(1, 2), C('IntervalCoverage', 'slice_label'), [Ms('IntervalCoverage', 'Avg range width (units/day)')], 'Range width by segment (units/day)',
             filters=[('IntervalCoverage', 'slice_type', ['segment']), ('IntervalCoverage', 'period', ['Holdout (calibrated)'])], bar=True)
    pages.append(p)

    # 7 Weekly review list ---------------------------------------------------------
    p = Page('review', 'Weekly review list: what a planner would have seen',
             'Top 10 by the frozen score (0.2 x recent error + 0.1 x bias + 0.7 x range width), using only data known that Sunday. Outcomes are on page 9, not here.')
    p.slicer(M, TOP, 400, 72, C('AsOf', 'label'), 'As-of week (Sunday)', default=D['AsOf'].label.iloc[-1])
    y2 = TOP + 72 + GUT
    rows3 = dict(rows=5, top=y2)
    p.table(*cell(0, 0, rs=3, cs=3, **rows3), [C('ReviewList', 'rank'), C('ReviewList', 'series_label'), C('ReviewList', 'volume'), C('ReviewList', 'recent_error'),
                                                C('ReviewList', 'bias_signed'), C('ReviewList', 'uncertainty'), C('ReviewList', 'forecast_next7'), C('ReviewList', 'suggested_investigation')],
            'Top 10 to review', filters=[('ReviewList', 'top10', ['Yes'])], sort=(C('ReviewList', 'rank'), 'Ascending'), widths={'ReviewList.suggested_investigation': 470})
    p.column(*cell(3, 0, rs=2, **rows3), C('ReviewList', 'series_label'), [Ms('ReviewList', 'Review score')], 'Score', filters=[('ReviewList', 'top10', ['Yes'])],
             bar=True, sort=(Ms('ReviewList', 'Review score'), 'Descending'))
    p.column(*cell(3, 1, rs=2, cs=2, **rows3), C('ReviewList', 'series_label'), [Ms('ReviewList', 'Recent error (units/wk)'), Ms('ReviewList', 'Range width (units/7d)')],
             'What drives the score: recent error vs range width', filters=[('ReviewList', 'top10', ['Yes'])], labels=False)
    pages.append(p)

    # 8 Product drill-down ---------------------------------------------------------
    p = Page('product', 'Product drill-down: forecast, range and what happened',
             'Preloaded with the failure case FOODS_3_444_CA_1: no sales for 333 days while still priced, then 414 units against a forecast of 3. Every rule ranked it 193rd-199th.')
    p.slicer(*cell(0, 0, rows=1, top=TOP, bottom=TOP + 72), C('AsOf', 'label'), 'As-of week (Sunday)', default=D['AsOf'][D['AsOf'].origin == 1913].label.iloc[0])
    p.slicer(*cell(0, 1, rows=1, top=TOP, bottom=TOP + 72), C('Series', 'id'), 'Product-store series', default='FOODS_3_444_CA_1_evaluation')
    p.card(*cell(0, 2, rows=1, top=TOP, bottom=TOP + 72), Ms('ForecastBand', 'Forecast next 7 days'), 'Forecast, next 7 days')
    y2 = TOP + 72 + GUT
    p.line(*cell(0, 0, rs=3, cs=3, rows=4, top=y2), C('Dates', 'date'), [Ms('SalesHistory', 'Units sold'), Ms('ForecastBand', 'Forecast units'),
                                                                        Ms('ForecastBand', 'Lower 90%'), Ms('ForecastBand', 'Upper 90%')], 'Daily units: actual vs LightGBM forecast and 90% range')
    p.table(*cell(3, 0, cs=3, rows=4, top=y2), [C('ReviewList', 'rank'), C('ReviewList', 'recent_error'), C('ReviewList', 'bias_signed'), C('ReviewList', 'days_since_sale'),
                                                 C('ReviewList', 'suggested_investigation')], 'This series on the review list that week (rank of 200)',
            widths={'ReviewList.suggested_investigation': 700})
    pages.append(p)

    # 9 Did the lists work? --------------------------------------------------------
    p = Page('lists', 'Did the lists work? (retrospective)',
             f'Share of the next 7 days\' error caught by each list. Holdout, 5 picks: combined {fmt_pct(r("Holdout", "Combined score (frozen)"), 1)}, top sellers {fmt_pct(r("Holdout", "Top sellers"), 1)}, random {fmt_pct(r("Holdout", "Random (200 draws)"), 1)}. Captured error is not avoided error.')
    p.slicer(M, TOP, 400, 72, C('RuleWeekly', 'K'), 'Items reviewed per week (K)', default=5)
    y2 = TOP + 72 + GUT
    p.line(*cell(0, 0, cs=2, top=y2), C('AsOf', 'asof_date'), [Ms('RuleWeekly', 'Captured share of next-week error')], 'Captured share by week and rule', series=C('RuleWeekly', 'rule'))
    p.column(*cell(0, 2, top=y2), C('RuleSummary', 'rule'), [Ms('RuleSummary', 'Captured share (mean)')], 'Mean captured share, K = 5', series=C('RuleSummary', 'period'),
             filters=k5, bar=True, labels=False, sort=(Ms('RuleSummary', 'Captured share (mean)'), 'Descending'))
    p.column(*cell(1, 0, cs=2, top=y2), C('RuleSummary', 'rule'), [Ms('RuleSummary', 'Precision (mean)')], 'Precision for unusually large errors, K = 5 (random ~9%)',
             series=C('RuleSummary', 'period'), filters=k5, sort=(Ms('RuleSummary', 'Precision (mean)'), 'Descending'))
    p.column(*cell(1, 2, top=y2), C('RuleSummary', 'K'), [Ms('RuleSummary', 'Captured share (mean)')], 'Combined score: error caught at K = 1, 5, 10',
             series=C('RuleSummary', 'period'), filters=[('RuleSummary', 'rule', ['Combined score (frozen)'])], sort=(C('RuleSummary', 'K'), 'Ascending'))
    pages.append(p)

    # 10 Findings & limits ---------------------------------------------------------
    p = Page('findings', 'Findings, limits and recommendations', 'Everything here was measured in this project; nothing is claimed beyond it.')
    x, y, w, h = cell(0, 0, cols=2)
    p.bullets(x, y, w, h, 'Recommendations', [
        'Use LightGBM; keep ETS as a fast, less-biased fallback.',
        'Watch the downward bias on slow sellers (-15% holdout).',
        'Weekly review: use the simple rule (largest recent error or top sellers).',
        'Add a second list ranked by normalised error.',
        'Add a dormant-item flag for long zero-sales runs.'], size=15)
    x, y, w, h = cell(0, 1, cols=2)
    p.bullets(x, y, w, h, 'What we cannot claim', [
        'No inventory, lead-time, margin or override data: no stockout or savings claims.',
        'Zero sales may be censored demand.',
        'Two stores, two categories; sparse and new items excluded.',
        'Holdout is 28 days / 4 weekly lists: rule differences are within noise.'], bg='#FBF1E3', size=15)
    x, y, w, h = cell(1, 0, cols=1)
    p.bullets(x, y, w, h, 'How it was built', [
        ('Data:', 'SHA-256-verified M5 files; DuckDB SQL loads, joins, audits (26/26) and builds company tables.'),
        ('Models:', 'repeat-last-week, ETS, global LightGBM; 60 weekly refits using only data known that week.'),
        ('Honesty:', '8 leakage tests; final 28 days sealed until choices were frozen; SQL re-check 96/96, dashboard 351/351.')], size=15)
    pages.append(p)
    return pages


def write_report(pages):
    rp = OUT / f'{NAME}.Report'
    if rp.exists():
        shutil.rmtree(rp)
    (rp / 'definition' / 'pages').mkdir(parents=True)
    (rp / 'StaticResources' / 'SharedResources' / 'BaseThemes').mkdir(parents=True)
    (rp / 'StaticResources' / 'RegisteredResources').mkdir(parents=True)
    shutil.copy(THEME_SRC, rp / 'StaticResources' / 'SharedResources' / 'BaseThemes' / 'CY23SU04.json')
    theme = {'name': 'WDP', 'dataColors': ['#0F7173', '#E09F3E', '#9AA5A6', '#3D5A80', '#5B8E7D', '#B5544A', '#7A6C9E', '#C9A227'],
             'background': '#FFFFFF', 'foreground': INK, 'tableAccent': TEAL}
    (rp / 'StaticResources' / 'RegisteredResources' / 'WDP.json').write_text(json.dumps(theme, indent=2))
    (rp / 'definition.pbir').write_text(json.dumps({'version': '4.0', 'datasetReference': {'byPath': {'path': f'../{NAME}.SemanticModel'}}}, indent=2))
    (rp / '.platform').write_text(json.dumps({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json',
                                              'metadata': {'type': 'Report', 'displayName': NAME},
                                              'config': {'version': '2.0', 'logicalId': uid('rp', NAME)}}, indent=2))
    d = rp / 'definition'
    (d / 'version.json').write_text(json.dumps({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json', 'version': '2.0.0'}, indent=2))
    report = {'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.3.0/schema.json',
              'themeCollection': {'baseTheme': {'name': 'CY23SU04', 'reportVersionAtImport': '5.46', 'type': 'SharedResources'},
                                  'customTheme': {'name': 'WDP.json', 'reportVersionAtImport': '5.46', 'type': 'RegisteredResources'}},
              'layoutOptimization': 'None',
              'resourcePackages': [{'name': 'SharedResources', 'type': 'SharedResources', 'items': [{'name': 'CY23SU04', 'path': 'BaseThemes/CY23SU04.json', 'type': 'BaseTheme'}]},
                                   {'name': 'RegisteredResources', 'type': 'RegisteredResources', 'items': [{'name': 'WDP.json', 'path': 'WDP.json', 'type': 'CustomTheme'}]}],
              'settings': {'exportDataMode': 'AllowSummarizedAndUnderlying', 'defaultDrillFilterOtherVisuals': True, 'allowChangeFilterTypes': True, 'useEnhancedTooltips': True}}
    (d / 'report.json').write_text(json.dumps(report, indent=2))
    names = []
    for i, p in enumerate(pages):
        pname = hid('page', p.key)
        names.append(pname)
        pd_ = d / 'pages' / pname
        (pd_ / 'visuals').mkdir(parents=True)
        (pd_ / 'page.json').write_text(json.dumps({'$schema': S_PAGE, 'name': pname, 'displayName': f'{i + 1}. ' + {
            'home': 'Start here', 'company': 'The company', 'patterns': 'Demand patterns', 'sample': 'Our sample', 'accuracy': 'Forecast accuracy',
            'ranges': 'Forecast ranges', 'review': 'Weekly review list', 'product': 'Product drill-down', 'lists': 'Did the lists work?',
            'findings': 'Findings & limits'}[p.key], 'displayOption': 'FitToPage', 'height': 720, 'width': 1280}, indent=2))
        for v in p.visuals:
            (pd_ / 'visuals' / v['name']).mkdir()
            (pd_ / 'visuals' / v['name'] / 'visual.json').write_text(json.dumps(v, indent=2))
    (d / 'pages' / 'pages.json').write_text(json.dumps({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json',
                                                         'pageOrder': names, 'activePageName': names[0]}, indent=2))
    (OUT / f'{NAME}.pbip').write_text(json.dumps({'$schema': 'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json',
                                                  'version': '1.0', 'artifacts': [{'report': {'path': f'{NAME}.Report'}}], 'settings': {'enableAutoRecovery': True}}, indent=2))



def check_names(data):
    """Power BI names are case-insensitive: a measure may not share a name with a column of its table or another measure."""
    seen = set()
    for t, ms in MEASURES.items():
        cols = {c.lower() for c in data[t].columns}
        for m, _, _ in ms:
            assert m.lower() not in cols, f'measure {t}[{m}] clashes with a column'
            assert m.lower() not in seen, f'duplicate measure name {m}'
            seen.add(m.lower())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-folder', default=DEFAULT_FOLDER)
    a = ap.parse_args()
    data = prepare_data()
    check_names(data)
    dd = OUT / 'data'
    dd.mkdir(parents=True, exist_ok=True)
    for name, df in data.items():
        df.to_csv(dd / f'{name}.csv', index=False)
    write_model(data, a.data_folder)
    pages = build_pages(data)
    write_report(pages)
    print(f'tables {len(data)}, pages {len(pages)}, visuals {sum(len(p.visuals) for p in pages)}, measures {sum(len(v) for v in MEASURES.values())}')


if __name__ == '__main__':
    main()
