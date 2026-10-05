"""
Build a self-contained HTML report with SVG charts, using only the standard library.
Open outputs/rgm_report.html in any browser.
"""

from html import escape
from pathlib import Path

GREEN, RED, BLUE, GREY, DARK = "#2e7d32", "#c62828", "#1565c0", "#b0bec5", "#37474f"


def _svg(width: int, height: int, body: list[str]) -> str:
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Arial, sans-serif" font-size="12">'
            + "".join(body) + "</svg>")


def _text(x, y, s, anchor="middle", weight="normal", size=12, color="#222") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-weight="{weight}" '
            f'font-size="{size}" fill="{color}">{escape(str(s))}</text>')


def _rect(x, y, w, h, color) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" fill="{color}"/>'


def _line(x1, y1, x2, y2, color="#222", dash="", width=1) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{d}/>'


# ---------------------------------------------------------------- charts
def promo_chart(by_mechanic: list[dict]) -> str:
    W, H, top, bottom, left = 420, 320, 20, 40, 50
    vals = [r["roi"] for r in by_mechanic]
    lo, hi = min(min(vals) * 1.3, -0.2), max(max(vals) * 1.2, 0.2)
    y = lambda v: top + (hi - v) / (hi - lo) * (H - top - bottom)
    slot = (W - left - 10) / len(vals)
    body = [_line(left, y(0), W - 10, y(0))]
    for t in (lo, 0, hi):
        body.append(_text(left - 6, y(t) + 4, f"{t:+.1f}", anchor="end", size=10, color="#666"))
    for i, r in enumerate(by_mechanic):
        x = left + i * slot + slot * 0.2
        v = r["roi"]
        body.append(_rect(x, min(y(v), y(0)), slot * 0.6, abs(y(v) - y(0)), GREEN if v > 0 else RED))
        body.append(_text(x + slot * 0.3, y(v) - 6 if v > 0 else y(v) + 16, f"{v:+.2f}", weight="bold"))
        body.append(_text(x + slot * 0.3, H - 15, r["promo_type"]))
    return _svg(W, H, body)


def elasticity_chart(elast: list[dict]) -> str:
    rows = sorted(elast, key=lambda r: r["elasticity"], reverse=True)
    W, row_h, top, left, right = 400, 22, 30, 140, 12
    H = top + row_h * len(rows) + 30
    lo, hi = -3.0, 0.0
    x = lambda v: left + (v - lo) / (hi - lo) * (W - left - right)
    body = []
    for t in (-3, -2, -1, 0):
        body.append(_line(x(t), top - 5, x(t), H - 25, "#ddd"))
        body.append(_text(x(t), H - 10, t, size=10, color="#666"))
    body.append(_line(x(-1), top - 5, x(-1), H - 25, RED, dash="4 3"))
    for i, r in enumerate(rows):
        yc = top + i * row_h
        e, se = r["elasticity"], r["std_error"]
        body.append(_rect(x(e), yc + 3, x(0) - x(e), row_h - 8, BLUE if e > -1 else GREY))
        body.append(_line(x(e - 1.96 * se), yc + row_h / 2 - 1, x(e + 1.96 * se), yc + row_h / 2 - 1, "#222"))
        body.append(_line(x(r["true_elasticity"]), yc, x(r["true_elasticity"]), yc + row_h - 2, "#000", width=2.5))
        body.append(_text(left - 6, yc + row_h / 2 + 4, r["sku"].rsplit(" ", 1)[0], anchor="end", size=11))
    body.append(_text(W / 2, 14, "Bar = estimate ± 95% CI  ·  black tick = true value", size=11, color="#666"))
    return _svg(W, H, body)


