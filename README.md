# Revenue Growth Management (RGM) Analyzer

A Python + SQLite project that diagnoses a consumer-goods company's commercial
performance, the same way a Consumer Products / Retail consulting team would.

**No third-party packages.** It uses only Python's standard library
(`sqlite3`, `csv`, `math`, `random`, `html`), so there is nothing to `pip install`
and it runs on locked-down machines where compiled packages like pandas are blocked.

It answers four business questions over two years of weekly store-level sales
(12 SKUs x 12 stores x 104 weeks = 14,976 rows):

| # | Question | SQL does | Python does |
|---|----------|----------|-------------|
| 1 | Which promotions make money? | Promo ROI vs a ±4-week non-promo baseline (self-join on a time window) | Rolls up by mechanic, ranks best/worst |
| 2 | How price-sensitive is each SKU? | The whole regression: two-way fixed effects via window functions | Registers `ln()` / `sqrt()` for SQLite, validates against truth |
| 3 | Where can we raise prices? | FY26 full-price baseline per SKU | Simulates +3/5/8% price scenarios on gross profit |
| 4 | What drove revenue growth? | Full price-volume-mix bridge in CTEs | Waterfall chart |

## Run it

Python 3.10 or newer.

```bash
python main.py            # builds rgm.db on first run, then analyses
python main.py --rebuild  # regenerate data from scratch
```

Runs in about 2 seconds. Results print to the console and are saved in `outputs/`:
five CSVs plus `rgm_report.html`, a dashboard you open in any browser.

## Project layout

```
generate_data.py        synthetic data with known elasticities, seasonality, promos
sql/schema.sql          star schema: products, stores, calendar, sales
sql/promo_roi.sql       promo ROI with windowed baseline
sql/elasticity.sql      log-log regression with store + week fixed effects, in pure SQL
sql/pricing_base.sql    FY26 full-price baseline
sql/price_volume_mix.sql
analysis.py             scenarios, console report, CSV export
report.py               HTML dashboard with hand-drawn SVG charts
main.py                 entry point
```

You can also explore the database directly with any SQLite client (e.g. DB Browser for SQLite).

## Key findings (seed 42)

- **Display promos return ₹1.12 of profit per ₹1 of discount; TPR (−0.34) and deep
  discounts (−0.36) destroy value.** Shift budget from deep cuts to display.
- **The SQL regression recovers the true elasticities within 0.04 on average**, which
  validates the method (the data was simulated with known elasticities).
- **9 of 12 SKUs can take a price increase profitably.** Mass-market chips, value
  chips and cola are too price-sensitive; hold their price.
- **Revenue grew 3.1%: price (+₹0.20 Cr) and premium mix (+₹0.11 Cr) offset a
  volume decline (−₹0.18 Cr).** Growth is price-led, so volume is the risk to watch.

## Notes and limitations

- Data is synthetic (fictional brands) so the "true" answers are known and the
  model can be checked against them.
- Promo baseline ignores pantry-loading (post-promo dip), so promo ROI is slightly
  flattering. Adding a post-promo window is a natural next step.
- Price scenarios assume constant elasticity and no competitor reaction.
- "Best tested" price increase is the best of the scenarios run, not an optimum.
- Two-way demeaning is exact only for a balanced panel; excluding DISPLAY weeks makes
  it slightly unbalanced, which the validation shows has negligible effect here.
