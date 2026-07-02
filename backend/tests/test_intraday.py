"""Intraday 'living plan' — pure, deterministic unit tests (no DB, no LLM)."""
from __future__ import annotations

import datetime as dt

from app.recommender.intraday import (
    CLOSE_HOUR,
    DEFAULT_PACE,
    OPEN_HOUR,
    cumulative_fraction,
    intraday_signal,
    pace_curve,
    project_end_of_day,
    projected_sellout_time,
)
from app.recommender.types import (
    Forecast,
    ProductInfo,
    SiteCapability,
    SiteState,
)

TODAY = dt.date(2026, 7, 1)


def _product(**kw) -> ProductInfo:
    base = dict(product_id=1, name="Croissant", batch_size=12, price=2.0, ingredient_cost=0.6)
    base.update(kw)
    return ProductInfo(**base)


def _at(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 7, 1, hour, minute)


def _forecast(expected: float, sigma: float = 10.0, confidence: str = "HIGH") -> Forecast:
    return Forecast(
        product_id=1, site_id=1, target_date=TODAY,
        expected_demand=expected, confidence=confidence, sample_size=20, sigma=sigma,
    )


# ---------------------------------------------------------------- pace_curve

def _flat_day(units_per_hour: int) -> dict[int, int]:
    return {h: units_per_hour for h in range(OPEN_HOUR, CLOSE_HOUR)}


def test_pace_curve_learns_monotone_curve_ending_at_one():
    # A flat footfall day => cumulative fraction rises linearly to 1.0.
    days = [_flat_day(10) for _ in range(7)]
    curve = pace_curve(days)
    hours = list(range(OPEN_HOUR, CLOSE_HOUR))
    assert set(curve) == set(hours)
    # monotone non-decreasing
    vals = [curve[h] for h in hours]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert curve[CLOSE_HOUR - 1] == 1.0
    assert 0.0 < curve[OPEN_HOUR] < 1.0
    # flat day => first-of-13 hours ~ 1/13
    assert abs(curve[OPEN_HOUR] - 1 / 13) < 1e-6


def test_pace_curve_falls_back_when_sparse():
    days = [_flat_day(10) for _ in range(3)]  # < MIN_PACE_DAYS
    assert pace_curve(days) == DEFAULT_PACE


def test_pace_curve_ignores_empty_and_zero_days():
    # 4 real days + several empty/zero days => still < MIN_PACE_DAYS usable => fallback.
    days = [_flat_day(10) for _ in range(4)] + [{}, {h: 0 for h in range(OPEN_HOUR, CLOSE_HOUR)}]
    assert pace_curve(days) == DEFAULT_PACE
    # 5 usable days => a learned curve, not the default.
    days = [_flat_day(10) for _ in range(5)] + [{}]
    curve = pace_curve(days)
    assert curve != DEFAULT_PACE
    assert curve[CLOSE_HOUR - 1] == 1.0


def test_pace_curve_handles_empty_input():
    assert pace_curve([]) == DEFAULT_PACE


# ----------------------------------------------------- cumulative_fraction

def test_cumulative_fraction_interpolates_within_hour():
    # Halfway through hour 10, fraction sits between end-of-9 and end-of-10.
    at = _at(10, 30)
    f = cumulative_fraction(DEFAULT_PACE, at)
    lo, hi = DEFAULT_PACE[9], DEFAULT_PACE[10]
    assert lo < f < hi
    assert abs(f - (lo + (hi - lo) * 0.5)) < 1e-9


def test_cumulative_fraction_on_the_hour_matches_previous_hour_end():
    # At 10:00 exactly we've sold through end-of-hour-9.
    f = cumulative_fraction(DEFAULT_PACE, _at(10, 0))
    assert abs(f - DEFAULT_PACE[9]) < 1e-9


def test_cumulative_fraction_clamps_before_open_and_after_close():
    before = cumulative_fraction(DEFAULT_PACE, _at(OPEN_HOUR - 1, 30))
    assert 0.0 < before < 0.01
    after = cumulative_fraction(DEFAULT_PACE, _at(CLOSE_HOUR, 5))
    assert after == 1.0


# ------------------------------------------------------ project_end_of_day

def test_project_hot_pace_projects_above_current_sales():
    # By 10:30 only ~44% of the day has passed; strong sales imply a big full day.
    at = _at(10, 30)
    sold = 60
    projected, sigma = project_end_of_day(sold, at, DEFAULT_PACE)
    assert projected > sold
    cf = cumulative_fraction(DEFAULT_PACE, at)
    assert abs(projected - sold / cf) < 1e-6
    assert sigma > 0


def test_project_blends_toward_prior_early_in_day():
    at = _at(8, 0)  # early: pace signal thin, lean on the prior
    # Run-rate alone would project very high; prior pulls it down.
    naive = project_end_of_day(30, at, DEFAULT_PACE)[0]
    blended = project_end_of_day(30, at, DEFAULT_PACE, daily_forecast=_forecast(120))[0]
    assert blended < naive
    assert blended > 120  # still above the prior since pace is running hot


def test_project_leans_on_pace_late_in_day():
    early = _at(8, 0)
    late = _at(18, 0)
    prior = _forecast(120)
    # Same run-rate signal; later in the day the projection tracks the pace estimate more.
    e_pace = project_end_of_day(30, early, DEFAULT_PACE)[0]
    l_pace = project_end_of_day(30, late, DEFAULT_PACE)[0]
    e_blend = project_end_of_day(30, early, DEFAULT_PACE, daily_forecast=prior)[0]
    l_blend = project_end_of_day(30, late, DEFAULT_PACE, daily_forecast=prior)[0]
    # Late blend sits closer to its own pace estimate than the early blend does.
    assert abs(l_blend - l_pace) < abs(e_blend - e_pace)


