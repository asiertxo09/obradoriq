"""Unit tests for the recommender core: forecast, production, reallocation, backtest."""
from __future__ import annotations

import datetime as dt

import pytest

from app.recommender.forecast import forecast
from app.recommender.production import recommend_production, round_to_batch
from app.recommender.reallocation import reallocate_across_sites
from app.recommender.types import ProductInfo, SaleObservation, SiteState

CROISSANT = ProductInfo(product_id=1, name="Croissant", batch_size=6, price=1.8, ingredient_cost=0.55)


def _weekday_series(target: dt.date, value: int, weeks: int, noise=0) -> list[SaleObservation]:
    """Build `weeks` of same-weekday observations ending before `target`."""
    obs = []
    for w in range(1, weeks + 1):
        d = target - dt.timedelta(days=7 * w)
        obs.append(SaleObservation(d, value + (noise if w % 2 else -noise), False))
    return obs


# ---- forecast ----
def _weekday_series_ctx(target, dry_val, weeks, rain_val=None, holiday_val=None):
    """Same-weekday history mixing dry, rainy, and holiday days."""
    obs = []
    for w in range(1, weeks + 1):
        d = target - dt.timedelta(days=7 * w)
        if rain_val is not None and w % 3 == 0:
            obs.append(SaleObservation(d, rain_val, False, rainy=True))
        elif holiday_val is not None and w % 4 == 0:
            obs.append(SaleObservation(d, holiday_val, False, holiday=True))
        else:
            obs.append(SaleObservation(d, dry_val, False))
    return obs


def test_forecast_applies_learned_rain_factor():
    target = dt.date(2026, 7, 1)
    # dry ~ 80, rainy ~ 60 (learned factor ~0.75)
    hist = _weekday_series_ctx(target, 80, weeks=12, rain_val=60)
    dry = forecast(1, 10, target, hist, target_rainy=False)
    wet = forecast(1, 10, target, hist, target_rainy=True)
    assert wet.expected_demand < dry.expected_demand
    assert "rain" in wet.missing


def test_forecast_applies_learned_holiday_factor():
    target = dt.date(2026, 7, 1)
    hist = _weekday_series_ctx(target, 60, weeks=12, holiday_val=90)  # holidays busier
    normal = forecast(1, 10, target, hist, target_holiday=False)
    holiday = forecast(1, 10, target, hist, target_holiday=True)
    assert holiday.expected_demand > normal.expected_demand


def test_forecast_normal_is_high_confidence():
    target = dt.date(2026, 7, 1)  # Wednesday
    hist = _weekday_series(target, 60, weeks=8, noise=2)
    f = forecast(1, 10, target, hist)
    assert 55 <= f.expected_demand <= 65
    assert f.confidence == "HIGH"


def test_forecast_sparse_is_low_confidence():
    target = dt.date(2026, 7, 1)
    hist = _weekday_series(target, 60, weeks=2)
    f = forecast(1, 10, target, hist)
    assert f.confidence == "LOW"
    assert f.missing


def test_forecast_no_same_weekday_falls_back_low():
    target = dt.date(2026, 7, 1)  # Wednesday
    # only Mondays in history
    hist = [SaleObservation(dt.date(2026, 6, 1) + dt.timedelta(days=7 * w), 40, False) for w in range(5)]
    f = forecast(1, 10, target, hist)
    assert f.confidence == "LOW"
    assert f.expected_demand > 0


def test_forecast_spike_lowers_confidence():
    target = dt.date(2026, 7, 1)
    hist = _weekday_series(target, 60, weeks=8)
    # inject a spike
    hist.append(SaleObservation(target - dt.timedelta(days=7), 200, False))
    f = forecast(1, 10, target, hist)
    assert f.confidence == "LOW"


# ---- production ----
def test_round_to_batch():
    assert round_to_batch(29, 6) == 30
    assert round_to_batch(0, 6) == 6  # never below one batch
    assert round_to_batch(31, 6) == 30


