"""Production recommendation — turns a forecast into a batch-rounded quantity.

Pure Python. Frames the result with a predicted euro-waste figure (the product's
unit of value). The reason string is a grounded baseline; the LLM may rephrase it
later but may never change the numbers (Trust Layer grounding guarantee).
"""
from __future__ import annotations

from app.recommender.types import Forecast, ProductInfo, Recommendation

HIGH_WASTE_RATE = 0.15  # recent waste / production above this -> trim a batch


def round_to_batch(x: float, batch: int) -> int:
    batch = max(1, batch)
    return max(batch, int(round(x / batch)) * batch)


def recommend_production(
    forecast: Forecast,
    product: ProductInfo,
    recent_waste_rate: float = 0.0,
    sold_out_recently: bool = False,
    risk_preference: str = "waste",
) -> Recommendation:
    """Recommend a production quantity for one (product, site, date).

    risk_preference: "waste" (minimize leftovers) | "availability" (avoid stockouts).
    """
    qty = round_to_batch(forecast.expected_demand, product.batch_size)

    notes: list[str] = []
    if recent_waste_rate >= HIGH_WASTE_RATE and qty > product.batch_size:
        qty -= product.batch_size
        notes.append(f"recent waste {recent_waste_rate:.0%} is high, so trimmed a batch")
    if sold_out_recently and risk_preference == "availability":
        qty += product.batch_size
        notes.append("sold out recently and you prioritise availability, so added a batch")

    predicted_waste_units = max(0.0, qty - forecast.expected_demand)
    predicted_waste_eur = round(predicted_waste_units * product.unit_waste_cost, 2)

    reason = (
        f"Forecast demand {forecast.expected_demand:.0f}; recommend baking {qty} "
        f"({product.batch_size}-unit batches). Confidence {forecast.confidence}."
    )
    if predicted_waste_eur > 0:
        reason += f" Expected leftover ~€{predicted_waste_eur:.2f}."
    if notes:
        reason += " " + "; ".join(notes).capitalize() + "."
    if forecast.confidence == "LOW" and forecast.missing:
        reason += f" Low confidence: {forecast.missing}."

    return Recommendation(
        product_id=product.product_id,
        site_id=forecast.site_id,
        target_date=forecast.target_date,
        forecast_qty=forecast.expected_demand,
        recommended_qty=qty,
        confidence=forecast.confidence,
        predicted_waste_eur=predicted_waste_eur,
        reason=reason,
    )
