-- Promotion ROI: did each promo create profit, or just give away margin?
--
-- Baseline = what the store would have sold WITHOUT the promo, estimated as the
-- average units of the same product in the same store during non-promo weeks
-- within +/- 4 weeks of the promo week (self-join on a time window).
--
-- incremental_gp = profit actually earned in promo weeks
--                - profit the baseline units would have earned at full price
-- roi            = incremental_gp / promo_spend  (return per rupee of discount)

WITH promo_weeks AS (
    SELECT s.*, p.unit_cost
    FROM sales s
    JOIN products p USING (product_id)
    WHERE s.promo_type IS NOT NULL
),
baseline AS (
    SELECT pw.week_id, pw.store_id, pw.product_id,
           AVG(nb.units) AS baseline_units
    FROM promo_weeks pw
    JOIN sales nb
      ON  nb.product_id = pw.product_id
      AND nb.store_id   = pw.store_id
      AND nb.promo_type IS NULL
      AND nb.week_id BETWEEN pw.week_id - 4 AND pw.week_id + 4
    GROUP BY pw.week_id, pw.store_id, pw.product_id
),
event_level AS (
    SELECT pw.product_id, pw.promo_type,
           pw.units,
           b.baseline_units,
           (pw.list_price - pw.net_price) * pw.units           AS promo_spend,
           pw.units * (pw.net_price - pw.unit_cost)             AS promo_gp,
           b.baseline_units * (pw.list_price - pw.unit_cost)    AS baseline_gp
    FROM promo_weeks pw
    JOIN baseline b USING (week_id, store_id, product_id)
)
SELECT p.category,
       p.sku,
       p.tier,
       e.promo_type,
       COUNT(*)                                        AS events,
       ROUND(SUM(e.units))                             AS promo_units,
       ROUND(SUM(e.baseline_units))                    AS baseline_units,
       ROUND(100.0 * (SUM(e.units) / SUM(e.baseline_units) - 1), 1) AS uplift_pct,
       ROUND(SUM(e.promo_spend))                       AS promo_spend,
       ROUND(SUM(e.promo_gp - e.baseline_gp))          AS incremental_gp,
       ROUND(SUM(e.promo_gp - e.baseline_gp) / SUM(e.promo_spend), 2) AS roi
FROM event_level e
JOIN products p USING (product_id)
GROUP BY p.category, p.sku, p.tier, e.promo_type
ORDER BY roi DESC;