def waterfall_chart(pvm: dict) -> str:
    cr = {k: v / 1e7 for k, v in pvm.items() if k != "growth_pct"}   # INR -> crore
    steps = [("FY25", cr["revenue_fy25"], True), ("Volume", cr["volume_effect"], False),
             ("Mix", cr["mix_effect"], False), ("Price", cr["price_effect"], False),
             ("FY26", cr["revenue_fy26"], True)]
    W, H, top, bottom, left = 420, 320, 30, 40, 50
    lo = min(cr["revenue_fy25"], cr["revenue_fy26"]) * 0.88
    hi = max(cr["revenue_fy25"], cr["revenue_fy26"]) * 1.04
    y = lambda v: top + (hi - v) / (hi - lo) * (H - top - bottom)
    slot = (W - left - 10) / len(steps)
    body, running = [], 0.0
    for i, (label, val, total) in enumerate(steps):
        bx = left + i * slot + slot * 0.15
        if total:
            body.append(_rect(bx, y(val), slot * 0.7, y(lo) - y(val), DARK))
            body.append(_text(bx + slot * 0.35, y(val) - 6, f"₹{val:.2f} Cr", weight="bold"))
            running = val
        else:
            a, b = running, running + val
            body.append(_rect(bx, y(max(a, b)), slot * 0.7, abs(y(a) - y(b)), GREEN if val >= 0 else RED))
            body.append(_text(bx + slot * 0.35, y(max(a, b)) - 6, f"{val:+.2f}"))
            running = b
        body.append(_text(bx + slot * 0.35, H - 15, label))
    return _svg(W, H, body)


# ---------------------------------------------------------------- tables
def html_table(rows: list[dict], columns: list[str] | None = None) -> str:
    columns = columns or list(rows[0])
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body = ""
    for r in rows:
        cells = ""
        for c in columns:
            v = r[c]
            cls = ' class="num"' if isinstance(v, (int, float)) else ""
            if isinstance(v, (int, float)) and v < 0 and c != "elasticity":   # elasticity is always negative
                cls = ' class="num neg"'
            cells += f"<td{cls}>{escape(f'{v:,.2f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v))}</td>"
        body += f"<tr>{cells}</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_report(path: Path, roi, by_mechanic, elast, pricing, pvm, mae) -> None:
    worst = sorted(roi, key=lambda r: r["roi"])[:5]
    best = sorted(roi, key=lambda r: r["roi"], reverse=True)[:5]
    roi_cols = ["sku", "promo_type", "uplift_pct", "promo_spend", "incremental_gp", "roi"]
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RGM Diagnostic</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 0; background: #f5f6f8; color: #222; }}
  header {{ background: #263238; color: #fff; padding: 22px 32px; }}
  header h1 {{ margin: 0; font-size: 22px; }}
  header p {{ margin: 6px 0 0; color: #b0bec5; }}
  main {{ max-width: 1200px; margin: 0 auto; padding: 24px 16px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 16px; }}
  .card h2 {{ font-size: 16px; margin: 0 0 4px; }}
  .card .so-what {{ color: #555; font-size: 13px; margin: 0 0 12px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  th, td {{ padding: 6px 8px; border-bottom: 1px solid #eee; text-align: left; }}
  th {{ background: #fafafa; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.neg {{ color: {RED}; }}
  .scroll {{ overflow-x: auto; }}
</style></head><body>
<header><h1>Revenue Growth Management diagnostic: FY25 vs FY26</h1>
<p>12 SKUs · 12 stores · 104 weeks · SQLite + Python standard library</p></header>
<main>
<div class="grid">
  <div class="card"><h2>Promo ROI by mechanic</h2>
    <p class="so-what">Incremental profit per ₹1 of discount. Below zero = the promo destroys value.</p>
    {promo_chart(by_mechanic)}</div>
  <div class="card"><h2>Price elasticity by SKU</h2>
    <p class="so-what">Blue (right of −1) = inelastic → room to raise price. Mean error vs truth: {mae:.3f}.</p>
    {elasticity_chart(elast)}</div>
  <div class="card"><h2>Revenue bridge (₹ crore)</h2>
    <p class="so-what">Growth {pvm['growth_pct']:+.1f}%, split into volume, mix and price effects.</p>
    {waterfall_chart(pvm)}</div>
</div>
<div class="card"><h2>Promos to cut (worst 5 SKU × mechanic)</h2><div class="scroll">{html_table(worst, roi_cols)}</div></div>
<div class="card"><h2>Promos to scale (best 5 SKU × mechanic)</h2><div class="scroll">{html_table(best, roi_cols)}</div></div>
<div class="card"><h2>Pricing headroom</h2>
  <p class="so-what">% change in gross profit if list price rises by 3 / 5 / 8%, using the estimated elasticity.</p>
  <div class="scroll">{html_table(pricing)}</div></div>
</main></body></html>"""
    path.write_text(html, encoding="utf-8")
