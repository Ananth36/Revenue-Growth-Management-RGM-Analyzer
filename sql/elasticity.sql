-- Price elasticity per SKU, estimated entirely in SQL.
--
-- Model (log-log regression with store and week fixed effects):
--     ln(units) = elasticity * ln(price) + store effect + week effect + noise
--
-- How: "two-way demeaning". For every observation subtract its store average and
-- its week average, then add back the overall average. This strips out store size
-- and seasonality, leaving only price-driven variation. The slope of the demeaned
-- y on demeaned x is then simply SUM(x*y) / SUM(x*x).
--
-- ln() and sqrt() are Python functions registered on the connection (see analysis.py).
-- DISPLAY promos are excluded: their extra volume comes from visibility, not price.

WITH obs AS (
    SELECT product_id, store_id, week_id,
           ln(net_price) AS x,
           ln(units)     AS y
    FROM sales
    WHERE promo_type IS NULL OR promo_type <> 'DISPLAY'
),
demeaned AS (
    SELECT product_id,
           x - AVG(x) OVER (PARTITION BY product_id, store_id)
             - AVG(x) OVER (PARTITION BY product_id, week_id)
             + AVG(x) OVER (PARTITION BY product_id)            AS xd,
           y - AVG(y) OVER (PARTITION BY product_id, store_id)
             - AVG(y) OVER (PARTITION BY product_id, week_id)
             + AVG(y) OVER (PARTITION BY product_id)            AS yd
    FROM obs
),
fit AS (
    SELECT product_id,
           SUM(xd * yd) / SUM(xd * xd) AS beta,
           SUM(xd * xd)                AS sxx,
           COUNT(*)                    AS n
    FROM demeaned
    GROUP BY product_id
)
SELECT p.product_id,
       p.sku,
       p.category,
       ROUND(f.beta, 2) AS elasticity,
       ROUND(sqrt(SUM((d.yd - f.beta * d.xd) * (d.yd - f.beta * d.xd)) / (f.n - 2) / f.sxx), 3) AS std_error
FROM demeaned d
JOIN fit f      USING (product_id)
JOIN products p USING (product_id)
GROUP BY p.product_id
ORDER BY p.product_id;
