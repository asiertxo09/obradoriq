"""Generate a deterministic 2-site, 10-week synthetic bakery-chain dataset.

Story baked into the data: the chain ("Obrador Demo") has two shops.
  - Centro (busy downtown) UNDER-produces "Almond Croissant" -> frequent sell-outs.
  - Barrio (quiet residential) OVER-produces "Almond Croissant" -> chronic waste.
That imbalance is exactly what the plan-level reallocation engine should catch:
shift planned Almond Croissant production Barrio -> Centro.

Other products carry a mild habitual over-production so the backtest can show the
forecast trimming waste.

Outputs CSVs into this directory: sites.csv, products.csv, sales.csv, waste.csv.
On a non-sold-out day, quantity_sold == demand (leftovers prove demand was met),
which the backtest uses as ground-truth demand.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import random

SEED = 20260629
random.seed(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = 70
END_DATE = dt.date(2026, 6, 28)
START_DATE = END_DATE - dt.timedelta(days=DAYS - 1)

SITES = [
    {"name": "Centro", "location": "Downtown"},
    {"name": "Barrio", "location": "Residential"},
]

# Latent demand effects the baker can't predict from the calendar alone.
RAIN_EFFECT = 0.82       # rainy days lose foot traffic
HOLIDAY_EFFECT = 1.35    # holidays are busier
# Public / regional / bridge days in the window (Spain) — enough history for the model
# to learn a holiday elasticity before the evaluation window.
HOLIDAYS = {
    dt.date(2026, 4, 23),  # Sant Jordi
    dt.date(2026, 5, 1),   # Labour Day
    dt.date(2026, 5, 15),  # local festa major
    dt.date(2026, 6, 1),   # bridge day
    dt.date(2026, 6, 24),  # Sant Joan (falls in the eval window)
}

# weekday_profile: multipliers Mon..Sun (0=Mon). base = average weekday demand at a typical site.
PRODUCTS = [
    {"name": "Croissant", "category": "Viennoiserie", "price": 1.80, "ingredient_cost": 0.55,
     "batch_size": 6, "base": 60, "weekday": [1.0, 1.0, 1.0, 1.05, 1.2, 1.5, 1.4]},
    {"name": "Pain au Chocolat", "category": "Viennoiserie", "price": 2.10, "ingredient_cost": 0.70,
     "batch_size": 6, "base": 45, "weekday": [1.0, 1.0, 1.0, 1.05, 1.25, 1.5, 1.4]},
    {"name": "Baguette", "category": "Bread", "price": 1.20, "ingredient_cost": 0.30,
     "batch_size": 10, "base": 80, "weekday": [1.1, 1.05, 1.05, 1.1, 1.3, 1.4, 1.2]},
    {"name": "Sourdough", "category": "Bread", "price": 4.50, "ingredient_cost": 1.10,
     "batch_size": 4, "base": 24, "weekday": [0.9, 0.9, 1.0, 1.0, 1.2, 1.5, 1.3]},
    {"name": "Cinnamon Roll", "category": "Pastry", "price": 2.80, "ingredient_cost": 0.85,
     "batch_size": 6, "base": 30, "weekday": [0.8, 0.85, 0.9, 1.0, 1.2, 1.6, 1.5]},
    {"name": "Almond Croissant", "category": "Viennoiserie", "price": 2.60, "ingredient_cost": 0.95,
     "batch_size": 6, "base": 28, "weekday": [0.9, 0.9, 1.0, 1.05, 1.2, 1.5, 1.4]},
]

# Per-site demand multipliers; Centro busier than Barrio overall.
SITE_DEMAND = {"Centro": 1.30, "Barrio": 0.80}

# Habitual production factor relative to mean demand (the baker's gut).
# Default slight over-production; the engineered story overrides Almond Croissant.
HABITUAL = {
    ("Centro", "Almond Croissant"): 0.80,   # under-produce -> sells out
    ("Barrio", "Almond Croissant"): 1.85,   # over-produce  -> chronic waste
}
DEFAULT_HABITUAL = 1.15


def round_to_batch(x: float, batch: int) -> int:
    return max(batch, int(round(x / batch)) * batch)


def main() -> None:
    sales_rows = []
    waste_rows = []

    # City-wide weather, shared by both sites: ~30% of days rainy.
    precip_by_day = {}
    for i in range(DAYS):
        day = START_DATE + dt.timedelta(days=i)
        precip_by_day[day] = round(random.uniform(2, 16), 1) if random.random() < 0.30 else 0.0

    for site in SITES:
        sname = site["name"]
        for p in PRODUCTS:
            mean_demand = p["base"] * SITE_DEMAND[sname]
            factor = HABITUAL.get((sname, p["name"]), DEFAULT_HABITUAL)
            production = round_to_batch(mean_demand * factor, p["batch_size"])
            for i in range(DAYS):
                day = START_DATE + dt.timedelta(days=i)
                wd = day.weekday()
                precip = precip_by_day[day]
                rainy = precip >= 2.0
                holiday = day in HOLIDAYS
                # demand = mean * weekday * trend * noise * weather * holiday
                trend = 1.0 + 0.0015 * i  # slight growth over the 10 weeks
                noise = random.gauss(1.0, 0.12)
                weather = RAIN_EFFECT if rainy else 1.0
                hol = HOLIDAY_EFFECT if holiday else 1.0
                demand = max(0, mean_demand * p["weekday"][wd] * trend * noise * weather * hol)
                demand = int(round(demand))
                sold = min(demand, production)
                sold_out = demand > production
                waste = max(0, production - demand)
                # `demand` is the UNCENSORED true demand — used only as backtest ground
                # truth. The model never reads it (it trains on quantity_sold + sold_out).
                sales_rows.append({
                    "site": sname, "product": p["name"], "date": day.isoformat(),
                    "quantity_sold": sold, "revenue": round(sold * p["price"], 2),
                    "sold_out": "true" if sold_out else "false", "demand": demand,
                    "precip_mm": precip, "is_holiday": "true" if holiday else "false",
                })
                if waste > 0:
                    waste_rows.append({
                        "site": sname, "product": p["name"], "date": day.isoformat(),
                        "quantity_wasted": waste,
                    })

    _write("sites.csv", ["name", "location"], SITES)
    _write("products.csv",
           ["name", "category", "price", "ingredient_cost", "batch_size"],
           [{k: p[k] for k in ["name", "category", "price", "ingredient_cost", "batch_size"]}
            for p in PRODUCTS])
    _write("sales.csv",
           ["site", "product", "date", "quantity_sold", "revenue", "sold_out", "demand",
            "precip_mm", "is_holiday"],
           sales_rows)
    _write("waste.csv", ["site", "product", "date", "quantity_wasted"], waste_rows)

    print(f"Wrote {len(sales_rows)} sales rows and {len(waste_rows)} waste rows "
          f"for {len(SITES)} sites x {len(PRODUCTS)} products over {DAYS} days.")


def _write(name: str, fields: list[str], rows: list[dict]) -> None:
    path = os.path.join(HERE, name)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
