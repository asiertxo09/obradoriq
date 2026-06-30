"""Demand forecasting — pure Python, deterministic, no I/O, no LLM.

Approach (v1, intentionally simple and explainable):
  base   = recency-weighted average of recent same-weekday demand
  trend  = recent 7-day demand / prior 7-day demand   (clamped)
  demand = base * trend

Sold-out days censor demand (real demand was higher), so we apply a small uplift
to those observations before averaging.
"""
from __future__ import annotations

import datetime as dt
import statistics

from app.recommender.types import Forecast, SaleObservation

SOLD_OUT_UPLIFT = 1.15
TREND_CLAMP = (0.80, 1.25)
SAME_WEEKDAY_WINDOW = 4
HIGH_CONF_MIN_SAMPLES = 6
HIGH_CONF_MAX_CV = 0.40


def effective_demand(obs: SaleObservation) -> float:
    """Demand implied by a day's sales, correcting for censoring on sold-out days."""
    return obs.quantity_sold * (SOLD_OUT_UPLIFT if obs.sold_out else 1.0)


def _weighted_mean(values: list[float]) -> float:
    # Oldest..newest -> increasing weights (recency bias).
    n = len(values)
    weights = list(range(1, n + 1))
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def _trend(history: list[SaleObservation]) -> float:
    if len(history) < 14:
        return 1.0
    recent = [effective_demand(o) for o in history[-7:]]
    prior = [effective_demand(o) for o in history[-14:-7]]
    prior_mean = statistics.mean(prior)
    if prior_mean <= 0:
        return 1.0
    raw = statistics.mean(recent) / prior_mean
    return max(TREND_CLAMP[0], min(TREND_CLAMP[1], raw))


def forecast(
    product_id: int,
    site_id: int,
    target_date: dt.date,
    history: list[SaleObservation],
    target_rainy: bool = False,
    target_holiday: bool = False,
) -> Forecast:
    """Forecast demand for (product, site) on target_date from sorted history.

    The weekday base is computed on 'normal' (dry, non-holiday) same-weekday days, then
    scaled by learned rain/holiday elasticities for the target day's actual conditions.
    """
    from app.recommender.signals import context_factors

    history = sorted(history, key=lambda o: o.date)
    same_weekday = [o for o in history if o.date.weekday() == target_date.weekday()]

    if not same_weekday:
        # No same-weekday data: fall back to overall recent average, low confidence.
        recent = [effective_demand(o) for o in history[-7:]] or [0.0]
        mean = statistics.mean(recent)
        sigma = statistics.pstdev(recent) if len(recent) >= 2 else mean * 0.25
        return Forecast(
            product_id, site_id, target_date,
            expected_demand=round(mean, 1),
            confidence="LOW", sample_size=0,
            sigma=round(sigma, 2), missing="no same-weekday history",
        )

    # Prefer 'normal' (dry, non-holiday) same-weekday days for the base level so the
    # context elasticities aren't double-counted; fall back to all same-weekday.
    normal = [o for o in same_weekday if not o.rainy and not o.holiday]
    base_pool = normal if len(normal) >= 2 else same_weekday
    window = base_pool[-SAME_WEEKDAY_WINDOW:]
    base = _weighted_mean([effective_demand(o) for o in window])
    demand = base * _trend(history)

    # Apply learned weather/holiday elasticities for the target day's conditions.
    rain_f, holiday_f = context_factors(history)
    notes = []
    if target_rainy and rain_f != 1.0:
        demand *= rain_f
        notes.append(f"rain ×{rain_f:.2f}")
    if target_holiday and holiday_f != 1.0:
        demand *= holiday_f
        notes.append(f"holiday ×{holiday_f:.2f}")

    n = len(same_weekday)
    vals = [effective_demand(o) for o in base_pool]
    mean = statistics.mean(vals)
    sigma = statistics.pstdev(vals) if len(vals) >= 2 else mean * 0.25
    cv = (sigma / mean) if mean > 0 else 1.0
    if len(base_pool) >= HIGH_CONF_MIN_SAMPLES and cv <= HIGH_CONF_MAX_CV:
        confidence, missing = "HIGH", ""
    else:
        confidence = "LOW"
        missing = (
            f"only {len(base_pool)} comparable same-weekday samples"
            if len(base_pool) < HIGH_CONF_MIN_SAMPLES else f"high variability (cv={cv:.2f})"
        )
    if notes:
        missing = (missing + "; " if missing else "") + "applied " + ", ".join(notes)

    return Forecast(
        product_id, site_id, target_date,
        expected_demand=round(demand, 1),
        confidence=confidence, sample_size=n, sigma=round(sigma, 2), missing=missing,
    )
