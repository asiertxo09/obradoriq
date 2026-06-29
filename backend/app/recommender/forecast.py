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
) -> Forecast:
    """Forecast demand for (product, site) on target_date from sorted history."""
    history = sorted(history, key=lambda o: o.date)
    same_weekday = [o for o in history if o.date.weekday() == target_date.weekday()]
    window = same_weekday[-SAME_WEEKDAY_WINDOW:]

    if not window:
        # No same-weekday data: fall back to overall recent average, low confidence.
        recent = [effective_demand(o) for o in history[-7:]] or [0.0]
        return Forecast(
            product_id, site_id, target_date,
            expected_demand=round(statistics.mean(recent), 1),
            confidence="LOW", sample_size=len(same_weekday),
            missing="no same-weekday history",
        )

    base = _weighted_mean([effective_demand(o) for o in window])
    demand = base * _trend(history)

    n = len(same_weekday)
    vals = [effective_demand(o) for o in same_weekday]
    mean = statistics.mean(vals)
    cv = (statistics.pstdev(vals) / mean) if mean > 0 else 1.0
    if n >= HIGH_CONF_MIN_SAMPLES and cv <= HIGH_CONF_MAX_CV:
        confidence, missing = "HIGH", ""
    else:
        confidence = "LOW"
        missing = (
            f"only {n} same-weekday samples" if n < HIGH_CONF_MIN_SAMPLES
            else f"high variability (cv={cv:.2f})"
        )

    return Forecast(
        product_id, site_id, target_date,
        expected_demand=round(demand, 1),
        confidence=confidence, sample_size=n, missing=missing,
    )
