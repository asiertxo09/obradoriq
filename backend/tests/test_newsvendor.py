"""Unit tests for the newsvendor profit-optimizer."""
from __future__ import annotations

from app.recommender.newsvendor import (
    critical_ratio,
    expected_leftover,
    newsvendor_quantity,
)


def test_high_margin_has_higher_critical_ratio():
    high = critical_ratio(price=10.0, unit_cost=1.0, risk_preference="waste")
    low = critical_ratio(price=1.2, unit_cost=1.0, risk_preference="waste")
    assert high > low


def test_risk_preference_tilts_ratio():
    base = critical_ratio(3.0, 1.0, "neutral")
    assert critical_ratio(3.0, 1.0, "availability") > base
    assert critical_ratio(3.0, 1.0, "waste") < base


def test_quantity_above_mean_when_cr_high():
    assert newsvendor_quantity(mean=100, sigma=10, cr=0.9) > 100


def test_quantity_below_mean_when_cr_low():
    assert newsvendor_quantity(mean=100, sigma=10, cr=0.1) < 100


def test_quantity_equals_mean_with_no_variance():
    assert newsvendor_quantity(mean=50, sigma=0, cr=0.9) == 50


def test_expected_leftover_nonnegative_and_grows_with_qty():
    a = expected_leftover(qty=100, mean=100, sigma=10)
    b = expected_leftover(qty=120, mean=100, sigma=10)
    assert a >= 0 and b > a
