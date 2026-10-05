"""
Generate two years of synthetic weekly point-of-sale data for a fictional
Indian FMCG company and load it into SQLite.

The data has realistic patterns built in (so the analysis has something to find):
  * each SKU has a true price elasticity (stored in PRODUCTS for validation)
  * seasonality: beverages peak in summer, household/personal care at Diwali
  * three promo mechanics with different economics (TPR, DEEP, DISPLAY)
  * FY26 list-price increases and a consumer shift toward premium SKUs
"""

import math
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "rgm.db"
SEED = 42

# sku, brand, category, tier, list price FY25, unit cost, base weekly units/store, TRUE elasticity
PRODUCTS = [
    ("CrunchCo Classic Chips 90g",  "CrunchCo",     "Snacks",        "Mainstream",  40,  22, 120, -2.2),
    ("CrunchCo Baked Chips 75g",    "CrunchCo",     "Snacks",        "Premium",     60,  30,  60, -1.4),
    ("ValueBite Chips 50g",         "ValueBite",    "Snacks",        "Value",       25,  16, 150, -2.8),
    ("FizzUp Cola 500ml",           "FizzUp",       "Beverages",     "Mainstream",  45,  20, 140, -1.8),
    ("FizzUp Zero 500ml",           "FizzUp",       "Beverages",     "Premium",     50,  21,  70, -1.3),
    ("PureLeaf Iced Tea 400ml",     "PureLeaf",     "Beverages",     "Premium",     55,  24,  55, -1.1),
    ("GlowWash Face Wash 100ml",    "GlowWash",     "Personal Care", "Premium",    150,  55,  35, -0.7),
    ("GlowWash Soap 4-pack",        "GlowWash",     "Personal Care", "Mainstream", 120,  60,  50, -1.2),
    ("FreshDent Toothpaste 150g",   "FreshDent",    "Personal Care", "Mainstream",  95,  38,  65, -0.6),
    ("SparkleClean Detergent 1kg",  "SparkleClean", "Household",     "Mainstream", 210, 110,  45, -0.9),
    ("SparkleClean Dish Bar 200g",  "SparkleClean", "Household",     "Value",       35,  18,  90, -1.6),
    ("ShineFloor Cleaner 1L",       "ShineFloor",   "Household",     "Premium",    180,  75,  30, -0.8),
]

# store name, region, format, size multiplier
STORES = [
    (f"{city} {fmt} {i}", region, fmt, mult)
    for i, (city, region, fmt, mult) in enumerate([
        ("Bengaluru", "South", "Hypermarket", 2.0), ("Bengaluru", "South", "Supermarket", 1.0),
        ("Hubballi",  "South", "Supermarket", 0.8), ("Chennai",   "South", "Kirana",      0.4),
        ("Mumbai",    "West",  "Hypermarket", 2.2), ("Pune",      "West",  "Supermarket", 1.0),
        ("Ahmedabad", "West",  "Kirana",      0.5), ("Delhi",     "North", "Hypermarket", 2.1),
        ("Gurugram",  "North", "Supermarket", 1.1), ("Lucknow",   "North", "Kirana",      0.5),
        ("Kolkata",   "East",  "Supermarket", 0.9), ("Bhubaneswar", "East", "Kirana",     0.4),
    ], start=1)
]

# promo type -> (probability per store-week, discount %, extra lift from visibility)
PROMOS = {"TPR": (0.07, 0.15, 1.00), "DEEP": (0.04, 0.30, 1.00), "DISPLAY": (0.04, 0.10, 1.45)}

# FY26 list-price increase and base-demand trend by category / tier
PRICE_INCREASE = {"Snacks": 0.03, "Beverages": 0.04, "Personal Care": 0.06, "Household": 0.05}
TIER_TREND = {"Value": -0.06, "Mainstream": 0.00, "Premium": 0.12}


def seasonality(category: str, week_of_year: int) -> float:
    """Multiplicative seasonal index (April = week 1 of the Indian fiscal year)."""
    w = week_of_year
    if category == "Beverages":            # summer peak in Apr-Jun
        return 1 + 0.35 * math.exp(-((w - 8) ** 2) / 60)
    festive = 1 + 0.25 * math.exp(-((w - 30) ** 2) / 6)   # Diwali ~ late Oct / early Nov
    return festive if category in ("Household", "Personal Care") else 1 + 0.05 * math.sin(2 * math.pi * w / 52)


def build(db_path: Path = DB_PATH) -> Path:
    rng = random.Random(SEED)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript((ROOT / "sql" / "schema.sql").read_text())

    conn.executemany(
        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)",
        [(i, sku, brand, cat, tier, cost)
         for i, (sku, brand, cat, tier, _, cost, _, _) in enumerate(PRODUCTS, start=1)],
    )
    conn.executemany(
        "INSERT INTO stores VALUES (?, ?, ?, ?)",
        [(i, name, region, fmt) for i, (name, region, fmt, _) in enumerate(STORES, start=1)],
    )

    start = date(2024, 4, 1)  # FY25 starts 1 April 2024
    calendar = []
    for week_id in range(1, 105):
        fy = "FY25" if week_id <= 52 else "FY26"
        calendar.append((week_id, (start + timedelta(weeks=week_id - 1)).isoformat(), fy, (week_id - 1) % 52 + 1))
    conn.executemany("INSERT INTO calendar VALUES (?, ?, ?, ?)", calendar)

    promo_names = list(PROMOS)
    promo_probs = [PROMOS[p][0] for p in promo_names]
    rows = []
    for pid, (_, _, cat, tier, price, _, base, elasticity) in enumerate(PRODUCTS, start=1):
        for sid, (_, _, _, size) in enumerate(STORES, start=1):
            store_affinity = rng.gauss(1.0, 0.10)         # some stores like some SKUs more
            for week_id, _, fy, woy in calendar:
                year2 = fy == "FY26"
                list_price = round(price * (1 + PRICE_INCREASE[cat]) if year2 else price, 2)
                trend = 1 + TIER_TREND[tier] if year2 else 1.0

                r = rng.random()
                promo, cum = None, 0.0
                for name, p in zip(promo_names, promo_probs):
                    cum += p
                    if r < cum:
                        promo = name
                        break
                discount, visibility = (PROMOS[promo][1], PROMOS[promo][2]) if promo else (0.0, 1.0)
                net_price = round(list_price * (1 - discount), 2)

                # demand reacts to price vs the FY25 reference price -> FY26 increase costs volume
                expected = (base * size * store_affinity * trend * seasonality(cat, woy)
                            * (net_price / price) ** elasticity * visibility)
                units = max(1, int(round(expected * rng.lognormvariate(0, 0.12))))
                rows.append((week_id, sid, pid, list_price, net_price, promo, units))

    conn.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return db_path


if __name__ == "__main__":
    path = build()
    print(f"Built {path} with {len(PRODUCTS) * len(STORES) * 104:,} sales rows")
