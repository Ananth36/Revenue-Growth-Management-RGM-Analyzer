-- FY26 full-price baseline per SKU: the starting point for price-increase scenarios.

SELECT p.product_id,
       p.sku,
       p.category,
       p.tier,
       p.unit_cost,
       ROUND(AVG(s.list_price), 2)            AS current_price,
       SUM(s.units)                            AS annual_units,
       ROUND(SUM(s.units * s.list_price))      AS annual_revenue,
       ROUND(SUM(s.units * (s.list_price - p.unit_cost))) AS annual_gp
FROM sales s
JOIN products p USING (product_id)
JOIN calendar c USING (week_id)
WHERE c.fiscal_year = 'FY26'
  AND s.promo_type IS NULL
GROUP BY p.product_id
ORDER BY p.product_id;
