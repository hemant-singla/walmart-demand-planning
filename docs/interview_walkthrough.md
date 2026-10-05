# Interview walkthrough

How to explain this project in an interview. Every number here is in `results/` and `PROGRESS.md`. Learn the reasoning behind each one rather than memorising the text.

## How to describe it on a resume (accurately)

> **Demand forecasting and review-priority study (public Walmart M5 data).** Built a leakage-safe weekly backtest for 200 product-store series in DuckDB SQL and Python. Compared seasonal naive, ETS and a global LightGBM model on six validation periods and an untouched 28-day holdout (LightGBM RMSSE 0.733 vs ETS 0.746 vs naive 0.932). Calibrated 90% forecast ranges to 89–91% coverage. Tested weekly review-list rules under equal capacity: simple rules matched a tuned composite score, about 5× random.

Don't say "at Walmart", "deployed", "saved $X" or "reduced stockouts". None of these are true or measurable here.

## 30-second version

"I used Walmart's public M5 sales data to answer two planner questions: which forecasts can I trust, and which five items should I check each week? I set it up so no forecast could see the future, compared three forecasting methods, and tested several ways to rank items for review, with the final month locked away until every choice was frozen. LightGBM was the most accurate, but only slightly ahead of ETS. The interesting result was that my combined review score didn't beat the simple rule of checking the worst recent forecasts, so that's what I'd recommend."

## Two-minute walkthrough

1. **Problem.** A planner has limited time. The forecasts need to be good, and a weekly list should point to where error will concentrate. Capacity is five items, with one and ten also tested.
2. **Data.** M5 data, a fixed panel of 200 food and household series in two stores. They were selected using only the first two years, so later results couldn't bias the sample. Checksums were verified, and 26 SQL checks covered row counts, totals, duplicate keys and joins.
3. **No leakage.** Forecasts are made every Sunday using only data up to that day. Price is the last fully known weekly price. LightGBM training rows must have targets dated on or before the forecast date. The final 28 days were sealed in code. A test scrambles all future data and confirms the features don't change.
4. **Forecasting.** Seasonal naive as the benchmark, ETS, and one LightGBM model across all series predicting each of 28 days ahead directly. Tuning was limited to three settings on separate early periods. Validation used six non-overlapping 28-day periods.
5. **Uncertainty.** 90% ranges came from each series' past out-of-sample errors, not model residuals. Raw ranges were too narrow (84–87%), so widths were calibrated on earlier weeks. The ranges then held up later: 90.9% coverage on validation, 89.3% on the holdout.
6. **Review list.** Rules were compared at equal capacity: top sellers, largest recent error, bias, range width, random, and a weighted combination. Each list was scored on the next seven days only. The combination won validation by about half a point and tied on the holdout.
7. **Takeaways.** LightGBM is slightly better than ETS, with ETS as a fast fallback. Use a simple review rule. Run a second list for forecasts that are unusual for that item. Item returns after long silences are a blind spot.

## Questions you should expect, with honest answers

**Why RMSSE and not MAPE?**
MAPE divides by actual sales, which are zero on about half of all series-days, so it breaks. RMSSE scales each series' squared error by its own day-to-day variability, so series of different sizes are comparable. It's the M5 competition's base metric. WAPE gives the business view, total error over total sales. I reported both, plus bias.

**How did you prevent leakage?**
Three ways:
- **Feature construction.** Every feature uses only days up to the forecast date. Price comes from the last completed week, carried forward.
- **Training rows.** LightGBM only uses targets dated on or before the forecast date.
- **Process.** Choices were made on earlier windows, then written to a frozen config file with a SHA-256 fingerprint before the holdout ran once.

A unit test replaces all future sales and prices with random numbers and checks that every feature is unchanged.

**Why is LightGBM only slightly better than ETS?**
Daily item-level retail sales are mostly noise around a weekly pattern and a level. Both models capture those. LightGBM adds calendar, price and cross-series learning, which helps a bit on high-volume items and not at all on slow sellers.

**Why does LightGBM under-forecast?**
Tweedie loss on skewed, zero-heavy data tends to pull predictions toward typical rather than mean values. The holdout also had higher sales than recent history. I didn't fix it after the fact because the holdout was spent. A bias correction is a next step to test on fresh data.

**Your combined score didn't win. Isn't the project a failure?**
No. The question was whether added complexity pays off, and the honest answer is "not measurably." Recommending the simpler rule is the useful result. The combined score also had an unfair advantage: its weights were picked on the same validation weeks, so even that half-point lead is optimistic.

**How did you pick 90% ranges, and how do you know they're right?**
They're empirical quantiles of past out-of-sample errors per series and horizon week, so no distribution is assumed. I checked coverage on data not used to set the widths: 90.9% validation, 89.3% holdout, and 87.7–91.7% by segment.

**What does "captured 13.4% of error" mean in business terms?**
The five listed items accounted for 13.4% of all absolute forecast error across the 200 items the next week. It shows where error is concentrated, not that a planner would have fixed it. Measuring that needs override history, which M5 doesn't have.

**What was the biggest failure?**
FOODS_3_444_CA_1 sold nothing for 333 days while still priced, then sold 414 units against a forecast of 3. Every list ranked it near the bottom. History-based methods can't predict a return from silence. A rule-based "dormant item" flag would at least surface it.

**What was SQL used for?**
DuckDB loaded the prepared files and cast day keys. It joined sales to the calendar and prices, reshaped the wide file to long and compared it cell by cell, and ran 26 audit checks. At the end it recomputed every reported metric independently from the saved forecasts. SQL and Python matched on all 96 compared rows.

**Why a global model instead of one model per item?**
200 series with a lot of zeros are too sparse to fit 200 separate tree models well. A global model shares patterns across items. The horizon is a feature, so one model predicts all 28 days without feeding its own predictions back in.

**Would this scale to all of Walmart?**
The pipeline would, since nothing in it is specific to 200 series. But the panel excludes sparse and new items, which are a large share of a real assortment, so results there would likely be worse.

**What would you do with more time or data?**
- Check the ETS implementation against statsmodels.
- Add bootstrap confidence intervals for the differences between rules.
- Try Croston/TSB on irregular items, plus a bias correction.
- With real data, inventory and planner overrides, measure whether reviewing a list improves outcomes.

## What not to claim

- Anything about stockouts. Zero sales may be no demand, no stock, or a recording issue.
- Causal price or promotion effects. Price features are associations only.
- Official M5 leaderboard comparisons. This is panel RMSSE, not full-hierarchy WRMSSE.
- That the dashboard or model ran in production.
