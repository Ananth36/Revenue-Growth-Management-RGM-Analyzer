"""
RGM analysis using only the Python standard library.

SQL does the joins, aggregations and even the elasticity regression.
Python registers math functions for SQLite, runs price scenarios, prints the
report and writes CSVs plus an HTML dashboard.

Questions answered (the same ones a Bain CP / Retail RGM case asks):
  1. Which promotions make money, and which just give away margin?
  2. How price-sensitive is each SKU (price elasticity)?
  3. Where is there headroom to raise prices?
  4. What drove revenue growth: price, volume or mix?
"""

import csv
import math
import sqlite3
from pathlib import Path

from generate_data import PRODUCTS
from report import build_report

ROOT = Path(__file__).parent
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"


def connect(db_path: Path) -> sqlite3.Connection:
    """Open the database and teach SQLite a few math functions it may lack."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.create_function("ln", 1, math.log, deterministic=True)
    conn.create_function("sqrt", 1, math.sqrt, deterministic=True)
    return conn


def run_sql(conn: sqlite3.Connection, name: str) -> list[dict]:
    """Run sql/<name>.sql and return the rows as a list of dicts."""
    return [dict(r) for r in conn.execute((SQL_DIR / f"{name}.sql").read_text())]


# ---------------------------------------------------------------- 1. promos
def promo_by_mechanic(roi: list[dict]) -> list[dict]:
    """Roll SKU-level promo results up to promo mechanic."""
    totals: dict[str, dict] = {}
    for r in roi:
        t = totals.setdefault(r["promo_type"], {"promo_type": r["promo_type"], "events": 0,
                                                "promo_spend": 0.0, "incremental_gp": 0.0})
        t["events"] += r["events"]
        t["promo_spend"] += r["promo_spend"]
        t["incremental_gp"] += r["incremental_gp"]
    for t in totals.values():
        t["roi"] = round(t["incremental_gp"] / t["promo_spend"], 2)
    return sorted(totals.values(), key=lambda t: t["roi"], reverse=True)


# ---------------------------------------------------------------- 3. pricing
def pricing_scenarios(base: list[dict], elast: list[dict], increases=(0.03, 0.05, 0.08)) -> list[dict]:
    """
    Simulate list-price increases with a constant-elasticity demand curve:
        new_units = units * (1 + increase) ** elasticity
    and report the % change in gross profit for each scenario.
    """
    e_by_id = {e["product_id"]: e["elasticity"] for e in elast}
    out = []
    for b in base:
        e = e_by_id[b["product_id"]]
        row = {"sku": b["sku"], "category": b["category"], "tier": b["tier"],
               "current_price": b["current_price"], "elasticity": e}
        best_inc, best_gp = None, 0.0
        for inc in increases:
            new_units = b["annual_units"] * (1 + inc) ** e
            new_gp = new_units * (b["current_price"] * (1 + inc) - b["unit_cost"])
            change = round((new_gp / b["annual_gp"] - 1) * 100, 1)
            row[f"gp_change_{int(inc * 100)}pct"] = change
            if change > best_gp:
                best_inc, best_gp = inc, change
        row["recommendation"] = (f"Raise price (best tested: +{int(best_inc * 100)}%)"
                                 if best_inc else "Hold price")
        out.append(row)
    return out


# ---------------------------------------------------------------- output helpers
def print_table(rows: list[dict], columns: list[str] | None = None) -> None:
    columns = columns or list(rows[0])
    fmt = lambda v: f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)
    cells = [[fmt(r[c]) for c in columns] for r in rows]
    widths = [max(len(c), *(len(row[i]) for row in cells)) for i, c in enumerate(columns)]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(v.rjust(w) if v[:1] in "-0123456789" else v.ljust(w) for v, w in zip(row, widths)))


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------- main
def run(db_path: Path) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    conn = connect(db_path)

    roi = run_sql(conn, "promo_roi")
    by_mechanic = promo_by_mechanic(roi)

    elast = run_sql(conn, "elasticity")
    for e in elast:                                # attach the true value for validation
        e["true_elasticity"] = PRODUCTS[e["product_id"] - 1][7]
    mae = sum(abs(e["elasticity"] - e["true_elasticity"]) for e in elast) / len(elast)

    pricing = pricing_scenarios(run_sql(conn, "pricing_base"), elast)
    pvm = run_sql(conn, "price_volume_mix")[0]
    conn.close()

    for name, rows in [("promo_roi_by_sku", roi), ("promo_roi_by_mechanic", by_mechanic),
                       ("elasticities", elast), ("pricing_scenarios", pricing), ("price_volume_mix", [pvm])]:
        write_csv(OUT_DIR / f"{name}.csv", rows)
    build_report(OUT_DIR / "rgm_report.html", roi, by_mechanic, elast, pricing, pvm, mae)

    line = "=" * 100
    roi_cols = ["sku", "promo_type", "uplift_pct", "promo_spend", "incremental_gp", "roi"]
    print(f"\n{line}\n1. PROMO ROI BY MECHANIC\n{line}")
    print_table(by_mechanic)
    print("\nWorst 5 SKU x promo combinations (cut these first):")
    print_table(sorted(roi, key=lambda r: r["roi"])[:5], roi_cols)
    print("\nBest 5 SKU x promo combinations (scale these):")
    print_table(sorted(roi, key=lambda r: r["roi"], reverse=True)[:5], roi_cols)

    print(f"\n{line}\n2. PRICE ELASTICITY (estimated in SQL vs true simulated value)\n{line}")
    print_table(elast, ["sku", "category", "elasticity", "std_error", "true_elasticity"])
    print(f"\nMean absolute error vs truth: {mae:.3f}  (model validation)")

    print(f"\n{line}\n3. PRICING HEADROOM (% change in gross profit for a list-price increase)\n{line}")
    print_table(pricing)

    print(f"\n{line}\n4. REVENUE BRIDGE FY25 -> FY26 (INR)\n{line}")
    for k, v in pvm.items():
        print(f"  {k:<15}{v:>15,.1f}")
    print(f"\nOutputs written to {OUT_DIR}/  (open rgm_report.html in a browser)")
