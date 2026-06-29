"""Backtest harness — quantifies waste avoided vs the bakery's historical baseline.

Walk-forward: for each evaluation day, forecast from strictly-prior history, compute
the recommended production, and compare predicted leftover against what the bakery
actually binned. On non-sold-out days the true demand equals units sold (there were
leftovers, so everyone who wanted one got one).

This produces the submission's headline metric: € and % of waste the model would
have avoided. Pure Python; deterministic given the same data.
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import statistics
from collections import defaultdict

from app.recommender.forecast import forecast
from app.recommender.production import recommend_production
from app.recommender.types import BacktestResult, ProductInfo, SaleObservation


class DayRecord:
    __slots__ = ("date", "sold", "sold_out", "waste")

    def __init__(self, date: dt.date, sold: int, sold_out: bool, waste: int):
        self.date = date
        self.sold = sold
        self.sold_out = sold_out
        self.waste = waste

    @property
    def production(self) -> int:
        return self.sold + self.waste


def run_backtest(
    series: dict[tuple[str, str], list[DayRecord]],
    products: dict[str, ProductInfo],
    risk_preference: str = "waste",
    eval_days: int = 21,
) -> BacktestResult:
    """series keyed by (product_name, site_name) -> chronological DayRecords."""
    result = BacktestResult()
    mape_terms: list[float] = []

    for (pname, sname), days in series.items():
        product = products[pname]
        days = sorted(days, key=lambda d: d.date)
        if len(days) <= eval_days + 14:
            continue
        result.products_evaluated += 1
        split = len(days) - eval_days

        for idx in range(split, len(days)):
            today = days[idx]
            history = [
                SaleObservation(d.date, d.sold, d.sold_out) for d in days[:idx]
            ]
            f = forecast(product.product_id, 0, today.date, history)

            recent = days[max(0, idx - 14):idx]
            prod_sum = sum(d.production for d in recent) or 1
            waste_rate = sum(d.waste for d in recent) / prod_sum
            sold_out_recently = any(d.sold_out for d in days[max(0, idx - 7):idx])

            rec = recommend_production(
                f, product, waste_rate, sold_out_recently, risk_preference
            )

            # Ground truth demand only known on non-sold-out days.
            if today.sold_out:
                continue
            demand = today.sold
            result.days_evaluated += 1
            result.baseline_waste_units += today.waste
            result.model_waste_units += max(0, rec.recommended_qty - demand)
            result.baseline_waste_eur += today.waste * product.unit_waste_cost
            result.model_waste_eur += (
                max(0, rec.recommended_qty - demand) * product.unit_waste_cost
            )
            if demand > 0:
                mape_terms.append(abs(f.expected_demand - demand) / demand)

    result.baseline_waste_eur = round(result.baseline_waste_eur, 2)
    result.model_waste_eur = round(result.model_waste_eur, 2)
    result.mape = round(100 * statistics.mean(mape_terms), 1) if mape_terms else 0.0
    return result


# ---- CSV loading (for the standalone harness / demo) ----
def load_from_csv(data_dir: str) -> tuple[dict, dict]:
    products: dict[str, ProductInfo] = {}
    for i, row in enumerate(csv.DictReader(open(os.path.join(data_dir, "products.csv"))), 1):
        products[row["name"]] = ProductInfo(
            product_id=i, name=row["name"], batch_size=int(row["batch_size"]),
            price=float(row["price"]), ingredient_cost=float(row["ingredient_cost"]),
        )

    waste_lookup: dict[tuple, int] = {}
    for row in csv.DictReader(open(os.path.join(data_dir, "waste.csv"))):
        waste_lookup[(row["product"], row["site"], row["date"])] = int(row["quantity_wasted"])

    series: dict[tuple[str, str], list[DayRecord]] = defaultdict(list)
    for row in csv.DictReader(open(os.path.join(data_dir, "sales.csv"))):
        key = (row["product"], row["site"])
        date = dt.date.fromisoformat(row["date"])
        waste = waste_lookup.get((row["product"], row["site"], row["date"]), 0)
        series[key].append(
            DayRecord(date, int(row["quantity_sold"]), row["sold_out"] == "true", waste)
        )
    return series, products


def main() -> None:
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    data_dir = os.path.abspath(data_dir)
    series, products = load_from_csv(data_dir)
    r = run_backtest(series, products)
    print("=== ObradorIQ backtest (forecast vs the bakery's own baseline) ===")
    print(f"Evaluated {r.days_evaluated} site-product-days across {r.products_evaluated} series")
    print(f"Forecast error (MAPE): {r.mape}%")
    print(f"Baseline waste: {r.baseline_waste_units} units (€{r.baseline_waste_eur})")
    print(f"Model waste:    {r.model_waste_units} units (€{r.model_waste_eur})")
    print(f"WASTE AVOIDED:  {r.waste_avoided_units} units "
          f"(€{r.waste_avoided_eur}, {r.waste_avoided_pct}%)")


if __name__ == "__main__":
    main()
