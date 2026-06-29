"""Plan-level cross-site reallocation — the differentiator.

Reallocates *planned production quantities* across sites of one chain (never physical
goods). Advisory only. Pure Python; the Reallocation Agent (Opus) decides whether to
surface a suggestion and justifies it, but these numbers are deterministic.

Signal:
  surplus site  = plans to bake meaningfully more than forecast demand (predicted waste)
  shortfall site= forecast demand exceeds its plan and/or it sells out often
Greedily move planned units surplus -> shortfall, capped by the shortfall's real gap
and rounded to the product's batch size.
"""
from __future__ import annotations

import datetime as dt

from app.recommender.types import ProductInfo, Reallocation, SiteState
from app.recommender.production import round_to_batch

MIN_SOLD_OUT_RATE = 0.20  # a site selling out >=20% of recent days signals shortfall


def reallocate_across_sites(
    product: ProductInfo,
    target_date: dt.date,
    states: list[SiteState],
) -> list[Reallocation]:
    """Suggest plan-level reallocations for one product across a chain's sites."""
    surplus: list[tuple[SiteState, float]] = []
    shortfall: list[tuple[SiteState, float]] = []

    for s in states:
        excess = s.planned_production - s.forecast_demand  # predicted leftover
        gap = s.forecast_demand - s.planned_production  # predicted unmet demand
        # Each site takes exactly one role, by the sign of plan-vs-demand, so we can
        # never emit a contradictory pair (A->B and B->A for the same product).
        if excess >= product.batch_size:
            surplus.append((s, excess))
        elif gap > 0 or s.sold_out_rate >= MIN_SOLD_OUT_RATE:
            shortfall.append((s, max(gap, 0.0)))

    # Largest surplus and largest shortfall first.
    surplus.sort(key=lambda t: t[1], reverse=True)
    shortfall.sort(key=lambda t: t[1], reverse=True)

    suggestions: list[Reallocation] = []
    si = 0
    for short_state, gap in shortfall:
        if si >= len(surplus):
            break
        surplus_state, excess = surplus[si]
        if surplus_state.site_id == short_state.site_id:
            si += 1
            continue
        # Only act on confident signals — never reallocate on guesswork.
        if surplus_state.confidence != "HIGH" or short_state.confidence != "HIGH":
            continue
        movable = min(excess, max(gap, product.batch_size))
        qty = round_to_batch(movable, product.batch_size)
        if qty <= 0:
            continue
        eur = round(qty * product.unit_waste_cost, 2)
        justification = (
            f"{product.name}: site {surplus_state.site_id} plans "
            f"{surplus_state.planned_production:.0f} for ~{surplus_state.forecast_demand:.0f} "
            f"demand (waste), while site {short_state.site_id} sells out "
            f"{short_state.sold_out_rate:.0%} of days. Shift {qty} of planned production "
            f"to recover ~€{eur:.2f}."
        )
        suggestions.append(
            Reallocation(
                product_id=product.product_id,
                target_date=target_date,
                from_site_id=surplus_state.site_id,
                to_site_id=short_state.site_id,
                quantity=qty,
                eur_waste_avoided=eur,
                justification=justification,
            )
        )
        # Reduce this surplus; move on if exhausted.
        surplus[si] = (surplus_state, excess - qty)
        if surplus[si][1] < product.batch_size:
            si += 1
    return suggestions
