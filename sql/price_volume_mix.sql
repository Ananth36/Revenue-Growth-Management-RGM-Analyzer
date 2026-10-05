-- Price / Volume / Mix bridge: why did revenue change from FY25 to FY26?
--
--   price  = sum over SKUs of (avg price FY26 - avg price FY25) * units FY26
--   volume = (total units FY26 - total units FY25) * portfolio avg price FY25
--   mix    = revenue from selling FY26 units at FY25 SKU prices
--            - revenue if those units had the FY25 portfolio-average price
--   price + volume + mix = revenue FY26 - revenue FY25 (exactly)

WITH sku_year AS (
    SELECT s.product_id,
           c.fiscal_year,
           SUM(s.units)               AS units,
           SUM(s.units * s.net_price) AS revenue
    FROM sales s
    JOIN calendar c USING (week_id)
    GROUP BY s.product_id, c.fiscal_year
),
sku AS (
    SELECT product_id,
           MAX(CASE WHEN fiscal_year = 'FY25' THEN units   END) AS u1,
           MAX(CASE WHEN fiscal_year = 'FY25' THEN revenue END) AS r1,
           MAX(CASE WHEN fiscal_year = 'FY26' THEN units   END) AS u2,
           MAX(CASE WHEN fiscal_year = 'FY26' THEN revenue END) AS r2
    FROM sku_year
    GROUP BY product_id
),
portfolio AS (
    SELECT SUM(u1) AS U1, SUM(r1) AS R1, SUM(u2) AS U2, SUM(r2) AS R2,
           SUM(r1) * 1.0 / SUM(u1)                 AS P1_avg,
           SUM(u2 * (r1 * 1.0 / u1))               AS R2_at_P1,
           SUM((r2 * 1.0 / u2 - r1 * 1.0 / u1) * u2) AS price_effect
    FROM sku
)
SELECT ROUND(R1)                              AS revenue_fy25,
       ROUND((U2 - U1) * P1_avg)              AS volume_effect,
       ROUND(R2_at_P1 - U2 * P1_avg)          AS mix_effect,
       ROUND(price_effect)                    AS price_effect,
       ROUND(R2)                              AS revenue_fy26,
       ROUND(100.0 * (R2 / R1 - 1), 1)        AS growth_pct
FROM portfolio;
