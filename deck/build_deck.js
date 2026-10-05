// Builds deck/Walmart_Demand_Planning_Project_Review.pptx from results recorded in PROGRESS.md / results/.
// Run: node deck/build_deck.js   (numbers below are copied from the saved result files)
const pptxgen = require('pptxgenjs');
const { applyTheme } = require('/root/.claude/skills/synced/ae791bd4-a8f8-4ee9-b7a2-f41d069e4761_73d734db-5afa-463a-85f5-9178ee5f05a1/pptx/scripts/apply_theme.js');

const THEME = {
  name: 'Demand Review',
  headFontFace: 'Cambria',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '1B2A2F', lt1: 'FFFFFF', dk2: '0E3B43', lt2: 'EEF3F3',
    accent1: '0F7173', accent2: 'E09F3E', accent3: '9AA5A6', accent4: '5B8E7D',
    accent5: 'B5544A', accent6: '3D5A80', hlink: '0F7173', folHlink: '3D5A80',
  },
};
const HEX = { teal: '0F7173', amber: 'E09F3E', gray: '9AA5A6', sage: '5B8E7D', red: 'B5544A', navy: '3D5A80',
  ink: '1B2A2F', dark: '0E3B43', light: 'EEF3F3', grid: 'D5DEDE', muted: '5E6B6E' };

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.333 x 7.5
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = 'Walmart Demand Planning: Project Review';
pres.author = 'Independent study on public M5 data';
const C = pres.SchemeColor;
const W = 13.333;
const FOOT = 'Independent study on public M5 (Kaggle/Zenodo) data. Not Walmart work; no deployment or savings claimed.';

pres.defineSlideMaster({
  title: 'TITLE_DARK', background: { color: HEX.dark },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.8, y: 2.0, w: 11.7, h: 1.9, fontFace: THEME.headFontFace, fontSize: 40, bold: true, color: C.background1, valign: 'bottom', margin: 0 }, text: '' } },
    { placeholder: { options: { name: 'body', type: 'body', x: 0.8, y: 4.15, w: 11.7, h: 1.6, fontFace: THEME.bodyFontFace, fontSize: 18, color: 'CFE3E3', valign: 'top', margin: 0 }, text: '' } },
  ],
});
pres.defineSlideMaster({
  title: 'SECTION', background: { color: HEX.teal },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.8, y: 2.6, w: 11.7, h: 1.3, fontFace: THEME.headFontFace, fontSize: 40, bold: true, color: C.background1, valign: 'bottom', margin: 0 }, text: '' } },
    { placeholder: { options: { name: 'body', type: 'body', x: 0.8, y: 4.05, w: 11.7, h: 1.2, fontFace: THEME.bodyFontFace, fontSize: 18, color: 'E3F1F1', valign: 'top', margin: 0 }, text: '' } },
  ],
  slideNumber: { x: 12.3, y: 6.95, w: 0.6, h: 0.35, fontSize: 10, color: 'E3F1F1', align: 'right' },
});
pres.defineSlideMaster({
  title: 'CONTENT', background: { color: 'FFFFFF' },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 0.35, w: 12.1, h: 0.85, fontFace: THEME.headFontFace, fontSize: 32, bold: true, color: C.text2, valign: 'middle', margin: 0 }, text: '' } },
    { text: { text: FOOT, options: { x: 0.6, y: 6.98, w: 10.5, h: 0.3, fontSize: 10, color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: 12.3, y: 6.95, w: 0.6, h: 0.35, fontSize: 10, color: HEX.muted, align: 'right' },
});

// ---------- helpers ----------
let sectionName = 'Overview';
function content(title, notes) {
  const s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: sectionName });
  s.addText(title, { placeholder: 'title' });
  if (notes) s.addNotes(notes);
  return s;
}
function section(title, sub, notes) {
  sectionName = title;
  pres.addSection({ title });
  const s = pres.addSlide({ masterName: 'SECTION', sectionTitle: title });
  s.addText(title, { placeholder: 'title' });
  if (sub) s.addText(sub, { placeholder: 'body' });
  if (notes) s.addNotes(notes);
  return s;
}
function txt(s, text, o) {
  s.addText(text, Object.assign({ isTextBox: true, fontFace: THEME.bodyFontFace, fontSize: 15, color: HEX.ink, valign: 'top', margin: 0, paraSpaceAfter: 6 }, o));
}
function bullets(s, items, o) {
  const runs = items.map((t, i) => {
    const base = { bullet: { indent: 16 }, breakLine: i < items.length - 1 };
    if (Array.isArray(t)) return { text: t[0], options: Object.assign({ bold: true }, base, { breakLine: false }) };
    return { text: t, options: base };
  });
  // allow [bold, rest] pairs
  const flat = [];
  items.forEach((t, i) => {
    const last = i === items.length - 1;
    if (Array.isArray(t)) {
      flat.push({ text: t[0], options: { bold: true, bullet: { indent: 16 } } });
      flat.push({ text: ' ' + t[1], options: { breakLine: !last } });
    } else flat.push({ text: t, options: { bullet: { indent: 16 }, breakLine: !last } });
  });
  s.addText(flat, Object.assign({ isTextBox: true, fontFace: THEME.bodyFontFace, fontSize: 15, color: HEX.ink, valign: 'top', margin: 0, paraSpaceAfter: 7 }, o));
}
function card(s, x, y, w, h, head, body, opt = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: opt.fill || HEX.light }, line: { color: opt.fill || HEX.light }, objectName: 'card ' + head });
  s.addText(head, { isTextBox: true, x: x + 0.22, y: y + 0.16, w: w - 0.44, h: 0.42, fontFace: THEME.headFontFace, fontSize: opt.headSize || 17, bold: true, color: opt.headColor || HEX.dark, margin: 0, valign: 'top' });
  if (body) s.addText(body, { isTextBox: true, x: x + 0.22, y: y + 0.62, w: w - 0.44, h: h - 0.75, fontFace: THEME.bodyFontFace, fontSize: opt.size || 14, color: opt.color || HEX.ink, margin: 0, valign: 'top', paraSpaceAfter: 4 });
}
function stat(s, x, y, w, big, label, color) {
  s.addText(big, { isTextBox: true, x, y, w, h: 0.95, fontFace: THEME.headFontFace, fontSize: 44, bold: true, color: color || HEX.teal, margin: 0, valign: 'bottom' });
  s.addText(label, { isTextBox: true, x, y: y + 1.0, w, h: 0.9, fontSize: 14, color: HEX.muted, margin: 0, valign: 'top' });
}
function code(s, x, y, w, h, lines, title) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: '17262A' }, line: { color: '17262A' }, objectName: 'code ' + (title || '') });
  s.addText(lines.join('\n'), { isTextBox: true, x: x + 0.2, y: y + 0.15, w: w - 0.4, h: h - 0.3, fontFace: 'Courier New', fontSize: 12, color: 'D8EBE6', margin: 0, valign: 'top' });
}
function table(s, rows, o) {
  const head = rows[0].map(t => ({ text: t, options: { bold: true, color: 'FFFFFF', fill: { color: HEX.dark } } }));
  const body = rows.slice(1).map((r, i) => r.map(t => ({ text: String(t), options: { fill: { color: i % 2 ? 'FFFFFF' : HEX.light } } })));
  s.addTable([head, ...body], Object.assign({ fontFace: THEME.bodyFontFace, fontSize: 13, color: HEX.ink, border: { type: 'solid', pt: 0.5, color: HEX.grid }, margin: 0.06, valign: 'middle' }, o));
}
const chartBase = (title) => ({
  showTitle: !!title, title, titleFontFace: '+mj-lt', titleFontSize: 14, titleColor: HEX.dark,
  catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
  catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, dataLabelFontFace: '+mn-lt', dataLabelFontSize: 11, dataLabelColor: HEX.ink,
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: 'none' }, legendFontFace: '+mn-lt', legendFontSize: 12, legendColor: HEX.ink,
});