# --------------------------------------------------- projected_sellout_time

def test_sellout_time_returns_a_time_on_shortfall():
    # 40 on hand, projecting 120 => sells out around 40/120 = 33% of the day.
    t = projected_sellout_time(40, DEFAULT_PACE, 120.0)
    assert isinstance(t, dt.time)
    assert OPEN_HOUR <= t.hour < CLOSE_HOUR


def test_sellout_time_none_when_covered():
    assert projected_sellout_time(200, DEFAULT_PACE, 120.0) is None
    assert projected_sellout_time(120, DEFAULT_PACE, 120.0) is None


def test_sellout_time_earlier_when_less_on_hand():
    early = projected_sellout_time(20, DEFAULT_PACE, 120.0)
    late = projected_sellout_time(80, DEFAULT_PACE, 120.0)
    assert early is not None and late is not None
    assert (early.hour, early.minute) < (late.hour, late.minute)


# -------------------------------------------------------- intraday_signal

def test_signal_bake_more_when_capable_and_time_left():
    p = _product()
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(10, 30), sold_so_far=60, on_hand=40,
        pace=DEFAULT_PACE, daily_forecast=_forecast(140), confidence="HIGH",
    )
    assert sig.action == "bake_more"
    assert sig.action_qty > 0 and sig.action_qty % p.batch_size == 0
    assert sig.from_site_id is None
    assert sig.projected_sellout_time is not None
    # lost margin = (price - waste) * gap, strictly positive
    assert sig.eur_at_risk > 0


def test_signal_moves_when_cannot_bake_and_high_surplus_sibling_exists():
    p = _product()
    siblings = [
        SiteState(site_id=2, forecast_demand=50, planned_production=90,
                  sold_out_rate=0.0, confidence="HIGH"),  # surplus 40 >= batch
        SiteState(site_id=3, forecast_demand=80, planned_production=82,
                  sold_out_rate=0.0, confidence="HIGH"),  # too small
    ]
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(11, 0), sold_so_far=70, on_hand=40,
        pace=DEFAULT_PACE, daily_forecast=_forecast(160),
        capability=SiteCapability(can_bake_off=False, can_move=True),
        sibling_states=siblings, confidence="HIGH",
    )
    assert sig.action == "move"
    assert sig.from_site_id == 2  # the larger HIGH surplus sibling
    assert sig.action_qty > 0


def test_signal_holds_when_cannot_bake_and_only_low_conf_sibling():
    p = _product()
    siblings = [
        SiteState(site_id=2, forecast_demand=50, planned_production=90,
                  sold_out_rate=0.0, confidence="LOW"),  # surplus but LOW conf => unusable
    ]
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(11, 0), sold_so_far=70, on_hand=40,
        pace=DEFAULT_PACE, daily_forecast=_forecast(160),
        capability=SiteCapability(can_bake_off=False, can_move=True),
        sibling_states=siblings, confidence="HIGH",
    )
    assert sig.action == "hold"
    assert sig.action_qty == 0
    assert sig.from_site_id is None
    assert sig.eur_at_risk > 0  # money is still honestly at risk


def test_signal_markdown_on_surplus():
    p = _product()
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(15, 0), sold_so_far=30, on_hand=120,
        pace=DEFAULT_PACE, daily_forecast=_forecast(45), confidence="HIGH",
    )
    assert sig.action == "markdown"
    assert sig.action_qty > 0
    assert sig.from_site_id is None
    assert sig.projected_sellout_time is None
    # leftover cost = unit_waste_cost * surplus
    assert abs(sig.eur_at_risk - round(p.unit_waste_cost * (sig.on_hand - sig.projected_demand), 2)) < 0.02


def test_signal_hold_when_balanced():
    p = _product()
    # on_hand tracks the projection => nothing to do. At 13:00 cf == DEFAULT_PACE[12] = 0.536,
    # so 54 sold + a matching 100-unit prior projects ~100, right on the 100 on hand.
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(13, 0), sold_so_far=54, on_hand=100,
        pace=DEFAULT_PACE, daily_forecast=_forecast(100), confidence="HIGH",
    )
    assert sig.action == "hold"
    assert sig.action_qty == 0
    assert sig.eur_at_risk == 0.0


def test_signal_eur_at_risk_shortfall_is_lost_margin():
    p = _product(price=3.0, ingredient_cost=1.0)
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(9, 0), sold_so_far=40, on_hand=30,
        pace=DEFAULT_PACE, daily_forecast=_forecast(150), confidence="HIGH",
    )
    gap = sig.projected_demand - sig.on_hand
    expected = round((p.price - p.unit_waste_cost) * gap, 2)
    assert abs(sig.eur_at_risk - expected) < 0.01


def test_signal_low_confidence_is_honest_but_still_projects():
    p = _product()
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(10, 0), sold_so_far=60, on_hand=40,
        pace=DEFAULT_PACE, daily_forecast=_forecast(140, confidence="LOW"),
        confidence="LOW",
    )
    assert sig.confidence == "LOW"
    assert "low confidence" in sig.reason.lower()
    assert sig.projected_demand > 0


def test_signal_never_crashes_on_empty_inputs():
    p = _product()
    sig = intraday_signal(
        product=p, site_id=1, as_of=_at(7, 0), sold_so_far=0, on_hand=0,
        pace=DEFAULT_PACE,
    )
    assert sig.action in {"bake_more", "move", "markdown", "hold"}
