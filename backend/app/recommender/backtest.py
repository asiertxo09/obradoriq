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
from app.recommender.production import naive_quantity, recommend_production
from app.recommender.types import BacktestResult, ProductInfo, SaleObservation


def _profit(qty: int, demand: int, price: float, unit_cost: float) -> float:
    """Realised profit: revenue on units sold minus the cost of everything baked."""
    return price * min(demand, qty) - unit_cost * qty


class DayRecord:
    __slots__ = ("date", "sold", "sold_out", "waste", "demand", "rainy", "holiday")

    def __init__(self, date: dt.date, sold: int, sold_out: bool, waste: int,
                 demand: int | None = None, rainy: bool = False, holiday: bool = False):
        self.date = date
        self.sold = sold
        self.sold_out = sold_out
        self.waste = waste
        # True uncensored demand for evaluation. Defaults to sold when unknown
        # (correct on non-sold-out days, where everyone who wanted one got one).
        self.demand = demand if demand is not None else sold
        self.rainy = rainy
        self.holiday = holiday

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
    mape_naive_terms: list[float] = []
    ctx_terms: list[float] = []        # weather-aware error on rainy/holiday days
    ctx_naive_terms: list[float] = []  # weather-naive error on those same days

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
                SaleObservation(d.date, d.sold, d.sold_out, d.rainy, d.holiday)
                for d in days[:idx]
            ]
            f = forecast(product.product_id, 0, today.date, history,
                         target_rainy=today.rainy, target_holiday=today.holiday)
            # Weather-naive comparison: ignore the target day's conditions.
            f_naive = forecast(product.product_id, 0, today.date, history)

            recent = days[max(0, idx - 14):idx]
            prod_sum = sum(d.production for d in recent) or 1
            waste_rate = sum(d.waste for d in recent) / prod_sum
            sold_out_recently = any(d.sold_out for d in days[max(0, idx - 7):idx])

            rec = recommend_production(
                f, product, waste_rate, sold_out_recently, risk_preference
            )
            naive_qty = naive_quantity(f, product)

            # Evaluate against TRUE demand (simulation ground truth). Crucially this
            # includes days where demand exceeds what was baked, so the availability
            # buffer's captured sales are counted, not just its extra waste.
            demand = today.demand
            baseline_qty = today.production
            uc, price = product.unit_waste_cost, product.price
            result.days_evaluated += 1

            # waste per strategy (leftover = qty over true demand)
            result.baseline_waste_units += max(0, baseline_qty - demand)
            result.naive_waste_units += max(0, naive_qty - demand)
            result.model_waste_units += max(0, rec.recommended_qty - demand)
            result.baseline_waste_eur += max(0, baseline_qty - demand) * uc
            result.naive_waste_eur += max(0, naive_qty - demand) * uc
            result.model_waste_eur += max(0, rec.recommended_qty - demand) * uc

            # profit per strategy (revenue on min(qty, demand) minus cost of all baked)
            result.baseline_profit += _profit(baseline_qty, demand, price, uc)
            result.naive_profit += _profit(naive_qty, demand, price, uc)
            result.model_profit += _profit(rec.recommended_qty, demand, price, uc)

            if demand > 0:
                aware_err = abs(f.expected_demand - demand) / demand
                naive_err = abs(f_naive.expected_demand - demand) / demand
                mape_terms.append(aware_err)
                mape_naive_terms.append(naive_err)
                if today.rainy or today.holiday:
                    ctx_terms.append(aware_err)
                    ctx_naive_terms.append(naive_err)

    result.baseline_waste_eur = round(result.baseline_waste_eur, 2)
    result.naive_waste_eur = round(result.naive_waste_eur, 2)
    result.model_waste_eur = round(result.model_waste_eur, 2)
    result.baseline_profit = round(result.baseline_profit, 2)
    result.naive_profit = round(result.naive_profit, 2)
    result.model_profit = round(result.model_profit, 2)
    result.mape = round(100 * statistics.mean(mape_terms), 1) if mape_terms else 0.0
    result.mape_weather_naive = (
        round(100 * statistics.mean(mape_naive_terms), 1) if mape_naive_terms else 0.0)
    result.context_days = len(ctx_terms)
    result.mape_context = round(100 * statistics.mean(ctx_terms), 1) if ctx_terms else 0.0
    result.mape_context_naive = (
        round(100 * statistics.mean(ctx_naive_terms), 1) if ctx_naive_terms else 0.0)
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
        demand = int(row["demand"]) if row.get("demand") else None
        rainy = float(row.get("precip_mm") or 0) >= 2.0
        holiday = str(row.get("is_holiday", "")).lower() == "true"
        series[key].append(
            DayRecord(date, int(row["quantity_sold"]), row["sold_out"] == "true",
                      waste, demand, rainy, holiday)
        )
    return series, products


def main() -> None:
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")
    data_dir = os.path.abspath(data_dir)
    series, products = load_from_csv(data_dir)
    r = run_backtest(series, products)
    print("=== ObradorIQ backtest ===")
    print(f"Evaluated {r.days_evaluated} site-product-days across {r.products_evaluated} series")
    print(f"Forecast error (MAPE), all days: {r.mape}% with weather+holidays vs "
          f"{r.mape_weather_naive}% without")
    print(f"Forecast error on the {r.context_days} rainy/holiday days (where the signal "
          f"acts): {r.mape_context}% vs {r.mape_context_naive}% without\n")
    print(f"{'strategy':<22}{'waste units':>12}{'waste €':>12}{'profit €':>12}")
    print(f"{'historical baseline':<22}{r.baseline_waste_units:>12}{r.baseline_waste_eur:>12}{r.baseline_profit:>12}")
    print(f"{'naive bake-to-forecast':<22}{r.naive_waste_units:>12}{r.naive_waste_eur:>12}{r.naive_profit:>12}")
    print(f"{'newsvendor (ours)':<22}{r.model_waste_units:>12}{r.model_waste_eur:>12}{r.model_profit:>12}\n")
    print(f"WASTE AVOIDED vs baseline: {r.waste_avoided_units} units "
          f"(€{r.waste_avoided_eur}, {r.waste_avoided_pct}%)")
    print(f"PROFIT UPLIFT vs naive rule: €{r.profit_uplift_vs_naive_eur} "
          f"({r.profit_uplift_vs_naive_pct}%)")
    print(f"PROFIT UPLIFT vs baseline:   €{r.profit_uplift_vs_baseline_eur}")


if __name__ == "__main__":
    main()