// ================= OVERVIEW =================
pres.addSection({ title: 'Overview' });
let s = pres.addSlide({ masterName: 'TITLE_DARK', sectionTitle: 'Overview' });
s.addText('Walmart Demand Planning: Forecast Reliability and Weekly Review Priorities', { placeholder: 'title' });
s.addText('Project review: methods, SQL and Python work, results, failures and next steps\nIndependent historical study on public M5 data (200 product-store series, 2011-2016)', { placeholder: 'body' });
s.addNotes('This deck walks through the whole project end to end: the business question, the data, how SQL and Python were used, every forecasting and prioritisation method we tested, the results on validation and on the final untouched holdout, what went wrong and how it was fixed, what we did not test, and recommendations. It is an independent study on public data, not work done for Walmart, and no savings or deployment are claimed.');

s = content('The short answer', 'Three headline findings. First, LightGBM is the most accurate of the three forecast methods on the untouched final 28 days, but only slightly better than ETS, and all methods under-forecast in that period. Second, our 90% forecast ranges contained the actual value 89% of the time in the holdout, close to target. Third, any sensible weekly review list captures about five times more forecast error than random picks, but our combined score did not clearly beat the simple rules of checking top sellers or the worst recent forecasts. The practical recommendation is to start with the simple rule.');
stat(s, 0.6, 1.5, 3.9, '0.733', 'LightGBM mean RMSSE on the final 28 days\n(ETS 0.746, "same as last week" 0.932)');
stat(s, 4.75, 1.5, 3.9, '89%', 'of actual daily sales fell inside the 90% forecast range on the final 28 days', HEX.sage);
stat(s, 8.9, 1.5, 3.9, '~5x', 'more next-week error captured by a 5-item review list than by random picks (13.4% vs 2.5%)', HEX.amber);
card(s, 0.6, 4.25, 12.1, 2.35, 'What this means for a planner',
  'LightGBM is the best forecast here, but ETS is close, about 500x faster and less biased, so it is a credible fallback. ' +
  'For the weekly 5-item review list, the combined score (16.4% captured on validation, 13.4% on holdout) was within noise of "check the top sellers" (15.6% / 13.0%) ' +
  'and "check the worst recent forecasts" (16.0% / 12.8%). Recommend the simpler rule. A list that captures error does not prove a planner can fix it.');

s = content('The business question', 'The decision framing comes from PROJECT_SPEC.md. A planner has limited time each week. Two questions: can the forecasts be trusted, and which five product-store series should be looked at first. Five is a workload assumption; we also test capacities of 1 and 10. We only measure where forecast error concentrates; we have no data on whether a planner would correct it.');
card(s, 0.6, 1.5, 5.9, 2.4, '1. Which forecasts are dependable?', 'Compare three forecasting methods on 28-day-ahead daily forecasts. Measure accuracy (RMSSE, WAPE), bias, and how often 90% forecast ranges contain the actual value, overall and by segment.');
card(s, 6.8, 1.5, 5.9, 2.4, '2. Which 5 series to review this week?', 'Rank 200 series every week using only information known that day. Score each list on how much of the next 7 days\' forecast error it captures. Test capacities K = 1, 5 and 10.');
card(s, 0.6, 4.2, 12.1, 2.4, 'What this project does NOT claim', 'No inventory, lead-time, margin or planner override data exists in M5, so no stockout reduction, cash savings or "forecast value added" can be measured. Recorded sales may be censored demand (zero sales does not prove a stockout). The 200-series panel is not Walmart-wide.', { fill: 'FBF1E3' });

s = content('The data: real M5 sales, fixed 200-series panel', 'M5 is the public Walmart dataset from the 2020 Kaggle forecasting competition, downloaded from the Zenodo mirror with checksums verified. The panel was chosen using only the first 730 days, stratified by early sales volume and share of zero-sales days, 100 food and household series in each of two stores. Products with fewer than 100 early units or 100 selling days were excluded, so sparse and newly launched items are not represented. The pilot of 30 series was used first to test the pipeline.');
table(s, [
  ['Item', 'Value'],
  ['Source', 'M5 (Kaggle 2020) via Zenodo record 10203108; SHA-256 verified'],
  ['History', '1,941 days: 29 Jan 2011 to 22 May 2016'],
  ['Panel', '200 series: CA_1 x 100, TX_1 x 100; FOODS 102, HOUSEHOLD 98'],
  ['Pilot', '30 series (15 per store) used first'],
  ['Rows / units', '388,200 series-days; 865,515 units sold'],
  ['Selection rule', 'First 730 days only; >=100 units and >=100 selling days; 20 strata'],
  ['Missing prices', '22,253 days, all before the item was first priced; kept missing'],
  ['Zero-sales days', '50% of all series-days (includes pre-launch)'],
], { x: 0.6, y: 1.5, w: 7.6, colW: [2.0, 5.6] });
card(s, 8.6, 1.5, 4.1, 5.1, 'Representativeness limits', 'Two stores in two states.\n\nOnly FOODS and HOUSEHOLD (no HOBBIES).\n\nSparse and new products excluded by design.\n\nAnonymised items; no store context.\n\nResults describe this panel, not Walmart.', { fill: 'FBF1E3' });


