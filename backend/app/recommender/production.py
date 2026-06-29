"""Production recommendation — profit-optimal quantity via the newsvendor model.

Pure Python. The quantity maximises expected profit given the product's own margin vs.
leftover cost (see newsvendor.py), so high-margin items keep an availability buffer while
low-margin items hug the forecast. `naive_quantity` (bake-to-forecast) is kept as the
baseline the backtest compares against.
"""
from __future__ import annotations

from app.recommender.newsvendor import (
    critical_ratio,
    expected_leftover,
    newsvendor_quantity,
)
from app.recommender.types import Forecast, ProductInfo, Recommendation


def round_to_batch(x: float, batch: int) -> int:
    batch = max(1, batch)
    return max(batch, int(round(x / batch)) * batch)


def naive_quantity(forecast: Forecast, product: ProductInfo) -> int:
    """Baseline: just bake the rounded forecast mean (what a simple rule would do)."""
    return round_to_batch(forecast.expected_demand, product.batch_size)


def recommend_production(
    forecast: Forecast,
    product: ProductInfo,
    recent_waste_rate: float = 0.0,  # kept for signature compat; economics now drive it
    sold_out_recently: bool = False,
    risk_preference: str = "waste",
) -> Recommendation:
    """Profit-optimal production for one (product, site, date)."""
    mean = forecast.expected_demand
    sigma = forecast.sigma
    cr = critical_ratio(product.price, product.unit_waste_cost, risk_preference)

    raw = newsvendor_quantity(mean, sigma, cr)
    qty = round_to_batch(raw, product.batch_size)

    exp_leftover = expected_leftover(qty, mean, sigma)
    predicted_waste_eur = round(max(0.0, exp_leftover) * product.unit_waste_cost, 2)

    cu = max(product.price - product.unit_waste_cost, 0.0)
    reason = (
        f"{product.name}: margin €{cu:.2f}/unit vs leftover cost "
        f"€{product.unit_waste_cost:.2f} → {cr:.0%} service level. Bake {qty} "
        f"(forecast {mean:.0f} ± {sigma:.0f}). Expected leftover ~€{predicted_waste_eur:.2f}. "
        f"Confidence {forecast.confidence}."
    )
    if forecast.confidence == "LOW" and forecast.missing:
        reason += f" Low confidence: {forecast.missing}."

    return Recommendation(
        product_id=product.product_id,
        site_id=forecast.site_id,
        target_date=forecast.target_date,
        forecast_qty=mean,
        recommended_qty=qty,
        confidence=forecast.confidence,
        predicted_waste_eur=predicted_waste_eur,
        reason=reason,
    )
