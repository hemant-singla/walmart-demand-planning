# Decision memo: forecast reliability and weekly review priorities

*Independent historical study on public M5 data (Walmart sales, 2011–2016). Not Walmart work; nothing was deployed and no savings are claimed.*

## Decision

A demand planner has time to review roughly five product-store forecasts a week. Two questions:
(1) which forecasting method gives dependable 28-day daily forecasts, and (2) which rule should choose the five series to review each week.

**Recommendation.** Use the global LightGBM forecast, keep ETS as a fallback, and choose the weekly review list with a simple rule: the series with the largest recent forecast error, or the top sellers. The combined score we designed did not show a real advantage over those simple rules. Add a second short list for forecasts that are unusually bad *for that item*, plus a flag for historically active items with long zero-sales runs.

## Data actually used

- M5 competition data (Kaggle 2020, Zenodo mirror); SHA-256 of all three raw files verified.
- Fixed panel of 200 series: 100 FOODS/HOUSEHOLD items in each of stores CA_1 and TX_1, chosen using only the first 730 days, stratified by early volume and share of zero-sales days. Items with fewer than 100 early units or 100 selling days were excluded.
- 388,200 series-days and 865,515 units, reconciled in DuckDB with 26/26 checks passing. All 22,253 missing-price days fall before an item's first priced week; they were left missing.
- **Time rules.** Every forecast uses only data up to its forecast date. The final 28 days (25 Apr–22 May 2016) were sealed in code until all choices were frozen, then used once.

## Alternatives tested

| Area | Alternatives | How chosen |
|---|---|---|
| Forecast | Seasonal naive (repeat last week); ETS (level + weekly pattern, per-series AIC); global LightGBM (3 settings) | LightGBM setting on 3 tuning periods; model on 6 later 28-day validation periods |
| Ranges | 90% ranges from past out-of-sample errors, raw vs width-calibrated | Width fixed on calibration weeks only |
| Review list | Top sellers; largest recent error; persistent bias; range width; random (200 draws); weighted combination (66 weights × 2 scalings) | Weights chosen on 35 validation weeks, frozen before holdout |

## Measured results

**Forecasts** (mean RMSSE, lower is better; WAPE; bias = forecast minus actual over actual):

| Model | Validation RMSSE | Holdout RMSSE | Holdout WAPE | Holdout bias |
|---|---|---|---|---|
| LightGBM | 0.674 | 0.733 | 57.9% | −4.9% |
| ETS | 0.688 | 0.746 | 58.6% | −6.8% |
| Seasonal naive | 0.889 | 0.932 | 68.0% | −10.6% |

LightGBM ranked first in all six validation periods and in every holdout segment, but only by 0.002–0.025 RMSSE over ETS. On low-volume items the two are tied. ETS runs about 500× faster (0.05 s vs 25 s per forecast date).

**Ranges.** After calibration, 90.9% of validation actuals and 89.3% of holdout actuals fell inside the nominal 90% range. The weakest segment was irregular sellers in the holdout (87.7%).

**Review list** (share of next-7-day absolute unit error captured by 5 picks):

| Rule | Validation (35 weeks) | Holdout (4 weeks) |
|---|---|---|
| Combined score (frozen) | 16.4% | 13.4% |
| Largest recent error | 16.0% | 12.8% |
| Top sellers | 15.6% | 13.0% |
| Random | 2.5% | 2.5% |

Every sensible rule captures about 5–6× more error than random. The gaps between them are about half a percentage point and change from week to week. The combined score's validation figure is optimistic, because its weights were chosen on those same weeks. On four holdout weeks it led in two.

Lists ranked by error in units mostly pick big sellers. Over the 35 validation weeks, their hit rate for *unusually* large errors (relative to each item's normal variability) was 8–13%, against 9% for random picks. A list ranked by normalised recent error hits 60%, but captures only about 4% of unit error. The two goals need two lists.

## Failure cases

- **Return from a long silence.** The largest single holdout error was FOODS_3_444_CA_1. It had no recorded sales for 333 days while still carrying a shelf price, then sold 414 units over the holdout against a forecast of 3. Every ranking rule placed it 193rd–199th of 200, because error-based signals cannot see an event with no recent history. The second-largest under-forecast, FOODS_1_043_TX_1, followed the same pattern after 76 silent days. The data cannot say why sales stopped: demand, availability and recording all remain possible.
- **Holdout under-forecasting.** All models under-forecast the final 28 days, LightGBM by 15% on low-volume items.
- **Concentration.** Ten of 200 series account for 27% of holdout absolute error, so unit-based metrics are dominated by a few items.

## Missing data and limits

- No inventory, lead times, margins or planner override history, so stockouts, service level, cash impact and forecast value added cannot be measured. A list that captures error does not show that a planner would correct it.
- Recorded sales may be censored demand; zero sales do not prove a stockout.
- Two stores, two categories, no sparse or new items. The holdout is 28 days and four weekly lists.
- Panel RMSSE is not the official M5 full-hierarchy WRMSSE.
- The ETS implementation is hand-written: statsmodels could not be installed where the models ran. A cross-check script is provided.

## Next steps

1. Run the statsmodels ETS cross-check (`scripts/ets_crosscheck_statsmodels.py`, validation periods only).
2. Pilot the two-list review with real planner feedback, recording overrides so value can be measured.
3. Add a dormant-item flag and test an intermittent-demand method (Croston/TSB) and a bias correction. Evaluate on fresh data, since this holdout is spent.