s = content('The company: where the sales are', 'Built in DuckDB from the full raw M5 sales file: 59 million series-days. Food is two-thirds of units, and one department, FOODS_3, is half of everything. Sales are very concentrated: the top 10% of product-store series sell 55% of units. Most products are intermittent: a typical series sells nothing on 60% of days after launch, which is why percentage-error metrics like MAPE break down.');
stat(s, 0.6, 1.45, 2.9, '66.9M', 'units sold across 30,490 product-store series in 10 stores, 2011-2016');
stat(s, 0.6, 3.35, 2.9, '55%', 'of units come from the top 10% of series (top 20%: 70%)', HEX.amber);
stat(s, 0.6, 5.25, 2.9, '60%', 'of days with zero sales for a typical series after launch', HEX.sage);
s.addChart(pres.charts.BAR, [{ name: 'Share of units', labels: ['FOODS_3', 'HOUSEHOLD_1', 'FOODS_2', 'HOBBIES_1', 'FOODS_1', 'HOUSEHOLD_2', 'HOBBIES_2'], values: [0.492, 0.175, 0.116, 0.085, 0.078, 0.045, 0.008] }],
  Object.assign(chartBase('Share of all units by department'), { x: 3.8, y: 1.45, w: 4.4, h: 5.3, barDir: 'bar', chartColors: [HEX.teal], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0%', valAxisMinVal: 0, valAxisMaxVal: 0.6, valAxisLabelFormatCode: '0%', showLegend: false, catAxisOrientation: 'maxMin' }));
s.addChart(pres.charts.BAR, [{ name: 'Share of units', labels: ['CA_3', 'CA_1', 'TX_2', 'WI_2', 'WI_3', 'TX_3', 'CA_2', 'TX_1', 'WI_1', 'CA_4'], values: [0.170, 0.117, 0.110, 0.100, 0.098, 0.093, 0.087, 0.085, 0.079, 0.062] }],
  Object.assign(chartBase('Share of all units by store'), { x: 8.4, y: 1.45, w: 4.3, h: 5.3, barDir: 'bar', chartColors: [HEX.amber], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0%', valAxisMinVal: 0, valAxisMaxVal: 0.2, valAxisLabelFormatCode: '0%', showLegend: false, catAxisOrientation: 'maxMin' }));

s = content('Demand patterns a forecast must respect', 'Also from the full M5 file. Weekends run about 20% above the weekly average. On SNAP food-assistance payment days, FOODS sells more, most of all in Wisconsin; household goods barely move. That is an association, not a measured causal effect. Christmas is effectively a closed day. These patterns are why the models use weekday, SNAP and event features of the forecast day, which are known in advance.');
s.addChart(pres.charts.BAR, [
  { name: 'FOODS', labels: ['CA', 'TX', 'WI'], values: [0.105, 0.155, 0.308] },
  { name: 'HOUSEHOLD', labels: ['CA', 'TX', 'WI'], values: [0.036, 0.033, 0.036] },
  { name: 'HOBBIES', labels: ['CA', 'TX', 'WI'], values: [0.027, 0.017, 0.017] },
], Object.assign(chartBase('Sales on SNAP days vs other days, 2012-2015'), { x: 0.6, y: 1.45, w: 6.0, h: 5.3, barDir: 'col', barGrouping: 'clustered', chartColors: [HEX.teal, HEX.amber, HEX.gray], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '+0%', valAxisMinVal: 0, valAxisMaxVal: 0.35, valAxisLabelFormatCode: '0%', showLegend: true, legendPos: 'b' }));
card(s, 6.9, 1.45, 5.8, 1.6, 'Weekly rhythm', 'Saturday and Sunday run about 120-123 vs a mid-week trough near 86-89 (week average = 100).');
card(s, 6.9, 3.3, 5.8, 1.6, 'Holidays', 'Christmas -100% (stores closed); Thanksgiving -28%; Labor Day +26% vs the same weekday in nearby weeks.');
card(s, 6.9, 5.15, 5.8, 1.6, 'Our sample vs the company', 'Sample series sell 2.4 units/day vs 1.4 company-wide and have fewer zero days: results flatter sparse items.', { fill: 'FBF1E3' });

// ================= HOW IT WAS BUILT =================
section('How the project was built', 'Pipeline, tools, SQL and the rules that keep the test honest',
  'This section explains the pipeline from raw files to results, what SQL and Python each did, and the time rules that prevent the forecasts from seeing the future.');

s = content('Pipeline: from raw files to results', 'Each box is a script in the repository. Data preparation was supplied and re-verified. DuckDB SQL builds and audits the model input and later recomputes metrics independently. Python does the forecasting and the priority experiment. Every stage writes results to files and a PROGRESS.md entry.');
const steps = [
  ['Raw M5 files', 'checksums verified\n(scripts/download_data.py)'],
  ['Prepare panel', 'fixed 200 series\n(prepare_data.py)'],
  ['DuckDB SQL', 'load, join, 26 audit checks\n(sql/01_load_audit.sql)'],
  ['Python models', 'naive, ETS, LightGBM\nweekly backtest'],
  ['Evaluate', 'metrics, ranges,\npriority lists, holdout'],
  ['SQL reconcile', 'recompute metrics\n(sql/02_analytics.sql)'],
];
steps.forEach((st, i) => {
  const x = 0.6 + i * 2.07;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.9, w: 1.8, h: 1.9, rectRadius: 0.1, fill: { color: i === 2 || i === 5 ? HEX.amber : HEX.teal }, line: { color: 'FFFFFF' }, objectName: 'step ' + st[0] });
  s.addText(st[0], { isTextBox: true, x: x + 0.1, y: 2.0, w: 1.6, h: 0.6, fontFace: THEME.headFontFace, fontSize: 15, bold: true, color: 'FFFFFF', align: 'center', margin: 0, valign: 'middle' });
  s.addText(st[1], { isTextBox: true, x: x + 0.1, y: 2.65, w: 1.6, h: 1.05, fontSize: 12, color: 'FFFFFF', align: 'center', margin: 0, valign: 'top' });
  if (i < steps.length - 1) s.addShape(pres.shapes.RIGHT_TRIANGLE, { x: x + 1.84, y: 2.72, w: 0.2, h: 0.25, rot: 90, fill: { color: HEX.gray }, line: { color: HEX.gray }, objectName: 'arrow ' + i });
});
card(s, 0.6, 4.3, 3.9, 2.3, 'Checkpoint 1-2', 'Data audit, environment, SQL tables. 30-series pilot and 8 automated leakage / metric tests.');
card(s, 4.7, 4.3, 3.9, 2.3, 'Checkpoint 3-4', 'Tuning, 60-origin weekly backtest, model comparison, interval calibration, priority experiment, freeze, one-time holdout.');
card(s, 8.8, 4.3, 3.9, 2.3, 'Checkpoint 5', 'Company context in SQL, Power BI project (10 pages), 2-page memo, interview walkthrough, README, version locks.');

s = content('Step by step: every command we ran, in order', 'This is the actual run log. Steps 1 to 8 and 10 to 12 ran in the Claude workspace (DuckDB command-line program, Python 3.13, LightGBM 4.6.0). Step 9 ran on your laptop. Step 10 first crashed on your laptop, was fixed, then rerun. The backtest in step 7 is the only slow step, about 27 minutes for 60 weekly LightGBM refits; its results are saved so it never needs rerunning.');
table(s, [
  ['#', 'Command (from the project folder)', 'What it did', 'Result'],
  ['1', 'sha256sum data/raw/*.csv', 'Verify raw downloads', '3 / 3 match manifest'],
  ['2', 'python scripts/run_sql.py sql/01_load_audit.sql --scope pilot | panel', 'Load, join, audit; export model input', 'Tables + model_input'],
  ['3', 'python scripts/checkpoint1_verify.py', 'Compare SQL audit to supplied audit', '26 / 26 checks pass'],
  ['4', 'python tests/test_temporal.py', 'Leakage and metric tests', '8 / 8 pass'],
  ['5', 'python scripts/checkpoint2_pilot.py', '30-series pilot, 3 origins', 'ETS 0.630, LGBM 0.633, naive 0.821'],
  ['6', 'python scripts/checkpoint3_tune.py', '3 LightGBM settings, tuning origins', 'Tweedie 63 leaves chosen'],
  ['7', 'python scripts/checkpoint3_backtest.py', '60 weekly origins x 3 models', '0 failures, ~27 min'],
  ['8', 'python scripts/checkpoint3_evaluate.py', 'Model comparison + ranges', 'LightGBM chosen; 90.9% coverage'],
  ['9', 'python scripts/checkpoint4_priority.py', 'Ranking rules; freeze choices', 'frozen_choices.json (your laptop)'],
  ['10', 'python scripts/checkpoint4_holdout.py', 'One-time final 28-day test', 'Crashed, fixed, rerun'],
  ['11', 'python scripts/run_sql.py sql/02_analytics.sql --scope panel', 'Recompute metrics in SQL', 'SQL tables written'],
  ['12', 'python scripts/reconcile.py', 'SQL vs Python comparison', '96 rows, 0 mismatches'],
  ['13', 'python scripts/run_sql.py sql/03_business_context.sql', 'Company tables from full raw file', '59.2M series-days'],
  ['14', 'python scripts/build_dashboard_data.py', 'Dashboard tables + re-check', '351 / 351 match'],
  ['15', 'python powerbi/build_pbip.py', 'Generate Power BI project', '10 pages, 0 schema errors'],
], { x: 0.6, y: 1.35, w: 12.1, colW: [0.45, 5.6, 3.25, 2.8], fontSize: 11 });

s = content('Toolkit: what each tool was actually used for', 'Honest inventory of the environment. The Claude workspace could not reach the Python package index, so LightGBM came from its official GitHub release and DuckDB ran as its official command-line program. statsmodels could not be installed, so ETS was written by hand in numpy and checked with a toy test. scipy and scikit-learn are listed in requirements.txt but the final code never imports them, so they can be removed. Your laptop ran the priority step with duckdb 1.5.6 and its own pandas 2.x.');
table(s, [
  ['Tool', 'Used for', 'Status'],
  ['DuckDB (SQL)', 'Load prepared files, joins, key/total audits, model input export, independent metric recomputation', 'CLI 1.4.1 here; Python duckdb 1.5.6 on your laptop'],
  ['pandas', 'Tables, group-by metrics, merges, result files', 'Used everywhere'],
  ['numpy', 'Sales arrays, features, hand-written ETS, scoring', 'Used everywhere'],
  ['LightGBM', 'Global direct-horizon forecasting model', '4.6.0, official wheel'],
  ['statsmodels', 'Planned for ETS', 'Not installable here: ETS written in numpy'],
  ['scipy, scikit-learn', 'Listed in requirements', 'Not used by final code: remove'],
  ['Streamlit', 'Planned dashboard', 'Never run; dashboard moving to Power BI'],
  ['Python stdlib', 'hashlib (freeze fingerprint), json, argparse, subprocess (DuckDB CLI)', 'Used'],
], { x: 0.6, y: 1.45, w: 12.1, colW: [2.1, 6.4, 3.6] });

s = content('SQL step 1: load, type and join the data', 'This is the first part of sql/01_load_audit.sql. It casts day labels such as d_123 to integers, joins sales to the calendar and to weekly prices, and reshapes the wide file into long format so it can be compared cell by cell with the long file. The join keeps the same-week price, but Python never uses it directly as a forecast input: it lags price to the last completed week before each forecast date.');
code(s, 0.6, 1.45, 7.4, 5.25, [
  "CREATE OR REPLACE TABLE daily_sales AS",
  "SELECT id, item_id, store_id, state_id, d,",
  "  CAST(replace(d,'d_','') AS INTEGER) AS d_num,",
  "  CAST(units AS INTEGER) AS units",
  "FROM read_csv('data/prepared/daily_sales.csv.gz');",
  "",
  "-- wide file reshaped to long, to reconcile",
  "CREATE OR REPLACE TABLE wide_long AS",
  "SELECT id, CAST(replace(d,'d_','') AS INTEGER) d_num, units",
  "FROM (UNPIVOT sales_wide ON COLUMNS('^d_[0-9]+$')",
  "      INTO NAME d VALUE units);",
  "",
  "CREATE OR REPLACE TABLE observed_history AS",
  "SELECT s.*, c.wm_yr_wk, c.wday, c.event_type_1,",
  "  CASE s.state_id WHEN 'CA' THEN c.snap_CA",
  "                  ELSE c.snap_TX END AS snap, p.sell_price",
  "FROM daily_sales s",
  "LEFT JOIN calendar c ON s.d_num = c.d_num",
  "LEFT JOIN prices p ON s.store_id = p.store_id",
  "  AND s.item_id = p.item_id AND c.wm_yr_wk = p.wm_yr_wk;",
]);
card(s, 8.3, 1.45, 4.4, 5.25, 'What "cleaning" meant here', 'The prepared data was already clean: no missing or negative sales. SQL work was verification, not repair:\n\n- consistent integer day keys\n- one row per series-day\n- calendar + SNAP + price joined by key\n- missing prices left missing (all are pre-launch weeks)\n- compact model input exported for Python (data/derived/model_input.csv.gz)');

s = content('SQL step 2: audit checks and their results', 'The audit is one SQL statement that computes every check at once; scripts/checkpoint1_verify.py then compares each value to the supplied audit_summary.json. All 26 checks passed for both the 200-series panel and the 30-series pilot.');
code(s, 0.6, 1.45, 5.9, 5.25, [
  "dup AS (SELECT count(*) AS dup_id_day FROM",
  "  (SELECT id, d_num FROM daily_sales",
  "   GROUP BY 1,2 HAVING count(*) > 1)),",
  "wm AS (SELECT count(*) AS wide_long_mismatch",
  "  FROM wide_long w FULL OUTER JOIN daily_sales s",
  "    ON w.id = s.id AND w.d_num = s.d_num",
  "  WHERE w.units IS DISTINCT FROM s.units),",
  "j AS (SELECT count(*) AS joined_rows,",
  "  sum(units) AS joined_units,",
  "  sum(CASE WHEN sell_price IS NULL",
  "      AND units > 0 THEN 1 ELSE 0 END)",
  "    AS positive_sales_missing_price",
  "  FROM observed_history)",
]);
table(s, [
  ['Check (200-series panel)', 'Result'],
  ['Rows = 200 series x 1,941 days', '388,200'],
  ['Total units (= supplied audit)', '865,515'],
  ['Duplicate series-day keys', '0'],
  ['Duplicate store-item-week prices', '0'],
  ['Wide vs long cell mismatches', '0'],
  ['Rows / units after joins', 'unchanged'],
  ['Missing-price days (= audit)', '22,253'],
  ['Sales on days without a price', '0'],
  ['Early selection stats vs metadata', '0 mismatches'],
  ['All checks, panel + pilot', '26 / 26 pass'],
], { x: 6.8, y: 1.45, w: 5.9, colW: [4.0, 1.9] });

s = content('SQL step 3: independent recomputation of results', 'After the holdout, sql/02_analytics.sql reads the saved forecast files and recomputes WAPE, bias and mean RMSSE by model and segment, plus the priority-list summaries, completely separately from Python. scripts/reconcile.py compares the two: 60 forecast-metric rows and 36 priority rows, zero differences above one in a million. Guard queries also confirm validation rows never reach into the holdout days.');
code(s, 0.6, 1.45, 6.6, 3.6, [
  "SELECT period, model, segment_type, segment,",
  "  sum(abs(forecast - y)) / nullif(sum(y),0) AS wape,",
  "  sum(forecast - y)     / nullif(sum(y),0) AS bias",
  "FROM unioned GROUP BY ALL;",
  "",
  "SELECT period, model, origin, idx,",
  "  sqrt(avg(power(forecast - y, 2))",
  "       / any_value(scale)) AS rmsse",
  "FROM forecast_eval GROUP BY ALL;",
]);
table(s, [
  ['Guard / reconciliation', 'Result'],
  ['Validation rows', '100,800; days 1746-1913; 0 missing'],
  ['Holdout rows', '16,800; days 1914-1941; 0 missing'],
  ['Forecast metric rows, SQL vs Python', '60 compared, 0 mismatches'],
  ['Priority summary rows, SQL vs Python', '36 compared, 0 mismatches'],
], { x: 0.6, y: 5.25, w: 6.6, colW: [3.3, 3.3] });
card(s, 7.5, 1.45, 5.2, 5.2, 'Why do it twice?', '"Dashboard-to-result reconciliation" is a spec requirement. Two engines with independent code agreeing to 6 decimals is strong evidence that metrics were not mis-computed.\n\nnullif(sum(y),0) is the SQL form of the explicit rule "WAPE is undefined when actual sales are zero."');

s = content('Time rules: every forecast only sees its own past', 'Bars show which days each stage uses. Forecasts are made at weekly "origins" (always a Sunday). Choices were made only on earlier windows: LightGBM tuning on three origins, model choice on six later origins, interval width and event threshold on the calibration weeks, priority weights on the validation weeks. The last 28 days were sealed in code (set to missing) until all choices were frozen in config/frozen_choices.json with a SHA-256 fingerprint, then used once.');
const lanes = [
  ['Panel selection', 1, 730, HEX.gray],
  ['Error-history warm-up', 1494, 1584, HEX.sage],
  ['Calibration (ranges, threshold)', 1585, 1668, HEX.sage],
  ['LightGBM tuning windows', 1662, 1745, HEX.navy],
  ['Priority validation (35 weeks)', 1669, 1913, HEX.teal],
  ['Forecast validation (6 x 28 days)', 1746, 1913, HEX.teal],
  ['Final holdout (sealed, used once)', 1914, 1941, HEX.red],
];
const x0 = 4.3, x1 = 12.6, scale = d => x0 + (d - 1) / 1940 * (x1 - x0);
lanes.forEach((l, i) => {
  const y = 1.55 + i * 0.6;
  s.addText(l[0], { isTextBox: true, x: 0.6, y, w: 3.6, h: 0.42, fontSize: 14, color: HEX.ink, margin: 0, valign: 'middle' });
  s.addShape(pres.shapes.RECTANGLE, { x: x0, y: y + 0.17, w: x1 - x0, h: 0.08, fill: { color: HEX.light }, line: { color: HEX.light }, objectName: 'lane ' + i });
  const bx = scale(l[1]), bw = Math.max(scale(l[2]) - bx, 0.08);
  s.addShape(pres.shapes.RECTANGLE, { x: bx, y: y + 0.06, w: bw, h: 0.3, fill: { color: l[3] }, line: { color: l[3] }, objectName: 'bar ' + l[0] });
  s.addText(`d${l[1]}-${l[2]}`, { isTextBox: true, x: bx - 1.25, y, w: 1.2, h: 0.42, fontSize: 11, color: HEX.muted, align: 'right', margin: 0, valign: 'middle' });
});
txt(s, '2011', { x: x0 - 0.2, y: 5.85, w: 0.6, h: 0.3, fontSize: 11, color: HEX.muted });
txt(s, 'May 2016', { x: x1 - 0.9, y: 5.85, w: 1.0, h: 0.3, fontSize: 11, color: HEX.muted, align: 'right' });
txt(s, 'LightGBM is refit at every weekly origin on the previous 104 weeks, keeping only training targets dated on or before that origin.', { x: 0.6, y: 6.25, w: 12.1, h: 0.55, fontSize: 14, color: HEX.dark, italic: true });

s = content('Leakage and correctness checks (8 automated tests)', 'tests/test_temporal.py runs these on the pilot. The most important is the scramble test: replacing all future sales and future prices with random numbers must leave every feature unchanged. The near-end test was added after the holdout crash. Separately, one RMSSE and one WAPE were recomputed by hand and matched exactly.');
const tests = [
  ['Holdout sealed', 'Final 28 days are missing in pre-holdout runs; asking for them errors'],
  ['Future scramble', 'Random future sales and prices leave every feature identical'],
  ['Training targets', 'Every LightGBM training target is dated on or before the forecast date'],
  ['Baseline match', '"Same as last week" equals the matching feature; weekdays align'],
  ['ETS recovery', 'Recovers a known weekly pattern and a constant series'],
  ['Zero denominators', 'Zero actuals give undefined WAPE / RMSSE, counted, not hidden'],
  ['Disjoint weeks', 'Weekly evaluation windows never overlap; none touch the holdout'],
  ['Near end of data', 'Forecasts past d1941 still get calendar features (regression)'],
];
tests.forEach((t, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  const x = 0.6 + col * 6.15, y = 1.5 + row * 1.3;
  s.addShape(pres.shapes.OVAL, { x, y: y + 0.08, w: 0.5, h: 0.5, fill: { color: HEX.teal }, line: { color: HEX.teal }, objectName: 'check ' + i });
  s.addText('✓', { isTextBox: true, x, y: y + 0.08, w: 0.5, h: 0.5, fontSize: 18, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0 });
  s.addText(t[0], { isTextBox: true, x: x + 0.7, y, w: 5.2, h: 0.4, fontFace: THEME.headFontFace, fontSize: 16, bold: true, color: HEX.dark, margin: 0 });
  s.addText(t[1], { isTextBox: true, x: x + 0.7, y: y + 0.42, w: 5.2, h: 0.75, fontSize: 14, color: HEX.ink, margin: 0, valign: 'top' });
});

// ================= FORECASTING =================
section('Forecasting: which forecasts are dependable?', 'Three methods, limited tuning, six validation periods, one holdout',
  'This section covers the three forecasting methods, how they were tuned, and how they compare overall, over time, by segment, and on the final holdout. It also covers the forecast ranges.');

s = content('Three forecasting methods', 'Seasonal naive is the benchmark every method must beat. ETS is a classic exponential smoothing model: a level plus a weekly pattern updated by each new day, with smoothing strengths chosen per series by grid search and the seasonal or non-seasonal version picked by AIC. LightGBM is one gradient-boosted tree model trained across all 200 series; it predicts each of the 28 days ahead directly using features known at the forecast date. All forecasts are clipped at zero.');
card(s, 0.6, 1.5, 3.9, 5.1, 'Seasonal naive', 'Forecast for each of the next 28 days = sales on the same weekday last week.\n\nNo parameters. The benchmark.\n\nRuntime: instant.');
card(s, 4.75, 1.5, 3.9, 5.1, 'ETS (hand-written)', 'Level + weekly pattern, additive errors. Per series: ETS(A,N,A) or ETS(A,N,N) by AIC; smoothing grid 8 x 4.\n\nFit on the last 728 days.\n\nFallback to naive if a fit fails: 0 times.\n\nRuntime: 0.05 s for 200 series.');
card(s, 8.9, 1.5, 3.8, 5.1, 'LightGBM (global)', 'One model for all series; 28 horizons with horizon as a feature.\n\nFeatures: recent means, weekday averages, zero share, days since sale, last known price and change, target-day weekday / event / SNAP, store / dept.\n\nTweedie loss. Runtime: about 25 s per refit.');

s = content('Limited tuning: 3 LightGBM settings on 3 tuning origins', 'Only three LightGBM settings were tried, on tuning origins 1661, 1689 and 1717, whose forecast days end before validation starts. Fixed number of trees, no early stopping, so no validation data leaked into tuning. The 63-leaf Tweedie setting won narrowly and was frozen. ETS and naive shown for reference on the same origins.');
s.addChart(pres.charts.BAR, [{ name: 'Mean RMSSE', labels: ['Tweedie 63 leaves', 'Tweedie 31 leaves', 'Poisson 31 leaves', 'ETS', 'Seasonal naive'], values: [0.658, 0.662, 0.664, 0.673, 0.896] }],
  Object.assign(chartBase('Mean RMSSE on tuning origins (lower is better)'), { x: 0.6, y: 1.45, w: 7.6, h: 5.2, barDir: 'bar', chartColors: [HEX.teal, HEX.teal, HEX.teal, HEX.amber, HEX.gray], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.000', valAxisMinVal: 0, valAxisMaxVal: 1.0, showLegend: false, catAxisOrientation: 'maxMin' }));
card(s, 8.5, 1.45, 4.2, 5.2, 'Choice recorded', 'Rule fixed in advance: lowest mean RMSSE on tuning origins.\n\nChosen: Tweedie, 63 leaves, 800 trees, learning rate 0.03.\n\nThe gap between settings (0.006) is small; tuning was deliberately limited to avoid overfitting.');

s = content('Validation: LightGBM best, ETS close behind', 'Six non-overlapping 28-day validation periods, origins 1745 to 1885, 200 series. RMSSE compares squared error to the series\' own day-to-day variability, so 1.0 would be as bad as a naive one-day change. WAPE is total absolute error over total sales. Bias is total forecast minus actual over actual; negative means under-forecast. LightGBM had the lowest RMSSE and WAPE but the most negative bias.');
s.addChart(pres.charts.BAR, [{ name: 'Mean RMSSE', labels: ['LightGBM', 'ETS', 'Seasonal naive'], values: [0.674, 0.688, 0.889] }],
  Object.assign(chartBase('Mean RMSSE, 6 validation periods'), { x: 0.6, y: 1.45, w: 6.0, h: 5.2, barDir: 'col', chartColors: [HEX.teal, HEX.amber, HEX.gray], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.000', valAxisMinVal: 0, valAxisMaxVal: 1.0, showLegend: false }));
table(s, [
  ['Model', 'Mean RMSSE', 'Median', 'WAPE', 'Bias'],
  ['LightGBM', '0.674', '0.629', '60.5%', '-5.8%'],
  ['ETS', '0.688', '0.644', '62.6%', '-1.1%'],
  ['Seasonal naive', '0.889', '0.865', '75.4%', '-2.3%'],
], { x: 6.9, y: 1.55, w: 5.8, colW: [1.7, 1.15, 0.95, 1.0, 1.0] });
bullets(s, [['Won 6 of 6 periods,', 'but paired gap vs ETS is only -0.014 RMSSE.'], ['Better on 57%', 'of series-periods; ETS wins the other 43%.'], ['Under-forecasts more:', '-6% on high and medium volume.']], { x: 6.9, y: 3.6, w: 5.8, h: 2.9 });

s = content('Consistency over time: same order in every period', 'The ranking LightGBM, ETS, naive held in all six validation periods. Error rises in the last two periods for every method, which suggests that period was harder rather than a model breaking.');
s.addChart(pres.charts.LINE, [
  { name: 'LightGBM', labels: ['d1745', 'd1773', 'd1801', 'd1829', 'd1857', 'd1885'], values: [0.669, 0.654, 0.654, 0.683, 0.696, 0.686] },
  { name: 'ETS', labels: ['d1745', 'd1773', 'd1801', 'd1829', 'd1857', 'd1885'], values: [0.676, 0.674, 0.665, 0.697, 0.708, 0.706] },
  { name: 'Seasonal naive', labels: ['d1745', 'd1773', 'd1801', 'd1829', 'd1857', 'd1885'], values: [0.861, 0.882, 0.876, 0.874, 0.923, 0.918] },
], Object.assign(chartBase('Mean RMSSE by validation forecast date'), { x: 0.6, y: 1.45, w: 12.1, h: 5.3, chartColors: [HEX.teal, HEX.amber, HEX.gray], lineSize: 3, lineDataSymbolSize: 8, valAxisMinVal: 0.6, valAxisMaxVal: 0.95, valAxisLabelFormatCode: '0.00', showLegend: true, legendPos: 'b' }));

s = content('By segment: LightGBM edge disappears on slow sellers', 'Segments were defined from the first 730 days only. LightGBM leads in high and medium volume and in frequent sellers, but on low-volume series it is essentially tied with ETS (0.595 vs 0.598). Lower RMSSE on low-volume series does not mean they are easy in business terms; RMSSE is scaled by each series\' own variability.');
s.addChart(pres.charts.BAR, [
  { name: 'LightGBM', labels: ['High volume', 'Medium volume', 'Low volume', 'Frequent sellers', 'Irregular sellers'], values: [0.694, 0.693, 0.595, 0.695, 0.659] },
  { name: 'ETS', labels: ['High volume', 'Medium volume', 'Low volume', 'Frequent sellers', 'Irregular sellers'], values: [0.710, 0.710, 0.598, 0.714, 0.669] },
  { name: 'Seasonal naive', labels: ['High volume', 'Medium volume', 'Low volume', 'Frequent sellers', 'Irregular sellers'], values: [0.899, 0.930, 0.788, 0.927, 0.863] },
], Object.assign(chartBase('Mean RMSSE by segment, validation'), { x: 0.6, y: 1.45, w: 12.1, h: 5.3, barDir: 'col', barGrouping: 'clustered', chartColors: [HEX.teal, HEX.amber, HEX.gray], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00', valAxisMinVal: 0, valAxisMaxVal: 1.0, showLegend: true, legendPos: 'b' }));

s = content('Final holdout: same ranking, everyone under-forecasts', 'The untouched final 28 days, 25 April to 22 May 2016, forecast once from d1913 with all choices frozen. LightGBM is still lowest in every segment but by 0.002 to 0.025 RMSSE. All models under-forecast, most of all on low-volume items (LightGBM -15%), so the period had higher sales than recent history suggested. The holdout first crashed on your laptop; after the fix it was rerun here. LightGBM forecasts differed slightly between the two machines (RMSSE 0.7339 vs 0.7333).');
s.addChart(pres.charts.BAR, [{ name: 'Mean RMSSE', labels: ['LightGBM', 'ETS', 'Seasonal naive'], values: [0.733, 0.746, 0.932] }],
  Object.assign(chartBase('Mean RMSSE, final 28 days'), { x: 0.6, y: 1.45, w: 5.6, h: 5.2, barDir: 'col', chartColors: [HEX.teal, HEX.amber, HEX.gray], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.000', valAxisMinVal: 0, valAxisMaxVal: 1.0, showLegend: false }));
table(s, [
  ['Holdout', 'LightGBM', 'ETS', 'Naive'],
  ['WAPE', '57.9%', '58.6%', '68.0%'],
  ['Bias, all', '-4.9%', '-6.8%', '-10.6%'],
  ['Bias, low volume', '-15.3%', '-16.9%', '-12.5%'],
  ['RMSSE, low volume', '0.682', '0.684', '0.898'],
  ['RMSSE, high volume', '0.709', '0.734', '0.878'],
], { x: 6.5, y: 1.55, w: 6.2, colW: [2.3, 1.3, 1.3, 1.3] });
card(s, 6.5, 4.6, 6.2, 2.05, 'Reading it', 'Validation and holdout agree on the order. Holdout RMSSE is higher than validation (0.733 vs 0.674): one 28-day window is a small, noisy sample.');

s = content('Forecast ranges: calibrated on old weeks, held up later', 'Ranges are built from each series\' past out-of-sample errors (last 26 weeks, by horizon week), taking the 5th and 95th percentile. Raw ranges were too narrow on the calibration weeks (84-87%), so each horizon week got a width multiplier (1.05, 1.10, 1.10, 1.15) fixed on calibration weeks only. Validation coverage then reached 90.9%, holdout 89.3%. Weakest holdout segments: irregular sellers 87.7%, FOODS 88.1%.');
s.addChart(pres.charts.BAR, [
  { name: 'Raw (calibration weeks)', labels: ['Days 1-7', 'Days 8-14', 'Days 15-21', 'Days 22-28'], values: [0.874, 0.865, 0.856, 0.843] },
  { name: 'Calibrated (validation)', labels: ['Days 1-7', 'Days 8-14', 'Days 15-21', 'Days 22-28'], values: [0.898, 0.905, 0.912, 0.921] },
  { name: 'Calibrated (holdout)', labels: ['Days 1-7', 'Days 8-14', 'Days 15-21', 'Days 22-28'], values: [0.901, 0.885, 0.886, 0.900] },
], Object.assign(chartBase('Share of actual sales inside the 90% range (target 0.90)'), { x: 0.6, y: 1.45, w: 8.0, h: 5.3, barDir: 'col', barGrouping: 'clustered', chartColors: [HEX.gray, HEX.teal, HEX.amber], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.00', valAxisMinVal: 0.8, valAxisMaxVal: 0.95, valAxisLabelFormatCode: '0.00', showLegend: true, legendPos: 'b' }));
card(s, 8.9, 1.45, 3.8, 5.3, 'Why it matters', 'A range is only useful if its stated confidence is honest.\n\nAverage width: about 6 units per day, from 2 (low volume) to 10 (high volume).\n\nThe range width also became one of the review-list signals.');

// ================= PRIORITY =================
section('Weekly review list: which 5 series to check?', 'Equal-budget comparison of ranking rules, frozen before the holdout',
  'This section explains the ranking rules, how lists were scored, and what happened on validation weeks and the four holdout weeks.');

s = content('Ranking rules and how a list is scored', 'Every Sunday each rule ranks the 200 series using only information known that day. The signals come from earlier forecasts\' real errors, never from model fit. A list is scored on the next 7 days only, so consecutive weeks never share outcomes. The combined score adds three signals after dividing each by its weekly median; weights were picked from 66 combinations x 2 normalisations on validation weeks.');
table(s, [
  ['Rule', 'Ranks series by'],
  ['Volume', 'Units sold in the last 28 days'],
  ['Recent error', 'Average weekly absolute error of the last 4 weekly forecasts'],
  ['Bias', 'Size of average signed error over the last 8 weeks'],
  ['Uncertainty', 'Width of this week\'s 90% range, summed over 7 days'],
  ['Combined (proposed)', '0.2 x recent error + 0.1 x bias + 0.7 x uncertainty'],
  ['Random', '200 seeded random lists (benchmark)'],
  ['Normalised error (diagnostic)', 'Recent error divided by the series\' usual daily change'],
], { x: 0.6, y: 1.45, w: 7.3, colW: [2.6, 4.7] });
card(s, 8.2, 1.45, 4.5, 5.3, 'Scoring a list', 'Captured share: the list\'s share of all 200 series\' absolute unit error over the next 7 days.\n\nLarge-error event: error relative to the series\' usual variability above 1.44 (90th percentile on calibration weeks).\n\nPrecision: share of picks that were events. Recall: share of events picked.\n\nCaptured error is not avoided error.');

s = content('Validation (35 weeks): combined score wins by a hair', 'At K = 5, the combined score captured 16.4% of next-week error, versus 16.1% for uncertainty alone, 16.0% recent error and 15.6% volume, and 2.5% random. It beat recent error in only 18 of 35 weeks (9 ties). The pre-registered split check (choose weights on the first half, score on the second) passed by 0.06 percentage points. These weights were picked on these same weeks, so this number flatters the combined score.');
s.addChart(pres.charts.BAR, [{ name: 'Captured share, K=5', labels: ['Combined', 'Uncertainty', 'Recent error', 'Volume', 'Bias', 'Normalised error', 'Random'], values: [0.164, 0.161, 0.160, 0.156, 0.139, 0.039, 0.025] }],
  Object.assign(chartBase('Share of next-7-day unit error captured by 5 picks, validation'), { x: 0.6, y: 1.45, w: 7.6, h: 5.3, barDir: 'bar', chartColors: [HEX.teal, HEX.navy, HEX.navy, HEX.navy, HEX.navy, HEX.sage, HEX.gray], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0.0%', valAxisMinVal: 0, valAxisMaxVal: 0.2, valAxisLabelFormatCode: '0%', showLegend: false, catAxisOrientation: 'maxMin' }));
table(s, [
  ['Captured share', 'K=1', 'K=5', 'K=10'],
  ['Combined', '6.2%', '16.4%', '23.6%'],
  ['Recent error', '6.0%', '16.0%', '23.2%'],
  ['Volume', '5.1%', '15.6%', '23.4%'],
  ['Random', '0.5%', '2.5%', '5.0%'],
], { x: 8.5, y: 1.55, w: 4.2, colW: [1.65, 0.85, 0.85, 0.85] });
card(s, 8.5, 4.2, 4.2, 2.55, 'Takeaway', 'All sensible rules are 6x random. Differences between them are about half a point and vary week to week.');

s = content('Holdout (4 weeks): effectively a tie', 'Frozen rules applied to the four holdout weeks. The combined score captured 13.4%, volume 13.0%, recent error 12.8%. It led in 2 of 4 weeks. With only four weeks and 15-25 large-error events per week, these differences are within noise. Per the pre-registered rule the combined score was the formal pick, but the honest reading is that it has not shown an advantage over the simpler rules.');
s.addChart(pres.charts.LINE, [
  { name: 'Combined', labels: ['Week of d1913', 'd1920', 'd1927', 'd1934'], values: [0.119, 0.112, 0.139, 0.167] },
  { name: 'Volume', labels: ['Week of d1913', 'd1920', 'd1927', 'd1934'], values: [0.119, 0.098, 0.139, 0.163] },
  { name: 'Recent error', labels: ['Week of d1913', 'd1920', 'd1927', 'd1934'], values: [0.121, 0.116, 0.132, 0.142] },
], Object.assign(chartBase('Captured share by holdout week, K=5'), { x: 0.6, y: 1.45, w: 7.4, h: 5.3, chartColors: [HEX.teal, HEX.amber, HEX.navy], lineSize: 3, lineDataSymbolSize: 8, valAxisMinVal: 0.08, valAxisMaxVal: 0.18, valAxisLabelFormatCode: '0%', showLegend: true, legendPos: 'b' }));
table(s, [
  ['Holdout, K=5', 'Captured', 'Precision'],
  ['Combined', '13.4%', '15%'],
  ['Volume', '13.0%', '10%'],
  ['Recent error', '12.8%', '25%'],
  ['Uncertainty', '12.8%', '10%'],
  ['Bias', '8.6%', '25%'],
  ['Random', '2.5%', '10%'],
], { x: 8.3, y: 1.55, w: 4.4, colW: [1.9, 1.25, 1.25] });

s = content('Two goals need two different lists', 'This is the most useful finding of the priority experiment. Ranking by error in units mostly selects big sellers: their precision for unusually bad forecasts is about the same as random. Ranking by error relative to each series\' normal variability finds unusual forecasts 60% of the time, but captures little unit error. A planner should decide which goal matters: biggest unit exposure, or forecasts that are broken for that item.');
s.addChart(pres.charts.BAR, [
  { name: 'Validation', labels: ['Normalised error', 'Recent error', 'Bias', 'Combined', 'Volume', 'Random'], values: [0.60, 0.12, 0.131, 0.097, 0.086, 0.09] },
  { name: 'Holdout', labels: ['Normalised error', 'Recent error', 'Bias', 'Combined', 'Volume', 'Random'], values: [0.60, 0.25, 0.25, 0.15, 0.10, 0.103] },
], Object.assign(chartBase('Precision@5 for unusually large errors'), { x: 0.6, y: 1.45, w: 7.6, h: 5.3, barDir: 'col', barGrouping: 'clustered', chartColors: [HEX.teal, HEX.amber], showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0%', valAxisMinVal: 0, valAxisMaxVal: 0.7, valAxisLabelFormatCode: '0%', showLegend: true, legendPos: 'b' }));
card(s, 8.5, 1.45, 4.2, 2.5, 'Unit-exposure list', 'Volume / recent error / combined.\nCaptures ~13-16% of unit error.\nPicks are mostly high sellers.');
card(s, 8.5, 4.2, 4.2, 2.55, '"Broken forecast" list', 'Normalised recent error.\n60% of picks are true large-error events; only ~4% of unit error.', { fill: 'E6F0EC' });

// ================= HONESTY =================
section('What went wrong, and what we did not test', 'Failures, fixes, limits and gaps',
  'This section is about credibility: the problems found and fixed, the paths we did not explore, and the data we do not have.');

s = content('Problems found and how they were handled', 'Every one of these is recorded in PROGRESS.md with evidence. The ETS bug was caught by a test before it affected results. The holdout crash affected only weekly origins after d1913 and was fixed without changing frozen choices. The environment limits are why ETS is hand-written and why the dashboard was never run in the cloud workspace.');
table(s, [
  ['Problem', 'Impact', 'Resolution'],
  ['ETS dropped perfect fits (log of zero error)', 'Wrong model choice on clean series', 'Caught by toy test; fixed before any results'],
  ['Holdout crashed on your laptop (calendar stopped at d1941)', 'LightGBM missing for 3 holdout weeks', 'Full calendar loaded; regression test; script now stops loudly; rerun'],
  ['Package index blocked in both work environments', 'No statsmodels / Streamlit', 'LightGBM + DuckDB from official releases; ETS in numpy'],
  ['LightGBM differs across machines (4.7.0 laptop vs 4.6.0)', 'Holdout RMSSE 0.7339 vs 0.7333', 'Recorded; conclusions unchanged; lightgbm 4.6.0 pinned'],
  ['pandas 3 read-only arrays', 'Load step failed', 'Explicit copies; code runs on pandas 2 and 3'],
], { x: 0.6, y: 1.45, w: 12.1, colW: [4.3, 3.4, 4.4] });

s = content('Paths tested, and paths not tested', 'We did not test every possible approach. We tested a defined, pre-specified set and kept tuning limited on purpose, because every extra option tried on the same data makes the winner look better than it really is. The right column is a candidate list for future work; any of these now needs fresh data to evaluate, because the holdout has been used.');
card(s, 0.6, 1.45, 5.9, 5.3, 'Tested', '- 3 forecast methods: naive, ETS, LightGBM\n- 3 LightGBM settings (Tweedie / Poisson, 31 / 63 leaves)\n- ETS seasonal vs non-seasonal, chosen per series by AIC\n- 5 single-signal ranking rules + 200 random lists\n- 66 weight mixes x 2 normalisations for the combined score\n- Capacities K = 1, 5, 10\n- Unit exposure vs normalised error\n- Raw vs calibrated forecast ranges\n- Segments: volume, pattern, store, category, horizon');
card(s, 6.8, 1.45, 5.9, 5.3, 'Not tested', '- Intermittent-demand methods (Croston, TSB) for irregular sellers\n- Quantile LightGBM for forecast ranges\n- Bias correction of LightGBM\n- Separate models by segment (no evidence of need)\n- Known-future-price scenario (optional in spec)\n- Hierarchical / aggregate forecasts (store, department)\n- Deep learning (out of scope by spec)\n- Statistical confidence intervals on rule differences', { fill: 'FBF1E3' });

s = content('Missing data and limits of the conclusions', 'These limits belong in the memo and in any interview answer. The biggest is that we cannot measure business value: there is no inventory, cost or planner data, so a high captured share is not savings.');
const lim = [
  ['No inventory or lead times', 'Cannot measure stockouts, service level or cash impact.'],
  ['No planner override history', 'Cannot test whether reviewing a list improves forecasts.'],
  ['Censored demand', 'Zero sales may be no demand, no stock, or recording; indistinguishable here.'],
  ['Small holdout', '28 days and 4 weekly lists; rule differences are within noise.'],
  ['Narrow panel', '2 stores, 2 categories; sparse and new items excluded.'],
  ['Not official M5 metric', 'Panel RMSSE, not the full-hierarchy WRMSSE leaderboard metric.'],
];
lim.forEach((l, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  card(s, 0.6 + col * 6.15, 1.45 + row * 1.8, 5.95, 1.6, l[0], l[1], { fill: col ? 'FBF1E3' : HEX.light });
});

// ================= NEXT =================
section('Recommendations and next steps', 'How to use this, how to improve it, and the Power BI dashboard',
  'This last section covers recommendations for a planner, improvements to the project, the Power BI dashboard plan, and remaining work.');

s = content('Recommendations', 'Operational recommendations are based only on what was measured. Project improvements are ordered by value for effort. Remember that the holdout is spent: any new method can only be evaluated on validation weeks, so results must be labelled as such.');
card(s, 0.6, 1.45, 5.9, 5.3, 'For a planner (from the evidence)', '- Use LightGBM forecasts; keep ETS as a fast, less-biased fallback.\n- Watch the downward bias, especially on slow sellers.\n- Review list: start with the simple rule (top recent error or top volume); the combined score has not earned its complexity.\n- Run a second, normalised-error list to catch broken forecasts.\n- Treat ranges as about 89-91% honest.');
card(s, 6.8, 1.45, 5.9, 5.3, 'To improve the project', '1. Cross-check hand-written ETS against statsmodels on your laptop.\n2. Add bootstrap confidence intervals for rule differences across weeks.\n3. Try Croston/TSB for irregular sellers and a simple bias correction (validation only).\n4. Pin exact package versions; remove scipy and scikit-learn.\n5. Extend to more stores and categories with the same frozen pipeline.\n6. With real data: inventory and planner overrides to measure value.', { fill: 'E6F0EC' });

s = content('Power BI dashboard: 10 pages', 'Generated as a Power BI project (.pbip) by powerbi/build_pbip.py, with no manual clicking: a data model of 23 tables, 8 relationships and 35 DAX measures, and a report of 10 pages with 69 visuals. All report files pass Microsoft\'s official schemas. It was opened and refreshed in Power BI Desktop and every page inspected; the first open found a measure/column name clash, which was fixed, and the layout was redesigned onto a fixed grid after review. The review-list page shows only what a planner knew that week; outcomes live on the retrospective page.');
table(s, [
  ['Page', 'What it explains', 'Source'],
  ['1. Start here', 'The two questions, KPI cards, headline findings', 'all'],
  ['2. The company', 'Store and department shares, growth, monthly trend', 'ctx_* (full M5)'],
  ['3. Demand patterns', 'Weekday rhythm, SNAP days, events, zero-sales share', 'ctx_* (full M5)'],
  ['4. Our sample', 'Sample vs company, 26 data checks, limits', 'ctx_panel_vs_m5, checks'],
  ['5. Forecast accuracy', 'RMSSE / WAPE / bias by model, segment, period', 'model_comparison'],
  ['6. Forecast ranges', 'Coverage raw vs calibrated, by horizon and segment', 'interval_coverage'],
  ['7. Weekly review list', 'As-of week slicer, top 10 with evidence text', 'review_lists'],
  ['8. Product drill-down', 'Actual vs forecast and 90% band; failure case preloaded', 'sales_history, forecast_intervals'],
  ['9. Did the lists work?', 'Captured share by week and rule; precision', 'rule_weekly, rule_summary'],
  ['10. Findings & limits', 'Recommendations, what cannot be claimed, how it was built', 'docs'],
], { x: 0.6, y: 1.4, w: 12.1, colW: [2.4, 6.3, 3.4], fontSize: 12 });

s = content('Status and next steps', 'Status at the time of this deck.');
const todo = [
  ['Done', 'Checkpoints 1-4: data audit, pilot, forecast comparison, priority experiment, holdout, SQL reconciliation', HEX.teal],
  ['Done', 'Company context in SQL; dashboard tables (351/351 checks); memo; interview walkthrough; source dictionary; README', HEX.teal],
  ['Done', 'Power BI report: generated, opened, refreshed and checked page by page (10 pages, 72 visuals)', HEX.teal],
  ['Next', 'Optional: run the statsmodels ETS cross-check on the laptop and record the result', HEX.amber],
  ['You', 'Learn the numbers well enough to explain them without notes', HEX.navy],
];
todo.forEach((t, i) => {
  const y = 1.5 + i * 0.85;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y, w: 1.3, h: 0.6, rectRadius: 0.08, fill: { color: t[2] }, line: { color: t[2] }, objectName: 'status ' + i });
  s.addText(t[0], { isTextBox: true, x: 0.6, y, w: 1.3, h: 0.6, fontSize: 15, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0 });
  s.addText(t[1], { isTextBox: true, x: 2.15, y, w: 10.5, h: 0.6, fontSize: 16, color: HEX.ink, valign: 'middle', margin: 0 });
});

pres.addSection({ title: 'Close' });
s = pres.addSlide({ masterName: 'TITLE_DARK', sectionTitle: 'Close' });
s.addText('Rigorous testing, modest gains, honest conclusions', { placeholder: 'title' });
s.addText('LightGBM is slightly better than ETS; ranges are close to their stated 90%; simple review rules are as good as the combined score.\nEverything is reproducible from the scripts, SQL and saved results in the project folder.', { placeholder: 'body' });
s.addNotes('Close on the interview message: the value of this project is the process. Leakage-proof evaluation, simple baselines, a frozen holdout, independent SQL reconciliation, and a willingness to report that the extra complexity did not pay off.');

(async () => {
  const f = 'deck/Walmart_Demand_Planning_Project_Review.pptx';
  await pres.writeFile({ fileName: f });
  await applyTheme(f, THEME);
  console.log('wrote', f);
})();
