-- Revenue Growth Management (RGM) star schema
-- One fact table (sales) surrounded by dimension tables.

DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS calendar;

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    sku          TEXT    NOT NULL,
    brand        TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    tier         TEXT    NOT NULL CHECK (tier IN ('Value', 'Mainstream', 'Premium')),
    unit_cost    REAL    NOT NULL           -- cost of goods per unit (INR)
);

CREATE TABLE stores (
    store_id     INTEGER PRIMARY KEY,
    store_name   TEXT    NOT NULL,
    region       TEXT    NOT NULL,
    format       TEXT    NOT NULL           -- Hypermarket / Supermarket / Kirana
);

CREATE TABLE calendar (
    week_id      INTEGER PRIMARY KEY,       -- 1..104
    week_start   TEXT    NOT NULL,          -- ISO date
    fiscal_year  TEXT    NOT NULL,          -- 'FY25' / 'FY26'
    week_of_year INTEGER NOT NULL
);

CREATE TABLE sales (
    week_id      INTEGER NOT NULL REFERENCES calendar(week_id),
    store_id     INTEGER NOT NULL REFERENCES stores(store_id),
    product_id   INTEGER NOT NULL REFERENCES products(product_id),
    list_price   REAL    NOT NULL,          -- shelf price before discount
    net_price    REAL    NOT NULL,          -- price actually paid
    promo_type   TEXT,                      -- NULL = no promo; TPR / DEEP / DISPLAY
    units        INTEGER NOT NULL,
    PRIMARY KEY (week_id, store_id, product_id)
);

CREATE INDEX idx_sales_product_store ON sales(product_id, store_id, week_id);
CREATE INDEX idx_sales_promo         ON sales(promo_type);
