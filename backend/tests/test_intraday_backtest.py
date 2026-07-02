"""Intraday backtest harness tests — hermetic (no DB, no dependency on data/ files)."""
from __future__ import annotations

import datetime as dt

from app.recommender.intraday import CLOSE_HOUR, OPEN_HOUR
from app.recommender.intraday_backtest import (
    DECISION_HOUR,
    IntradayDayRecord,
    evaluate_intraday_day,
    run_intraday_backtest,
)
from app.recommender.types import ProductInfo, SiteCapability, SiteState

CROISSANT = ProductInfo(product_id=1, name="Croissant", batch_size=12, price=2.0,
                         ingredient_cost=0.6)
START = dt.date(2026, 6, 1)


def _flat_day(units_per_hour: int, date: dt.date, waste: int = 8,
              sold_out: bool = False) -> IntradayDayRecord:
    counts = {h: units_per_hour for h in range(OPEN_HOUR, CLOSE_HOUR)}
    return IntradayDayRecord(date=date, hourly_counts=counts, waste=waste, sold_out=sold_out)


def _habitual_history(n: int = 5, units_per_hour: int = 10, waste: int = 8):
    """`n` typical prior days -> a learned (non-default) pace curve."""
    return [_flat_day(units_per_hour, START + dt.timedelta(days=i), waste) for i in range(n)]


# --------------------------------------------------------------- HOT -> bake_more

def test_hot_pace_yields_bake_more_with_positive_recovered_eur():
    prior = _habitual_history()  # habitual production = 130 sold + 8 waste = 138/day
    today_date = START + dt.timedelta(days=len(prior))
    # By 11:00, way more has sold than the habitual pace implies; the site sells out
    # of everything it baked (censored demand -> true demand exceeds on_hand).
    hot_hours = {7: 10, 8: 15, 9: 20, 10: 25, 11: 18, 12: 15, 13: 12, 14: 12, 15: 6, 16: 3}
    today = IntradayDayRecord(date=today_date, hourly_counts=hot_hours, waste=0, sold_out=True)

    ev = evaluate_intraday_day(CROISSANT, site_id=1, day=today, prior_days=prior)

    assert ev.action in ("bake_more", "move")
    assert ev.action_qty > 0
    assert ev.eur_recovered > 0
    # true demand (uncensored) must exceed on_hand for this to be a genuine shortfall
    assert today.true_demand > today.production


def test_hot_pace_moves_when_bake_off_unavailable_but_surplus_sibling_exists():
    prior = _habitual_history()
    today_date = START + dt.timedelta(days=len(prior))
    hot_hours = {7: 10, 8: 15, 9: 20, 10: 25, 11: 18, 12: 15, 13: 12, 14: 12, 15: 6, 16: 3}
    today = IntradayDayRecord(date=today_date, hourly_counts=hot_hours, waste=0, sold_out=True)
    siblings = [
        SiteState(site_id=2, forecast_demand=50, planned_production=95,
                  sold_out_rate=0.0, confidence="HIGH"),  # ample surplus
    ]

    ev = evaluate_intraday_day(
        CROISSANT, site_id=1, day=today, prior_days=prior,
        capability=SiteCapability(can_bake_off=False, can_move=True),
        sibling_states=siblings,
    )

    assert ev.action == "move"
    assert ev.signal.from_site_id == 2
    assert ev.action_qty > 0
    assert ev.eur_recovered > 0


# -------------------------------------------------------------- COLD -> markdown

def test_cold_pace_yields_markdown_with_positive_cleared_eur():
    prior = _habitual_history()
    today_date = START + dt.timedelta(days=len(prior))
    # Sales limp along all morning; most of what was baked will go unsold.
    cold_hours = {7: 3, 8: 4, 9: 4, 10: 4, 11: 8, 12: 7, 13: 6, 14: 5, 15: 4}
    today = IntradayDayRecord(date=today_date, hourly_counts=cold_hours, waste=93,
                               sold_out=False)  # sold 45, on_hand 138

    ev = evaluate_intraday_day(CROISSANT, site_id=2, day=today, prior_days=prior)

    assert ev.action == "markdown"
    assert ev.action_qty > 0
    assert ev.eur_recovered > 0
    assert today.production > today.true_demand


# -------------------------------------------------------------- BALANCED -> hold

def test_balanced_pace_yields_hold_and_zero_recovered_eur():
    prior = _habitual_history()
    today_date = START + dt.timedelta(days=len(prior))
    # Same shape/volume as the habitual history -> tracks the learned pace exactly.
    today = _flat_day(10, today_date, waste=0)

    ev = evaluate_intraday_day(CROISSANT, site_id=3, day=today, prior_days=prior)

    assert ev.action == "hold"
    assert ev.action_qty == 0
    assert ev.eur_recovered == 0.0


# ------------------------------------------------------------ aggregate headline

def _chain_series():
    prior = _habitual_history()
    today_date = START + dt.timedelta(days=len(prior))
    hot_hours = {7: 10, 8: 15, 9: 20, 10: 25, 11: 18, 12: 15, 13: 12, 14: 12, 15: 6, 16: 3}
    cold_hours = {7: 3, 8: 4, 9: 4, 10: 4, 11: 8, 12: 7, 13: 6, 14: 5, 15: 4}
    hot_day = IntradayDayRecord(date=today_date, hourly_counts=hot_hours, waste=0,
                                 sold_out=True)
    cold_day = IntradayDayRecord(date=today_date, hourly_counts=cold_hours, waste=93,
                                  sold_out=False)
    balanced_day = _flat_day(10, today_date, waste=0)
    return {
        ("Croissant", 1): _habitual_history() + [hot_day],
        ("Croissant", 2): _habitual_history() + [cold_day],
        ("Croissant", 3): _habitual_history() + [balanced_day],
    }, {"Croissant": CROISSANT}


def test_aggregate_headline_is_positive_and_reproducible():
    series, products = _chain_series()

    r1 = run_intraday_backtest(series, products)
    r2 = run_intraday_backtest(series, products)

    assert r1.days_evaluated == r2.days_evaluated > 0
    assert r1.actionable_signals == r2.actionable_signals > 0
    assert r1.total_eur_recovered == r2.total_eur_recovered
    assert r1.total_eur_recovered > 0
    assert r1.baseline_eur_recovered == 0.0

    # do-nothing baseline is strictly worse than acting on the signals
    assert r1.total_eur_recovered > r1.baseline_eur_recovered

    # the three hand-built site scenarios each land in the by_action breakdown
    special_date = list(series[("Croissant", 1)])[-1].date
    by_site = {e.site_id: e.action for e in r1.evaluations if e.date == special_date}
    assert by_site[1] in ("bake_more", "move")
    assert by_site[2] == "markdown"
    assert by_site[3] == "hold"


def test_decision_hour_is_eleven_by_default():
    assert DECISION_HOUR == 11
