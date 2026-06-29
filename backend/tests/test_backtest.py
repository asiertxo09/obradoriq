"""Backtest harness tests — hermetic (no dependency on data/ files)."""
from __future__ import annotations

import datetime as dt

from app.recommender.backtest import DayRecord, run_backtest
from app.recommender.types import ProductInfo

ROLL = ProductInfo(product_id=1, name="Roll", batch_size=6, price=2.0, ingredient_cost=0.8)


def _series_overproducing(days: int = 60, demand: int = 30, production: int = 48):
    """A site that habitually bakes `production` for steady `demand` -> chronic waste."""
    start = dt.date(2026, 1, 1)
    recs = []
    for i in range(days):
        sold = demand  # steady, never sells out
        waste = production - sold
        recs.append(DayRecord(start + dt.timedelta(days=i), sold, False, waste))
    return {("Roll", "Centro"): recs}


def test_backtest_reduces_waste_against_overproducing_baseline():
    series = _series_overproducing()
    r = run_backtest(series, {"Roll": ROLL}, eval_days=21)
    assert r.days_evaluated > 0
    assert r.baseline_waste_units > 0
    # Forecast tracks the steady demand, so the model wastes far less than the baseline.
    assert r.model_waste_units < r.baseline_waste_units
    assert r.waste_avoided_eur > 0
    assert r.waste_avoided_pct > 50


HIGH_MARGIN = ProductInfo(product_id=2, name="Cake", batch_size=1, price=10.0, ingredient_cost=1.0)


def _series_volatile(days: int = 70, base: int = 50, swing: int = 12):
    """Demand alternates by week (so same-weekday history has real variance), and the
    baker bakes to the mean. A high-margin product should profit from an availability
    buffer on the high weeks."""
    start = dt.date(2026, 1, 5)  # a Monday
    recs = []
    for i in range(days):
        week = i // 7
        demand = base + (swing if week % 2 == 0 else -swing)
        production = base  # baseline bakes to the mean
        sold = min(demand, production)
        recs.append(DayRecord(start + dt.timedelta(days=i), sold,
                              demand > production, max(0, production - demand), demand))
    return {("Cake", "Centro"): recs}


def test_newsvendor_beats_naive_on_high_margin_volatile_demand():
    r = run_backtest(_series_volatile(), {"Cake": HIGH_MARGIN},
                     risk_preference="availability", eval_days=21)
    assert r.model_profit > r.naive_profit
    assert r.profit_uplift_vs_naive_eur > 0


def test_backtest_reproducible():
    series = _series_overproducing()
    r1 = run_backtest(series, {"Roll": ROLL}, eval_days=21)
    r2 = run_backtest(series, {"Roll": ROLL}, eval_days=21)
    assert r1.waste_avoided_units == r2.waste_avoided_units
    assert r1.mape == r2.mape