def test_recommendation_rounds_and_estimates_waste():
    target = dt.date(2026, 7, 1)
    f = forecast(1, 10, target, _weekday_series(target, 58, weeks=8, noise=1))
    rec = recommend_production(f, CROISSANT, recent_waste_rate=0.0)
    assert rec.recommended_qty % CROISSANT.batch_size == 0
    assert rec.predicted_waste_eur >= 0
    assert "service level" in rec.reason


def test_availability_risk_bakes_at_least_as_much_as_waste():
    """Higher service level (availability) never recommends fewer than the waste tilt."""
    target = dt.date(2026, 7, 1)
    f = forecast(1, 10, target, _weekday_series(target, 60, weeks=8, noise=8))
    avail = recommend_production(f, CROISSANT, risk_preference="availability")
    waste = recommend_production(f, CROISSANT, risk_preference="waste")
    assert avail.recommended_qty >= waste.recommended_qty


def test_high_margin_product_keeps_a_bigger_buffer():
    """A high-margin product should be baked further above the mean than a low-margin one
    with the same demand distribution (the newsvendor critical-ratio effect)."""
    target = dt.date(2026, 7, 1)
    f = forecast(1, 10, target, _weekday_series(target, 60, weeks=8, noise=8))
    high = ProductInfo(1, "Cake", batch_size=1, price=10.0, ingredient_cost=1.0)   # CR high
    low = ProductInfo(1, "Bread", batch_size=1, price=1.2, ingredient_cost=1.0)    # CR low
    qty_high = recommend_production(f, high, risk_preference="waste").recommended_qty
    qty_low = recommend_production(f, low, risk_preference="waste").recommended_qty
    assert qty_high > qty_low


# ---- reallocation ----
def test_reallocation_moves_surplus_to_shortfall():
    target = dt.date(2026, 7, 1)
    states = [
        SiteState(site_id=1, forecast_demand=36, planned_production=30, sold_out_rate=0.9, confidence="HIGH"),
        SiteState(site_id=2, forecast_demand=22, planned_production=42, sold_out_rate=0.0, confidence="HIGH"),
    ]
    sug = reallocate_across_sites(CROISSANT, target, states)
    assert len(sug) == 1
    assert sug[0].from_site_id == 2  # surplus site
    assert sug[0].to_site_id == 1  # shortfall site
    assert sug[0].quantity > 0
    assert sug[0].quantity % CROISSANT.batch_size == 0
    assert sug[0].eur_waste_avoided > 0


def test_reallocation_skips_low_confidence():
    target = dt.date(2026, 7, 1)
    states = [
        SiteState(1, 36, 30, 0.9, "LOW"),
        SiteState(2, 22, 42, 0.0, "HIGH"),
    ]
    assert reallocate_across_sites(CROISSANT, target, states) == []


def test_reallocation_none_when_balanced():
    target = dt.date(2026, 7, 1)
    states = [
        SiteState(1, 30, 30, 0.0, "HIGH"),
        SiteState(2, 28, 30, 0.0, "HIGH"),
    ]
    assert reallocate_across_sites(CROISSANT, target, states) == []


def test_reallocation_no_contradictory_pair():
    """A site must not be told to both send and receive the same product."""
    target = dt.date(2026, 7, 1)
    # Both sites over-bake (surplus) -> nobody should receive.
    states = [
        SiteState(1, 20, 30, 0.3, "HIGH"),
        SiteState(2, 18, 30, 0.3, "HIGH"),
    ]
    sug = reallocate_across_sites(CROISSANT, target, states)
    pairs = {(s.from_site_id, s.to_site_id) for s in sug}
    for a, b in pairs:
        assert (b, a) not in pairs  # no reciprocal suggestion


def test_reallocation_never_exceeds_surplus():
    target = dt.date(2026, 7, 1)
    states = [
        SiteState(1, 100, 30, 0.9, "HIGH"),  # huge shortfall
        SiteState(2, 22, 36, 0.0, "HIGH"),   # small surplus (excess 14)
    ]
    sug = reallocate_across_sites(CROISSANT, target, states)
    assert sug
    assert sug[0].quantity <= 14 + CROISSANT.batch_size  # capped near the surplus
